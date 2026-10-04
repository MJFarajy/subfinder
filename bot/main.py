"""Main entry point for the Telegram bot with robust network handling."""

import asyncio
import logging
import socket
import sys
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiohttp import TCPConnector
import ssl
import certifi

from bot.config import get_settings
from bot.handlers import router, setup_bot_commands, shutdown_bot

# Force Windows Selector Event Loop Policy for better compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Reduce noise from libraries
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class IPv4AiohttpSession(AiohttpSession):
    """AiohttpSession that forces IPv4 connections."""

    def __init__(
        self,
        proxy: Optional[str] = None,
        limit: int = 100,
        request_timeout: int = 60,
        **kwargs: Any,
    ):
        # Initialize parent with proxy but without custom connector
        super().__init__(proxy=proxy, limit=limit, **kwargs)
        
        # Override connector init to force IPv4 and disable happy eyeballs
        self._connector_init = {
            "ssl": ssl.create_default_context(cafile=certifi.where()),
            "limit": limit,
            "ttl_dns_cache": 300,
            "family": socket.AF_INET,  # Force IPv4
            "enable_cleanup_closed": True,
            "happy_eyeballs_delay": None,  # Disable happy eyeballs (IPv4/IPv6 race)
        }
        
        # Store timeout for use in make_request
        self._request_timeout = request_timeout
        logger.info(f"IPv4 session initialized (proxy: {proxy}, timeout: {request_timeout}s)")

    async def make_request(
        self, bot: Bot, method: Any, timeout: Optional[int] = None
    ) -> Any:
        """Override to use our custom timeout."""
        return await super().make_request(bot, method, timeout or self._request_timeout)


def with_telegram_retry(
    max_attempts: int = 4,
    base_delay: float = 1.0,
    exceptions: tuple = (TelegramNetworkError, TelegramRetryAfter),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to retry Telegram API calls on network errors."""
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            f"Telegram API error (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Telegram API failed after {max_attempts} attempts: {e}"
                        )
                        raise
                except Exception:
                    raise
            raise last_exception
        return wrapper
    return decorator


class RobustBot(Bot):
    """Bot subclass with automatic retry on network errors for common methods."""

    @with_telegram_retry(max_attempts=4, base_delay=1.0)
    async def send_message(self, *args: Any, **kwargs: Any) -> Any:
        return await super().send_message(*args, **kwargs)

    @with_telegram_retry(max_attempts=4, base_delay=1.0)
    async def edit_message_text(self, *args: Any, **kwargs: Any) -> Any:
        return await super().edit_message_text(*args, **kwargs)

    @with_telegram_retry(max_attempts=4, base_delay=1.0)
    async def send_document(self, *args: Any, **kwargs: Any) -> Any:
        return await super().send_document(*args, **kwargs)

    @with_telegram_retry(max_attempts=4, base_delay=1.0)
    async def answer_callback_query(self, *args: Any, **kwargs: Any) -> Any:
        return await super().answer_callback_query(*args, **kwargs)

    @with_telegram_retry(max_attempts=4, base_delay=1.0)
    async def get_me(self, *args: Any, **kwargs: Any) -> Any:
        return await super().get_me(*args, **kwargs)


async def startup_self_check(
    bot: Bot,
    max_attempts: int = 5,
    base_delay: float = 2.0,
) -> bool:
    """Verify bot can connect to Telegram with retries."""
    logger.info("Performing startup self-check (getMe)...")
    for attempt in range(1, max_attempts + 1):
        try:
            me = await bot.get_me()
            logger.info(f"Startup check passed: @{me.username} (ID: {me.id})")
            return True
        except (TelegramNetworkError, TelegramRetryAfter, TimeoutError) as e:
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    f"Startup check failed (attempt {attempt}/{max_attempts}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Startup check failed after {max_attempts} attempts: {e}")
                return False
        except Exception as e:
            logger.error(f"Startup check failed with unexpected error: {e}")
            return False
    return False


async def main() -> None:
    """Main entry point."""
    settings = get_settings()

    # Validate token
    if not settings.bot_token or settings.bot_token == "your_bot_token_here":
        logger.error("BOT_TOKEN not set in .env file")
        sys.exit(1)

    # Mask token for logging
    masked_token = f"{settings.bot_token[:5]}...{settings.bot_token[-3:]}"
    logger.info(f"Starting bot with token: {masked_token}")
    if settings.proxy_url:
        logger.info(f"Proxy configured: {settings.proxy_url}")

    # Create session with proxy, IPv4, and proper timeouts
    session = IPv4AiohttpSession(
        proxy=settings.proxy_url,
        limit=100,
        request_timeout=settings.request_timeout,
    )

    # Create bot with robust retry wrapper
    bot = RobustBot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        session=session,
    )
    dp = Dispatcher()

    # Register router
    dp.include_router(router)

    # Set bot commands for both languages
    await setup_bot_commands(bot)

    # Setup shutdown handler
    async def on_shutdown() -> None:
        await shutdown_bot()
        await session.close()

    dp.shutdown.register(on_shutdown)

    # Startup self-check
    if not await startup_self_check(bot):
        logger.error("Startup self-check failed. Exiting.")
        await session.close()
        sys.exit(1)

    # Global error handler for unhandled exceptions in handlers
    @dp.errors()
    async def global_error_handler(event: Any):
        logger.exception(f"Unhandled error in handler: {event.exception}")
        return True

    # Start polling with automatic retry on network errors
    logger.info("Starting long polling...")
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=settings.request_timeout,
            )
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            break
        except (TelegramNetworkError, TelegramRetryAfter, TimeoutError) as e:
            logger.exception(f"Polling network error, retrying in 5s: {e}")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            logger.exception(f"Polling unexpected error, retrying in 5s: {e}")
            await asyncio.sleep(5)
            continue
        else:
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)