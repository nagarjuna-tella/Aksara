"""
Vidyut Configuration System

Centralized settings management with environment variable support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Parse boolean from environment variable."""
    value = os.environ.get(key, "").lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return default


def _get_int_env(key: str, default: int) -> int:
    """Parse integer from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class Settings:
    """
    Vidyut configuration settings.
    
    Settings can be configured via:
    1. Internal defaults (lowest priority)
    2. Environment variables (VIDYUT_*)
    3. Explicit configure() call (highest priority)
    
    Usage:
        from vidyut.conf import settings
        
        # Access settings
        db_url = settings.DATABASE_URL
        
        # Or configure explicitly
        from vidyut.conf import configure, Settings
        configure(Settings(database_url="postgresql://...", debug=True))
    """
    
    # Database
    database_url: Optional[str] = None
    pool_min_size: int = 5
    pool_max_size: int = 20
    
    # Debug & Logging
    debug: bool = False
    log_level: str = "INFO"
    
    # v0.3.13: Request logging
    log_requests: bool = True
    log_json: bool = False
    
    # App metadata (v0.3.4)
    app_title: Optional[str] = None
    app_version: Optional[str] = None
    
    # Migrations
    migrations_dir: str = "migrations"
    
    # Future: AI features
    ai_enabled: bool = False
    mcp_enabled: bool = False
    
    # v0.3.6: Multi-app support
    apps: List[str] = field(default_factory=lambda: ["app"])
    
    # v0.3.20: Django-style INSTALLED_APPS
    # These apps are auto-loaded on startup
    installed_apps: List[str] = field(default_factory=lambda: [
        "vidyut.contrib.auth",   # User authentication (creates vidyut_users table)
        "vidyut.contrib.admin",  # Admin interface
        "app",                   # Default user app
    ])
    
    # Internal tracking
    _configured: bool = field(default=False, repr=False)
    
    def __post_init__(self):
        """Load from environment if not explicitly configured."""
        if not self._configured:
            self._load_from_env()
    
    def _load_from_env(self) -> None:
        """Load settings from environment variables."""
        # Database URL
        if self.database_url is None:
            self.database_url = os.environ.get("VIDYUT_DATABASE_URL") or os.environ.get("DATABASE_URL")
        
        # Pool sizes
        env_pool_min = os.environ.get("VIDYUT_POOL_MIN_SIZE")
        if env_pool_min:
            try:
                self.pool_min_size = int(env_pool_min)
            except ValueError:
                pass
        
        env_pool_max = os.environ.get("VIDYUT_POOL_SIZE") or os.environ.get("VIDYUT_POOL_MAX_SIZE")
        if env_pool_max:
            try:
                self.pool_max_size = int(env_pool_max)
            except ValueError:
                pass
        
        # Debug mode
        if not self.debug:
            self.debug = _get_bool_env("VIDYUT_DEBUG", False)
        
        # Log level
        env_log_level = os.environ.get("VIDYUT_LOG_LEVEL")
        if env_log_level:
            self.log_level = env_log_level
        
        # v0.3.13: Request logging
        if self.log_requests:
            self.log_requests = not _get_bool_env("VIDYUT_LOG_REQUESTS_DISABLED", False)
        if not self.log_json:
            self.log_json = _get_bool_env("VIDYUT_LOG_JSON", False)
        
        # App metadata (v0.3.4)
        if self.app_title is None:
            self.app_title = os.environ.get("VIDYUT_APP_TITLE")
        if self.app_version is None:
            self.app_version = os.environ.get("VIDYUT_APP_VERSION")
        
        # Migrations directory
        env_migrations = os.environ.get("VIDYUT_MIGRATIONS_DIR")
        if env_migrations:
            self.migrations_dir = env_migrations
        
        # Future: AI features
        if not self.ai_enabled:
            self.ai_enabled = _get_bool_env("VIDYUT_AI_ENABLED", False)
        
        if not self.mcp_enabled:
            self.mcp_enabled = _get_bool_env("VIDYUT_MCP_ENABLED", False)
    
    @property
    def DATABASE_URL(self) -> Optional[str]:
        """Alias for database_url (uppercase convention)."""
        return self.database_url
    
    @property
    def DEBUG(self) -> bool:
        """Alias for debug (uppercase convention)."""
        return self.debug
    
    @property
    def POOL_SIZE(self) -> int:
        """Alias for pool_max_size (uppercase convention)."""
        return self.pool_max_size
    
    @property
    def MIGRATIONS_DIR(self) -> str:
        """Alias for migrations_dir (uppercase convention)."""
        return self.migrations_dir
    
    @property
    def AI_ENABLED(self) -> bool:
        """Alias for ai_enabled (uppercase convention)."""
        return self.ai_enabled
    
    @property
    def MCP_ENABLED(self) -> bool:
        """Alias for mcp_enabled (uppercase convention)."""
        return self.mcp_enabled
    
    @property
    def APPS(self) -> List[str]:
        """Alias for apps (uppercase convention)."""
        return self.apps


# Global settings instance
settings = Settings()


def configure(new_settings: Optional[Settings] = None, **kwargs: Any) -> Settings:
    """
    Configure Vidyut settings.
    
    Can be called with a Settings instance or keyword arguments.
    This overrides environment variables and defaults.
    
    Usage:
        # With Settings instance
        configure(Settings(database_url="...", debug=True))
        
        # With keyword arguments
        configure(database_url="...", debug=True)
    
    Args:
        new_settings: A Settings instance to use
        **kwargs: Individual settings to override
        
    Returns:
        The configured settings instance
    """
    global settings
    
    if new_settings is not None:
        # Use the provided Settings object
        new_settings._configured = True
        settings = new_settings
    elif kwargs:
        # Create new Settings from kwargs (marked as configured to skip env loading)
        # First, get current values as base
        current_values = {
            "database_url": settings.database_url,
            "pool_min_size": settings.pool_min_size,
            "pool_max_size": settings.pool_max_size,
            "debug": settings.debug,
            "log_level": settings.log_level,
            "log_requests": settings.log_requests,
            "log_json": settings.log_json,
            "app_title": settings.app_title,
            "app_version": settings.app_version,
            "migrations_dir": settings.migrations_dir,
            "ai_enabled": settings.ai_enabled,
            "mcp_enabled": settings.mcp_enabled,
            "apps": settings.apps,
        }
        # Override with kwargs
        current_values.update(kwargs)
        current_values["_configured"] = True
        settings = Settings(**current_values)
    
    return settings


def reset_settings() -> Settings:
    """
    Reset settings to defaults (re-reads from environment).
    
    Useful for testing.
    
    Returns:
        The reset settings instance
    """
    global settings
    settings = Settings()
    return settings


__all__ = [
    "Settings",
    "settings",
    "configure",
    "reset_settings",
]
