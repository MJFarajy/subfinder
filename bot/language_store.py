"""Language persistence using SQLite database."""

import logging
from typing import Dict, Optional

from bot.database import (
    get_user_language as db_get_user_language,
    set_user_language as db_set_user_language,
    get_user_allowed,
    set_user_allowed,
    upsert_user,
)

logger = logging.getLogger(__name__)


# Backward compatibility functions - now use database
async def get_user_language(user_id: int) -> Optional[str]:
    """Get user's saved language preference from database."""
    return await db_get_user_language(user_id)


async def set_user_language(user_id: int, lang: str) -> bool:
    """Set user's language preference and persist to database."""
    from bot.i18n import SUPPORTED_LANGUAGES

    if lang not in SUPPORTED_LANGUAGES:
        logger.warning(f"Attempted to set unsupported language: {lang}")
        return False

    await upsert_user(user_id, language_code=lang)
    logger.info(f"Set language for user {user_id} to {lang}")
    return True


async def get_effective_language(user_id: int, telegram_lang_code: Optional[str] = None) -> str:
    """
    Get effective language for a user.

    Priority:
    1. Saved user preference
    2. Telegram language_code (if 'fa' -> Persian, else English)
    3. Default (English)
    """
    from bot.i18n import DEFAULT_LANGUAGE

    # Check saved preference
    saved = await db_get_user_language(user_id)
    if saved:
        return saved

    # Fallback to Telegram language
    if telegram_lang_code:
        if telegram_lang_code.lower().startswith("fa"):
            return "fa"

    return DEFAULT_LANGUAGE


async def clear_user_language(user_id: int) -> bool:
    """Remove user's language preference (revert to fallback)."""
    # We can't easily remove just the language, so set to default
    await upsert_user(user_id, language_code="en")
    logger.info(f"Cleared language preference for user {user_id} (set to default)")
    return True


async def get_all_languages() -> Dict[int, str]:
    """Get all saved language preferences (for debugging/admin)."""
    from bot.database import get_all_users
    users, _ = await get_all_users()
    return {u["user_id"]: u["language_code"] for u in users if u.get("language_code")}


async def check_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    return await get_user_allowed(user_id)


async def set_user_allowed_status(user_id: int, allowed: bool) -> bool:
    """Set user's allowed status."""
    return await set_user_allowed(user_id, allowed)


async def get_all_users_with_langs() -> list:
    """Get all users with their language preferences."""
    from bot.database import get_all_users
    users, _ = await get_all_users()
    return [(u["user_id"], u.get("language_code")) for u in users]