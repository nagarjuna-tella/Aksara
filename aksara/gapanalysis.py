"""
Aksara Gap Analysis Engine — v0.5.26

Performs a structural pre-flight scan of an Aksara project and surfaces
actionable issues across eight check categories:

    imports       – required Python packages available in the environment
    db            – database URL, connection settings and pool config
    migrations    – pending / conflict / unapplied migration state
    routers       – ViewSet registration and route reachability
    providers     – AI provider profiles and required secrets
    studio        – Studio panel reachability and configuration
    environment   – required environment variables present
    ai_pipeline   – AI pipeline chain (models → tools → agents)

The engine is intentionally complementary to ``aksara.diagnostics``
(which checks live connectivity).  Gap analysis is a *static* scan that
can run offline without a live database connection.

Usage::

    from aksara.gapanalysis import run_gap_analysis

    report = await run_gap_analysis()
    print(report.summary_line)          # "3 issues (1 critical, 2 warnings)"
    for issue in report.issues:
        print(issue.severity, issue.title)

v0.5.26: Initial release
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Type Aliases
# ---------------------------------------------------------------------------

GapIssueSeverity = Literal["info", "warning", "error", "critical"]
"""
Severity levels for gap issues.

* ``info``     – informational note, no action required
* ``warning``  – worth fixing before production
* ``error``    – will impair functionality
* ``critical`` – prevents the application from starting / running
"""

GapIssueCategory = Literal[
    "imports",
    "db",
    "migrations",
    "routers",
    "providers",
    "studio",
    "environment",
    "ai_pipeline",
    "ai_hub",
]
"""Nine check categories performed by the gap analysis engine (v0.5.28: +ai_hub)."""


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class GapFixCommand(BaseModel):
    """A shell command that remedies a gap issue."""

    description: str = Field(..., description="Human-readable description of what this command does")
    command: str = Field(..., description="Shell command to run (may contain env-var placeholders)")
    env_required: List[str] = Field(
        default_factory=list,
        description="Environment variables that must be set before running the command",
    )


class GapIssue(BaseModel):
    """A single gap issue found during analysis."""

    category: GapIssueCategory = Field(..., description="Which check category flagged this issue")
    severity: GapIssueSeverity = Field(..., description="Severity level")
    code: str = Field(..., description="Unique machine-readable code, e.g. 'IMPORT_MISSING_ASYNCPG'")
    title: str = Field(..., description="Short human-readable title (one line)")
    message: str = Field(..., description="Detailed explanation with context")
    hint: Optional[str] = Field(default=None, description="Suggested fix (plain English)")
    fix_commands: List[GapFixCommand] = Field(
        default_factory=list,
        description="Ordered shell commands to automatically remediate this issue",
    )
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Extra metadata (e.g. the missing package name, env var key, etc.)",
    )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------
    @property
    def is_blocking(self) -> bool:
        """Return True if this issue is critical or error severity."""
        return self.severity in ("critical", "error")

    @property
    def short_code(self) -> str:
        """Return category prefix, e.g. 'IMPORT' for 'IMPORT_MISSING_ASYNCPG'."""
        return self.code.split("_")[0]


class GapAnalysisStats(BaseModel):
    """Issue count breakdown by severity."""

    critical: int = Field(default=0)
    error: int = Field(default=0)
    warning: int = Field(default=0)
    info: int = Field(default=0)
    total: int = Field(default=0)

    def increment(self, severity: GapIssueSeverity) -> None:  # noqa: D401
        """Increment the counter for *severity* and total."""
        setattr(self, severity, getattr(self, severity) + 1)
        self.total += 1

    @property
    def has_blocking(self) -> bool:
        """True when there are critical or error severity issues."""
        return self.critical > 0 or self.error > 0

    @property
    def overall_status(self) -> str:
        """One of 'clean', 'warning', 'error', 'critical'."""
        if self.critical > 0:
            return "critical"
        if self.error > 0:
            return "error"
        if self.warning > 0:
            return "warning"
        return "clean"


class GapAnalysisReport(BaseModel):
    """Aggregated gap analysis report."""

    issues: List[GapIssue] = Field(default_factory=list)
    stats: GapAnalysisStats = Field(default_factory=GapAnalysisStats)
    categories_checked: List[GapIssueCategory] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = Field(default=0.0)
    system: Dict[str, str] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def add(self, issue: GapIssue) -> None:
        """Append an issue and update stats."""
        self.issues.append(issue)
        self.stats.increment(issue.severity)

    def by_severity(self, severity: GapIssueSeverity) -> List[GapIssue]:
        """Return all issues with the given *severity*."""
        return [i for i in self.issues if i.severity == severity]

    def by_category(self, category: GapIssueCategory) -> List[GapIssue]:
        """Return all issues for the given *category*."""
        return [i for i in self.issues if i.category == category]

    @property
    def summary_line(self) -> str:
        """E.g. '3 issues (1 critical, 2 warnings)' or 'All clear'."""
        s = self.stats
        if s.total == 0:
            return "All clear — no gaps found"
        parts = []
        if s.critical:
            parts.append(f"{s.critical} critical")
        if s.error:
            parts.append(f"{s.error} error{'s' if s.error > 1 else ''}")
        if s.warning:
            parts.append(f"{s.warning} warning{'s' if s.warning > 1 else ''}")
        if s.info:
            parts.append(f"{s.info} info")
        detail = ", ".join(parts)
        noun = "issue" if s.total == 1 else "issues"
        return f"{s.total} {noun} ({detail})"

    @property
    def has_critical(self) -> bool:
        return self.stats.critical > 0

    @property
    def has_errors(self) -> bool:
        return self.stats.error > 0 or self.stats.critical > 0

    @property
    def overall_status(self) -> str:
        return self.stats.overall_status


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _lazy_settings():
    """Lazy import of aksara.conf.settings — avoids circular imports."""
    from aksara.conf import settings
    return settings


def _lazy_registry():
    """Lazy import of ModelRegistry."""
    from aksara.registry import ModelRegistry
    return ModelRegistry


def _make_issue(
    category: GapIssueCategory,
    severity: GapIssueSeverity,
    code: str,
    title: str,
    message: str,
    hint: Optional[str] = None,
    fix_commands: Optional[List[GapFixCommand]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> GapIssue:
    """Convenience factory for GapIssue."""
    return GapIssue(
        category=category,
        severity=severity,
        code=code,
        title=title,
        message=message,
        hint=hint,
        fix_commands=fix_commands or [],
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Category 1: Import Checks
# ---------------------------------------------------------------------------

#: Packages that Aksara relies on.  Tuples of (import_name, install_name, severity).
_REQUIRED_PACKAGES: List[tuple[str, str, GapIssueSeverity]] = [
    ("fastapi", "fastapi", "critical"),
    ("pydantic", "pydantic", "critical"),
    ("asyncpg", "asyncpg", "critical"),
    ("click", "click", "error"),
    ("uvicorn", "uvicorn", "error"),
    ("alembic", "alembic", "warning"),
    ("httpx", "httpx", "warning"),
    ("passlib", "passlib", "warning"),
    ("python_jose", "python-jose", "warning"),
    ("rich", "rich", "info"),
    ("tabulate", "tabulate", "info"),
]


async def check_imports() -> List[GapIssue]:
    """Verify that required Python packages are importable."""
    issues: List[GapIssue] = []
    for import_name, install_name, severity in _REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError:
            issues.append(
                _make_issue(
                    category="imports",
                    severity=severity,
                    code=f"IMPORT_MISSING_{import_name.upper().replace('.', '_')}",
                    title=f"Package '{install_name}' is not installed",
                    message=(
                        f"Attempting to import '{import_name}' raised ImportError.  "
                        f"The package '{install_name}' must be installed in the "
                        f"current Python environment."
                    ),
                    hint=f"Run: pip install {install_name}",
                    fix_commands=[
                        GapFixCommand(
                            description=f"Install {install_name} via pip",
                            command=f"pip install {install_name}",
                        )
                    ],
                    meta={"import_name": import_name, "install_name": install_name},
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Category 2: Database Checks
# ---------------------------------------------------------------------------


async def check_db() -> List[GapIssue]:
    """Check database configuration (static — no live connection required)."""
    issues: List[GapIssue] = []
    try:
        settings = _lazy_settings()
    except Exception:
        issues.append(
            _make_issue(
                category="db",
                severity="critical",
                code="DB_SETTINGS_LOAD_FAILED",
                title="Could not load Aksara settings",
                message=(
                    "aksara.conf.settings could not be imported.  "
                    "This usually means a misconfigured settings module or a circular import."
                ),
                hint="Check your settings.py and ensure AKSARA_SETTINGS_MODULE is correct.",
            )
        )
        return issues

    db_url: Optional[str] = getattr(settings, "database_url", None) or os.environ.get(
        "DATABASE_URL"
    )
    if not db_url:
        issues.append(
            _make_issue(
                category="db",
                severity="critical",
                code="DB_NO_URL",
                title="No database URL configured",
                message=(
                    "Neither settings.database_url nor the DATABASE_URL environment "
                    "variable is set.  Aksara cannot connect to PostgreSQL without a "
                    "connection URL."
                ),
                hint="Set DATABASE_URL=postgresql://user:pass@host/dbname in your .env file.",
                fix_commands=[
                    GapFixCommand(
                        description="Add DATABASE_URL to your .env file",
                        command='echo "DATABASE_URL=postgresql://user:pass@localhost/mydb" >> .env',
                    )
                ],
                meta={"env_var": "DATABASE_URL"},
            )
        )
    else:
        # Check URL scheme
        if not db_url.startswith(("postgresql://", "postgresql+asyncpg://", "postgres://")):
            issues.append(
                _make_issue(
                    category="db",
                    severity="error",
                    code="DB_INVALID_SCHEME",
                    title="Database URL has an unsupported scheme",
                    message=(
                        f"The database URL starts with an unrecognised scheme.  "
                        f"Aksara requires a PostgreSQL URL "
                        f"(postgresql:// or postgresql+asyncpg://)."
                    ),
                    hint="Update DATABASE_URL to use postgresql:// or postgresql+asyncpg://",
                    meta={"db_url_prefix": db_url[:20]},
                )
            )

    # Pool settings sanity
    pool_min = getattr(settings, "pool_min_size", 1)
    pool_max = getattr(settings, "pool_max_size", 10)
    if isinstance(pool_min, int) and isinstance(pool_max, int):
        if pool_min > pool_max:
            issues.append(
                _make_issue(
                    category="db",
                    severity="error",
                    code="DB_POOL_INVERTED",
                    title="pool_min_size is greater than pool_max_size",
                    message=(
                        f"pool_min_size ({pool_min}) must be ≤ pool_max_size ({pool_max}).  "
                        f"This misconfiguration prevents asyncpg from creating a connection pool."
                    ),
                    hint="Set pool_min_size ≤ pool_max_size in AksaraSettings.",
                    meta={"pool_min_size": pool_min, "pool_max_size": pool_max},
                )
            )
        if pool_max > 100:
            issues.append(
                _make_issue(
                    category="db",
                    severity="warning",
                    code="DB_POOL_VERY_LARGE",
                    title="pool_max_size is unusually large",
                    message=(
                        f"pool_max_size is set to {pool_max}, which is unusually high.  "
                        f"Most PostgreSQL servers have a max_connections limit of 100.  "
                        f"Exceeding it will cause connection errors at peak load."
                    ),
                    hint="Consider reducing pool_max_size to 20-50 for typical deployments.",
                    meta={"pool_max_size": pool_max},
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Category 3: Migration Checks
# ---------------------------------------------------------------------------


async def check_migrations() -> List[GapIssue]:
    """Detect migration issues without a live DB connection."""
    issues: List[GapIssue] = []
    try:
        settings = _lazy_settings()
    except Exception:
        return issues

    from pathlib import Path

    migrations_dir = Path(getattr(settings, "migrations_dir", "migrations"))

    if not migrations_dir.exists():
        issues.append(
            _make_issue(
                category="migrations",
                severity="warning",
                code="MIGRATIONS_DIR_MISSING",
                title="Migrations directory does not exist",
                message=(
                    f"The configured migrations directory '{migrations_dir}' does not exist.  "
                    f"Run 'aksara makemigrations' to create your first migration."
                ),
                hint="Run: aksara makemigrations --app <your_app>.models",
                fix_commands=[
                    GapFixCommand(
                        description="Create first migration",
                        command="aksara makemigrations --app app.models",
                    )
                ],
                meta={"migrations_dir": str(migrations_dir)},
            )
        )
        return issues

    # Count migration files
    try:
        from aksara.migrations.executor import discover_migrations

        migration_files = discover_migrations(migrations_dir)
    except Exception:
        migration_files = []

    if not migration_files:
        issues.append(
            _make_issue(
                category="migrations",
                severity="info",
                code="MIGRATIONS_EMPTY",
                title="No migration files found",
                message=(
                    f"The migrations directory '{migrations_dir}' exists but contains "
                    f"no migration files.  Run 'aksara makemigrations' after defining models."
                ),
                hint="Run: aksara makemigrations --app <your_app>.models",
                fix_commands=[
                    GapFixCommand(
                        description="Generate first migration",
                        command="aksara makemigrations --app app.models",
                    )
                ],
                meta={"migrations_dir": str(migrations_dir)},
            )
        )
        return issues

    # Check for migration conflicts (multiple heads)
    try:
        from aksara.migrations.executor import build_migration_graph
        from aksara.migrations.graph import find_conflicts

        graph = build_migration_graph(migrations_list=migration_files)
        conflicts = find_conflicts(graph)
        if conflicts:
            conflict_names = [f"{app}.{name}" for app, name in conflicts]
            issues.append(
                _make_issue(
                    category="migrations",
                    severity="error",
                    code="MIGRATIONS_CONFLICT",
                    title=f"Migration conflict detected ({len(conflicts)} heads)",
                    message=(
                        f"The migration graph has conflicting heads: "
                        f"{', '.join(conflict_names)}.  "
                        f"Running 'aksara migrate' will fail until the conflict is resolved."
                    ),
                    hint="Run: aksara makemigrations --merge <app_label> to create a merge migration.",
                    fix_commands=[
                        GapFixCommand(
                            description="Create a merge migration",
                            command="aksara makemigrations --merge",
                        )
                    ],
                    meta={"conflicting_heads": conflict_names},
                )
            )
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Category 4: Router Checks
# ---------------------------------------------------------------------------


async def check_routers() -> List[GapIssue]:
    """Check that ViewSets and API routers are discoverable."""
    issues: List[GapIssue] = []
    try:
        settings = _lazy_settings()
    except Exception:
        return issues

    apps: List[str] = getattr(settings, "apps", []) or []
    if not apps:
        issues.append(
            _make_issue(
                category="routers",
                severity="warning",
                code="ROUTERS_NO_APPS",
                title="No apps configured in settings.apps",
                message=(
                    "settings.apps is empty.  Aksara will not discover any models, "
                    "ViewSets, or routes.  Add your app modules to AksaraSettings.apps."
                ),
                hint="Add your app modules to settings.apps, e.g. apps=['myapp'].",
                meta={"apps": apps},
            )
        )
        return issues

    missing_views: List[str] = []
    missing_models: List[str] = []

    for app in apps:
        # Check models
        try:
            importlib.import_module(f"{app}.models")
        except ImportError:
            missing_models.append(f"{app}.models")
        except Exception:
            pass

        # Check views
        try:
            importlib.import_module(f"{app}.views")
        except ImportError:
            missing_views.append(f"{app}.views")
        except Exception:
            pass

    if missing_models:
        issues.append(
            _make_issue(
                category="routers",
                severity="warning",
                code="ROUTERS_MISSING_MODELS_MODULE",
                title=f"models.py not found for {len(missing_models)} app(s)",
                message=(
                    f"The following model modules could not be imported: "
                    f"{', '.join(missing_models)}.  "
                    f"Ensure each app listed in settings.apps has a models.py file."
                ),
                hint="Create a models.py in each app directory or remove the app from settings.apps.",
                meta={"missing_modules": missing_models},
            )
        )

    if missing_views:
        issues.append(
            _make_issue(
                category="routers",
                severity="info",
                code="ROUTERS_MISSING_VIEWS_MODULE",
                title=f"views.py not found for {len(missing_views)} app(s)",
                message=(
                    f"The following view modules could not be imported: "
                    f"{', '.join(missing_views)}.  "
                    f"Without a views.py the app will have no API endpoints."
                ),
                hint="Create a views.py with a ModelViewSet in each app, or run: aksara startapp <name>.",
                meta={"missing_modules": missing_views},
            )
        )

    # Check model registry
    try:
        registry = _lazy_registry()
        all_models = registry.all()
        if not all_models:
            issues.append(
                _make_issue(
                    category="routers",
                    severity="warning",
                    code="ROUTERS_NO_MODELS_REGISTERED",
                    title="No models registered in ModelRegistry",
                    message=(
                        "ModelRegistry.all() returned an empty dict.  "
                        "This means no AksaraModel subclasses were discovered, so no "
                        "database tables or API routes will be generated."
                    ),
                    hint="Ensure your model classes extend AksaraModel and their module is in settings.apps.",
                )
            )
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Category 5: Provider Checks
# ---------------------------------------------------------------------------

#: Environment variables used by common AI providers.
_AI_PROVIDER_ENV_VARS: Dict[str, tuple[str, GapIssueSeverity]] = {
    "OPENAI_API_KEY": ("OpenAI", "warning"),
    "AZURE_OPENAI_API_KEY": ("Azure OpenAI", "warning"),
    "AZURE_OPENAI_ENDPOINT": ("Azure OpenAI", "warning"),
    "ANTHROPIC_API_KEY": ("Anthropic Claude", "warning"),
    "COHERE_API_KEY": ("Cohere", "info"),
    "MISTRAL_API_KEY": ("Mistral AI", "info"),
}


async def check_providers() -> List[GapIssue]:
    """Check AI provider configuration and secrets."""
    issues: List[GapIssue] = []
    try:
        settings = _lazy_settings()
    except Exception:
        return issues

    ai_enabled: bool = getattr(settings, "ai_enabled", False)
    if not ai_enabled:
        issues.append(
            _make_issue(
                category="providers",
                severity="info",
                code="PROVIDERS_AI_DISABLED",
                title="AI features are disabled",
                message=(
                    "settings.ai_enabled is False (or not set).  "
                    "AI-powered endpoints and the AI Hub will not be active.  "
                    "Set ai_enabled=True in AksaraSettings to enable them."
                ),
                hint="Set ai_enabled=True in AksaraSettings to activate AI features.",
                meta={"ai_enabled": ai_enabled},
            )
        )
        return issues

    # With AI enabled, check provider hints
    try:
        from aksara.ai.providers import build_secret_hints_from_settings

        hints = build_secret_hints_from_settings(settings)
        missing_required = [
            h for h in hints if h.required and not os.environ.get(h.env_var)
        ]
        missing_optional = [
            h for h in hints if not h.required and not os.environ.get(h.env_var)
        ]

        for hint in missing_required:
            issues.append(
                _make_issue(
                    category="providers",
                    severity="error",
                    code=f"PROVIDERS_MISSING_SECRET_{hint.env_var}",
                    title=f"Required AI secret '{hint.env_var}' is not set",
                    message=(
                        f"The environment variable {hint.env_var} is required by the "
                        f"'{hint.provider_name}' provider but is not present in the "
                        f"environment.  AI calls to this provider will fail."
                    ),
                    hint=f"Add {hint.env_var}=<your-key> to your .env file.",
                    fix_commands=[
                        GapFixCommand(
                            description=f"Add {hint.env_var} to .env",
                            command=f'echo "{hint.env_var}=<your-key>" >> .env',
                            env_required=[hint.env_var],
                        )
                    ],
                    meta={"env_var": hint.env_var, "provider": hint.provider_name},
                )
            )

        if missing_optional:
            env_list = ", ".join(h.env_var for h in missing_optional[:5])
            issues.append(
                _make_issue(
                    category="providers",
                    severity="info",
                    code="PROVIDERS_OPTIONAL_SECRETS_MISSING",
                    title=f"{len(missing_optional)} optional AI secret(s) not configured",
                    message=(
                        f"The following optional AI provider secrets are not set: {env_list}.  "
                        f"The providers they belong to will not be usable."
                    ),
                    hint="Set the relevant environment variables to enable those AI providers.",
                    meta={"missing_optional": [h.env_var for h in missing_optional]},
                )
            )
    except Exception:
        # AI providers module may not be present; downgrade to info
        pass

    # Check for example-only providers
    try:
        from aksara.ai.providers import build_default_ai_profile_set

        profile_set = build_default_ai_profile_set(settings)
        all_example = all(
            p.metadata.get("_example", False) for p in profile_set.providers
        )
        if profile_set.providers and all_example:
            issues.append(
                _make_issue(
                    category="providers",
                    severity="warning",
                    code="PROVIDERS_ALL_EXAMPLE",
                    title="All AI providers are built-in examples",
                    message=(
                        "Every configured AI provider is marked as an example/placeholder.  "
                        "Real API calls will fail.  Configure at least one real provider "
                        "via the ai_providers setting or set the relevant API key env vars."
                    ),
                    hint="Set OPENAI_API_KEY or configure real providers in AksaraSettings.",
                    meta={"provider_count": len(profile_set.providers)},
                )
            )
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Category 6: Studio Checks
# ---------------------------------------------------------------------------


async def check_studio() -> List[GapIssue]:
    """Check Studio panel configuration and static assets."""
    issues: List[GapIssue] = []
    try:
        settings = _lazy_settings()
    except Exception:
        return issues

    studio_enabled = getattr(settings, "enable_studio", True)
    if not studio_enabled:
        issues.append(
            _make_issue(
                category="studio",
                severity="info",
                code="STUDIO_DISABLED",
                title="Studio panel is disabled",
                message=(
                    "settings.enable_studio is False.  The /studio/ui dashboard "
                    "will not be accessible."
                ),
                hint="Set enable_studio=True in AksaraSettings to re-enable the Studio panel.",
                meta={"enable_studio": studio_enabled},
            )
        )
        return issues

    # Check that static directory exists
    try:
        from aksara.studio.fastapi import get_static_dir

        static_dir = get_static_dir()
        if not static_dir.exists():
            issues.append(
                _make_issue(
                    category="studio",
                    severity="error",
                    code="STUDIO_STATIC_DIR_MISSING",
                    title="Studio static assets directory not found",
                    message=(
                        f"The Studio UI static directory '{static_dir}' does not exist.  "
                        f"This usually means the Aksara package was not correctly installed "
                        f"or the static files were accidentally deleted."
                    ),
                    hint="Reinstall Aksara: pip install --force-reinstall aksara-framework",
                    fix_commands=[
                        GapFixCommand(
                            description="Reinstall Aksara to restore static assets",
                            command="pip install --force-reinstall aksara-framework",
                        )
                    ],
                    meta={"static_dir": str(static_dir)},
                )
            )
        else:
            # Check for core index file
            index_html = static_dir / "index.html"
            if not index_html.exists():
                issues.append(
                    _make_issue(
                        category="studio",
                        severity="warning",
                        code="STUDIO_INDEX_MISSING",
                        title="Studio index.html not found in static directory",
                        message=(
                            f"'{static_dir}/index.html' is missing.  "
                            f"The Studio UI may not render correctly."
                        ),
                        hint="Reinstall the Aksara package to restore missing static files.",
                        meta={"expected_file": str(index_html)},
                    )
                )
    except Exception:
        pass

    # Check secret key (used for CSRF / cookie signing)
    secret_key = getattr(settings, "secret_key", None) or os.environ.get("AKSARA_SECRET_KEY")
    if not secret_key:
        issues.append(
            _make_issue(
                category="studio",
                severity="warning",
                code="STUDIO_NO_SECRET_KEY",
                title="AKSARA_SECRET_KEY is not set",
                message=(
                    "No secret key found in settings.secret_key or the AKSARA_SECRET_KEY "
                    "environment variable.  Studio sessions and CSRF protection may be "
                    "weakened."
                ),
                hint="Generate a key with: python -c \"import secrets; print(secrets.token_hex(32))\" and set AKSARA_SECRET_KEY.",
                fix_commands=[
                    GapFixCommand(
                        description="Generate and set a secret key",
                        command='echo "AKSARA_SECRET_KEY=$(python -c \'import secrets; print(secrets.token_hex(32))\')" >> .env',
                    )
                ],
                meta={"env_var": "AKSARA_SECRET_KEY"},
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Category 7: Environment Checks
# ---------------------------------------------------------------------------

#: (env_var, severity, description)
_REQUIRED_ENV_VARS: List[tuple[str, GapIssueSeverity, str]] = [
    ("DATABASE_URL", "critical", "PostgreSQL connection URL"),
    ("SECRET_KEY", "warning", "Application secret key for JWT / session signing"),
    ("AKSARA_ENV", "info", "Environment name (development, staging, production)"),
]


async def check_environment() -> List[GapIssue]:
    """Check required environment variables."""
    issues: List[GapIssue] = []

    for env_var, severity, description in _REQUIRED_ENV_VARS:
        if not os.environ.get(env_var):
            # Also tolerate settings-level override
            try:
                settings = _lazy_settings()
                # Map env var to setting attribute
                attr_map = {
                    "DATABASE_URL": "database_url",
                    "SECRET_KEY": "secret_key",
                    "AKSARA_ENV": None,
                }
                attr = attr_map.get(env_var)
                if attr and getattr(settings, attr, None):
                    continue  # Provided via settings
            except Exception:
                pass

            issues.append(
                _make_issue(
                    category="environment",
                    severity=severity,
                    code=f"ENV_MISSING_{env_var}",
                    title=f"Environment variable {env_var} is not set",
                    message=(
                        f"{env_var} ({description}) is not present in the environment.  "
                        f"Aksara looks for this value at startup."
                    ),
                    hint=f"Add {env_var}=<value> to your .env or export it in your shell.",
                    fix_commands=[
                        GapFixCommand(
                            description=f"Add {env_var} to .env",
                            command=f'echo "{env_var}=<value>" >> .env',
                            env_required=[env_var],
                        )
                    ],
                    meta={"env_var": env_var, "description": description},
                )
            )

    # Check Python version
    py_major, py_minor = sys.version_info[:2]
    if py_major < 3 or (py_major == 3 and py_minor < 10):
        issues.append(
            _make_issue(
                category="environment",
                severity="error",
                code="ENV_PYTHON_VERSION_TOO_OLD",
                title=f"Python {py_major}.{py_minor} is below the minimum required version",
                message=(
                    f"Aksara requires Python 3.10 or newer.  "
                    f"You are running Python {py_major}.{py_minor}.  "
                    f"Update your Python installation."
                ),
                hint="Install Python 3.11+ via pyenv, brew, or your OS package manager.",
                meta={"python_version": f"{py_major}.{py_minor}"},
            )
        )

    # Debug mode in production warning
    try:
        settings = _lazy_settings()
        debug = getattr(settings, "debug", False)
        aksara_env = os.environ.get("AKSARA_ENV", "")
        if debug and aksara_env.lower() in ("production", "prod"):
            issues.append(
                _make_issue(
                    category="environment",
                    severity="error",
                    code="ENV_DEBUG_IN_PRODUCTION",
                    title="Debug mode is enabled in a production environment",
                    message=(
                        "settings.debug=True is set while AKSARA_ENV=production.  "
                        "Debug mode exposes sensitive information in error responses "
                        "and may enable internal dashboards that should be restricted."
                    ),
                    hint="Set debug=False in AksaraSettings for production deployments.",
                    meta={"debug": debug, "aksara_env": aksara_env},
                )
            )
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Category 8: AI Pipeline Checks
# ---------------------------------------------------------------------------


async def check_ai_pipeline() -> List[GapIssue]:
    """Check AI pipeline chain — models, tools, and agents."""
    issues: List[GapIssue] = []
    try:
        settings = _lazy_settings()
    except Exception:
        return issues

    ai_enabled: bool = getattr(settings, "ai_enabled", False)
    if not ai_enabled:
        # Not enabled — nothing to check
        return issues

    # Check for AI module availability
    for module_name in ("aksara.ai.agent", "aksara.ai.providers", "aksara.ai.planner"):
        try:
            importlib.import_module(module_name)
        except ImportError:
            issues.append(
                _make_issue(
                    category="ai_pipeline",
                    severity="critical",
                    code=f"AI_PIPELINE_MODULE_MISSING_{module_name.replace('.', '_').upper()}",
                    title=f"AI pipeline module '{module_name}' could not be imported",
                    message=(
                        f"Importing '{module_name}' raised ImportError.  "
                        f"AI features depend on this module and will not work."
                    ),
                    hint="Reinstall Aksara with AI extras: pip install aksara-framework[ai]",
                    fix_commands=[
                        GapFixCommand(
                            description="Install Aksara AI extras",
                            command="pip install aksara-framework[ai]",
                        )
                    ],
                    meta={"module": module_name},
                )
            )

    # Check MCP (Model Context Protocol) if enabled
    mcp_enabled = getattr(settings, "mcp_enabled", False)
    if mcp_enabled:
        try:
            importlib.import_module("mcp")
        except ImportError:
            issues.append(
                _make_issue(
                    category="ai_pipeline",
                    severity="warning",
                    code="AI_PIPELINE_MCP_NOT_INSTALLED",
                    title="MCP is enabled but the 'mcp' package is not installed",
                    message=(
                        "settings.mcp_enabled=True but 'import mcp' failed.  "
                        "MCP (Model Context Protocol) tool serving will be unavailable."
                    ),
                    hint="Install the MCP package: pip install mcp",
                    fix_commands=[
                        GapFixCommand(
                            description="Install MCP package",
                            command="pip install mcp",
                        )
                    ],
                    meta={"mcp_enabled": mcp_enabled},
                )
            )

    # Check for AI model registry / tools with registered models
    try:
        registry = _lazy_registry()
        all_models = registry.all()
        if all_models:
            # Check if models have AI metadata
            ai_exposed_count = 0
            for model_name, model_cls in all_models.items():
                meta = getattr(model_cls, "_meta", None)
                if meta and getattr(meta, "ai_agent_exposed", True):
                    ai_exposed_count += 1

            if ai_exposed_count == 0 and len(all_models) > 0:
                issues.append(
                    _make_issue(
                        category="ai_pipeline",
                        severity="info",
                        code="AI_PIPELINE_NO_EXPOSED_MODELS",
                        title="No models are exposed to the AI agent",
                        message=(
                            f"All {len(all_models)} registered model(s) have "
                            f"ai_agent_exposed=False.  The AI agent will have no data "
                            f"context to work with."
                        ),
                        hint="Set ai_agent_exposed=True on at least one model's Meta class.",
                        meta={
                            "total_models": len(all_models),
                            "ai_exposed": ai_exposed_count,
                        },
                    )
                )
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Category 9: AI Hub Checks (v0.5.28)
# ---------------------------------------------------------------------------


async def check_ai_hub() -> List[GapIssue]:
    """Check AI Hub 2.0 configuration, defaults, and embedding setup."""
    issues: List[GapIssue] = []
    try:
        from aksara.ai.hub_settings import load_aihub_settings, resolve_defaults

        hub = load_aihub_settings()
        configured = hub.configured_providers()

        # Gap 1: No providers configured at all
        if not configured:
            issues.append(
                _make_issue(
                    category="ai_hub",
                    severity="warning",
                    code="AI_HUB_NO_PROVIDER",
                    title="No AI providers configured in AI Hub",
                    message=(
                        "The AI Hub has no providers with valid credentials. "
                        "AI chat, code generation, and embedding features are unavailable."
                    ),
                    hint="Run: aksara ai-hub configure openai --api-key <key>",
                    fix_commands=[
                        GapFixCommand(
                            description="Configure OpenAI provider",
                            command='aksara ai-hub configure openai --api-key "$OPENAI_API_KEY"',
                            env_required=["OPENAI_API_KEY"],
                        ),
                    ],
                )
            )

        # Gap 2: Active provider unreachable (best-effort, no network call)
        if hub.active_provider and configured:
            active_prov = hub.get_provider(hub.active_provider)
            if active_prov and not active_prov.is_configured:
                issues.append(
                    _make_issue(
                        category="ai_hub",
                        severity="error",
                        code="AI_HUB_ACTIVE_PROVIDER_UNCONFIGURED",
                        title=f"Active provider '{hub.active_provider}' is not configured",
                        message=(
                            f"The active provider '{hub.active_provider}' is set but lacks "
                            f"required credentials. AI requests will fail."
                        ),
                        hint=f"aksara ai-hub configure {hub.active_provider} --api-key <key>",
                    )
                )

        # Gap 3: Defaults missing after resolve
        defaults = resolve_defaults(hub)
        if configured:
            if not defaults.chat_model:
                issues.append(
                    _make_issue(
                        category="ai_hub",
                        severity="warning",
                        code="AI_HUB_DEFAULTS_NO_CHAT",
                        title="AI Hub: No default chat model",
                        message=(
                            "No default chat model is configured or resolvable. "
                            "AI agent and chat features will not work."
                        ),
                        hint="aksara ai-hub defaults --chat-model gpt-4o",
                        fix_commands=[
                            GapFixCommand(
                                description="Set default chat model",
                                command="aksara ai-hub defaults --chat-model gpt-4o",
                            ),
                        ],
                    )
                )
            if not defaults.embeddings_model:
                issues.append(
                    _make_issue(
                        category="ai_hub",
                        severity="info",
                        code="AI_HUB_DEFAULTS_NO_EMBEDDINGS",
                        title="AI Hub: No embeddings model configured",
                        message=(
                            "No embeddings model is set. Semantic search will fall back "
                            "to local TF-IDF matching, which may be less accurate."
                        ),
                        hint="aksara ai-hub defaults --embeddings-model text-embedding-3-large",
                        fix_commands=[
                            GapFixCommand(
                                description="Set default embeddings model",
                                command="aksara ai-hub defaults --embeddings-model text-embedding-3-large",
                            ),
                        ],
                    )
                )

        # Gap 4: Search embeddings provider mismatch
        try:
            from aksara.search.embeddings import get_embedding_provider
            emb_prov = get_embedding_provider()
            if emb_prov == "local" and defaults.embeddings_model:
                # Hub says to use a remote model, but search defaults to local
                issues.append(
                    _make_issue(
                        category="ai_hub",
                        severity="info",
                        code="AI_HUB_SEARCH_EMBEDDING_MISMATCH",
                        title="Embeddings model set but search uses local provider",
                        message=(
                            f"AI Hub has embeddings_model='{defaults.embeddings_model}' but "
                            f"the search engine resolved to the 'local' provider. "
                            f"Ensure the embedding provider is registered."
                        ),
                        hint="Register the embedding provider or update hub defaults.",
                    )
                )
        except Exception:
            pass

        # Gap 5: Agent model not set when agents are used
        try:
            from aksara.ai.agent import AksaraAgent  # noqa: F401
            if configured and not defaults.chat_model:
                issues.append(
                    _make_issue(
                        category="ai_hub",
                        severity="warning",
                        code="AI_HUB_AGENT_NO_MODEL",
                        title="Agent module available but no chat model set",
                        message=(
                            "The aksara.ai.agent module is available but no default "
                            "chat model is configured. Agent workflows will not be able "
                            "to execute."
                        ),
                        hint="aksara ai-hub defaults --chat-model gpt-4o",
                    )
                )
        except ImportError:
            pass

    except ImportError:
        # hub_settings module not available
        pass
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

_CATEGORY_CHECKERS: Dict[
    GapIssueCategory,
    Callable[[], Coroutine[Any, Any, List[GapIssue]]],
] = {
    "imports": check_imports,
    "db": check_db,
    "migrations": check_migrations,
    "routers": check_routers,
    "providers": check_providers,
    "studio": check_studio,
    "environment": check_environment,
    "ai_pipeline": check_ai_pipeline,
    "ai_hub": check_ai_hub,
}


async def run_gap_analysis(
    categories: Optional[List[GapIssueCategory]] = None,
) -> GapAnalysisReport:
    """
    Run the full gap analysis engine.

    Parameters
    ----------
    categories:
        Optional subset of categories to check.  When *None* (default)
        all eight categories are run.

    Returns
    -------
    GapAnalysisReport
        Aggregated report with all found issues and statistics.

    Example::

        from aksara.gapanalysis import run_gap_analysis

        report = await run_gap_analysis()
        if report.has_critical:
            raise SystemExit("Critical gaps found — cannot start.")
    """
    start = time.monotonic()

    selected: List[GapIssueCategory] = categories or list(_CATEGORY_CHECKERS.keys())
    report = GapAnalysisReport(categories_checked=selected)

    # Populate system metadata
    try:
        import platform
        import aksara as _aksara

        report.system = {
            "aksara_version": getattr(_aksara, "__version__", "unknown"),
            "python_version": platform.python_version(),
            "os": platform.system(),
            "platform": platform.platform(),
        }
    except Exception:
        pass

    # Run each checker
    for category in selected:
        checker = _CATEGORY_CHECKERS.get(category)
        if checker is None:
            continue
        try:
            issues = await checker()
            for issue in issues:
                report.add(issue)
        except Exception as exc:
            # Never let a failing checker crash the whole analysis
            report.add(
                _make_issue(
                    category=category,
                    severity="warning",
                    code=f"{category.upper()}_CHECKER_FAILED",
                    title=f"Gap analysis checker for '{category}' raised an exception",
                    message=(
                        f"The '{category}' checker encountered an unexpected error: {exc!r}.  "
                        f"Some issues in this category may not have been detected."
                    ),
                    hint="This is likely a bug in Aksara — please report it.",
                    meta={"exception": str(exc), "category": category},
                )
            )

    report.duration_ms = (time.monotonic() - start) * 1000

    # v0.5.32: Emit graph event for gap report
    try:
        from aksara.ai.graph_events import emit_graph_event
        if report.total_issues > 0:
            emit_graph_event(
                "gap_report_changed",
                "gap_analysis",
                "run_gap_analysis",
                severity="warning" if report.has_critical else "info",
                message=f"Gap analysis found {report.total_issues} issues",
                total=report.total_issues,
            )
    except Exception:
        pass  # event emission must never break gap analysis

    return report


# ---------------------------------------------------------------------------
# Convenience helpers for callers
# ---------------------------------------------------------------------------


async def run_gap_analysis_for_category(
    category: GapIssueCategory,
) -> List[GapIssue]:
    """Run gap analysis for a single *category* and return raw issues."""
    checker = _CATEGORY_CHECKERS.get(category)
    if checker is None:
        return []
    try:
        return await checker()
    except Exception as exc:
        import logging

        logging.getLogger("aksara.gapanalysis").warning(
            "Checker %r raised %s: %s", category, type(exc).__name__, exc,
        )
        return []


def build_fix_plan(report: GapAnalysisReport) -> List[Dict[str, Any]]:
    """
    Build a structured fix plan from *report*.

    Returns a list of dicts, one per issue that has fix commands,
    sorted by severity (critical first).
    """
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    actionable = [i for i in report.issues if i.fix_commands]
    actionable.sort(key=lambda i: severity_order.get(i.severity, 99))

    plan: List[Dict[str, Any]] = []
    for issue in actionable:
        plan.append(
            {
                "severity": issue.severity,
                "category": issue.category,
                "code": issue.code,
                "title": issue.title,
                "commands": [
                    {
                        "description": cmd.description,
                        "command": cmd.command,
                        "env_required": cmd.env_required,
                    }
                    for cmd in issue.fix_commands
                ],
            }
        )
    return plan


__all__ = [
    # Types
    "GapIssueSeverity",
    "GapIssueCategory",
    # Models
    "GapFixCommand",
    "GapIssue",
    "GapAnalysisStats",
    "GapAnalysisReport",
    # Checkers
    "check_imports",
    "check_db",
    "check_migrations",
    "check_routers",
    "check_providers",
    "check_studio",
    "check_environment",
    "check_ai_pipeline",
    "check_ai_hub",
    # Orchestrator
    "run_gap_analysis",
    "run_gap_analysis_for_category",
    "build_fix_plan",
]
