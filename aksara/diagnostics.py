"""
Aksara Self-Diagnostics Engine

v0.5.17: Comprehensive health checks for database, migrations, AI providers,
environment, settings, security, cache, and file-system.

Usage:
    from aksara.diagnostics import run_all_checks
    report = await run_all_checks()
    for issue in report.issues:
        print(f"[{issue.severity}] {issue.title}: {issue.message}")
"""

from __future__ import annotations

import os
import platform
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Data Models
# =============================================================================

DiagnosticSeverity = Literal["info", "warning", "error"]

DiagnosticKind = Literal[
    "database_connectivity",
    "database_schema",
    "migrations_pending",
    "migrations_conflict",
    "ai_provider_missing",
    "ai_provider_invalid",
    "ai_secret_missing",
    "ai_profile_issue",
    "env_missing",
    "settings_invalid",
    "cache_unavailable",
    "file_system_unwritable",
    "security_warning",
    "general",
]


class DiagnosticIssue(BaseModel):
    """A single diagnostic finding."""

    kind: str = Field(..., description="Issue category")
    severity: DiagnosticSeverity = Field(..., description="info | warning | error")
    title: str = Field(..., description="Short human-readable title")
    message: str = Field(..., description="Detailed explanation")
    hint: Optional[str] = Field(default=None, description="Suggested fix")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata")


