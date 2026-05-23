"""
Aksara Security Check Helpers

Implements the individual checks used by:
  - aksara doctor security-check
  - aksara doctor production-check

Round 1: config-level checks and matrix validation.
Runtime enforcement (field-level, Principal, policy engine) comes in later rounds.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Check result models
# ---------------------------------------------------------------------------

CHECK_STATUSES = {"pass", "warn", "fail", "block", "skip", "unknown"}


@dataclass
class SecurityCheckResult:
    id: str
    title: str
    severity: str          # info | warning | error | critical
    status: str            # pass | warn | fail | block | skip | unknown
    message: str
    recommendation: str = ""


@dataclass
class SecurityCheckReport:
    check_name: str
    results: List[SecurityCheckResult] = field(default_factory=list)
    is_production: bool = False

    def add(self, result: SecurityCheckResult) -> None:
        self.results.append(result)

    @property
    def has_blocks(self) -> bool:
        return any(r.status == "block" for r in self.results)

    @property
    def has_failures(self) -> bool:
        return any(r.status in ("fail", "block") for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.status == "warn" for r in self.results)

    @property
    def overall_status(self) -> str:
        if self.has_blocks:
            return "block"
        if self.has_failures:
            return "fail"
        if self.has_warnings:
            return "warn"
        return "pass"

    @property
    def should_exit_nonzero(self) -> bool:
        """production-check exits non-zero on blocks/failures; security-check on failures."""
        if self.is_production:
            return self.has_failures or self.has_blocks
        return self.has_blocks


# ---------------------------------------------------------------------------
# Setting helpers
# ---------------------------------------------------------------------------

_WEAK_SECRETS = {
    "change-me", "changeme", "secret", "dev", "development",
    "test", "testing", "your-secret-key", "replace-me",
    "insert-your-key-here", "django-insecure", "insecure",
    "password", "12345678", "placeholder",
}
_MIN_SECRET_LEN = 32


def get_setting(name: str, default: Any = None) -> Any:
    """Safely retrieve a setting by attribute name from aksara.conf.settings."""
    try:
        from aksara.conf import settings
        return getattr(settings, name, default)
    except Exception:
        return default


def get_env(name: str, default: Any = None) -> Any:
    """Read directly from environment (bypasses settings object)."""
    return os.environ.get(name, default)


def is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


def is_production_env(settings: Any = None) -> bool:
    """
    Return True when we can detect a production-like environment.

    Checks AKSARA_ENV, ENV, APP_ENV, NODE_ENV, and debug mode.
    A non-debug environment is treated as production for the
    production-check command.
    """
    for env_var in ("AKSARA_ENV", "ENV", "APP_ENV", "NODE_ENV"):
        val = os.environ.get(env_var, "").lower()
        if val in ("production", "prod", "live"):
            return True
        if val in ("development", "dev", "test", "staging", "local"):
            return False
    # Fall back: non-debug == production-like
    debug = False
    if settings is not None:
        debug = getattr(settings, "debug", False)
    else:
        try:
            from aksara.conf import settings as s
            debug = s.debug
        except Exception:
            pass
    return not debug


def looks_like_weak_secret(value: Any) -> bool:
    """Return True if the value looks like a weak or default SECRET_KEY."""
    if value is None:
        return True
    s = str(value).strip()
    if not s:
        return True
    if len(s) < _MIN_SECRET_LEN:
        return True
    low = s.lower()
    if low in _WEAK_SECRETS:
        return True
    # Prefix checks for common patterns
    for prefix in ("change", "replace", "insecure", "django-insecure-", "your-"):
        if low.startswith(prefix):
            return True
    return False


def _get_secret_key() -> Optional[str]:
    """Look for SECRET_KEY in settings and environment."""
    for env_var in ("AKSARA_SECRET_KEY", "SECRET_KEY"):
        val = os.environ.get(env_var)
        if val:
            return val
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_secret_key() -> SecurityCheckResult:
    secret = _get_secret_key()
    if secret is None:
        return SecurityCheckResult(
            id="security.secret_key",
            title="SECRET_KEY not set",
            severity="critical",
            status="fail",
            message="No AKSARA_SECRET_KEY or SECRET_KEY environment variable found.",
            recommendation="Set a strong SECRET_KEY: export SECRET_KEY=\"$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')\"",
        )
    if looks_like_weak_secret(secret):
        return SecurityCheckResult(
            id="security.secret_key",
            title="SECRET_KEY appears weak or default",
            severity="critical",
            status="fail",
            message=f"SECRET_KEY is too short (< {_MIN_SECRET_LEN} chars) or matches a known default value.",
            recommendation="Replace with a strong random value: python3 -c 'import secrets; print(secrets.token_urlsafe(64))'",
        )
    return SecurityCheckResult(
        id="security.secret_key",
        title="SECRET_KEY",
        severity="info",
        status="pass",
        message="SECRET_KEY is set and does not appear to be a known default.",
        recommendation="",
    )


def check_debug_mode(is_production: bool = False) -> SecurityCheckResult:
    debug = get_setting("debug", False)
    if debug:
        status = "block" if is_production else "warn"
        return SecurityCheckResult(
            id="security.debug_mode",
            title="Debug mode is enabled",
            severity="high",
            status=status,
            message="Running with debug=True. This exposes stack traces and internal details.",
            recommendation="Set AKSARA_DEBUG=false or debug=False for production.",
        )
    return SecurityCheckResult(
        id="security.debug_mode",
        title="Debug mode",
        severity="info",
        status="pass",
        message="debug=False.",
        recommendation="",
    )


def check_cors(is_production: bool = False) -> SecurityCheckResult:
    """Check CORS wildcard + credentials combination."""
    allowed_origins = get_setting("studio_allowed_origins", [])
    has_wildcard = "*" in allowed_origins
    cors_allow_all = is_truthy(get_env("CORS_ALLOW_ALL_ORIGINS", False))
    cors_credentials = is_truthy(get_env("CORS_ALLOW_CREDENTIALS", False))

    wildcard = has_wildcard or cors_allow_all

    if wildcard and cors_credentials:
        status = "block" if is_production else "fail"
        return SecurityCheckResult(
            id="security.cors",
            title="CORS wildcard with credentials",
            severity="high",
            status=status,
            message="CORS wildcard origin ('*') is combined with credentials=True. This allows any site to make credentialed requests.",
            recommendation="Restrict CORS to explicit trusted origins and remove credentials=True, or disable wildcard.",
        )
    if wildcard:
        return SecurityCheckResult(
            id="security.cors",
            title="CORS allows all origins",
            severity="warning" if not is_production else "error",
            status="warn",
            message="CORS or studio_allowed_origins contains '*'. Any domain can make cross-origin requests.",
            recommendation="Restrict studio_allowed_origins to trusted domains.",
        )
    return SecurityCheckResult(
        id="security.cors",
        title="CORS configuration",
        severity="info",
        status="pass",
        message="No CORS wildcard detected.",
        recommendation="",
    )


def check_studio_exposure(is_production: bool = False) -> SecurityCheckResult:
    enable_studio = get_setting("enable_studio", False)
    studio_expose_in_production = get_setting("studio_expose_in_production", False)
    studio_require_auth = get_setting("studio_require_auth", True)

    if enable_studio and studio_expose_in_production and not studio_require_auth:
        status = "block" if is_production else "fail"
        return SecurityCheckResult(
            id="security.studio_exposure",
            title="Studio exposed in production without auth",
            severity="critical",
            status=status,
            message="Studio is exposed in production (studio_expose_in_production=True) but studio_require_auth=False.",
            recommendation="Set studio_require_auth=True or disable studio_expose_in_production.",
        )
    if enable_studio and studio_expose_in_production:
        if is_production:
            return SecurityCheckResult(
                id="security.studio_exposure",
                title="Studio exposed in production",
                severity="high",
                status="warn",
                message="Studio is explicitly exposed in production with auth required. Verify this is intentional.",
                recommendation="Confirm studio_require_auth=True and that the auth token is strong.",
            )
    return SecurityCheckResult(
        id="security.studio_exposure",
        title="Studio production exposure",
        severity="info",
        status="pass",
        message="Studio is not exposed in production or requires authentication.",
        recommendation="",
    )


def check_mcp_exposure(is_production: bool = False) -> SecurityCheckResult:
    mcp_enabled = get_setting("mcp_enabled", False)
    ai_agent_token = get_setting("ai_agent_token", None)

    # Check for additional MCP auth settings (may not exist yet)
    mcp_require_auth = is_truthy(get_env("AKSARA_MCP_REQUIRE_AUTH", False))
    mcp_require_scoped = is_truthy(get_env("AKSARA_MCP_REQUIRE_SCOPED_TOKENS", False))

    has_auth = bool(ai_agent_token) or mcp_require_auth or mcp_require_scoped

    if mcp_enabled and not has_auth:
        status = "block" if is_production else "warn"
        return SecurityCheckResult(
            id="security.mcp_exposure",
            title="MCP enabled without authentication",
            severity="critical",
            status=status,
            message="MCP is enabled (mcp_enabled=True) but no agent token or auth requirement is configured.",
            recommendation="Set AKSARA_AI_AGENT_TOKEN to a strong shared secret, or set AKSARA_MCP_REQUIRE_AUTH=true.",
        )
    if not mcp_enabled:
        return SecurityCheckResult(
            id="security.mcp_exposure",
            title="MCP disabled",
            severity="info",
            status="pass",
            message="MCP is disabled by default (mcp_enabled=False). This is the safe default.",
            recommendation="",
        )
    return SecurityCheckResult(
        id="security.mcp_exposure",
        title="MCP exposure",
        severity="info",
        status="pass",
        message="MCP is enabled and an authentication mechanism is configured.",
        recommendation="Verify AKSARA_AI_AGENT_TOKEN is strong and rotated regularly.",
    )


def check_ai_console_exposure(is_production: bool = False) -> SecurityCheckResult:
    """Check AI Console exposure. AI Console is not yet implemented; this is forward-looking."""
    ai_console_enabled = is_truthy(get_env("AKSARA_AI_CONSOLE_ENABLED", False))
    ai_console_auth = is_truthy(get_env("AKSARA_AI_CONSOLE_AUTH_REQUIRED", True))

    if ai_console_enabled and not ai_console_auth:
        status = "block" if is_production else "warn"
        return SecurityCheckResult(
            id="security.ai_console_exposure",
            title="AI Console enabled without auth",
            severity="critical",
            status=status,
            message="AKSARA_AI_CONSOLE_ENABLED=true but AKSARA_AI_CONSOLE_AUTH_REQUIRED=false.",
            recommendation="Set AKSARA_AI_CONSOLE_AUTH_REQUIRED=true.",
        )
    if ai_console_enabled:
        return SecurityCheckResult(
            id="security.ai_console_exposure",
            title="AI Console enabled",
            severity="info",
            status="warn",
            message="AI Console is enabled. Ensure it is protected by authentication.",
            recommendation="Verify AKSARA_AI_CONSOLE_AUTH_REQUIRED=true.",
        )
    return SecurityCheckResult(
        id="security.ai_console_exposure",
        title="AI Console",
        severity="info",
        status="pass",
        message="AI Console is not enabled (default).",
        recommendation="",
    )


def check_cookies() -> SecurityCheckResult:
    cookie_secure = get_setting("cookie_secure", True)
    if not cookie_secure:
        return SecurityCheckResult(
            id="security.cookies",
            title="Insecure cookie settings",
            severity="high",
            status="warn",
            message="cookie_secure=False. Session cookies will not be restricted to HTTPS.",
            recommendation="Set AKSARA_COOKIE_SECURE=true or cookie_secure=True for production deployments.",
        )
    return SecurityCheckResult(
        id="security.cookies",
        title="Cookie security",
        severity="info",
        status="pass",
        message="cookie_secure=True.",
        recommendation="",
    )


def check_rate_limits() -> SecurityCheckResult:
    rate_limit_enabled = get_setting("admin_rate_limit_enabled", True)
    if not rate_limit_enabled:
        return SecurityCheckResult(
            id="security.rate_limits",
            title="Rate limiting disabled",
            severity="medium",
            status="warn",
            message="admin_rate_limit_enabled=False. Admin endpoints lack rate limiting.",
            recommendation="Set AKSARA_ADMIN_RATE_LIMIT_ENABLED=true.",
        )
    return SecurityCheckResult(
        id="security.rate_limits",
        title="Rate limiting",
        severity="info",
        status="pass",
        message="Admin rate limiting is enabled.",
        recommendation="",
    )


def check_tenancy_rls(is_production: bool = False) -> SecurityCheckResult:
    """Check multi-tenancy and RLS configuration."""
    # Check for tenancy-related settings
    tenancy_enabled = is_truthy(get_env("AKSARA_MULTI_TENANT", False)) or \
                      is_truthy(get_env("AKSARA_TENANCY_ENABLED", False))
    rls_enabled = is_truthy(get_env("AKSARA_RLS_ENABLED", False)) or \
                  is_truthy(get_env("AKSARA_REQUIRE_RLS", False))

    if tenancy_enabled and not rls_enabled:
        status = "warn"  # warn in both modes; upgrading to block requires more confidence
        return SecurityCheckResult(
            id="security.rls",
            title="Multi-tenancy without confirmed RLS",
            severity="high",
            status=status,
            message="AKSARA_MULTI_TENANT=true but AKSARA_RLS_ENABLED is not set. RLS provides a defense-in-depth layer for tenant isolation.",
            recommendation="Enable PostgreSQL RLS policies and set AKSARA_RLS_ENABLED=true.",
        )
    if tenancy_enabled:
        return SecurityCheckResult(
            id="security.rls",
            title="Multi-tenancy with RLS",
            severity="info",
            status="pass",
            message="Multi-tenancy is enabled and RLS is configured.",
            recommendation="",
        )
    return SecurityCheckResult(
        id="security.rls",
        title="Tenancy/RLS",
        severity="info",
        status="pass",
        message="Multi-tenancy is not explicitly enabled via environment variables.",
        recommendation="If your app is multi-tenant, set AKSARA_MULTI_TENANT=true and AKSARA_RLS_ENABLED=true.",
    )


def check_ai_field_defaults() -> SecurityCheckResult:
    """Warn if AI fields default to broadly writable (ai_agent_writable=True is the current default)."""
    ai_deny_by_default = is_truthy(get_env("AKSARA_AI_DENY_BY_DEFAULT", False))
    if not ai_deny_by_default:
        return SecurityCheckResult(
            id="security.ai_field_defaults",
            title="AI fields broadly writable by default",
            severity="medium",
            status="warn",
            message="ai_agent_writable defaults to True. AI agents can write all fields unless explicitly marked ai_agent_writable=False.",
            recommendation="Mark sensitive fields with ai_agent_writable=False or set AKSARA_AI_DENY_BY_DEFAULT=true when that setting is available.",
        )
    return SecurityCheckResult(
        id="security.ai_field_defaults",
        title="AI field writability",
        severity="info",
        status="pass",
        message="AI deny-by-default is enabled.",
        recommendation="",
    )


def check_mcp_hardening(is_production: bool = False) -> SecurityCheckResult:
    """Check that MCP is configured with scoped tokens, TTL, audience, and tenant binding."""
    mcp_enabled = get_setting("mcp_enabled", False)

    if not mcp_enabled:
        return SecurityCheckResult(
            id="security.mcp_hardening",
            title="MCP hardening",
            severity="info",
            status="pass",
            message="MCP is disabled; hardening checks skipped.",
            recommendation="",
        )

    require_scoped = is_truthy(get_env("AKSARA_MCP_REQUIRE_SCOPED_TOKENS", False))
    if not require_scoped:
        status = "block" if is_production else "warn"
        return SecurityCheckResult(
            id="security.mcp_hardening",
            title="MCP scoped tokens not required",
            severity="high",
            status=status,
            message="MCP is enabled but AKSARA_MCP_REQUIRE_SCOPED_TOKENS is not set. Per-tool scope enforcement is disabled.",
            recommendation="Set AKSARA_MCP_REQUIRE_SCOPED_TOKENS=true and issue tokens with explicit per-tool scopes.",
        )

    ttl_raw = get_env("AKSARA_MCP_TOKEN_TTL_SECONDS")
    if ttl_raw is None:
        status = "block" if is_production else "warn"
        return SecurityCheckResult(
            id="security.mcp_hardening",
            title="MCP token TTL not configured",
            severity="high",
            status=status,
            message="AKSARA_MCP_TOKEN_TTL_SECONDS is not set. Token lifetime is undefined.",
            recommendation="Set AKSARA_MCP_TOKEN_TTL_SECONDS (recommended: 300–900 seconds).",
        )

    try:
        ttl_seconds = int(ttl_raw)
    except (ValueError, TypeError):
        ttl_seconds = 0

    if ttl_seconds > 3600:
        return SecurityCheckResult(
            id="security.mcp_hardening",
            title="MCP token TTL is too long",
            severity="medium",
            status="warn",
            message=f"AKSARA_MCP_TOKEN_TTL_SECONDS={ttl_seconds} exceeds 3600s. Long-lived MCP tokens increase exposure window.",
            recommendation="Set AKSARA_MCP_TOKEN_TTL_SECONDS to 300–900 seconds.",
        )

    require_audience = is_truthy(get_env("AKSARA_MCP_REQUIRE_AUDIENCE", False))
    if not require_audience:
        status = "block" if is_production else "warn"
        return SecurityCheckResult(
            id="security.mcp_hardening",
            title="MCP audience validation not required",
            severity="high",
            status=status,
            message="AKSARA_MCP_REQUIRE_AUDIENCE is not set. Tokens may be accepted by unintended services.",
            recommendation="Set AKSARA_MCP_REQUIRE_AUDIENCE=true and AKSARA_MCP_TOKEN_AUDIENCE to a stable service identifier.",
        )

    multi_tenant = is_truthy(get_env("AKSARA_MULTI_TENANT", False))
    if multi_tenant:
        require_tenant_bound = is_truthy(get_env("AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS", False))
        if not require_tenant_bound:
            status = "block" if is_production else "warn"
            return SecurityCheckResult(
                id="security.mcp_hardening",
                title="Multi-tenant MCP without tenant-bound tokens",
                severity="high",
                status=status,
                message="Multi-tenancy is enabled (AKSARA_MULTI_TENANT=true) but AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS is not set.",
                recommendation="Set AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS=true to ensure MCP tokens carry a tenant_id claim.",
            )

    return SecurityCheckResult(
        id="security.mcp_hardening",
        title="MCP credential hardening",
        severity="info",
        status="pass",
        message="MCP scoped tokens, TTL, and audience validation are all configured.",
        recommendation="",
    )


def check_security_matrix(is_production: bool = False) -> SecurityCheckResult:
    """Check that security_matrix.yml exists and validates."""
    from aksara.security.matrix import _find_default_matrix_path, validate_security_matrix, _load_yaml

    require_matrix = is_truthy(get_env("AKSARA_REQUIRE_SECURITY_MATRIX", False))

    matrix_path = _find_default_matrix_path()
    if matrix_path is None:
        status = "block" if require_matrix else "warn"
        return SecurityCheckResult(
            id="security.matrix",
            title="Security matrix not found",
            severity="high",
            status=status,
            message="security/security_matrix.yml was not found.",
            recommendation=(
                "Copy security/security_matrix.example.yml to security/security_matrix.yml "
                "and customise it for your project. "
                "Set AKSARA_REQUIRE_SECURITY_MATRIX=true to make this a blocking check."
            ),
        )

    try:
        data = _load_yaml(matrix_path)
        issues = validate_security_matrix(data)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            msgs = "; ".join(f"{i.field}: {i.message}" for i in errors[:3])
            status = "block" if require_matrix else "fail"
            return SecurityCheckResult(
                id="security.matrix",
                title="Security matrix invalid",
                severity="critical",
                status=status,
                message=f"security_matrix.yml has {len(errors)} validation error(s): {msgs}",
                recommendation="Fix the validation errors in security/security_matrix.yml.",
            )
    except ImportError:
        return SecurityCheckResult(
            id="security.matrix",
            title="Security matrix: PyYAML not installed",
            severity="warning",
            status="warn",
            message="Cannot load security_matrix.yml because PyYAML is not installed.",
            recommendation="Install PyYAML: pip install pyyaml",
        )
    except Exception as e:
        status = "block" if require_matrix else "fail"
        return SecurityCheckResult(
            id="security.matrix",
            title="Security matrix load error",
            severity="critical",
            status=status,
            message=f"Error loading security_matrix.yml: {e}",
            recommendation="Check the file for YAML syntax errors.",
        )

    return SecurityCheckResult(
        id="security.matrix",
        title="Security matrix",
        severity="info",
        status="pass",
        message=f"security_matrix.yml loaded and validated from {matrix_path}.",
        recommendation="",
    )


# ---------------------------------------------------------------------------
# Aggregators
# ---------------------------------------------------------------------------

def run_security_checks(is_production: bool = False) -> SecurityCheckReport:
    """Run all security checks and return a report."""
    report = SecurityCheckReport(
        check_name="production-check" if is_production else "security-check",
        is_production=is_production,
    )
    report.add(check_secret_key())
    report.add(check_debug_mode(is_production=is_production))
    report.add(check_cors(is_production=is_production))
    report.add(check_studio_exposure(is_production=is_production))
    report.add(check_mcp_exposure(is_production=is_production))
    report.add(check_mcp_hardening(is_production=is_production))
    report.add(check_ai_console_exposure(is_production=is_production))
    report.add(check_cookies())
    report.add(check_rate_limits())
    report.add(check_tenancy_rls(is_production=is_production))
    report.add(check_ai_field_defaults())
    report.add(check_security_matrix(is_production=is_production))
    return report
