"""Internationalization (i18n) module for the bot.

Provides translations for English (en) and Persian/Farsi (fa).
"""

from typing import Dict, Any

# Type alias for translation dictionaries
Translations = Dict[str, Dict[str, str]]

TRANSLATIONS: Translations = {
    "en": {
        # Welcome & Language Selection
        "welcome_title": "Welcome to Subdomain Finder Bot!",
        "welcome_text": (
            "This bot finds subdomains of a given domain using an external API.\n\n"
            "Send me a website URL or domain to get started, e.g. example.com"
        ),
        "choose_language_prompt": "Please choose your preferred language:",
        "choose_language": "Choose language:",
        "lang_english": "English",
        "lang_persian": "Persian",
        "language_set": "Language set to English.",
        "language_confirmed": "✅ Language set to English.\n\nSend me a website URL or domain, e.g. example.com",
        "language_already": "Language is already set to English.",

        # Commands
        "cmd_start_desc": "Start the bot and show welcome message",
        "cmd_help_desc": "Show help and usage instructions",
        "cmd_language_desc": "Change bot language",

        # Help
        "help_title": "Subdomain Finder Bot - Help",
        "help_text": (
            "How it works:\n"
            "Send a domain or URL, and the bot will search for subdomains.\n\n"
            "Accepted formats:\n"
            "• example.com\n"
            "• www.example.com\n"
            "• https://example.com\n"
            "• https://www.example.com/path\n"
            "• example.com:8080\n"
            "• International domains (IDN) like example.ir\n\n"
            "Output:\n"
            "• List of subdomains (deduplicated, lowercase, sorted)\n"
            "• Total count\n"
            "• Large results (>4000 chars) sent as .txt file\n\n"
            "Limits:\n"
            "• {rate_limit}s between requests per user\n"
            "• API limit: 60 requests/minute\n\n"
            "Commands:\n"
            "/start - Welcome message\n"
            "/help - This help message\n"
            "/language - Change language\n\n"
            "Questions? Contact the developer."
        ),
        "change_language_btn": "Change Language",

        # Search flow
        "searching": "Searching for subdomains of `{domain}`...",
        "queued": "⏳ Queued: searching for subdomains of `{domain}`...\nPosition in queue: {position}",
        "still_searching": "🔍 Still searching for subdomains of `{domain}`... ({elapsed}s elapsed)",
        "queue_position": "⏳ Queued: searching for `{domain}`... (position in queue: {position})",
        "results_header": "Total: {count} subdomains",
        "results_too_long": (
            "Total: {count} subdomains\n"
            "Result too long for message, sent as file attachment."
        ),
        "no_subdomains": "No subdomains found for this domain.",
        "file_caption": "Subdomains for {domain} ({count} total)",

        # Errors
        "err_invalid_domain": "Invalid domain. Please enter a valid domain (e.g. example.com).",
        "err_rate_limit": "Rate limited. Please wait {wait:.1f} seconds before trying again.",
        "err_api_rate_limit": "API rate limit reached. Please try again later.",
        "err_timeout": "Request timed out. Please try again.",
        "err_unauthorized": "API authentication failed. Please contact admin.",
        "err_forbidden": "Access to API forbidden.",
        "err_unknown": "An unknown error occurred: {detail}",
        "err_not_allowed": "You are not authorized to use this bot.",
        "err_not_domain": "This doesn't look like a domain or URL.\nExample: example.com or https://www.example.com/path",

        # Admin
        "admin_stats": (
            "📊 *Bot Statistics*\n\n"
            "👥 Total Users: {total_users}\n"
            "🔍 Searches Today: {searches_today}\n"
            "📅 Searches This Week: {searches_this_week}\n"
            "📈 Searches All-Time: {searches_all_time}\n"
            "💾 Cache Hit Rate: {cache_hit_rate}%\n"
            "⚡ Rate Limit: {rate_limit_used}/{rate_limit_max} req/min\n"
            "⏳ Queue Length: {queue_length}"
        ),
        "admin_broadcast_usage": "Usage: /broadcast <message>",
        "admin_broadcast_started": "📢 *Broadcast Started*\n\nSending to {total} users...",
        "admin_broadcast_progress": "📢 *Broadcast Progress*\n\nSent: {sent}/{total} ({failed} failed)",
        "admin_broadcast_complete": (
            "✅ *Broadcast Complete*\n\n"
            "📊 Total: {total}\n"
            "✅ Success: {success}\n"
            "❌ Failed: {failed}"
        ),
        "admin_users_header": "👥 *Users ({total} total)*\n\n",
        "admin_no_users": "No users found.",
        "admin_clearcache_usage": "Usage: /clearcache <domain> or /clearcache all",
        "admin_clearcache_confirm_all": "⚠️ Are you sure you want to clear ALL cache?",
        "admin_clearcache_done": "✅ Cache cleared for `{domain}`",
        "admin_clearcache_all_done": "✅ All cache cleared ({count} entries removed)",
        "confirm_yes": "✅ Yes",
        "confirm_no": "❌ No",
        "cancelled": "Cancelled",
        "admin_setlimit_usage": "Usage: /setlimit <seconds>",
        "admin_setlimit_invalid": "Invalid value. Must be between 1 and 300 seconds.",
        "admin_setlimit_done": "✅ Rate limit set to {seconds} seconds",
        "admin_help": (
            "🔧 *Admin Commands*\n\n"
            "/stats - Show bot statistics\n"
            "/broadcast <text> - Send message to all users\n"
            "/users - Show recent users\n"
            "/clearcache <domain|all> - Clear cache\n"
            "/setlimit <seconds> - Change rate limit\n"
            "/adminhelp - Show this help"
        ),

        # File
        "filename_template": "subdomains_{domain}.txt",
    },
    "fa": {
        # Welcome & Language Selection
        "welcome_title": "به ربات یافتن ساب‌دامین خوش آمدید!",
        "welcome_text": (
            "این ربات ساب‌دامین‌های یک دامنه را با استفاده از API خارجی جستجو می‌کند.\n\n"
            "برای شروع، لینک وبسایت یا دامنه را بفرستید، مثلاً: example.com"
        ),
        "choose_language_prompt": "لطفاً زبان مورد نظر خود را انتخاب کنید:",
        "choose_language": "انتخاب زبان:",
        "lang_english": "انگلیسی",
        "lang_persian": "فارسی",
        "language_set": "زبان روی فارسی تنظیم شد.",
        "language_confirmed": "✅ زبان روی فارسی تنظیم شد.\n\nلینک وبسایت یا دامنه را بفرستید، مثلاً: example.com",
        "language_already": "زبان از قبل روی فارسی تنظیم شده است.",

        # Commands
        "cmd_start_desc": "شروع ربات و نمایش پیام خوش‌آمدگویی",
        "cmd_help_desc": "نمایش راهنما و دستورالعمل‌ها",
        "cmd_language_desc": "تغییر زبان ربات",

        # Help
        "help_title": "ربات یافتن ساب‌دامین - راهنما",
        "help_text": (
            "نحوه کارکرد:\n"
            "یک دامنه یا URL بفرستید تا ربات ساب‌دامین‌های آن را جستجو کند.\n\n"
            "فرمت‌های قابل قبول:\n"
            "• example.com\n"
            "• www.example.com\n"
            "• https://example.com\n"
            "• https://www.example.com/path\n"
            "• example.com:8080\n"
            "• دامنه‌های بین‌المللی (IDN) مثل مثال.ایران\n\n"
            "خروجی:\n"
            "• لیست ساب‌دامین‌ها (بدون تکرار، حروف کوچک، مرتب الفبایی)\n"
            "• تعداد کل\n"
            "• نتایج طولانی (بیش از ۴۰۰۰ کاراکتر) به صورت فایل متنی ارسال می‌شوند\n\n"
            "محدودیت‌ها:\n"
            "• {rate_limit} ثانیه بین هر درخواست از هر کاربر\n"
            "• محدودیت API: ۶۰ درخواست در دقیقه\n\n"
            "دستورات:\n"
            "/start - پیام خوش‌آمدگویی\n"
            "/help - این راهنما\n"
            "/language - تغییر زبان\n\n"
            "سوال دارید؟ با توسعه‌دهنده تماس بگیرید."
        ),
        "change_language_btn": "تغییر زبان",

        # Search flow
        "searching": "در حال جستجوی ساب‌دامین‌های `{domain}`...",
        "queued": "⏳ در صف: جستجوی ساب‌دامین‌های `{domain}`...\nموقعیت در صف: {position}",
        "still_searching": "🔍 همچنان در حال جستجو برای `{domain}`... ({elapsed}s گذشته)",
        "queue_position": "⏳ در صف: جستجوی `{domain}`... (موقعیت در صف: {position})",
        "results_header": "تعداد کل: {count} ساب‌دامین",
        "results_too_long": (
            "تعداد کل: {count} ساب‌دامین\n"
            "نتیجه طولانی است، در فایل پیوست ارسال شد."
        ),
        "no_subdomains": "هیچ ساب‌دامینی برای این دامنه یافت نشد.",
        "file_caption": "ساب‌دامین‌های {domain} ({count} مورد)",

        # Errors
        "err_invalid_domain": "دامنه نامعتبر است. لطفاً یک دامنه معتبر وارد کنید (مثال: example.com).",
        "err_rate_limit": "محدودیت نرخ درخواست. لطفاً {wait:.1f} ثانیه صبر کنید و دوباره تلاش کنید.",
        "err_api_rate_limit": "محدودیت API. لطفاً بعداً تلاش کنید.",
        "err_timeout": "زمان انتظار تمام شد. لطفاً دوباره تلاش کنید.",
        "err_unauthorized": "احراز هویت API ناموفق. لطفاً با ادمین تماس بگیرید.",
        "err_forbidden": "دسترسی به API ممنوع است.",
        "err_unknown": "خطای ناشناخته رخ داد: {detail}",
        "err_not_allowed": "شما اجازه استفاده از این ربات را ندارید.",
        "err_not_domain": "این ورودی شبیه به دامنه یا URL نیست.\nمثال: example.com یا https://www.example.com/path",

        # Admin
        "admin_stats": (
            "📊 *آمار ربات*\n\n"
            "👥 کل کاربران: {total_users}\n"
            "🔍 جستجوهای امروز: {searches_today}\n"
            "📅 جستجوهای این هفته: {searches_this_week}\n"
            "📈 جستجوهای کل: {searches_all_time}\n"
            "💾 نرخ هیت کش: {cache_hit_rate}%\n"
            "⚡ محدودیت نرخ: {rate_limit_used}/{rate_limit_max} درخواست/دقیقه\n"
            "⏳ طول صف: {queue_length}"
        ),
        "admin_broadcast_usage": "استفاده: /broadcast <پیام>",
        "admin_broadcast_started": "📢 *شروع ارسال همگانی*\n\nارسال به {total} کاربر...",
        "admin_broadcast_progress": "📢 پیشرفت ارسال: {sent}/{total} ({failed} ناموفق)",
        "admin_broadcast_complete": (
            "✅ *ارسال همگانی تکمیل شد*\n\n"
            "📊 کل: {total}\n"
            "✅ موفق: {success}\n"
            "❌ ناموفق: {failed}"
        ),
        "admin_users_header": "👥 کاربران ({total} کل):\n\n",
        "admin_no_users": "هیچ کاربری یافت نشد.",
        "admin_clearcache_usage": "استفاده: /clearcache <دامنه> یا /clearcache all",
        "admin_clearcache_confirm_all": "⚠️ آیا مطمئن هستید که می‌خواهید تمام کش را پاک کنید؟",
        "admin_clearcache_done": "✅ کش برای `{domain}` پاک شد",
        "admin_clearcache_all_done": "✅ تمام کش پاک شد ({count} مورد)",
        "confirm_yes": "✅ بله",
        "confirm_no": "❌ خیر",
        "cancelled": "لغو شد",
        "admin_setlimit_usage": "استفاده: /setlimit <ثانیه>",
        "admin_setlimit_invalid": "مقدار نامعتبر. باید بین ۱ تا ۳۰۰ ثانیه باشد.",
        "admin_setlimit_done": "✅ محدودیت نرخ روی {seconds} ثانیه تنظیم شد",
        "admin_help": (
            "🔧 *دستورات ادمین*\n\n"
            "/stats - نمایش آمار ربات\n"
            "/broadcast <متن> - ارسال پیام به همه کاربران\n"
            "/users - نمایش کاربران اخیر\n"
            "/clearcache <دامنه|all> - پاک کردن کش\n"
            "/setlimit <ثانیه> - تغییر محدودیت نرخ\n"
            "/adminhelp - نمایش این راهنما"
        ),

        # File
        "filename_template": "subdomains_{domain}.txt",
    },
}

SUPPORTED_LANGUAGES = ["en", "fa"]
DEFAULT_LANGUAGE = "en"

# Language code to display name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "fa": "فارسی",
}

# Emoji flags for language selection
LANGUAGE_FLAGS = {
    "en": "🇬🇧",
    "fa": "🇮🇷",
}


def get_translation(key: str, lang: str, **kwargs: Any) -> str:
    """Get translated string for a key in given language with formatting."""
    lang = lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE
    template = TRANSLATIONS[lang].get(key)
    if template is None:
        # Fallback to English
        template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def get_available_languages() -> list[tuple[str, str, str]]:
    """Get list of (code, flag, name) for available languages."""
    return [(code, LANGUAGE_FLAGS.get(code, ""), LANGUAGE_NAMES.get(code, code)) for code in SUPPORTED_LANGUAGES]


def get_bot_commands(lang: str) -> list[tuple[str, str]]:
    """Get bot command descriptions for a language."""
    return [
        ("start", get_translation("cmd_start_desc", lang)),
        ("help", get_translation("cmd_help_desc", lang)),
        ("language", get_translation("cmd_language_desc", lang)),
    ]