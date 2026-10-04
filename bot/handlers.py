"""Telegram bot handlers for commands and messages."""

import logging
import time
from typing import Dict

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)

from bot.api_client import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    InvalidDomainError,
    RateLimitError,
    TimeoutError,
    get_api_client,
)
from bot.config import get_settings
from bot.i18n import (
    DEFAULT_LANGUAGE,
    get_translation,
    get_available_languages,
    get_bot_commands,
)
from bot.language_store import get_effective_language, set_user_language
from bot.utils import (
    format_subdomain_list,
    looks_like_domain,
    normalize_domain,
)

logger = logging.getLogger(__name__)

# Router for handlers
router = Router()

# Per-user rate limiting: {user_id: last_request_timestamp}
_user_last_request: Dict[int, float] = {}


def check_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    settings = get_settings()
    if not settings.allowed_user_ids:
        return True
    return user_id in settings.allowed_user_ids


def check_rate_limit(user_id: int) -> tuple[bool, float]:
    """
    Check if user has exceeded rate limit.

    Returns:
        Tuple of (allowed, seconds_until_next_allowed)
    """
    settings = get_settings()
    now = time.time()
    last = _user_last_request.get(user_id, 0)
    elapsed = now - last

    if elapsed >= settings.rate_limit_seconds:
        _user_last_request[user_id] = now
        return True, 0.0

    return False, settings.rate_limit_seconds - elapsed


def _get_lang(message: Message) -> str:
    """Get effective language for the user."""
    telegram_lang = message.from_user.language_code if message.from_user else None
    return get_effective_language(message.from_user.id, telegram_lang)


def _get_lang_sync(message: Message) -> str:
    """Get effective language for the user (synchronous version for sync contexts)."""
    telegram_lang = message.from_user.language_code if message.from_user else None
    # This is a synchronous wrapper that will be awaited
    return get_effective_language(message.from_user.id, telegram_lang)


def _build_language_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for language selection."""
    buttons = []
    for code, flag, name in get_available_languages():
        buttons.append(
            [InlineKeyboardButton(text=f"{flag} {name}", callback_data=f"lang:{code}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command - show language selection if not set, else welcome."""
    if not check_user_allowed(message.from_user.id):
        lang = _get_lang(message)
        await message.answer(get_translation("err_not_allowed", lang))
        return

    lang = _get_lang(message)

    # Check if user already has a saved language
    from bot.language_store import get_user_language
    saved_lang = await get_user_language(message.from_user.id)

    if saved_lang:
        # User already has a language, show welcome in their language (no language prompt)
        welcome_text = get_translation("welcome_title", lang) + "\n\n" + get_translation("welcome_text", lang)
        await message.answer(welcome_text)
    else:
        # First time - show language selection with prompt
        keyboard = _build_language_keyboard()
        welcome_text = (
            get_translation("welcome_title", lang) + "\n\n" +
            get_translation("welcome_text", lang) + "\n\n" +
            get_translation("choose_language_prompt", lang)
        )
        await message.answer(welcome_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("lang:"))
async def callback_language_select(callback: CallbackQuery) -> None:
    """Handle language selection from inline keyboard."""
    if not check_user_allowed(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    lang_code = callback.data.split(":")[1]
    from bot.i18n import SUPPORTED_LANGUAGES

    if lang_code not in SUPPORTED_LANGUAGES:
        await callback.answer("Invalid language", show_alert=True)
        return

    # Save language preference
    set_user_language(callback.from_user.id, lang_code)

    # Answer callback with toast
    await callback.answer(get_translation("language_set", lang_code))

    # Show confirmation message in the NEWLY chosen language (no keyboard)
    confirmed_text = get_translation("language_confirmed", lang_code)
    await callback.message.edit_text(confirmed_text)


@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    """Handle /language command - show language selection keyboard."""
    if not check_user_allowed(message.from_user.id):
        lang = _get_lang(message)
        await message.answer(get_translation("err_not_allowed", lang))
        return

    lang = _get_lang(message)
    keyboard = _build_language_keyboard()
    await message.answer(get_translation("choose_language", lang), reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    if not check_user_allowed(message.from_user.id):
        lang = _get_lang(message)
        await message.answer(get_translation("err_not_allowed", lang))
        return

    lang = _get_lang(message)
    settings = get_settings()

    help_text = get_translation("help_title", lang) + "\n\n" + get_translation(
        "help_text", lang, rate_limit=settings.rate_limit_seconds
    )

    # Add "Change Language" button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_translation("change_language_btn", lang), callback_data="cmd:language")]
        ]
    )

    await message.answer(help_text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "cmd:language")
