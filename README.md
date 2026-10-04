# Subdomain Finder Bot (Bale / Telegram)

A fully async Python bot that finds subdomains of a given domain using the AgniOps subdomain lookup API. Supports both **Bale Messenger** (works in Iran without VPN) and **Telegram**.

## Features

- 🔍 **Subdomain Discovery**: Finds subdomains using external API
- 🌐 **Flexible Input**: Accepts URLs, domains with/without www, with paths, ports
- 🌍 **Bilingual Support**: English and Persian (Farsi) with persistent language preference
- 🤖 **Dual Platform**: Bale (no VPN needed in Iran) and Telegram
- ⚡ **Async/Await**: Built with httpx for high performance
- 🛡️ **Robust**: Retries with exponential backoff, rate limiting, caching
- 💾 **Persistent Cache**: Disk-backed SQLite cache (L1 memory + L2 disk) survives restarts
- ⏱️ **Rate Limiting**: Global sliding window (60 req/min) with request queue
- 📦 **File Output**: Large results sent as .txt files
- 🐳 **Docker Ready**: Includes Dockerfile for easy deployment
- 🔁 **Auto-Restart**: `run_forever` scripts for production deployment

## Quick Start

### Prerequisites

- Python 3.11+
- Bot Token:
  - **Bale**: From [@BotFather](https://t.me/BotFather) in Bale app
  - **Telegram**: From [@BotFather](https://t.me/BotFather) in Telegram

### Installation

```bash
# Clone the repository
git clone <your-repo>
cd subfinder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your bot token(s)

# Run the bot (Bale - default)
python -m bot.bale_main

# Or run on Telegram
python -m bot.main
```

### Production Deployment (Auto-Restart)

**Windows:**
```cmd
scripts\run_forever.bat
```

**Linux/macOS:**
```bash
chmod +x scripts/run_forever.sh
./scripts/run_forever.sh
```

**Windows Task Scheduler (run at startup, restart on failure):**
1. Open Task Scheduler
2. Create Basic Task → Name: "Subdomain Finder Bot"
3. Trigger: "When the computer starts"
4. Action: "Start a Program"
   - Program: `C:\path\to\subfinder\venv\Scripts\python.exe`
   - Arguments: `-m bot.bale_main`
   - Start in: `C:\path\to\subfinder`
5. Settings: Check "Restart on failure" → Restart every 1 minute, attempt 3 times

### Using Docker

```bash
# Build image
docker build -t subfinder-bot .

# Run container (Bale - default)
docker run -d --name subfinder-bot --env-file .env subfinder-bot

# Run container (Telegram)
docker run -d --name subfinder-bot --env-file .env -e PLATFORM=telegram subfinder-bot
```

## Configuration

All configuration is done via environment variables in `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLATFORM` | No | `bale` | `bale` or `telegram` |
| `BALE_BOT_TOKEN` | When PLATFORM=bale | - | Bale bot token from @BotFather in Bale |
| `BOT_TOKEN` | When PLATFORM=telegram | - | Telegram bot token from @BotFather |
| `API_BASE_URL` | No | `https://app.agniops.in` | Base URL for the subdomain API |
| `API_KEY` | No | - | API key if required by the API |
| `ALLOWED_USER_IDS` | No | - | Comma-separated list of allowed user IDs |
| `REQUEST_TIMEOUT` | No | `180` | Request timeout in seconds (3 min for slow domains) |
| `CACHE_TTL` | No | `600` | Cache TTL in seconds (10 minutes) |
| `RATE_LIMIT_SECONDS` | No | `1` | Minimum seconds between user requests |
| `PROXY_URL` | No | - | Proxy for Telegram/API (e.g., `socks5://127.0.0.1:1080`) |

### Bale Setup (Recommended for Iran)

1. Open Bale app and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Copy the token and add to `.env` as `BALE_BOT_TOKEN`
4. Set `PLATFORM=bale` (default)
5. **No VPN or proxy needed** - Bale works directly in Iran

### Telegram Setup

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Copy the token and add to `.env` as `BOT_TOKEN`
4. Set `PLATFORM=telegram`
5. If in Iran, configure `PROXY_URL` in `.env` (e.g., `socks5://127.0.0.1:1080`)

## Language Support

The bot supports **English** and **Persian (Farsi)**:

- **First run**: User is prompted to choose language via inline keyboard (🇬🇧 English / 🇮🇷 فارسی)
- **Persistence**: Language preference is saved in `data/user_languages.json` and survives bot restarts
- **Fallback**: 
  - Bale: Defaults to Persian (no `language_code` in updates)
  - Telegram: Uses Telegram's `language_code` (fa → Persian, else → English)
- **Switch anytime**: Use `/language` command or "Change Language" button in `/help` to switch

## Usage

1. Start the bot with `/start`
2. Choose your language (first time only)
3. Send any domain or URL:
   - `example.com`
   - `www.example.com`
   - `https://example.com/path`
   - `https://www.example.com:8080/path?query=1`
4. Receive subdomain list (sorted, deduplicated, with count)
5. Large results (>4000 chars) are sent as `.txt` files

## Commands

- `/start` - Welcome message and usage instructions (shows language selector on first run)
- `/help` - Detailed help with "Change Language" button
- `/language` - Change bot language at any time

## Reliability Features

### Disk-Backed Cache (L1 + L2)
- **L1**: In-memory cache (instant access)
- **L2**: SQLite database (`data/cache.db`) - survives restarts
- Configurable TTL via `CACHE_TTL` (default 600s)
- Automatic cleanup of expired entries on startup

### Global Rate Limiter (60 req/min)
- Sliding window algorithm (60 requests per rolling 60 seconds)
- Honors `x-ratelimit-*` headers from the API
- Request queue with FIFO processing
- Max 3 concurrent in-flight requests

### Request Queue with Status Updates
- When limit exceeded, requests are queued (not dropped)
- User sees queue position: "⏳ Queued: searching for `example.com`... (position in queue: 3)"
- Periodic status updates: "🔍 Still searching... (45s elapsed)"
- Updates throttled (min 15s between edits)

### 429 Handling
- Reads `Retry-After` / `x-ratelimit-reset` headers
- Pauses entire queue until limit resets
- Automatic resume after backoff
- Never retries immediately in tight loop

### Graceful Degradation
- Each message processed in its own asyncio task
- One slow/queued search never blocks polling or other users
- Global error handler logs but never crashes the bot
- Clean shutdown closes all HTTP sessions and cache connections

## Usage

1. Start the bot with `/start`
2. Choose your language (first time only)
3. Send any domain or URL:
   - `example.com`
   - `www.example.com`
   - `https://example.com/path`
   - `https://www.example.com:8080/path?query=1`
4. Receive subdomain list (sorted, deduplicated, with count)
5. Large results (>4000 chars) are sent as `.txt` files

## Commands

- `/start` - Welcome message and usage instructions (shows language selector on first run)
- `/help` - Detailed help with "Change Language" button
- `/language` - Change bot language at any time

## Project Structure

```
subfinder/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Telegram entry point
│   ├── bale_main.py         # Bale entry point
│   ├── config.py            # Configuration management
│   ├── handlers.py          # Telegram handlers
│   ├── bale_handlers.py     # Bale handlers
│   ├── api_client.py        # Subdomain API client with retries/caching
│   ├── bale_client.py       # Bale Bot API client
│   ├── cache.py             # Disk-backed cache (SQLite + memory)
│   ├── rate_limit.py        # Sliding window rate limiter + queue
│   ├── utils.py             # Domain normalization & formatting
│   ├── i18n.py              # Translations (EN/FA)
│   └── language_store.py    # Language persistence (JSON)
├── data/
│   ├── user_languages.json  # User language preferences (auto-created)
│   └── cache.db             # SQLite cache (auto-created)
├── tests/
│   ├── __init__.py
│   ├── test_utils.py        # Unit tests for utils
│   ├── test_api_client.py   # Unit tests for subdomain API client
│   ├── test_bale_client.py  # Unit tests for Bale client
│   ├── test_i18n.py         # Unit tests for translations
│   └── test_language_store.py # Unit tests for language persistence
├── docs/
│   ├── api_notes.md         # AgniOps API exploration notes
│   └── bale_notes.md        # Bale Bot API exploration notes
├── scripts/
│   ├── run_forever.bat      # Windows auto-restart script
│   └── run_forever.sh       # Linux/macOS auto-restart script
├── .env                     # Environment variables (not in git)
├── .env.example             # Example environment file
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

## API Details

### Subdomain API (AgniOps)
- **Endpoint**: `GET https://app.agniops.in/v1/search?domain=<DOMAIN>`
- **Response**: Plain text, one subdomain per line
- **Rate Limit**: 60 requests/minute (via headers)
- **Auth**: No API key required (as of current exploration)

### Bale Bot API
- **Base URL**: `https://tapi.bale.ai/bot<TOKEN>`
- **Auth**: Token in URL path
- **Format**: JSON (POST requests)
- **Parse Mode**: Markdown only
- **Long Polling**: Supported via `getUpdates` with `timeout` parameter
- **Works in Iran without VPN**

See [docs/api_notes.md](docs/api_notes.md) and [docs/bale_notes.md](docs/bale_notes.md) for detailed exploration notes.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bot --cov-report=html

# Run specific test file
pytest tests/test_utils.py -v
```

## Logging

Structured logging to stdout. Log level can be adjusted in `bot/main.py` / `bot/bale_main.py`.
Bot tokens and API keys are never logged.

## Security

- `.env` is in `.gitignore` - never commit secrets
- Tokens/keys never logged (masked as `9990...gRQ` or `8815...YA`)
- Optional user allowlist via `ALLOWED_USER_IDS`
- Per-user rate limiting

## License

MIT License