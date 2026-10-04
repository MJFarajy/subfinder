"""Unit tests for bot handlers - language selection and callbacks."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import CallbackQuery, Message, User, Chat

from bot.handlers import cmd_start, callback_language_select
from bot.language_store import (
    clear_user_language,
    get_effective_language,
    get_user_language,
    set_user_language,
)
from bot.database import init_db


class TestLanguageCallback:
    """Tests for language selection callback handler."""

    @pytest.fixture
    def mock_callback(self):
        """Create a mock CallbackQuery."""
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "lang:fa"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = 12345
        callback.from_user.language_code = "en"
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()
        return callback

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Initialize database and clear language store before each test."""
        await init_db()
        await clear_user_language(12345)
        await clear_user_language(67890)
        yield
        await clear_user_language(12345)
        await clear_user_language(67890)

    @pytest.mark.asyncio
    async def test_callback_fa_saves_language(self, mock_callback):
        """Test callback with 'fa' saves language as 'fa'."""
        mock_callback.data = "lang:fa"
        await callback_language_select(mock_callback)

        # Verify language was saved
        assert await get_user_language(12345) == "fa"

    @pytest.mark.asyncio
    async def test_callback_en_saves_language(self, mock_callback):
        """Test callback with 'en' saves language as 'en'."""
        mock_callback.data = "lang:en"
        await callback_language_select(mock_callback)

        # Verify language was saved
        assert await get_user_language(12345) == "en"

    @pytest.mark.asyncio
    async def test_callback_fa_shows_confirmation_message(self, mock_callback):
        """Test callback with 'fa' shows Persian confirmation, not choose-language text."""
        mock_callback.data = "lang:fa"
        await callback_language_select(mock_callback)

        # Get the text that was sent to edit_text
        call_args = mock_callback.message.edit_text.call_args
        assert call_args is not None, "edit_text should have been called"
        message_text = call_args[0][0]  # first positional argument

        # Should contain Persian confirmation
        assert "زبان روی فارسی تنظیم شد" in message_text
        assert "دامنه را بفرستید" in message_text

        # Should NOT contain the choose-language prompt
        assert "انتخاب زبان" not in message_text
        assert "لطفاً زبان مورد نظر" not in message_text

    @pytest.mark.asyncio
    async def test_callback_en_shows_confirmation_message(self, mock_callback):
        """Test callback with 'en' shows English confirmation, not choose-language text."""
        mock_callback.data = "lang:en"
        await callback_language_select(mock_callback)

        # Get the text that was sent to edit_text
        call_args = mock_callback.message.edit_text.call_args
        assert call_args is not None, "edit_text should have been called"
        message_text = call_args[0][0]  # first positional argument

        # Should contain English confirmation
        assert "Language set to English" in message_text
        assert "Send me a website URL or domain" in message_text

        # Should NOT contain the choose-language prompt
        assert "Choose language" not in message_text
        assert "Please choose your preferred language" not in message_text

    @pytest.mark.asyncio
    async def test_callback_answers_with_toast(self, mock_callback):
        """Test callback answers with a toast message."""
        mock_callback.data = "lang:fa"
        await callback_language_select(mock_callback)

        # Verify callback.answer was called
        mock_callback.answer.assert_called_once()
        # The toast should contain the language_set translation
        call_args = mock_callback.answer.call_args
        assert call_args is not None


class TestStartCommand:
    """Tests for /start command handler."""

    @pytest.fixture
    def mock_message(self):
        """Create a mock Message."""
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=User)
        message.from_user.id = 67890
        message.from_user.language_code = "en"
        message.answer = AsyncMock()
        return message

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Clear language store before each test."""
        await clear_user_language(67890)
        yield
        await clear_user_language(67890)

    @pytest.mark.asyncio
    async def test_start_with_saved_language_shows_welcome_no_prompt(self, mock_message):
        """Test /start for user with saved language shows welcome without language prompt."""
        # Pre-set language
        await set_user_language(67890, "fa")
        mock_message.from_user.language_code = "fa"

        await cmd_start(mock_message)

        # Get the text that was sent
        call_args = mock_message.answer.call_args
        assert call_args is not None
        message_text = call_args[0][0]

        # Should contain welcome text
        assert "به ربات یافتن ساب‌دامین خوش آمدید" in message_text
        assert "دامنه را بفرستید" in message_text

        # Should NOT contain choose-language prompt
        assert "انتخاب زبان" not in message_text
        assert "لطفاً زبان مورد نظر" not in message_text

    @pytest.mark.asyncio
    async def test_start_without_saved_language_shows_prompt(self, mock_message):
        """Test /start for user without saved language shows language prompt."""
        # No saved language
        mock_message.from_user.language_code = "en"

        await cmd_start(mock_message)

        # Get the text that was sent
        call_args = mock_message.answer.call_args
        assert call_args is not None
        message_text = call_args[0][0]

        # Should contain welcome text
        assert "Welcome to Subdomain Finder Bot" in message_text
        assert "Send me a website URL or domain" in message_text

        # Should contain choose-language prompt
        assert "Please choose your preferred language" in message_text

    @pytest.mark.asyncio
    async def test_start_with_saved_en_shows_english_welcome(self, mock_message):
        """Test /start for user with saved English shows English welcome."""
        await set_user_language(67890, "en")

        await cmd_start(mock_message)

        call_args = mock_message.answer.call_args
        message_text = call_args[0][0]

        assert "Welcome to Subdomain Finder Bot" in message_text
        assert "Send me a website URL or domain" in message_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])