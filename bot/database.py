"""Database module with SQLite WAL mode for shared bot/dashboard access."""

import aiosqlite
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional, Tuple

from bot.config import get_settings

logger = logging.getLogger(__name__)

# Database file path
DB_DIR = Path(__file__).parent.parent / "data"
DB_FILE = DB_DIR / "bot.db"


async def init_db() -> None:
    """Initialize database with WAL mode and create tables."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_FILE) as db:
        # Enable WAL mode for concurrent access
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA busy_timeout=5000")
        
        # Create tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language_code TEXT DEFAULT 'fa',
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_searches INTEGER DEFAULT 0,
                is_allowed INTEGER DEFAULT 1
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result_count INTEGER DEFAULT 0,
                cache_hit INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_search_history_user_id 
            ON search_history(user_id)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_search_history_timestamp 
            ON search_history(timestamp)
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_failed_logins (
                username TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            )
        """)
        
        await db.commit()
        logger.info("Database initialized with WAL mode")


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Get database connection with row factory."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        yield db


# User operations
async def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_user(
    user_id: int,
    language_code: Optional[str] = None,
    is_allowed: Optional[int] = None
) -> None:
    """Insert or update user."""
    async with get_db() as db:
        if language_code is not None and is_allowed is not None:
            await db.execute("""
                INSERT INTO users (user_id, language_code, last_seen, is_allowed)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    language_code = COALESCE(?, language_code),
                    last_seen = CURRENT_TIMESTAMP,
                    is_allowed = COALESCE(?, is_allowed),
                    total_searches = total_searches + 1
            """, (user_id, language_code, is_allowed, language_code, is_allowed))
        elif language_code is not None:
            await db.execute("""
                INSERT INTO users (user_id, language_code, last_seen)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    language_code = ?,
                    last_seen = CURRENT_TIMESTAMP,
                    total_searches = total_searches + 1
            """, (user_id, language_code, language_code))
        elif is_allowed is not None:
            await db.execute("""
                INSERT INTO users (user_id, is_allowed, last_seen)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    is_allowed = ?,
                    last_seen = CURRENT_TIMESTAMP
            """, (user_id, is_allowed, is_allowed))
        else:
            await db.execute("""
                INSERT INTO users (user_id, last_seen)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    total_searches = total_searches + 1
            """, (user_id,))
        await db.commit()


async def get_user_language(user_id: int) -> Optional[str]:
    """Get user's language preference."""
    user = await get_user(user_id)
    return user.get("language_code") if user else None


async def set_user_language(user_id: int, lang: str) -> bool:
    """Set user's language preference."""
    await upsert_user(user_id, language_code=lang)
    return True


async def get_user_allowed(user_id: int) -> bool:
    """Check if user is allowed."""
    user = await get_user(user_id)
    if user is None:
        return True  # Default to allowed if not in DB
    return bool(user.get("is_allowed", 1))


async def set_user_allowed(user_id: int, allowed: bool) -> bool:
    """Set user's allowed status."""
    await upsert_user(user_id, is_allowed=1 if allowed else 0)
    return True


async def get_all_users(
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[dict], int]:
    """Get all users with optional search and pagination."""
    async with get_db() as db:
        # Count total
        if search:
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE CAST(user_id AS TEXT) LIKE ?",
                (f"%{search}%",)
            )
        else:
            count_cursor = await db.execute("SELECT COUNT(*) FROM users")
        total = (await count_cursor.fetchone())[0]
        
        # Get paginated results
        if search:
            cursor = await db.execute("""
                SELECT * FROM users 
                WHERE CAST(user_id AS TEXT) LIKE ?
                ORDER BY last_seen DESC
                LIMIT ? OFFSET ?
            """, (f"%{search}%", limit, offset))
        else:
            cursor = await db.execute("""
                SELECT * FROM users 
                ORDER BY last_seen DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def set_user_allowed_status(user_id: int, allowed: bool) -> bool:
    """Set user allowed status (for admin panel)."""
    await upsert_user(user_id, is_allowed=1 if allowed else 0)
    return True


# Search history operations
async def add_search_history(
    user_id: int,
    domain: str,
    result_count: int,
    cache_hit: bool,
    duration_ms: int
) -> int:
    """Add search history entry."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO search_history (user_id, domain, result_count, cache_hit, duration_ms)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, domain, result_count, 1 if cache_hit else 0, duration_ms))
        await db.commit()
        return cursor.lastrowid


async def get_search_history(
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None
) -> Tuple[List[dict], int]:
    """Get search history with optional filters."""
    async with get_db() as db:
        where_clauses = []
        params = []
        
        if user_id is not None:
            where_clauses.append("sh.user_id = ?")
            params.append(user_id)
        
        if search:
            where_clauses.append("sh.domain LIKE ?")
            params.append(f"%{search}%")
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Count total
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM search_history sh {where_sql}", params
        )
        total = (await count_cursor.fetchone())[0]
        
        # Get paginated results with user info
        params.extend([limit, offset])
        cursor = await db.execute(f"""
            SELECT sh.*, u.language_code as user_language
            FROM search_history sh
            LEFT JOIN users u ON sh.user_id = u.user_id
            {where_sql}
            ORDER BY sh.timestamp DESC
            LIMIT ? OFFSET ?
        """, params)
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def export_search_history_csv(
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """Export search history as CSV."""
    import csv
    import io
    
    async with get_db() as db:
        where_clauses = []
        params = []
        
        if user_id is not None:
            where_clauses.append("sh.user_id = ?")
            params.append(user_id)
        
        if start_date:
            where_clauses.append("sh.timestamp >= ?")
            params.append(start_date)
        
        if end_date:
            where_clauses.append("sh.timestamp <= ?")
            params.append(end_date)
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        cursor = await db.execute(f"""
            SELECT sh.*, u.language_code as user_language
            FROM search_history sh
            LEFT JOIN users u ON sh.user_id = u.user_id
            {where_sql}
            ORDER BY sh.timestamp DESC
        """, params)
        
        rows = await cursor.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "User ID", "Domain", "Timestamp", 
            "Result Count", "Cache Hit", "Duration (ms)", "User Language"
        ])
        for row in rows:
            writer.writerow([
                row["id"], row["user_id"], row["domain"], row["timestamp"],
                row["result_count"], row["cache_hit"], row["duration_ms"],
                row["user_language"]
            ])
        
        return output.getvalue()


