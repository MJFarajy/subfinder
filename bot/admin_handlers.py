"""Admin-only bot commands for Bale."""

import logging
import asyncio
from typing import Dict, Any, List

from bot.bale_client import BaleClient
from bot.database import (
    get_stats, get_all_users, set_user_allowed_status, 
    get_search_history, export_search_history_csv
)
from bot.cache import cleanup_expired_cache
from bot.config import get_settings
from bot.i18n import get_translation, get_effective_language
from bot.language_store import check_user_allowed

logger = logging.getLogger(__name__)


async def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    settings = get_settings()
    return user_id in settings.admin_user_ids


async def handle_admin_command(client: BaleClient, update: Dict[str, Any]) -> bool:
    """Handle admin commands. Returns True if handled."""
    message = update.get("message", {})
    user = message.get("from", {})
    user_id = user.get("id")
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    
    if not await is_admin(user_id):
        return False
    
    lang = await get_effective_language(user_id, user.get("language_code"))
    
    if text.startswith("/stats"):
        await handle_stats(client, chat_id, lang)
        return True
    
    elif text.startswith("/broadcast"):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await client.send_message(chat_id, get_translation("admin_broadcast_usage", lang))
            return True
        broadcast_text = parts[1]
        await handle_broadcast(client, chat_id, lang, broadcast_text)
        return True
    
    elif text.startswith("/users"):
        await handle_users(client, chat_id, lang)
        return True
    
    elif text.startswith("/clearcache"):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await client.send_message(chat_id, get_translation("admin_clearcache_usage", lang))
            return True
        await handle_clearcache(client, chat_id, lang, parts[1])
        return True
    
    elif text.startswith("/setlimit"):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await client.send_message(chat_id, get_translation("admin_setlimit_usage", lang))
            return True
        try:
            seconds = int(parts[1])
            await handle_setlimit(client, chat_id, lang, seconds)
        except ValueError:
            await client.send_message(chat_id, get_translation("admin_setlimit_invalid", lang))
        return True
    
    elif text.startswith("/adminhelp"):
        await handle_adminhelp(client, chat_id, lang)
        return True
    
    return False


async def handle_stats(client: BaleClient, chat_id: int, lang: str) -> None:
    """Handle /stats command."""
    stats = await get_stats()
    from bot.rate_limit import get_rate_limiter, get_rate_queue
    
    rate_limiter = await get_rate_limiter()
    rate_status = await rate_limiter.get_status()
    queue = await get_rate_queue()
    queue_info = await queue.get_queue_info()
    
    text = get_translation("admin_stats", lang,
        total_users=stats["total_users"],
        searches_today=stats["searches_today"],
        searches_this_week=stats["searches_this_week"],
        searches_all_time=stats["searches_all_time"],
        cache_hit_rate=stats["cache_hit_rate"],
        rate_limit_used=rate_status["requests_in_window"],
        rate_limit_max=rate_status["max_requests"],
        queue_length=queue_info["queue_length"],
    )
    
    await client.send_message(chat_id, text, parse_mode="Markdown")


async def handle_broadcast(client: BaleClient, chat_id: int, lang: str, text: str) -> None:
    """Handle /broadcast command."""
    from bot.bale_client import BaleClient
    from bot.config import get_settings
    from bot.database import get_all_users
    
    settings = get_settings()
    bale_client = BaleClient(
        token=settings.bale_bot_token,
        timeout=settings.request_timeout,
        proxy_url=settings.proxy_url,
    )
    
    # Get all users
    users, _ = await get_all_users(limit=10000)
    user_ids = [u["user_id"] for u in users]
    
    # Send initial status
    status_msg = await bale_client.send_message(
        chat_id, 
        get_translation("admin_broadcast_started", lang, total=len(user_ids)),
        parse_mode="Markdown"
    )
    status_msg_id = status_msg.get("message_id")
    
    success_count = 0
    fail_count = 0
    
    for i, user_id in enumerate(user_ids):
        try:
            await bale_client.send_message(chat_id=user_id, text=text)
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to user {user_id}: {e}")
            fail_count += 1
        
        # Update status every 10 messages
        if i % 10 == 0 or i == len(user_ids) - 1:
            try:
                progress_text = get_translation("admin_broadcast_progress", lang,
                    sent=i + 1,
                    total=len(user_ids),
                    failed=fail_count
                )
                await bale_client.edit_message_text(chat_id, status_msg_id, progress_text, parse_mode="Markdown")
            except Exception:
                pass
        
        # Stagger: 3 messages per second
        if i < len(user_ids) - 1:
            await asyncio.sleep(0.33)
    
    # Final report
    final_text = get_translation("admin_broadcast_complete", lang,
        total=len(user_ids),
        success=success_count,
        failed=fail_count
    )
    await bale_client.edit_message_text(chat_id, status_msg_id, final_text, parse_mode="Markdown")


