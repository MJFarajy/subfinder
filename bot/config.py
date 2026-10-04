"""Configuration management using Pydantic Settings."""

import os
import secrets
import string
from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_proxy_url() -> Optional[str]:
    """Detect proxy URL from environment, system, or running processes."""
    # Check if explicitly set in env (not the default placeholder)
    explicit = os.environ.get("PROXY_URL")
    if explicit and explicit.strip() and explicit != "your_proxy_url_here":
        return explicit.strip()

    # Try auto-detection
    try:
        from bot.proxy_detect import find_working_proxy

        detected = find_working_proxy()
        if detected is not None and detected != "":
            # Cache the detected proxy so we don't re-detect
            os.environ["PROXY_URL"] = detected
            return detected
    except Exception as e:
        print(f"[config] Proxy detection failed: {e}")

    return None


def _generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    # Use only alphanumeric to avoid bcrypt 72-byte limit issues
    # Length 16 = 16 bytes, well within bcrypt's 72-byte limit
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _ensure_admin_credentials() -> tuple[str, str]:
    """Ensure admin credentials exist, generate if missing. Returns (username, password)."""
    username = os.environ.get("ADMIN_PANEL_USERNAME")
    password = os.environ.get("ADMIN_PANEL_PASSWORD")
    
    if not username or not password:
        # Generate new credentials
        username = "admin"
        # Generate 16-char alphanumeric password, well within bcrypt's 72-byte limit
        password = _generate_secure_password(16)
        os.environ["ADMIN_PANEL_USERNAME"] = username
        os.environ["ADMIN_PANEL_PASSWORD"] = password
        # Write to .env file
        _write_env_credentials(username, password)
        print("=" * 60)
        print("ADMIN CREDENTIALS GENERATED (save these now):")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print("  CHANGE THIS PASSWORD AFTER FIRST LOGIN!")
        print("=" * 60)
    
    return username, password


def _write_env_credentials(username: str, password: str) -> None:
    """Write admin credentials to .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    # Remove existing admin credentials
    lines = [l for l in lines if not l.startswith(("ADMIN_PANEL_USERNAME=", "ADMIN_PANEL_PASSWORD="))]
    
    # Add new credentials
    lines.append(f"ADMIN_PANEL_USERNAME={username}\n")
    lines.append(f"ADMIN_PANEL_PASSWORD={password}\n")
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot Token (required)
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # API Configuration
    api_base_url: str = Field(default="https://app.agniops.in", alias="API_BASE_URL")
    api_key: Optional[str] = Field(default=None, alias="API_KEY")

    # Allowed users (empty = all allowed)
    allowed_user_ids: List[int] = Field(default_factory=list, alias="ALLOWED_USER_IDS")

    # Timeouts and limits
    request_timeout: int = Field(default=180, alias="REQUEST_TIMEOUT")  # 3 minutes for slow domains
    cache_ttl: int = Field(default=600, alias="CACHE_TTL")  # 10 minutes
    rate_limit_seconds: int = Field(default=1, alias="RATE_LIMIT_SECONDS")  # per-user cooldown

    # Proxy (optional - auto-detected if not set)
    proxy_url: Optional[str] = Field(default=None, alias="PROXY_URL")

    # Platform: "telegram" or "bale"
    platform: str = Field(default="bale", alias="PLATFORM")

    # Bale Bot Token
    bale_bot_token: str = Field(default="", alias="BALE_BOT_TOKEN")

    # Admin Panel Settings
    admin_panel_username: str = Field(default="admin", alias="ADMIN_PANEL_USERNAME")
    admin_panel_password: str = Field(default="", alias="ADMIN_PANEL_PASSWORD")
    admin_panel_password_hash: str = Field(default="", alias="ADMIN_PANEL_PASSWORD_HASH")
    admin_panel_host: str = Field(default="127.0.0.1", alias="ADMIN_PANEL_HOST")
    admin_panel_port: int = Field(default=8000, alias="ADMIN_PANEL_PORT")
    admin_user_ids: List[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")
    admin_failed_attempts_limit: int = Field(default=5, alias="ADMIN_FAILED_ATTEMPTS_LIMIT")
    admin_lockout_duration: int = Field(default=300, alias="ADMIN_LOCKOUT_DURATION")  # 5 minutes

    def __init__(self, **kwargs):
        # Auto-detect proxy before pydantic validation
        if "proxy_url" not in kwargs:
            kwargs["proxy_url"] = _detect_proxy_url()
        
        # Generate admin credentials if not set
        if "admin_panel_username" not in kwargs or "admin_panel_password" not in kwargs:
            username, password = _ensure_admin_credentials()
            if "admin_panel_username" not in kwargs:
                kwargs["admin_panel_username"] = username
            if "admin_panel_password" not in kwargs:
                kwargs["admin_panel_password"] = password
        
        super().__init__(**kwargs)
        
        # Hash the password for storage (truncate to 72 bytes for bcrypt limit)
        if self.admin_panel_password and not self.admin_panel_password_hash:
            password_bytes = self.admin_panel_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            # Use plain SHA256 for simplicity and to avoid bcrypt 72-byte limit issues
            import hashlib
            self.admin_panel_password_hash = hashlib.sha256(password_bytes).hexdigest()
    
    def verify_admin_password(self, password: str) -> bool:
        """Verify admin password against stored hash."""
        if not self.admin_panel_password_hash:
            return False
        import hashlib
        password_bytes = password.encode('utf-8')
        return hashlib.sha256(password_bytes).hexdigest() == self.admin_panel_password_hash

    @property
    def api_search_url(self) -> str:
        """Full URL for the search endpoint."""
        return f"{self.api_base_url.rstrip('/')}/v1/search"
    
    @property
    def is_admin_panel_enabled(self) -> bool:
        """Check if admin panel is enabled."""
        return bool(self.admin_panel_username and self.admin_panel_password_hash)
    
    @property
    def is_admin_commands_enabled(self) -> bool:
        """Check if admin commands are enabled."""
        return bool(self.admin_user_ids)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# For backward compatibility and easy imports
settings = get_settings()