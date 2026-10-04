"""Unit tests for i18n (translations) module."""

import pytest

from bot.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    get_available_languages,
    get_bot_commands,
    get_translation,
)


class TestTranslationsExist:
    """Test that all required translation keys exist in both languages."""

    REQUIRED_KEYS = [
        # Welcome & Language Selection
        "welcome_title",
        "welcome_text",
        "choose_language",
        "lang_english",
        "lang_persian",
        "language_set",
        "language_already",
        # Commands
        "cmd_start_desc",
        "cmd_help_desc",
        "cmd_language_desc",
        # Help
        "help_title",
        "help_text",
        "change_language_btn",
        # Search flow
        "searching",
        "results_header",
        "results_too_long",
        "no_subdomains",
        "file_caption",
        # Errors
        "err_invalid_domain",
        "err_rate_limit",
        "err_api_rate_limit",
        "err_timeout",
        "err_unauthorized",
        "err_forbidden",
        "err_unknown",
        "err_not_allowed",
        "err_not_domain",
        # File
        "filename_template",
    ]

    def test_all_keys_exist_in_english(self):
        """All required keys must exist in English translations."""
        en_translations = TRANSLATIONS["en"]
        for key in self.REQUIRED_KEYS:
            assert key in en_translations, f"Missing key in English: {key}"
            assert en_translations[key], f"Empty value for key in English: {key}"

    def test_all_keys_exist_in_persian(self):
        """All required keys must exist in Persian translations."""
        fa_translations = TRANSLATIONS["fa"]
        for key in self.REQUIRED_KEYS:
            assert key in fa_translations, f"Missing key in Persian: {key}"
            assert fa_translations[key], f"Empty value for key in Persian: {key}"

    def test_no_extra_keys_in_persian(self):
        """Persian should not have keys that English doesn't have (and vice versa)."""
        en_keys = set(TRANSLATIONS["en"].keys())
        fa_keys = set(TRANSLATIONS["fa"].keys())
        assert en_keys == fa_keys, f"Key mismatch: EN has {en_keys - fa_keys}, FA has {fa_keys - en_keys}"


class TestGetTranslation:
    """Test get_translation function."""

    def test_english_translation(self):
        """Test getting English translation."""
        result = get_translation("welcome_title", "en")
        assert result == "Welcome to Subdomain Finder Bot!"

    def test_persian_translation(self):
        """Test getting Persian translation."""
        result = get_translation("welcome_title", "fa")
        assert result == "به ربات یافتن ساب‌دامین خوش آمدید!"

    def test_formatting_with_kwargs(self):
        """Test translation with format kwargs."""
        result = get_translation("results_header", "en", count=42)
        assert result == "Total: 42 subdomains"

        result = get_translation("results_header", "fa", count=42)
        assert result == "تعداد کل: 42 ساب‌دامین"

    def test_fallback_to_english_for_unknown_lang(self):
        """Unknown language codes should fallback to English."""
        result = get_translation("welcome_title", "xx")
        assert result == "Welcome to Subdomain Finder Bot!"

    def test_fallback_to_english_for_missing_key(self):
        """Missing keys should fallback to English (or return key)."""
        # This key doesn't exist
        result = get_translation("nonexistent_key", "fa")
        # Should fallback to English which also doesn't have it, so returns key
        assert result == "nonexistent_key"

    def test_rate_limit_translation_formatting(self):
        """Test rate limit translation with wait time."""
        result = get_translation("err_rate_limit", "en", wait=3.5)
        assert "3.5" in result

        result = get_translation("err_rate_limit", "fa", wait=3.5)
        assert "3.5" in result


class TestSupportedLanguages:
    """Test supported languages configuration."""

    def test_supported_languages_list(self):
        assert SUPPORTED_LANGUAGES == ["en", "fa"]

    def test_default_language(self):
        assert DEFAULT_LANGUAGE == "en"

    def test_get_available_languages(self):
        langs = get_available_languages()
        assert len(langs) == 2
        assert ("en", "🇬🇧", "English") in langs
        assert ("fa", "🇮🇷", "فارسی") in langs


class TestBotCommands:
    """Test bot command descriptions for each language."""

    def test_english_commands(self):
        commands = get_bot_commands("en")
        assert len(commands) == 3
        assert ("start", "Start the bot and show welcome message") in commands
        assert ("help", "Show help and usage instructions") in commands
        assert ("language", "Change bot language") in commands

    def test_persian_commands(self):
        commands = get_bot_commands("fa")
        assert len(commands) == 3
        assert ("start", "شروع ربات و نمایش پیام خوش‌آمدگویی") in commands
        assert ("help", "نمایش راهنما و دستورالعمل‌ها") in commands
        assert ("language", "تغییر زبان ربات") in commands


if __name__ == "__main__":
    pytest.main([__file__, "-v"])