async def handle_users(client: BaleClient, chat_id: int, lang: str) -> None:
    """Handle /users command."""
    from bot.database import get_all_users
    
    users, total = await get_all_users(limit=10)
    
    if not users:
        await client.send_message(chat_id, get_translation("admin_no_users", lang))
        return
    
    lines = [get_translation("admin_users_header", lang, total=total)]
    for user in users:
        lang_flag = "🇮🇷" if user.get("language_code") == "fa" else "🇬🇧"
        allowed = "✅" if user.get("is_allowed", 1) else "🚫"
        lines.append(
            f"`{user['user_id']}` {lang_flag} {allowed} "
            f"Searches: {user.get('total_searches', 0)} | Last: {user.get('last_seen', 'N/A')}"
        )
    
    text = "\n".join(lines)
    await client.send_message(chat_id, text, parse_mode="Markdown")


async def handle_clearcache(client: BaleClient, chat_id: int, lang: str, target: str) -> None:
    """Handle /clearcache command."""
    from bot.cache import invalidate_cache, cleanup_expired_cache
    from bot.config import get_settings
    
    settings = get_settings()
    
    if target.lower() == "all":
        # Confirm with user
        keyboard = {
            "inline_keyboard": [[
                {"text": get_translation("confirm_yes", lang), "callback_data": "clearcache_confirm_all"},
                {"text": get_translation("confirm_no", lang), "callback_data": "clearcache_cancel"}
            ]}
        }
        await client.send_message(
            chat_id,
            get_translation("admin_clearcache_confirm_all", lang),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        # Clear specific domain
        domain = target.strip().lower()
        await invalidate_cache(domain)
        await client.send_message(
            chat_id,
            get_translation("admin_clearcache_done", lang, domain=domain),
            parse_mode="Markdown"
        )


async def handle_clearcache_callback(client: BaleClient, update: Dict[str, Any]) -> bool:
    """Handle clearcache confirmation callbacks."""
    callback_query = update.get("callback_query", {})
    data = callback_query.get("data", "")
    callback_query_id = callback_query.get("id")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    user_id = callback_query.get("from", {}).get("id")
    
    if not await is_admin(user_id):
        await client.answer_callback_query(callback_query_id, "Not authorized", show_alert=True)
        return True
    
    lang = await get_effective_language(user_id, callback_query.get("from", {}).get("language_code"))
    
    if data == "clearcache_confirm_all":
        from bot.cache import cleanup_expired_cache
        from bot.config import get_settings
        settings = get_settings()
        deleted = await cleanup_expired_cache(settings.cache_ttl)
        await client.answer_callback_query(callback_query_id, get_translation("admin_clearcache_all_done", lang, count=deleted))
        await client.edit_message_text(
            callback_query.get("message", {}).get("chat", {}).get("id"),
            callback_query.get("message", {}).get("message_id"),
            get_translation("admin_clearcache_all_done", lang, count=deleted),
            parse_mode="Markdown"
        )
    elif data == "clearcache_cancel":
        await client.answer_callback_query(callback_query_id, get_translation("cancelled", lang))
        await client.edit_message_text(
            callback_query.get("message", {}).get("chat", {}).get("id"),
            callback_query.get("message", {}).get("message_id"),
            get_translation("cancelled", lang)
        )
    
    return True


async def handle_setlimit(client: BaleClient, chat_id: int, lang: str, seconds: int) -> None:
    """Handle /setlimit command."""
    from bot.config import get_settings
    from bot.database import set_setting
    
    settings = get_settings()
    
    if seconds < 1 or seconds > 300:
        await client.send_message(chat_id, get_translation("admin_setlimit_invalid", lang))
        return
    
    await set_setting("rate_limit_seconds", str(seconds))
    settings.rate_limit_seconds = seconds
    
    await client.send_message(
        chat_id,
        get_translation("admin_setlimit_done", lang, seconds=seconds),
        parse_mode="Markdown"
    )


async def handle_adminhelp(client: BaleClient, chat_id: int, lang: str) -> None:
    """Handle /adminhelp command."""
    text = get_translation("admin_help", lang)
    await client.send_message(chat_id, text, parse_mode="Markdown")