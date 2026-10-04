"""Disk-backed cache with SQLite for persistent subdomain results."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Optional

from bot.config import get_settings
from bot.database import get_db, DB_DIR

logger = logging.getLogger(__name__)

# Cache file path
CACHE_DIR = DB_DIR
CACHE_FILE = CACHE_DIR / "cache.db"

# In-memory cache for fast access (L1)
_memory_cache: dict = {}
_memory_cache_lock = asyncio.Lock()


async def _init_cache_table() -> None:
    """Ensure cache table exists in database."""
    async with get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subdomain_cache (
                domain TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                subdomains TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_subdomain_cache_timestamp 
            ON subdomain_cache(timestamp)
        """)
        await db.commit()


async def get_from_cache(domain: str, ttl: int) -> Optional[List[str]]:
    """Get cached subdomains from memory (L1) or disk (L2)."""
    # Check memory cache first
    async with _memory_cache_lock:
        if domain in _memory_cache:
            timestamp, subdomains = _memory_cache[domain]
            if time.time() - timestamp < ttl:
                logger.debug(f"Memory cache hit for {domain}")
                return subdomains
            else:
                # Expired in memory, remove it
                del _memory_cache[domain]

    # Check disk cache
    async with get_db() as db:
        await _init_cache_table()
        cursor = await db.execute(
            "SELECT timestamp, subdomains FROM subdomain_cache WHERE domain = ?",
            (domain,)
        )
        row = await cursor.fetchone()
        
        if row:
            timestamp, subdomains_json = row
            if time.time() - timestamp < ttl:
                subdomains = json.loads(subdomains_json)
                # Update memory cache
                async with _memory_cache_lock:
                    _memory_cache[domain] = (timestamp, subdomains)
                logger.debug(f"Disk cache hit for {domain}")
                return subdomains
            else:
                # Expired on disk, remove it
                await db.execute("DELETE FROM subdomain_cache WHERE domain = ?", (domain,))
                await db.commit()

    return None


async def set_cache(domain: str, subdomains: List[str]) -> None:
    """Save subdomains to both memory and disk cache."""
    timestamp = time.time()
    
    # Update memory cache
    async with _memory_cache_lock:
        _memory_cache[domain] = (timestamp, subdomains)
    
    # Save to disk asynchronously
    await _save_to_disk(domain, timestamp, subdomains)
    logger.debug(f"Cached {len(subdomains)} subdomains for {domain} (memory + disk)")


async def _save_to_disk(domain: str, timestamp: float, subdomains: List[str]) -> None:
    """Save to disk cache."""
    try:
        async with get_db() as db:
            await _init_cache_table()
            await db.execute("""
                INSERT OR REPLACE INTO subdomain_cache (domain, timestamp, subdomains)
                VALUES (?, ?, ?)
            """, (domain, timestamp, json.dumps(subdomains)))
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to save cache to disk for {domain}: {e}")


async def invalidate_cache(domain: str) -> None:
    """Remove domain from both memory and disk cache."""
    async with _memory_cache_lock:
        _memory_cache.pop(domain, None)
    
    try:
        async with get_db() as db:
            await _init_cache_table()
            await db.execute("DELETE FROM subdomain_cache WHERE domain = ?", (domain,))
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to invalidate cache for {domain}: {e}")


async def cleanup_expired_cache(ttl: int) -> int:
    """Clean up expired entries from both caches. Returns count of deleted disk entries."""
    # Clean memory cache
    async with _memory_cache_lock:
        now = time.time()
        expired = [d for d, (ts, _) in _memory_cache.items() if now - ts >= ttl]
        for d in expired:
            del _memory_cache[d]
    
    # Clean disk cache
    try:
        async with get_db() as db:
            await _init_cache_table()
            cutoff = time.time() - ttl
            cursor = await db.execute(
                "DELETE FROM subdomain_cache WHERE timestamp < ?",
                (cutoff,)
            )
            await db.commit()
            return cursor.rowcount
    except Exception as e:
        logger.warning(f"Failed to cleanup expired disk cache: {e}")
        return 0


async def init_cache() -> None:
    """Initialize the cache system."""
    await _init_cache_table()
    # Clean up expired entries on startup
    settings = get_settings()
    await cleanup_expired_cache(settings.cache_ttl)
    logger.info("Disk cache initialized")


async def get_cache_stats() -> dict:
    """Get cache statistics."""
    async with _memory_cache_lock:
        memory_count = len(_memory_cache)
    
    try:
        async with get_db() as db:
            await _init_cache_table()
            cursor = await db.execute("SELECT COUNT(*) FROM subdomain_cache")
            row = await cursor.fetchone()
            disk_count = row[0] if row else 0
    except Exception:
        disk_count = 0
    
    return {
        "memory_entries": memory_count,
        "disk_entries": disk_count,
    }