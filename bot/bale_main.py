"""Main entry point for the Bale bot with long polling."""

import asyncio
import logging
import sys
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from bot.bale_client import BaleClient, BaleAPIError
from bot.bale_handlers import process_update, set_bale_commands
from bot.cache import init_cache, cleanup_expired_cache
from bot.config import get_settings
from bot.handlers import shutdown_bot
from bot.rate_limit import init_rate_limiting, shutdown_rate_limiting

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Reduce noise from libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_bale_retry(
    max_attempts: int = 4,
    base_delay: float = 1.0,
    exceptions: tuple = (BaleAPIError, asyncio.TimeoutError, ConnectionError),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to retry Bale API calls on network errors."""

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
                            f"Bale API error (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Bale API failed after {max_attempts} attempts: {e}"
                        )
                        raise
                except Exception:
                    raise
            raise last_exception

        return wrapper

    return decorator


async def startup_self_check(client: BaleClient, max_attempts: int = 5, base_delay: float = 2.0) -> bool:
    """Verify bot can connect to Bale with retries."""
    logger.info("Performing startup self-check (getMe)...")
    for attempt in range(1, max_attempts + 1):
        try:
            me = await client.get_me()
            logger.info(f"Startup check passed: @{me.get('username')} (ID: {me.get('id')})")
            return True
        except (BaleAPIError, asyncio.TimeoutError, ConnectionError) as e:
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
    if settings.platform == "bale":
        token = settings.bale_bot_token
        if not token or token == "your_bale_bot_token_here":
            logger.error("BALE_BOT_TOKEN not set in .env file")
            sys.exit(1)
    else:
        token = settings.bot_token
        if not token or token == "your_bot_token_here":
            logger.error("BOT_TOKEN not set in .env file")
            sys.exit(1)

    # Mask token for logging
    masked_token = f"{token[:5]}...{token[-3:]}"
    logger.info(f"Starting bot with token: {masked_token}")
    if settings.proxy_url:
        logger.info(f"Proxy configured: {settings.proxy_url}")

    # Initialize cache and rate limiting
    await init_cache()
    await init_rate_limiting()

    # Create Bale client
    client = BaleClient(
        token=token,
        timeout=settings.request_timeout,
        proxy_url=settings.proxy_url,
    )

    # Startup self-check
    if not await startup_self_check(client):
        logger.error("Startup self-check failed. Exiting.")
        await client.close()
        await shutdown_rate_limiting()
        sys.exit(1)

    # Set bot commands
    await set_bale_commands(client)

    # Long polling loop
    logger.info("Starting long polling...")
    offset = 0
    allowed_updates = ["message", "callback_query"]

    while True:
        try:
            updates = await client.get_updates(
                offset=offset,
                limit=100,
                timeout=30,
                allowed_updates=allowed_updates,
            )

            for update in updates:
                update_id = update.get("update_id", 0)
                if update_id >= offset:
                    offset = update_id + 1
                # Process each update in its own task to not block polling
                asyncio.create_task(process_update(client, update))

        except BaleAPIError as e:
            if e.error_code == 429:
                # Rate limited by Bale
                logger.warning(f"Rate limited by Bale: {e}. Waiting 60s...")
                await asyncio.sleep(60)
            else:
                logger.exception(f"Bale API error, retrying in 5s: {e}")
                await asyncio.sleep(5)
        except (asyncio.TimeoutError, ConnectionError) as e:
            logger.exception(f"Network error, retrying in 5s: {e}")
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            break
        except Exception as e:
            logger.exception(f"Unexpected error, retrying in 5s: {e}")
            await asyncio.sleep(5)
        else:
            continue

    # Cleanup
    await client.close()
    await shutdown_bot()
    await shutdown_rate_limiting()
    logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)