"""Bale bot handlers for commands and messages."""

import asyncio
import logging
import time
from typing import Dict, Any, Callable

from bot.admin_handlers import handle_admin_command, handle_clearcache_callback
from bot.api_client import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    InvalidDomainError,
    RateLimitError,
    TimeoutError,
    get_api_client,
)
from bot.bale_client import BaleClient, BaleAPIError
from bot.config import get_settings
from bot.i18n import (
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


def _get_lang(user_id: int, telegram_lang_code: str = None) -> str:
    """Get effective language for the user."""
    return get_effective_language(user_id, telegram_lang_code)


def _build_language_keyboard() -> Dict[str, Any]:
    """Build inline keyboard for language selection."""
    inline_keyboard = []
    for code, flag, name in get_available_languages():
        inline_keyboard.append([
            {"text": f"{flag} {name}", "callback_data": f"lang:{code}"}
        ])
    return {"inline_keyboard": inline_keyboard}


async def cmd_start(client: BaleClient, update: Dict[str, Any]) -> None:
    """Handle /start command - show language selection if not set, else welcome."""
    message = update.get("message", {})
    user = message.get("from", {})
    user_id = user.get("id")
    chat_id = message.get("chat", {}).get("id")
    lang_code = user.get("language_code")

    if not check_user_allowed(user_id):
        lang = _get_lang(user_id, lang_code)
        await client.send_message(chat_id, get_translation("err_not_allowed", lang))
        return

    lang = _get_lang(user_id, lang_code)

    # Check if user already has a saved language
    from bot.language_store import get_user_language
    saved_lang = get_user_language(user_id)

    if saved_lang:
        # User already has a language, show welcome in their language
        welcome_text = (
            get_translation("welcome_title", lang) + "\n\n" +
            get_translation("welcome_text", lang)
        )
        await client.send_message(chat_id, welcome_text)
    else:
        # First time - show language selection
        keyboard = _build_language_keyboard()
        welcome_text = (
            get_translation("welcome_title", lang) + "\n\n" +
            get_translation("welcome_text", lang) + "\n\n" +
            get_translation("choose_language_prompt", lang)
        )
        await client.send_message(chat_id, welcome_text, reply_markup=keyboard)


async def callback_language_select(client: BaleClient, update: Dict[str, Any]) -> None:
    """Handle language selection from inline keyboard."""
    callback_query = update.get("callback_query", {})
    user = callback_query.get("from", {})
    user_id = user.get("id")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    data = callback_query.get("data", "")
    callback_query_id = callback_query.get("id")
    lang_code = user.get("language_code")

    if not check_user_allowed(user_id):
        await client.answer_callback_query(callback_query_id, "Not allowed", show_alert=True)
        return

    lang = data.split(":")[1]
    from bot.i18n import SUPPORTED_LANGUAGES

    if lang not in SUPPORTED_LANGUAGES:
        await client.answer_callback_query(callback_query_id, "Invalid language", show_alert=True)
        return

    # Save language preference
    set_user_language(user_id, lang)

    # Answer callback with toast
    await client.answer_callback_query(callback_query_id, get_translation("language_set", lang))

    # Show confirmation message in the NEWLY chosen language (no keyboard)
    confirmed_text = get_translation("language_confirmed", lang)
    await client.edit_message_text(chat_id, message_id, confirmed_text)


async def cmd_language(client: BaleClient, update: Dict[str, Any]) -> None:
    """Handle /language command - show language selection keyboard."""
    message = update.get("message", {})
    user = message.get("from", {})
    user_id = user.get("id")
    chat_id = message.get("chat", {}).get("id")
    lang_code = user.get("language_code")

    if not check_user_allowed(user_id):
        lang = _get_lang(user_id, lang_code)
        await client.send_message(chat_id, get_translation("err_not_allowed", lang))
        return

    lang = _get_lang(user_id, lang_code)
    keyboard = _build_language_keyboard()
    await client.send_message(chat_id, get_translation("choose_language", lang), reply_markup=keyboard)


async def cmd_help(client: BaleClient, update: Dict[str, Any]) -> None:
    """Handle /help command."""
    message = update.get("message", {})
    user = message.get("from", {})
    user_id = user.get("id")
    chat_id = message.get("chat", {}).get("id")
    lang_code = user.get("language_code")

    if not check_user_allowed(user_id):
        lang = _get_lang(user_id, lang_code)
        await client.send_message(chat_id, get_translation("err_not_allowed", lang))
        return

    lang = _get_lang(user_id, lang_code)
    settings = get_settings()

    help_text = get_translation("help_title", lang) + "\n\n" + get_translation(
        "help_text", lang, rate_limit=settings.rate_limit_seconds
    )

    # Add "Change Language" button
    keyboard = {
        "inline_keyboard": [[
            {"text": get_translation("change_language_btn", lang), "callback_data": "cmd:language"}
        ]]
    }

    await client.send_message(chat_id, help_text, reply_markup=keyboard, parse_mode="Markdown")


async def callback_help_language(client: BaleClient, update: Dict[str, Any]) -> None:
    """Handle 'Change Language' button from help."""
    callback_query = update.get("callback_query", {})
    user = callback_query.get("from", {})
    user_id = user.get("id")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    callback_query_id = callback_query.get("id")
    lang_code = user.get("language_code")

    if not check_user_allowed(user_id):
        await client.answer_callback_query(callback_query_id, "Not allowed", show_alert=True)
        return

    await client.answer_callback_query(callback_query_id)
    lang = get_effective_language(user_id, lang_code)
    keyboard = _build_language_keyboard()
    await client.send_message(chat_id, get_translation("choose_language", lang), reply_markup=keyboard)


async def _update_status_message(client: BaleClient, chat_id: int, message_id: int, text: str) -> None:
    """Safely update a status message, ignoring errors."""
    try:
        await client.edit_message_text(chat_id, message_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.debug(f"Failed to update status message: {e}")


async def handle_message(client: BaleClient, update: Dict[str, Any]) -> None:
    """Handle plain text messages that look like domains/URLs."""
    message = update.get("message", {})
    user = message.get("from", {})
    user_id = user.get("id")
    chat_id = message.get("chat", {}).get("id")
    lang_code = user.get("language_code")
    text = message.get("text", "")

    if not check_user_allowed(user_id):
        lang = _get_lang(user_id, lang_code)
        await client.send_message(chat_id, get_translation("err_not_allowed", lang))
        return

    if not text or not text.strip():
        return

    lang = _get_lang(user_id, lang_code)
    text = text.strip()

    # Quick check if it looks like a domain
    if not looks_like_domain(text):
        await client.send_message(chat_id, get_translation("err_not_domain", lang))
        return

    # Check per-user rate limit
    allowed, wait_time = check_rate_limit(user_id)
    if not allowed:
        await client.send_message(chat_id, get_translation("err_rate_limit", lang, wait=wait_time))
        return

    # Normalize domain
    domain = normalize_domain(text)
    if not domain:
        await client.send_message(chat_id, get_translation("err_invalid_domain", lang))
        return

    # Send initial "queued" status message
    queued_text = get_translation("queued", lang, domain=domain)
    status_msg = await client.send_message(chat_id, queued_text, parse_mode="Markdown")
    status_msg_id = status_msg.get("message_id")

    # Define status update function for the queue
    async def update_status(text: str) -> None:
        await _update_status_message(client, chat_id, status_msg_id, text)

    try:
        # Call API - this will be queued and return when complete
        api_client = get_api_client()
        subdomains = await api_client.search(domain, status_update=update_status)

        # Format result (search completed, subdomains returned)
        _, as_file, unique_subs = format_subdomain_list(subdomains)

        if not unique_subs:
            await _update_status_message(client, chat_id, status_msg_id, get_translation("no_subdomains", lang))
            return

        if as_file:
            # Send as file
            file_content = "\n".join(unique_subs)
            caption = get_translation("file_caption", lang, domain=domain, count=len(unique_subs))
            filename = get_translation("filename_template", lang, domain=domain)
            await client.send_document(chat_id, file_content.encode("utf-8"), filename, caption)
        else:
            # Send as message with results header + subdomains in code block
            results_header = get_translation("results_header", lang, count=len(unique_subs))
            subs_text = "\n".join(unique_subs)
            message_text = f"{results_header}\n```\n{subs_text}\n```"
            await _update_status_message(client, chat_id, status_msg_id, message_text)

    except InvalidDomainError:
        await _update_status_message(client, chat_id, status_msg_id, get_translation("err_invalid_domain", lang))

    except RateLimitError as e:
        wait_msg = get_translation("err_api_rate_limit", lang)
        if e.retry_after:
            wait_msg += f" ({e.retry_after}s)"
        await _update_status_message(client, chat_id, status_msg_id, wait_msg)

    except AuthenticationError:
        await _update_status_message(client, chat_id, status_msg_id, get_translation("err_unauthorized", lang))
        logger.error("API authentication failed - check API_KEY")

    except ForbiddenError:
        await _update_status_message(client, chat_id, status_msg_id, get_translation("err_forbidden", lang))

    except TimeoutError:
        await _update_status_message(client, chat_id, status_msg_id, get_translation("err_timeout", lang))

    except APIError as e:
        logger.error(f"API error for {domain}: {e}")
        await _update_status_message(client, chat_id, status_msg_id, get_translation("err_api_error", lang, detail=str(e)))

    except Exception as e:
        logger.exception(f"Unexpected error handling message from {user_id}")
        await _update_status_message(client, chat_id, status_msg_id, get_translation("err_unknown", lang, detail="Internal server error"))


async def process_update(client: BaleClient, update: Dict[str, Any]) -> None:
    """Process a single update from Bale."""
    if "callback_query" in update:
        data = update["callback_query"].get("data", "")
        if data.startswith("lang:"):
            await callback_language_select(client, update)
        elif data == "cmd:language":
            await callback_help_language(client, update)
        elif data.startswith("clearcache_"):
            await handle_clearcache_callback(client, update)
    elif "message" in update:
        message = update["message"]
        text = message.get("text", "")
        if text.startswith("/start"):
            await cmd_start(client, update)
        elif text.startswith("/help"):
            await cmd_help(client, update)
        elif text.startswith("/language"):
            await cmd_language(client, update)
        elif text.startswith("/"):
            # Check for admin commands first
            from bot.admin_handlers import handle_admin_command
            handled = await handle_admin_command(client, update)
            if not handled:
                # Not an admin command, could be unknown command
                pass
        elif text and not text.startswith("/"):
            await handle_message(client, update)


async def set_bale_commands(client: BaleClient) -> None:
    """Set bot commands for both languages."""
    for lang_code in ["en", "fa"]:
        commands = get_bot_commands(lang_code)
        bale_commands = [{"command": cmd, "description": desc} for cmd, desc in commands]
        await client.set_my_commands(bale_commands, language_code=lang_code)