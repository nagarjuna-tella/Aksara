"""
Aksara Configuration System

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
    Aksara configuration settings.
    
    Settings can be configured via:
    1. Internal defaults (lowest priority)
    2. Environment variables (AKSARA_*)
    3. Explicit configure() call (highest priority)
    
    Usage:
        from aksara.conf import settings
        
        # Access settings
        db_url = settings.DATABASE_URL
        
        # Or configure explicitly
        from aksara.conf import configure, Settings
        configure(Settings(database_url="postgresql://...", debug=True))
    """
    
    # Database
    database_url: Optional[str] = None
    pool_min_size: int = 5
    pool_max_size: int = 20
    
    # Debug & Logging
    debug: bool = False
    log_level: str = "INFO"
    cookie_secure: bool = True
    admin_csrf_enabled: bool = True
    admin_rate_limit_enabled: bool = True
    admin_rate_limit_requests: int = 20
    admin_rate_limit_window_seconds: int = 60
    
    # v0.3.13: Request logging
    log_requests: bool = True
    log_json: bool = False
    
    # App metadata (v0.3.4)
    app_title: Optional[str] = None
    app_version: Optional[str] = None
    
    # Migrations
    migrations_dir: str = "migrations"
    
    # v0.4.0: AI features
    ai_enabled: bool = False
    mcp_enabled: bool = False
    
    # v0.4.1: AI Debug Assistant
    ai_debug_enabled: bool = True  # Enabled by default in debug mode
    ai_debug_advisor_class: Optional[str] = None  # Custom advisor class path
    ai_agent_token: Optional[str] = None  # Shared token for server-side AI agent auth
    patch_sandbox: str = "subprocess"  # "subprocess" or "in_process" (execution strategy)
    
    # v0.5.0: Studio settings
    enable_studio: bool = False  # Disable Studio endpoints by default
    studio_secret_token: Optional[str] = None  # Required when enable_studio is True
    studio_expose_in_production: bool = False  # Require explicit flag in production
    studio_require_auth: bool = True  # Require auth for Studio endpoints by default
    studio_auth_token: Optional[str] = None  # Shared bearer token for Studio access
    studio_allowed_origins: List[str] = field(default_factory=lambda: [
        "https://studio.aksara.dev",
        "http://localhost:3000",  # Local Studio dev
    ])
    
    # v0.5.3: Studio UI settings
    studio_ui_enabled: bool = True  # Enable embedded Studio UI
    studio_ui_auto_open: bool = False  # Auto-open UI on server start (future)
    studio_ui_title: str = "Aksara Studio"  # Customizable UI title
    
    # v0.5.10: DB Query Tracing (Query Inspector & ORM Profiler)
    db_trace_enabled: bool = False  # Enable per-request query tracing
    db_trace_slow_threshold_ms: float = 100.0  # Threshold for "slow" query (ms)
    db_trace_max_queries: int = 500  # Max queries to capture per request
    
    # v0.5.11: AI Profiles & Provider Contracts
    # DEPRECATED(v0.5.28): Use AI Hub 2.0 (aksara.ai.hub_settings) instead.
    # These fields are kept for backward compatibility but will be removed in v0.6.
    ai_profiles_enabled: bool = True  # Enable AI profile discovery
    ai_default_provider: Optional[str] = None  # Default AI provider name
    ai_providers: Optional[List[dict]] = None  # List of AiProviderProfile dicts (no secrets)
    ai_secret_hints: Optional[List[dict]] = None  # List of AiProviderSecretHint dicts
    
    # v0.5.22: Semantic Search & AI Index
    # NOTE(v0.5.28): embedding_provider/embedding_model now fall back to
    # AI Hub defaults when set to "local".  See aksara.search.embeddings.
    semantic_search_enabled: bool = True  # Enable semantic search
    embedding_provider: str = "local"  # Embedding backend (local, openai, azure, anthropic)
    embedding_model: str = "local_tfidf"  # Model/strategy name
    embedding_dimensions: int = 512  # Max embedding dimensions
    search_index_backend: str = "memory"  # Index storage (memory only for now)
    
    # v0.3.6: Multi-app support
    apps: List[str] = field(default_factory=lambda: ["app"])
    
    # v0.3.20: Django-style INSTALLED_APPS
    # These apps are auto-loaded on startup
    installed_apps: List[str] = field(default_factory=lambda: [
        "aksara.contrib.auth",   # User authentication (creates aksara_users table)
        "aksara.contrib.admin",  # Admin interface
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
            self.database_url = os.environ.get("AKSARA_DATABASE_URL") or os.environ.get("DATABASE_URL")
        
        # Pool sizes
        env_pool_min = os.environ.get("AKSARA_POOL_MIN_SIZE")
        if env_pool_min:
            try:
                self.pool_min_size = int(env_pool_min)
            except ValueError:
                pass
        
        env_pool_max = os.environ.get("AKSARA_POOL_SIZE") or os.environ.get("AKSARA_POOL_MAX_SIZE")
        if env_pool_max:
            try:
                self.pool_max_size = int(env_pool_max)
            except ValueError:
                pass
        
        # Debug mode
        if not self.debug:
            self.debug = _get_bool_env("AKSARA_DEBUG", False)
        
        # Log level
        env_log_level = os.environ.get("AKSARA_LOG_LEVEL")
        if env_log_level:
            self.log_level = env_log_level

        if self.cookie_secure:
            self.cookie_secure = _get_bool_env("AKSARA_COOKIE_SECURE", True)
        if self.admin_csrf_enabled:
            self.admin_csrf_enabled = _get_bool_env("AKSARA_ADMIN_CSRF_ENABLED", True)
        if self.admin_rate_limit_enabled:
            self.admin_rate_limit_enabled = _get_bool_env("AKSARA_ADMIN_RATE_LIMIT_ENABLED", True)
        self.admin_rate_limit_requests = _get_int_env(
            "AKSARA_ADMIN_RATE_LIMIT_REQUESTS",
            self.admin_rate_limit_requests,
        )
        self.admin_rate_limit_window_seconds = _get_int_env(
            "AKSARA_ADMIN_RATE_LIMIT_WINDOW_SECONDS",
            self.admin_rate_limit_window_seconds,
        )
        
        # v0.3.13: Request logging
        if self.log_requests:
            self.log_requests = not _get_bool_env("AKSARA_LOG_REQUESTS_DISABLED", False)
        if not self.log_json:
            self.log_json = _get_bool_env("AKSARA_LOG_JSON", False)
        
        # App metadata (v0.3.4)
        if self.app_title is None:
            self.app_title = os.environ.get("AKSARA_APP_TITLE")
        if self.app_version is None:
            self.app_version = os.environ.get("AKSARA_APP_VERSION")
        
        # Migrations directory
        env_migrations = os.environ.get("AKSARA_MIGRATIONS_DIR")
        if env_migrations:
            self.migrations_dir = env_migrations
        
        # Future: AI features
        if not self.ai_enabled:
            self.ai_enabled = _get_bool_env("AKSARA_AI_ENABLED", False)
        
        if not self.mcp_enabled:
            self.mcp_enabled = _get_bool_env("AKSARA_MCP_ENABLED", False)

        if self.ai_agent_token is None:
            self.ai_agent_token = os.environ.get("AKSARA_AI_AGENT_TOKEN")
        
        env_patch_sandbox = os.environ.get("AKSARA_PATCH_SANDBOX")
        if env_patch_sandbox:
            self.patch_sandbox = env_patch_sandbox

        # v0.5.0: Studio settings
        if not self.enable_studio:
            self.enable_studio = _get_bool_env("AKSARA_ENABLE_STUDIO", False)
        if self.enable_studio:
            self.enable_studio = not _get_bool_env("AKSARA_STUDIO_DISABLED", False)
            
        if self.studio_secret_token is None:
            self.studio_secret_token = os.environ.get("AKSARA_STUDIO_SECRET_TOKEN")
            
        if self.enable_studio and not self.studio_secret_token:
            from aksara.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured("STUDIO_SECRET_TOKEN must be set when ENABLE_STUDIO=True")
            
        if not self.studio_expose_in_production:
            self.studio_expose_in_production = _get_bool_env("AKSARA_STUDIO_EXPOSE_IN_PRODUCTION", False)
        if self.studio_require_auth:
            self.studio_require_auth = _get_bool_env("AKSARA_STUDIO_REQUIRE_AUTH", True)
        if self.studio_auth_token is None:
            self.studio_auth_token = os.environ.get("AKSARA_STUDIO_AUTH_TOKEN")
        
        # Studio allowed origins from env (comma-separated)
        env_origins = os.environ.get("AKSARA_STUDIO_ALLOWED_ORIGINS")
        if env_origins:
            self.studio_allowed_origins = [o.strip() for o in env_origins.split(",")]
        
        # v0.5.10: DB Query Tracing
        if not self.db_trace_enabled:
            self.db_trace_enabled = _get_bool_env("AKSARA_DB_TRACE_ENABLED", False)
        
        env_slow_threshold = os.environ.get("AKSARA_DB_TRACE_SLOW_THRESHOLD_MS")
        if env_slow_threshold:
            try:
                self.db_trace_slow_threshold_ms = float(env_slow_threshold)
            except ValueError:
                pass
        
        env_max_queries = os.environ.get("AKSARA_DB_TRACE_MAX_QUERIES")
        if env_max_queries:
            try:
                self.db_trace_max_queries = int(env_max_queries)
            except ValueError:
                pass
        
        # v0.5.11: AI Profiles settings
        if self.ai_profiles_enabled:
            self.ai_profiles_enabled = not _get_bool_env("AKSARA_AI_PROFILES_DISABLED", False)
        
        env_default_provider = os.environ.get("AKSARA_AI_DEFAULT_PROVIDER")
        if env_default_provider:
            self.ai_default_provider = env_default_provider

        # v0.5.25: Populate ai_default_provider from unified provider if not set
        if not self.ai_default_provider:
            try:
                from aksara.ai.providers_unified import get_active_provider
                active = get_active_provider()
                if active and active.is_configured():
                    self.ai_default_provider = active.provider
            except Exception:
                pass  # Unified provider module may not be available
    
    @property
    def DATABASE_URL(self) -> Optional[str]:
        """Alias for database_url (uppercase convention)."""
        return self.database_url
    
    @property
    def DEBUG(self) -> bool:
        """Alias for debug (uppercase convention)."""
        return self.debug

    @property
    def COOKIE_SECURE(self) -> bool:
        """Alias for cookie_secure (uppercase convention)."""
        return self.cookie_secure

    @property
    def ADMIN_CSRF_ENABLED(self) -> bool:
        """Alias for admin_csrf_enabled (uppercase convention)."""
        return self.admin_csrf_enabled

    @property
    def ADMIN_RATE_LIMIT_ENABLED(self) -> bool:
        """Alias for admin_rate_limit_enabled (uppercase convention)."""
        return self.admin_rate_limit_enabled

    @property
    def ADMIN_RATE_LIMIT_REQUESTS(self) -> int:
        """Alias for admin_rate_limit_requests (uppercase convention)."""
        return self.admin_rate_limit_requests

    @property
    def ADMIN_RATE_LIMIT_WINDOW_SECONDS(self) -> int:
        """Alias for admin_rate_limit_window_seconds (uppercase convention)."""
        return self.admin_rate_limit_window_seconds
    
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
    def STUDIO_ENABLED(self) -> bool:
        """Alias for enable_studio (uppercase convention)."""
        return self.enable_studio

    @property
    def STUDIO_REQUIRE_AUTH(self) -> bool:
        """Alias for studio_require_auth (uppercase convention)."""
        return self.studio_require_auth
    
    @property
    def APPS(self) -> List[str]:
        """Alias for apps (uppercase convention)."""
        return self.apps
    
    @property
    def DB_TRACE_ENABLED(self) -> bool:
        """Alias for db_trace_enabled (uppercase convention)."""
        return self.db_trace_enabled
    
    @property
    def DB_TRACE_SLOW_THRESHOLD_MS(self) -> float:
        """Alias for db_trace_slow_threshold_ms (uppercase convention)."""
        return self.db_trace_slow_threshold_ms
    
    @property
    def DB_TRACE_MAX_QUERIES(self) -> int:
        """Alias for db_trace_max_queries (uppercase convention)."""
        return self.db_trace_max_queries
    
    @property
    def AI_PROFILES_ENABLED(self) -> bool:
        """Alias for ai_profiles_enabled (uppercase convention)."""
        return self.ai_profiles_enabled
    
    @property
    def AI_DEFAULT_PROVIDER(self) -> Optional[str]:
        """Alias for ai_default_provider (uppercase convention)."""
        return self.ai_default_provider

    @property
    def AI_AGENT_TOKEN(self) -> Optional[str]:
        """Alias for ai_agent_token (uppercase convention)."""
        return self.ai_agent_token


# Auto-load .env before creating the global singleton so AKSARA_* env vars
# are available when Settings.__post_init__ runs, regardless of import order.
# Search from CWD upward so that project .env files are found when uvicorn
# starts from the project root.
try:
    from dotenv import load_dotenv as _load_dotenv, find_dotenv as _find_dotenv
    _dotenv_path = _find_dotenv(usecwd=True)
    if _dotenv_path:
        _load_dotenv(_dotenv_path)
    else:
        _load_dotenv()  # fallback: default search
except ImportError:
    pass  # python-dotenv is optional; env vars may be set by other means

# Global settings instance
settings = Settings()


def configure(new_settings: Optional[Settings] = None, **kwargs: Any) -> Settings:
    """
    Configure Aksara settings.
    
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