async def callback_help_language(callback: CallbackQuery) -> None:
    """Handle 'Change Language' button from help."""
    if not check_user_allowed(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    await callback.answer()
    # Simulate /language command
    lang = get_effective_language(callback.from_user.id, callback.from_user.language_code)
    keyboard = _build_language_keyboard()
    await callback.message.answer(get_translation("choose_language", lang), reply_markup=keyboard)


@router.message(F.text)
async def handle_domain_message(message: Message) -> None:
    """Handle plain text messages that look like domains/URLs."""
    if not check_user_allowed(message.from_user.id):
        lang = _get_lang(message)
        await message.answer(get_translation("err_not_allowed", lang))
        return

    text = message.text or ""
    text = text.strip()

    if not text:
        return

    lang = _get_lang(message)

    # Quick check if it looks like a domain
    if not looks_like_domain(text):
        await message.answer(get_translation("err_not_domain", lang))
        return

    # Check rate limit
    allowed, wait_time = check_rate_limit(message.from_user.id)
    if not allowed:
        await message.answer(get_translation("err_rate_limit", lang, wait=wait_time))
        return

    # Normalize domain
    domain = normalize_domain(text)
    if not domain:
        await message.answer(get_translation("err_invalid_domain", lang))
        return

    # Send "typing" action
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Send initial searching message
    searching_text = get_translation("searching", lang, domain=domain)
    status_msg = await message.answer(searching_text, parse_mode="Markdown")

    try:
        # Call API
        client = get_api_client()
        subdomains = await client.search(domain)

        # Format result
        _, as_file, unique_subs = format_subdomain_list(subdomains)

        # Delete status message
        await status_msg.delete()

        if not unique_subs:
            await message.answer(get_translation("no_subdomains", lang))
            return

        if as_file:
            # Send as file
            file_content = "\n".join(unique_subs)
            file = BufferedInputFile(
                file_content.encode("utf-8"),
                filename=get_translation("filename_template", lang, domain=domain),
            )
            caption = get_translation("file_caption", lang, domain=domain, count=len(unique_subs))
            await message.answer_document(document=file, caption=caption)
        else:
            # Send as message with results header + subdomains in code block for RTL safety
            results_header = get_translation("results_header", lang, count=len(unique_subs))
            # Put subdomains in a code block to prevent RTL scrambling
            subs_text = "\n".join(unique_subs)
            message_text = f"{results_header}\n```\n{subs_text}\n```"
            await message.answer(message_text, parse_mode="Markdown")

    except InvalidDomainError:
        await status_msg.edit_text(get_translation("err_invalid_domain", lang))

    except RateLimitError as e:
        wait_msg = get_translation("err_api_rate_limit", lang)
        if e.retry_after:
            wait_msg += f" ({e.retry_after}s)"
        await status_msg.edit_text(wait_msg)

    except AuthenticationError:
        await status_msg.edit_text(get_translation("err_unauthorized", lang))
        logger.error("API authentication failed - check API_KEY")

    except ForbiddenError:
        await status_msg.edit_text(get_translation("err_forbidden", lang))

    except TimeoutError:
        await status_msg.edit_text(get_translation("err_timeout", lang))

    except APIError as e:
        logger.error(f"API error for {domain}: {e}")
        await status_msg.edit_text(get_translation("err_api_error", lang, detail=str(e)))

    except Exception as e:
        logger.exception(f"Unexpected error handling message from {message.from_user.id}")
        await status_msg.edit_text(get_translation("err_unknown", lang, detail="Internal server error"))


# Export router for main.py to register
__all__ = ["router", "setup_bot_commands", "shutdown_bot"]


async def setup_bot_commands(bot: Bot) -> None:
    """Set bot commands for both languages."""
    for lang_code in ["en", "fa"]:
        commands = get_bot_commands(lang_code)
        await bot.set_my_commands(
            commands=[types.BotCommand(command=cmd, description=desc) for cmd, desc in commands],
            language_code=lang_code,
        )


async def shutdown_bot() -> None:
    """Cleanup on shutdown."""
    from bot.api_client import close_api_client
    await close_api_client()
    logger.info("Bot shutdown complete")