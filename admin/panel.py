"""Admin panel FastAPI application."""

import csv
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from bot.config import get_settings
from bot.database import (
    add_search_history,
    close_db,
    create_admin_session,
    delete_admin_session,
    export_search_history_csv,
    get_all_users,
    get_db,
    get_recent_logs,
    get_search_history,
    get_stats,
    get_user,
    get_user_language,
    init_db,
    set_setting,
    set_user_allowed_status,
    validate_admin_session,
)
from bot.i18n import get_translation, get_available_languages

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Subdomain Finder Bot - Admin Panel",
    version="1.0.0",
)

# Templates
templates = Jinja2Templates(directory="admin/templates")

# Session cookie settings
SESSION_COOKIE_NAME = "admin_session"
SESSION_COOKIE_MAX_AGE = 3600  # 1 hour


# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str


class BroadcastRequest(BaseModel):
    text: str


class SettingUpdate(BaseModel):
    key: str
    value: str


class UserAllowedUpdate(BaseModel):
    user_id: int
    allowed: bool


# Dependency to get settings
def get_app_settings():
    return get_settings()


# Authentication dependency
async def get_current_admin(
    request: Request,
    session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Validate admin session and return username."""
    settings = get_app_settings()
    
    if not settings.is_admin_panel_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel is disabled. Set ADMIN_PANEL_USERNAME and ADMIN_PANEL_PASSWORD to enable."
        )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    from bot.database import validate_admin_session
    username = await validate_admin_session(session)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    return username


async def check_brute_force(username: str) -> bool:
    """Check if account is locked due to failed attempts."""
    from bot.database import check_account_locked
    return await check_account_locked(username)


async def record_failed_login(username: str) -> int:
    """Record failed login attempt."""
    from bot.database import record_failed_login
    return await record_failed_login(username)


async def reset_failed_logins(username: str) -> None:
    """Reset failed login attempts."""
    from bot.database import reset_failed_logins
    await reset_failed_logins(username)


# Routes

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle login."""
    settings = get_settings()
    
    # Check brute force
    if await check_brute_force(username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Account locked for 5 minutes."
        )
    
    # Validate credentials
    if username != settings.admin_panel_username:
        await record_failed_login(username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not settings.verify_admin_password(password):
        await record_failed_login(username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Successful login - reset failed attempts
    from bot.database import reset_failed_logins
    await reset_failed_logins(username)
    
    # Create session
    session_id = await create_admin_session(username)
    
    # Set cookie
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=3600,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
    )
    
    return response


@app.post("/logout")
async def logout(
    response: Response,
    session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Handle logout."""
    if session:
        await delete_admin_session(session)
    
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    username: str = Depends(get_current_admin),
):
    """Dashboard overview page."""
    stats = await get_stats()
    from bot.rate_limit import get_rate_limiter, get_rate_queue
    from bot.config import get_settings
    
    settings = get_settings()
    rate_limiter = await get_rate_limiter()
    rate_status = await rate_limiter.get_status()
    queue = await get_rate_queue()
    queue_info = await queue.get_queue_info()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": username,
        "stats": stats,
        "rate_status": rate_status,
        "queue_info": queue_info,
        "settings": settings,
    })


@app.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    username: str = Depends(get_current_admin),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Users management page."""
    offset = (page - 1) * page_size
    users, total = await get_all_users(search=search, limit=page_size, offset=offset)
    total_pages = (total + page_size - 1) // page_size
    
    return templates.TemplateResponse("users.html", {
        "request": request,
        "username": username,
        "users": users,
        "search": search,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@app.post("/users/{user_id}/allowed")
async def toggle_user_allowed(
    user_id: int,
    data: UserAllowedUpdate,
    username: str = Depends(get_current_admin),
):
    """Toggle user allowed status."""
    success = await set_user_allowed_status(data.user_id, data.allowed)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": f"User {user_id} allowed status updated"}


@app.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    username: str = Depends(get_current_admin),
    user_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Search history page."""
    offset = (page - 1) * page_size
    history, total = await get_search_history(
        user_id=user_id,
        limit=page_size,
        offset=offset,
        search=search
    )
    total_pages = (total + page_size - 1) // page_size
    
    # Get all users for filter dropdown
    users, _ = await get_all_users(limit=1000)
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "username": username,
        "history": history,
        "users": users,
        "selected_user_id": user_id,
        "search": search,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@app.get("/history/export")
async def export_history(
    user_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    username: str = Depends(get_current_admin),
):
    """Export search history as CSV."""
    csv_data = await export_search_history_csv(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    filename = f"search_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(
    request: Request,
    username: str = Depends(get_current_admin),
):
    """Broadcast message page."""
    return templates.TemplateResponse("broadcast.html", {
        "request": request,
        "username": username,
    })


@app.post("/broadcast")
async def send_broadcast(
    background_tasks: BackgroundTasks,
    data: BroadcastRequest,
    username: str = Depends(get_current_admin),
):
    """Send broadcast message to all users."""
    from bot.bale_client import BaleClient
    from bot.config import get_settings
    
    settings = get_settings()
    client = BaleClient(
        token=settings.bale_bot_token,
        timeout=settings.request_timeout,
        proxy_url=settings.proxy_url,
    )
    
    # Get all users
    users, _ = await get_all_users(limit=10000)
    user_ids = [u["user_id"] for u in users]
    
    # Send in background
    background_tasks.add_task(
        send_broadcast_messages,
        client,
        user_ids,
        data.text,
    )
    
    return {"success": True, "message": f"Broadcast started to {len(user_ids)} users"}


async def send_broadcast_messages(client: BaleClient, user_ids: List[int], text: str):
    """Send broadcast messages with staggering."""
    success_count = 0
    fail_count = 0
    
    for i, user_id in enumerate(user_ids):
        try:
            await client.send_message(chat_id=user_id, text=text)
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to user {user_id}: {e}")
            fail_count += 1
        
        # Stagger: 3 messages per second
        if i < len(user_ids) - 1:
            await asyncio.sleep(0.33)
    
    logger.info(f"Broadcast completed: {success_count} success, {fail_count} failed")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    username: str = Depends(get_current_admin),
):
    """Settings page."""
    settings_obj = get_settings()
    
    # Get current values from database
    rate_limit = await get_setting("rate_limit_seconds") or str(settings_obj.rate_limit_seconds)
    request_timeout = await get_setting("request_timeout") or str(settings_obj.request_timeout)
    cache_ttl = await get_setting("cache_ttl") or str(settings_obj.cache_ttl)
    allowlist_on = await get_setting("allowlist_enabled") or "false"
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "username": username,
        "rate_limit_seconds": rate_limit,
        "request_timeout": request_timeout,
        "cache_ttl": cache_ttl,
        "allowlist_enabled": allowlist_on == "true",
    })


@app.post("/settings")
async def update_settings(
    rate_limit_seconds: str = Form(...),
    request_timeout: str = Form(...),
    cache_ttl: str = Form(...),
    allowlist_enabled: Optional[str] = Form(None),
    username: str = Depends(get_current_admin),
):
    """Update settings."""
    await set_setting("rate_limit_seconds", rate_limit_seconds)
    await set_setting("request_timeout", request_timeout)
    await set_setting("cache_ttl", cache_ttl)
    await set_setting("allowlist_enabled", "true" if allowlist_enabled else "false")
    
    return RedirectResponse(url="/settings?updated=1", status_code=302)


async def get_setting(key: str) -> Optional[str]:
    """Get setting from database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    """Set setting in database."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = ?, updated_at = CURRENT_TIMESTAMP
        """, (key, value, value))
        await db.commit()


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    username: str = Depends(get_current_admin),
    level: Optional[str] = Query(None),
    lines: int = Query(200, ge=50, le=1000),
):
    """Logs page."""
    logs = await get_recent_logs(lines)
    
    # Filter by level if specified
    if level:
        logs = [log for log in logs if level.upper() in log]
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "username": username,
        "logs": logs,
        "selected_level": level,
        "lines": lines,
    })


@app.get("/api/stats")
async def api_stats(username: str = Depends(get_current_admin)):
    """API endpoint for stats."""
    stats = await get_stats()
    
    from bot.rate_limit import get_rate_limiter, get_rate_queue
    rate_limiter = await get_rate_limiter()
    rate_status = await rate_limiter.get_status()
    queue = await get_rate_queue()
    queue_info = await queue.get_queue_info()
    
    return {
        "stats": stats,
        "rate_limiter": rate_status,
        "queue": queue_info,
    }


@app.get("/api/logs")
async def api_logs(
    lines: int = Query(200, ge=50, le=1000),
    level: Optional[str] = Query(None),
    username: str = Depends(get_current_admin),
):
    """API endpoint for logs."""
    logs = await get_recent_logs(lines)
    
    if level:
        logs = [log for log in logs if level.upper() in log]
    
    return {"logs": logs}


# Startup/shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()
    logger.info("Admin panel started")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    await close_db()
    logger.info("Admin panel shut down")


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "admin.panel:app",
        host=settings.admin_panel_host,
        port=settings.admin_panel_port,
        reload=False,
    )