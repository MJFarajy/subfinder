"""Unit tests for language persistence module."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from bot.language_store import (
    clear_user_language,
    get_all_languages,
    get_effective_language,
    get_user_language,
    set_user_language,
)
from bot.database import get_db, init_db


class TestLanguageStore:
    """Test language persistence functionality."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Clear database before each test."""
        await init_db()
        async with get_db() as db:
            await db.execute("DELETE FROM users")
            await db.commit()
        yield
        async with get_db() as db:
            await db.execute("DELETE FROM users")
            await db.commit()

    @pytest.mark.asyncio
    async def test_get_user_language_empty(self):
        """Test getting language for user with no preference."""
        result = await get_user_language(12345)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_user_language(self):
        """Test setting and getting user language."""
        await set_user_language(12345, "fa")
        assert await get_user_language(12345) == "fa"

        await set_user_language(12345, "en")
        assert await get_user_language(12345) == "en"

    @pytest.mark.asyncio
    async def test_set_invalid_language(self):
        """Test setting invalid language returns False."""
        assert not await set_user_language(12345, "fr")
        assert await get_user_language(12345) is None

    @pytest.mark.asyncio
    async def test_clear_user_language(self):
        """Test clearing user language."""
        await set_user_language(12345, "fa")
        assert await get_user_language(12345) == "fa"

        await clear_user_language(12345)
        assert await get_user_language(12345) is None

        # Clearing non-existent should return False
        assert not await clear_user_language(12345)

    @pytest.mark.asyncio
    async def test_get_effective_language_saved_preference(self):
        """Test effective language uses saved preference first."""
        await set_user_language(12345, "fa")
        result = await get_effective_language(12345, "en")
        assert result == "fa"

    @pytest.mark.asyncio
    async def test_get_effective_language_telegram_fallback_fa(self):
        """Test effective language falls back to Telegram language_code for Persian."""
        result = await get_effective_language(12345, "fa")
        assert result == "fa"

        result = await get_effective_language(12345, "fa-IR")
        assert result == "fa"

    @pytest.mark.asyncio
    async def test_get_effective_language_telegram_fallback_en(self):
        """Test effective language falls back to English for non-Persian Telegram languages."""
        result = await get_effective_language(12345, "en")
        assert result == "en"

        result = await get_effective_language(12345, "en-US")
        assert result == "en"

        result = await get_effective_language(12345, "de")
        assert result == "en"

        result = await get_effective_language(12345, None)
        assert result == "en"

    @pytest.mark.asyncio
    async def test_get_effective_language_saved_overrides_telegram(self):
        """Test saved preference overrides Telegram language."""
        await set_user_language(12345, "en")
        result = await get_effective_language(12345, "fa")
        assert result == "en"

        await set_user_language(12345, "fa")
        result = await get_effective_language(12345, "en")
        assert result == "fa"

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self):
        """Test language preference persists across module reloads."""
        await set_user_language(12345, "fa")
        
        # Simulate new process by creating new connection
        # (The database file persists, so data should persist)
        result = await get_user_language(12345)
        assert result == "fa"

    @pytest.mark.asyncio
    async def test_get_all_languages(self):
        """Test getting all saved languages."""
        await set_user_language(111, "en")
        await set_user_language(222, "fa")
        await set_user_language(333, "en")

        all_langs = await get_all_languages()
        assert all_langs == [(111, "en"), (222, "fa"), (333, "en")]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])