# Admin session operations
async def create_admin_session(username: str, expires_in: int = 3600) -> str:
    """Create admin session and return session ID."""
    import uuid
    session_id = str(uuid.uuid4())
    expires_at = f"datetime('now', '+{expires_in} seconds')"
    
    async with get_db() as db:
        await db.execute("""
            INSERT INTO admin_sessions (session_id, username, expires_at)
            VALUES (?, ?, datetime('now', ?))
        """, (session_id, username, f"+{expires_in} seconds"))
        await db.commit()
    
    return session_id


async def validate_admin_session(session_id: str) -> Optional[str]:
    """Validate admin session and return username if valid."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT username FROM admin_sessions 
            WHERE session_id = ? AND expires_at > datetime('now')
        """, (session_id,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def delete_admin_session(session_id: str) -> bool:
    """Delete admin session (logout)."""
    async with get_db() as db:
        cursor = await db.execute("""
            DELETE FROM admin_sessions WHERE session_id = ?
        """, (session_id,))
        await db.commit()
        return cursor.rowcount > 0


async def cleanup_expired_sessions() -> int:
    """Clean up expired admin sessions."""
    async with get_db() as db:
        cursor = await db.execute("""
            DELETE FROM admin_sessions WHERE expires_at <= datetime('now')
        """)
        await db.commit()
        return cursor.rowcount


async def record_failed_login(username: str) -> int:
    """Record failed login attempt. Returns current attempt count."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO admin_failed_logins (username, attempts, locked_until)
            VALUES (?, 1, NULL)
            ON CONFLICT(username) DO UPDATE SET
                attempts = attempts + 1,
                locked_until = CASE 
                    WHEN attempts + 1 >= ? THEN datetime('now', '+300 seconds')
                    ELSE locked_until
                END
        """, (username, 5))  # 5 attempts limit
        await db.commit()
        
        cursor = await db.execute(
            "SELECT attempts FROM admin_failed_logins WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def check_account_locked(username: str) -> bool:
    """Check if account is locked."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT locked_until FROM admin_failed_logins 
            WHERE username = ? AND locked_until > datetime('now')
        """, (username,))
        row = await cursor.fetchone()
        return row is not None


async def reset_failed_logins(username: str) -> None:
    """Reset failed login attempts."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM admin_failed_logins WHERE username = ?", (username,)
        )
        await db.commit()


# Settings operations
async def get_setting(key: str) -> Optional[str]:
    """Get setting value."""
    async with get_db() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    """Set setting value."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = ?, updated_at = CURRENT_TIMESTAMP
        """, (key, value, value))
        await db.commit()


# Stats operations
async def get_stats() -> dict:
    """Get system statistics."""
    async with get_db() as db:
        # Total users
        total_users = (await db.execute("SELECT COUNT(*) FROM users")).fetchone()[0]
        
        # Searches today
        today_searches = (await db.execute("""
            SELECT COUNT(*) FROM search_history 
            WHERE date(timestamp) = date('now')
        """)).fetchone()[0]
        
        # Searches this week
        week_searches = (await db.execute("""
            SELECT COUNT(*) FROM search_history 
            WHERE date(timestamp) >= date('now', '-7 days')
        """)).fetchone()[0]
        
        # All-time searches
        all_searches = (await db.execute("SELECT COUNT(*) FROM search_history")).fetchone()[0]
        
        # Cache hit rate
        cache_hits = (await db.execute("""
            SELECT COUNT(*) FROM search_history WHERE cache_hit = 1
        """)).fetchone()[0]
        total_searches = all_searches
        cache_hit_rate = (cache_hits / total_searches * 100) if total_searches > 0 else 0
        
        return {
            "total_users": total_users,
            "searches_today": today_searches,
            "searches_this_week": week_searches,
            "searches_all_time": all_searches,
            "cache_hit_rate": round(cache_hit_rate, 2),
        }


async def get_recent_logs(limit: int = 200) -> List[str]:
    """Get recent log entries from the log file."""
    # This will be implemented by reading the log file
    # For now return empty
    return []


async def close_db() -> None:
    """Close database connections (cleanup)."""
    # aiosqlite handles connection pooling automatically
    pass