class DiagnosticReport(BaseModel):
    """Aggregated diagnostic report."""

    issues: List[DiagnosticIssue] = Field(default_factory=list)
    stats: Dict[str, int] = Field(
        default_factory=lambda: {"errors": 0, "warnings": 0, "info": 0}
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_ms: float = Field(default=0.0, description="Total check duration")
    system: Dict[str, str] = Field(default_factory=dict)

    def add(self, issue: DiagnosticIssue) -> None:
        """Add an issue and update stats."""
        self.issues.append(issue)
        key = issue.severity + "s" if issue.severity != "info" else "info"
        self.stats[key] = self.stats.get(key, 0) + 1

    @property
    def has_errors(self) -> bool:
        return self.stats.get("errors", 0) > 0

    @property
    def overall_status(self) -> str:
        if self.stats.get("errors", 0) > 0:
            return "error"
        if self.stats.get("warnings", 0) > 0:
            return "warning"
        return "ok"


# =============================================================================
# Individual Checkers
# =============================================================================


async def check_database_connectivity() -> List[DiagnosticIssue]:
    """Try an actual DB connection and report issues."""
    issues: List[DiagnosticIssue] = []
    try:
        from aksara.conf import settings

        db_url = settings.database_url
        if not db_url:
            issues.append(DiagnosticIssue(
                kind="database_connectivity",
                severity="error",
                title="No database URL configured",
                message="DATABASE_URL or database_url setting is not set.",
                hint="Set DATABASE_URL environment variable or configure database_url in Settings.",
            ))
            return issues

        # Try to connect
        try:
            import asyncpg
            conn = await asyncpg.connect(db_url, timeout=5)
            await conn.execute("SELECT 1")
            await conn.close()
        except Exception as e:
            issues.append(DiagnosticIssue(
                kind="database_connectivity",
                severity="error",
                title="Database connection failed",
                message=f"Could not connect to database: {e}",
                hint="Check that your database is running and the connection URL is correct.",
                meta={"error_type": type(e).__name__},
            ))
    except ImportError:
        issues.append(DiagnosticIssue(
            kind="database_connectivity",
            severity="error",
            title="asyncpg not installed",
            message="The asyncpg driver is required for PostgreSQL connections.",
            hint="Install asyncpg: pip install asyncpg",
        ))
    except Exception as e:
        issues.append(DiagnosticIssue(
            kind="database_connectivity",
            severity="error",
            title="Database check error",
            message=str(e),
        ))
    return issues


async def check_migrations_status() -> List[DiagnosticIssue]:
    """Detect pending migrations and conflicts."""
    issues: List[DiagnosticIssue] = []
    try:
        from aksara.conf import settings

        migrations_dir = Path(settings.migrations_dir)
        if not migrations_dir.exists():
            issues.append(DiagnosticIssue(
                kind="migrations_pending",
                severity="info",
                title="No migrations directory",
                message=f"Migrations directory '{migrations_dir}' does not exist.",
                hint="Run 'aksara makemigrations' to create initial migrations.",
            ))
            return issues

        # Count migration files
        migration_files = sorted(migrations_dir.glob("*.py"))
        migration_files = [f for f in migration_files if f.name != "__init__.py"]

        if not migration_files:
            issues.append(DiagnosticIssue(
                kind="migrations_pending",
                severity="info",
                title="No migrations found",
                message="No migration files exist yet.",
                hint="Run 'aksara makemigrations' to generate migrations.",
            ))
            return issues

        # Try to check applied status via DB
        db_url = settings.database_url
        if db_url:
            try:
                import asyncpg
                conn = await asyncpg.connect(db_url, timeout=5)
                try:
                    rows = await conn.fetch(
                        "SELECT name FROM aksara_migrations ORDER BY name"
                    )
                    applied = {r["name"] for r in rows}
                except Exception:
                    # Table might not exist yet
                    applied = set()
                finally:
                    await conn.close()

                total = len(migration_files)
                pending = [f.stem for f in migration_files if f.stem not in applied]

                if pending:
                    issues.append(DiagnosticIssue(
                        kind="migrations_pending",
                        severity="warning",
                        title=f"{len(pending)} pending migration(s)",
                        message=f"{len(pending)} of {total} migrations have not been applied.",
                        hint="Run 'aksara migrate' to apply pending migrations.",
                        meta={"pending": pending[:10], "total": total, "pending_count": len(pending)},
                    ))
            except ImportError:
                pass
            except Exception:
                pass

        # Check for potential conflicts (multiple heads)
        heads = [f.stem for f in migration_files if f.stem.startswith("0")]
        if len(heads) > 0:
            # Simple prefix conflict detection
            prefixes: Dict[str, List[str]] = {}
            for name in [f.stem for f in migration_files]:
                prefix = name.split("_")[0] if "_" in name else name
                prefixes.setdefault(prefix, []).append(name)
            for prefix, names in prefixes.items():
                if len(names) > 1:
                    issues.append(DiagnosticIssue(
                        kind="migrations_conflict",
                        severity="warning",
                        title="Possible migration conflict",
                        message=f"Multiple migrations share prefix '{prefix}': {', '.join(names)}",
                        hint="Review migration files for conflicts and merge if needed.",
                        meta={"prefix": prefix, "files": names},
                    ))
    except Exception as e:
        issues.append(DiagnosticIssue(
            kind="migrations_pending",
            severity="info",
            title="Could not check migrations",
            message=str(e),
        ))
    return issues


async def check_ai_profiles() -> List[DiagnosticIssue]:
    """Validate AI profile configuration using existing v0.5.12 validator."""
    issues: List[DiagnosticIssue] = []
    try:
        from aksara.conf import settings

        ai_profiles_enabled = getattr(settings, "ai_profiles_enabled", True)
        if not ai_profiles_enabled:
            issues.append(DiagnosticIssue(
                kind="ai_profile_issue",
                severity="info",
                title="AI profiles disabled",
                message="AI profiles are disabled in settings.",
                hint="Set ai_profiles_enabled=True to enable AI profile features.",
            ))
            return issues

        from aksara.ai.providers import build_default_ai_profile_set, validate_profile_set

        profile_set = build_default_ai_profile_set(settings)
        health = validate_profile_set(profile_set)

        for iss in health.issues:
            severity_map = {"error": "error", "warning": "warning", "info": "info"}
            severity = severity_map.get(iss.severity, "info")
            kind = "ai_provider_invalid" if severity == "error" else "ai_profile_issue"
            issues.append(DiagnosticIssue(
                kind=kind,
                severity=severity,
                title=f"AI profile: {iss.kind}",
                message=iss.message,
                meta={"provider": iss.provider_name, "model": iss.model_name, "field": iss.field},
            ))
    except ImportError:
        pass
    except Exception as e:
        issues.append(DiagnosticIssue(
            kind="ai_profile_issue",
            severity="info",
            title="Could not check AI profiles",
            message=str(e),
        ))
    return issues


async def check_ai_provider_secrets() -> List[DiagnosticIssue]:
    """Verify env vars for configured AI providers."""
    issues: List[DiagnosticIssue] = []
    try:
        from aksara.conf import settings
        from aksara.ai.providers import build_secret_hints_from_settings

        hints = build_secret_hints_from_settings(settings)
        for hint in hints:
            if hint.required and not os.environ.get(hint.env_var):
                issues.append(DiagnosticIssue(
                    kind="ai_secret_missing",
                    severity="warning",
                    title=f"Missing AI secret: {hint.env_var}",
                    message=f"Required environment variable '{hint.env_var}' for provider '{hint.provider_name}' is not set.",
                    hint=f"Set the {hint.env_var} environment variable.",
                    meta={"provider": hint.provider_name, "env_var": hint.env_var},
                ))
    except ImportError:
        pass
    except Exception:
        pass
    return issues


async def check_required_settings() -> List[DiagnosticIssue]:
    """Check canonical Aksara settings for common misconfigurations."""
    issues: List[DiagnosticIssue] = []
    try:
        from aksara.conf import settings

        # Database URL is essential
        if not settings.database_url:
            issues.append(DiagnosticIssue(
                kind="settings_invalid",
                severity="error",
                title="No database URL",
                message="DATABASE_URL is not configured. Aksara requires a PostgreSQL database.",
                hint="Set DATABASE_URL=postgresql://user:pass@localhost/dbname",
            ))

        # Pool size sanity
        if settings.pool_max_size < settings.pool_min_size:
            issues.append(DiagnosticIssue(
                kind="settings_invalid",
                severity="warning",
                title="Invalid pool size",
                message=f"Pool max ({settings.pool_max_size}) is less than min ({settings.pool_min_size}).",
                hint="Set pool_max_size >= pool_min_size.",
            ))

        if settings.pool_max_size > 100:
            issues.append(DiagnosticIssue(
                kind="settings_invalid",
                severity="warning",
                title="Very large connection pool",
                message=f"pool_max_size is {settings.pool_max_size}. This may exhaust database connections.",
                hint="Consider using pool_max_size <= 50 for most workloads.",
            ))

        # Slow query threshold
        if settings.db_trace_slow_threshold_ms <= 0:
            issues.append(DiagnosticIssue(
                kind="settings_invalid",
                severity="warning",
                title="Invalid slow query threshold",
                message=f"db_trace_slow_threshold_ms is {settings.db_trace_slow_threshold_ms}. Must be positive.",
                hint="Set db_trace_slow_threshold_ms to a positive number (e.g. 100).",
            ))

    except Exception as e:
        issues.append(DiagnosticIssue(
            kind="settings_invalid",
            severity="info",
            title="Could not check settings",
            message=str(e),
        ))
    return issues


async def check_cache_available() -> List[DiagnosticIssue]:
    """Attempt to verify cache backend availability."""
    issues: List[DiagnosticIssue] = []
    # Aksara currently has no built-in cache layer, so this is a forward-looking check.
    # We emit info if there's no cache configured; frameworks that add cache can extend this.
    try:
        cache_url = os.environ.get("AKSARA_CACHE_URL") or os.environ.get("CACHE_URL")
        if not cache_url:
            issues.append(DiagnosticIssue(
                kind="cache_unavailable",
                severity="info",
                title="No cache configured",
                message="No AKSARA_CACHE_URL or CACHE_URL environment variable is set.",
                hint="If your app uses caching, set AKSARA_CACHE_URL.",
            ))
    except Exception:
        pass
    return issues


async def check_file_system_permissions() -> List[DiagnosticIssue]:
    """Try writing a temp file to verify file-system writability."""
    issues: List[DiagnosticIssue] = []
    try:
        # Try the current working directory
        test_path = Path(tempfile.gettempdir()) / ".aksara_doctor_probe"
        try:
            test_path.write_text("probe", encoding="utf-8")
            test_path.unlink(missing_ok=True)
        except OSError as e:
            issues.append(DiagnosticIssue(
                kind="file_system_unwritable",
                severity="warning",
                title="Temp directory not writable",
                message=f"Cannot write to temp directory: {e}",
                hint="Check file-system permissions on the temp directory.",
                meta={"path": str(test_path)},
            ))

        # Try the migrations directory
        from aksara.conf import settings
        mig_dir = Path(settings.migrations_dir)
        if mig_dir.exists():
            probe = mig_dir / ".aksara_probe"
            try:
                probe.write_text("probe", encoding="utf-8")
                probe.unlink(missing_ok=True)
            except OSError as e:
                issues.append(DiagnosticIssue(
                    kind="file_system_unwritable",
                    severity="warning",
                    title="Migrations directory not writable",
                    message=f"Cannot write to migrations directory '{mig_dir}': {e}",
                    hint="Check file-system permissions for the migrations directory.",
                    meta={"path": str(mig_dir)},
                ))
    except Exception:
        pass
    return issues


async def check_security() -> List[DiagnosticIssue]:
    """Check for common security misconfigurations."""
    issues: List[DiagnosticIssue] = []
    try:
        from aksara.conf import settings

        # DEBUG in production
        if settings.debug:
            issues.append(DiagnosticIssue(
                kind="security_warning",
                severity="warning",
                title="Debug mode is enabled",
                message="Running with debug=True. Do NOT use this in production.",
                hint="Set AKSARA_DEBUG=false or debug=False for production.",
            ))

        # Studio exposed in production
        if not settings.debug and getattr(settings, "studio_expose_in_production", False):
            issues.append(DiagnosticIssue(
                kind="security_warning",
                severity="warning",
                title="Studio exposed in production",
                message="Studio is accessible in production mode. This may leak internal info.",
                hint="Set studio_expose_in_production=False unless intentionally exposing Studio.",
            ))

        # Allowed origins too open
        allowed = getattr(settings, "studio_allowed_origins", [])
        if "*" in allowed:
            issues.append(DiagnosticIssue(
                kind="security_warning",
                severity="warning",
                title="Studio allows all origins",
                message="studio_allowed_origins contains '*', allowing any domain.",
                hint="Restrict studio_allowed_origins to trusted origins.",
            ))

        # SECRET_KEY not set (future-proofing)
        secret = os.environ.get("AKSARA_SECRET_KEY") or os.environ.get("SECRET_KEY")
        if not secret:
            issues.append(DiagnosticIssue(
                kind="security_warning",
                severity="info",
                title="No SECRET_KEY set",
                message="No AKSARA_SECRET_KEY or SECRET_KEY environment variable found.",
                hint="Set a SECRET_KEY for session signing and CSRF protection.",
            ))

    except Exception as e:
        issues.append(DiagnosticIssue(
            kind="security_warning",
            severity="info",
            title="Could not check security",
            message=str(e),
        ))
    return issues


# =============================================================================
# Aggregator
# =============================================================================


async def run_all_checks() -> DiagnosticReport:
    """Execute every diagnostic check and return a consolidated report."""
    import aksara

    start = time.monotonic()
    report = DiagnosticReport()

    # System metadata
    report.system = {
        "aksara_version": aksara.__version__,
        "python_version": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
    }

    # Run all checkers
    checkers = [
        check_database_connectivity,
        check_migrations_status,
        check_ai_profiles,
        check_ai_provider_secrets,
        check_required_settings,
        check_cache_available,
        check_file_system_permissions,
        check_security,
    ]

    for checker in checkers:
        try:
            found = await checker()
            for issue in found:
                report.add(issue)
        except Exception as e:
            report.add(DiagnosticIssue(
                kind="general",
                severity="warning",
                title=f"Checker {checker.__name__} failed",
                message=str(e),
            ))

    # Sort: errors first, then warnings, then info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    report.issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    report.duration_ms = round((time.monotonic() - start) * 1000, 2)
    return report


__all__ = [
    "DiagnosticSeverity",
    "DiagnosticKind",
    "DiagnosticIssue",
    "DiagnosticReport",
    "check_database_connectivity",
    "check_migrations_status",
    "check_ai_profiles",
    "check_ai_provider_secrets",
    "check_required_settings",
    "check_cache_available",
    "check_file_system_permissions",
    "check_security",
    "run_all_checks",
]
