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


def _get_float_env(key: str, default: float) -> float:
    """Parse float from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _split_list_env(value: str) -> List[str]:
    """Split comma or path-separated environment values into a list."""
    raw_parts = value.replace(os.pathsep, ",").split(",")
    return [part.strip() for part in raw_parts if part.strip()]


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

    # v0.5.45: Media storage
    media_root: str = "media"
    media_url: str = "/media/"
    media_storage: str = "filesystem"
    media_s3_bucket: Optional[str] = None
    media_s3_region: Optional[str] = None
    media_s3_endpoint_url: Optional[str] = None
    media_s3_access_key: Optional[str] = None
    media_s3_secret_key: Optional[str] = None
    media_public_base_url: Optional[str] = None

    # v0.5.45: Email backends
    email_backend: str = "console"
    default_from_email: str = "webmaster@localhost"
    email_host: str = "localhost"
    email_port: int = 25
    email_host_user: Optional[str] = None
    email_host_password: Optional[str] = None
    email_use_tls: bool = False
    email_use_ssl: bool = False
    email_timeout: float = 10.0

    # v0.5.45: i18n and timezone handling
    supported_locales: List[str] = field(default_factory=lambda: ["en"])
    default_locale: str = "en"
    locale_paths: List[str] = field(default_factory=lambda: ["locale"])
    use_tz: bool = True
    time_zone: str = "UTC"

    # v0.5.45: Built-in background tasks
    tasks_enabled: bool = True
    task_poll_interval_seconds: float = 1.0
    task_retry_delay_seconds: float = 5.0
    task_max_attempts: int = 3
    task_stale_lock_timeout_seconds: float = 300.0
    task_lock_recovery_interval_seconds: float = 60.0
    task_concurrency: int = 1
    task_retry_backoff_base: float = 2.0
    task_retry_max_delay_seconds: float = 3600.0
    task_result_ttl_seconds: Optional[float] = None
    task_cleanup_interval_seconds: float = 3600.0
    task_cron_check_interval_seconds: float = 30.0
    
    # v0.4.0: AI features
    ai_enabled: bool = False
    mcp_enabled: bool = False
    # v0.6.0: protocol-level MCP execution boundary
    mcp_path: str = "/mcp"
    mcp_transport_host: str = "127.0.0.1"
    mcp_allowed_hosts: list[str] = field(default_factory=lambda: [
        "127.0.0.1:*", "localhost:*", "[::1]:*", "testserver:*", "testserver",
    ])
    mcp_allowed_origins: list[str] = field(default_factory=lambda: [
        "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
        "http://testserver:*", "http://testserver",
    ])
    mcp_max_request_body_size: int = 1_048_576
    mcp_tool_timeout_seconds: float = 30.0
    mcp_replay_ttl_seconds: float = 300.0
    mcp_require_scoped_tokens: bool = True
    mcp_token_audience: str | None = None
    mcp_approval_secret: str | None = None
    
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
    # These fields remain for v0.6 compatibility. New provider setup should use
    # AI Hub (aksara.ai.hub_settings); removal requires a later deprecation cycle.
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

        env_media_root = os.environ.get("AKSARA_MEDIA_ROOT")
        if env_media_root:
            self.media_root = env_media_root

        env_media_url = os.environ.get("AKSARA_MEDIA_URL")
        if env_media_url:
            self.media_url = env_media_url

        env_media_storage = os.environ.get("AKSARA_MEDIA_STORAGE")
        if env_media_storage:
            self.media_storage = env_media_storage

        if self.media_s3_bucket is None:
            self.media_s3_bucket = os.environ.get("AKSARA_MEDIA_S3_BUCKET")
        if self.media_s3_region is None:
            self.media_s3_region = os.environ.get("AKSARA_MEDIA_S3_REGION")
        if self.media_s3_endpoint_url is None:
            self.media_s3_endpoint_url = os.environ.get("AKSARA_MEDIA_S3_ENDPOINT_URL")
        if self.media_s3_access_key is None:
            self.media_s3_access_key = os.environ.get("AKSARA_MEDIA_S3_ACCESS_KEY")
        if self.media_s3_secret_key is None:
            self.media_s3_secret_key = os.environ.get("AKSARA_MEDIA_S3_SECRET_KEY")
        if self.media_public_base_url is None:
            self.media_public_base_url = os.environ.get("AKSARA_MEDIA_PUBLIC_BASE_URL")

        env_email_backend = os.environ.get("AKSARA_EMAIL_BACKEND")
        if env_email_backend:
            self.email_backend = env_email_backend

        env_default_from_email = os.environ.get("AKSARA_DEFAULT_FROM_EMAIL")
        if env_default_from_email:
            self.default_from_email = env_default_from_email

        env_email_host = os.environ.get("AKSARA_EMAIL_HOST")
        if env_email_host:
            self.email_host = env_email_host

        self.email_port = _get_int_env("AKSARA_EMAIL_PORT", self.email_port)

        if self.email_host_user is None:
            self.email_host_user = os.environ.get("AKSARA_EMAIL_HOST_USER")
        if self.email_host_password is None:
            self.email_host_password = os.environ.get("AKSARA_EMAIL_HOST_PASSWORD")

        self.email_use_tls = _get_bool_env("AKSARA_EMAIL_USE_TLS", self.email_use_tls)
        self.email_use_ssl = _get_bool_env("AKSARA_EMAIL_USE_SSL", self.email_use_ssl)
        self.email_timeout = _get_float_env("AKSARA_EMAIL_TIMEOUT", self.email_timeout)

        env_supported_locales = os.environ.get("AKSARA_SUPPORTED_LOCALES")
        if env_supported_locales:
            self.supported_locales = [
                locale for locale in _split_list_env(env_supported_locales)
            ]

        env_default_locale = os.environ.get("AKSARA_DEFAULT_LOCALE")
        if env_default_locale:
            self.default_locale = env_default_locale

        env_locale_paths = os.environ.get("AKSARA_LOCALE_PATHS")
        if env_locale_paths:
            self.locale_paths = _split_list_env(env_locale_paths)

        self.use_tz = _get_bool_env("AKSARA_USE_TZ", self.use_tz)

        env_time_zone = os.environ.get("AKSARA_TIME_ZONE")
        if env_time_zone:
            self.time_zone = env_time_zone

        self.tasks_enabled = _get_bool_env("AKSARA_TASKS_ENABLED", self.tasks_enabled)
        self.task_poll_interval_seconds = _get_float_env(
            "AKSARA_TASK_POLL_INTERVAL_SECONDS",
            self.task_poll_interval_seconds,
        )
        self.task_retry_delay_seconds = _get_float_env(
            "AKSARA_TASK_RETRY_DELAY_SECONDS",
            self.task_retry_delay_seconds,
        )
        self.task_max_attempts = _get_int_env(
            "AKSARA_TASK_MAX_ATTEMPTS",
            self.task_max_attempts,
        )
        self.task_stale_lock_timeout_seconds = _get_float_env(
            "AKSARA_TASK_STALE_LOCK_TIMEOUT_SECONDS",
            self.task_stale_lock_timeout_seconds,
        )
        self.task_lock_recovery_interval_seconds = _get_float_env(
            "AKSARA_TASK_LOCK_RECOVERY_INTERVAL_SECONDS",
            self.task_lock_recovery_interval_seconds,
        )
        self.task_concurrency = _get_int_env(
            "AKSARA_TASK_CONCURRENCY",
            self.task_concurrency,
        )
        self.task_retry_backoff_base = _get_float_env(
            "AKSARA_TASK_RETRY_BACKOFF_BASE",
            self.task_retry_backoff_base,
        )
        self.task_retry_max_delay_seconds = _get_float_env(
            "AKSARA_TASK_RETRY_MAX_DELAY_SECONDS",
            self.task_retry_max_delay_seconds,
        )
        _env_ttl = os.getenv("AKSARA_TASK_RESULT_TTL_SECONDS")
        if _env_ttl is not None:
            self.task_result_ttl_seconds = float(_env_ttl)
        self.task_cleanup_interval_seconds = _get_float_env(
            "AKSARA_TASK_CLEANUP_INTERVAL_SECONDS",
            self.task_cleanup_interval_seconds,
        )
        self.task_cron_check_interval_seconds = _get_float_env(
            "AKSARA_TASK_CRON_CHECK_INTERVAL_SECONDS",
            self.task_cron_check_interval_seconds,
        )

        # Future: AI features
        if not self.ai_enabled:
            self.ai_enabled = _get_bool_env("AKSARA_AI_ENABLED", False)
        
        if not self.mcp_enabled:
            self.mcp_enabled = _get_bool_env("AKSARA_MCP_ENABLED", False)

        env_mcp_path = os.environ.get("AKSARA_MCP_PATH")
        if env_mcp_path:
            self.mcp_path = env_mcp_path
        env_mcp_host = os.environ.get("AKSARA_MCP_TRANSPORT_HOST")
        if env_mcp_host:
            self.mcp_transport_host = env_mcp_host
        env_mcp_hosts = os.environ.get("AKSARA_MCP_ALLOWED_HOSTS")
        if env_mcp_hosts:
            self.mcp_allowed_hosts = _split_list_env(env_mcp_hosts)
        env_mcp_origins = os.environ.get("AKSARA_MCP_ALLOWED_ORIGINS")
        if env_mcp_origins:
            self.mcp_allowed_origins = _split_list_env(env_mcp_origins)
        self.mcp_max_request_body_size = _get_int_env(
            "AKSARA_MCP_MAX_REQUEST_BODY_SIZE", self.mcp_max_request_body_size
        )
        self.mcp_tool_timeout_seconds = _get_float_env(
            "AKSARA_MCP_TOOL_TIMEOUT_SECONDS", self.mcp_tool_timeout_seconds
        )
        self.mcp_replay_ttl_seconds = _get_float_env(
            "AKSARA_MCP_REPLAY_TTL_SECONDS", self.mcp_replay_ttl_seconds
        )
        self.mcp_require_scoped_tokens = _get_bool_env(
            "AKSARA_MCP_REQUIRE_SCOPED_TOKENS", self.mcp_require_scoped_tokens
        )
        if self.mcp_token_audience is None:
            self.mcp_token_audience = os.environ.get("AKSARA_MCP_TOKEN_AUDIENCE")
        if self.mcp_approval_secret is None:
            self.mcp_approval_secret = os.environ.get("AKSARA_MCP_APPROVAL_SECRET")

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
    def MEDIA_ROOT(self) -> str:
        """Alias for media_root (uppercase convention)."""
        return self.media_root

    @property
    def MEDIA_URL(self) -> str:
        """Alias for media_url (uppercase convention)."""
        return self.media_url

    @property
    def MEDIA_STORAGE(self) -> str:
        """Alias for media_storage (uppercase convention)."""
        return self.media_storage

    @property
    def EMAIL_BACKEND(self) -> str:
        """Alias for email_backend (uppercase convention)."""
        return self.email_backend

    @property
    def DEFAULT_FROM_EMAIL(self) -> str:
        """Alias for default_from_email (uppercase convention)."""
        return self.default_from_email

    @property
    def SUPPORTED_LOCALES(self) -> List[str]:
        """Alias for supported_locales (uppercase convention)."""
        return self.supported_locales

    @property
    def DEFAULT_LOCALE(self) -> str:
        """Alias for default_locale (uppercase convention)."""
        return self.default_locale

    @property
    def LOCALE_PATHS(self) -> List[str]:
        """Alias for locale_paths (uppercase convention)."""
        return self.locale_paths

    @property
    def USE_TZ(self) -> bool:
        """Alias for use_tz (uppercase convention)."""
        return self.use_tz

    @property
    def TIME_ZONE(self) -> str:
        """Alias for time_zone (uppercase convention)."""
        return self.time_zone

    @property
    def TASKS_ENABLED(self) -> bool:
        """Alias for tasks_enabled (uppercase convention)."""
        return self.tasks_enabled

    @property
    def TASK_POLL_INTERVAL_SECONDS(self) -> float:
        """Alias for task_poll_interval_seconds (uppercase convention)."""
        return self.task_poll_interval_seconds

    @property
    def TASK_RETRY_DELAY_SECONDS(self) -> float:
        """Alias for task_retry_delay_seconds (uppercase convention)."""
        return self.task_retry_delay_seconds

    @property
    def TASK_MAX_ATTEMPTS(self) -> int:
        """Alias for task_max_attempts (uppercase convention)."""
        return self.task_max_attempts
    
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


def _replace_settings(source: Settings, *, configured: Optional[bool] = None) -> Settings:
    """Copy settings values into the global instance without rebinding it."""
    values = dict(source.__dict__)
    if configured is not None:
        values["_configured"] = configured

    settings.__dict__.clear()
    settings.__dict__.update(values)

    try:
        from aksara.storage import clear_storage_cache

        clear_storage_cache()
    except Exception:
        pass

    try:
        from aksara.i18n import clear_i18n_cache

        clear_i18n_cache()
    except Exception:
        pass

    return settings


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
        return _replace_settings(new_settings, configured=True)
    elif kwargs:
        # Create new Settings from kwargs (marked as configured to skip env loading)
        current_values = {
            key: value
            for key, value in settings.__dict__.items()
            if not key.startswith("_")
        }
        # Override with kwargs
        current_values.update(kwargs)
        current_values["_configured"] = True
        return _replace_settings(Settings(**current_values))

    return settings


def reset_settings() -> Settings:
    """
    Reset settings to defaults (re-reads from environment).
    
    Useful for testing.
    
    Returns:
        The reset settings instance
    """
    return _replace_settings(Settings())


__all__ = [
    "Settings",
    "settings",
    "configure",
    "reset_settings",
]
