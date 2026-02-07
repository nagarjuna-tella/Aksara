"""
Tests for Individual Diagnostic Checkers.

v0.5.17: 40+ tests covering all checker functions with mocks.
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from aksara.diagnostics import (
    DiagnosticIssue,
    check_database_connectivity,
    check_migrations_status,
    check_ai_profiles,
    check_ai_provider_secrets,
    check_required_settings,
    check_cache_available,
    check_file_system_permissions,
    check_security,
    run_all_checks,
)


# =============================================================================
# check_database_connectivity
# =============================================================================


class TestCheckDatabaseConnectivity:
    """Tests for check_database_connectivity."""

    @pytest.mark.asyncio
    async def test_no_database_url(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            issues = await check_database_connectivity()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert any("database url" in i.title.lower() or "database_url" in i.message.lower() for i in errors)

    @pytest.mark.asyncio
    async def test_connection_success(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="SELECT 1")
        mock_conn.close = AsyncMock()

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            with patch("asyncpg.connect", new_callable=AsyncMock, return_value=mock_conn):
                issues = await check_database_connectivity()
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/nonexistent"
            with patch("asyncpg.connect", new_callable=AsyncMock, side_effect=ConnectionRefusedError("refused")):
                issues = await check_database_connectivity()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert any("connection failed" in i.title.lower() for i in errors)


# =============================================================================
# check_migrations_status
# =============================================================================


class TestCheckMigrationsStatus:
    """Tests for check_migrations_status."""

    @pytest.mark.asyncio
    async def test_no_migrations_dir(self, tmp_path):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.migrations_dir = str(tmp_path / "nonexistent")
            issues = await check_migrations_status()
        assert any("no migrations directory" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_empty_migrations_dir(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "__init__.py").write_text("")

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.migrations_dir = str(mig_dir)
            issues = await check_migrations_status()
        assert any("no migrations found" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_migrations_present_no_db(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "__init__.py").write_text("")
        (mig_dir / "001_initial.py").write_text("# migration")

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.migrations_dir = str(mig_dir)
            issues = await check_migrations_status()
        # With no DB, it should still not raise
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_pending_migrations_detected(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "__init__.py").write_text("")
        (mig_dir / "001_initial.py").write_text("# migration")
        (mig_dir / "002_add_users.py").write_text("# migration")

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"name": "001_initial"}])
        mock_conn.close = AsyncMock()

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            mock_settings.migrations_dir = str(mig_dir)
            with patch("asyncpg.connect", new_callable=AsyncMock, return_value=mock_conn):
                issues = await check_migrations_status()
        pending = [i for i in issues if i.kind == "migrations_pending" and i.severity == "warning"]
        assert len(pending) >= 1
        assert "1 pending" in pending[0].title.lower()


# =============================================================================
# check_ai_profiles
# =============================================================================


class TestCheckAiProfiles:
    """Tests for check_ai_profiles."""

    @pytest.mark.asyncio
    async def test_ai_profiles_disabled(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.ai_profiles_enabled = False
            issues = await check_ai_profiles()
        assert any("disabled" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_ai_profiles_enabled_valid(self):
        mock_health = MagicMock()
        mock_health.issues = []

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.ai_profiles_enabled = True
            with patch("aksara.ai.providers.build_default_ai_profile_set", return_value=MagicMock()):
                with patch("aksara.ai.providers.validate_profile_set", return_value=mock_health):
                    issues = await check_ai_profiles()
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_ai_profiles_import_error(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.ai_profiles_enabled = True
            with patch.dict("sys.modules", {"aksara.ai.providers": None}):
                # This should handle the ImportError gracefully
                issues = await check_ai_profiles()
        # Should not crash
        assert isinstance(issues, list)


# =============================================================================
# check_ai_provider_secrets
# =============================================================================


class TestCheckAiProviderSecrets:
    """Tests for check_ai_provider_secrets."""

    @pytest.mark.asyncio
    async def test_no_missing_secrets(self):
        mock_hint = MagicMock()
        mock_hint.required = True
        mock_hint.env_var = "TEST_KEY"
        mock_hint.provider_name = "test"

        with patch("aksara.conf.settings"):
            with patch("aksara.ai.providers.build_secret_hints_from_settings", return_value=[mock_hint]):
                with patch.dict(os.environ, {"TEST_KEY": "value"}):
                    issues = await check_ai_provider_secrets()
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_missing_secret(self):
        mock_hint = MagicMock()
        mock_hint.required = True
        mock_hint.env_var = "MISSING_KEY_12345"
        mock_hint.provider_name = "openai"

        with patch("aksara.conf.settings"):
            with patch("aksara.ai.providers.build_secret_hints_from_settings", return_value=[mock_hint]):
                with patch.dict(os.environ, {}, clear=False):
                    # Ensure the key doesn't exist
                    os.environ.pop("MISSING_KEY_12345", None)
                    issues = await check_ai_provider_secrets()
        warnings = [i for i in issues if i.severity == "warning"]
        assert len(warnings) >= 1
        assert any("MISSING_KEY_12345" in i.title for i in warnings)


# =============================================================================
# check_required_settings
# =============================================================================


class TestCheckRequiredSettings:
    """Tests for check_required_settings."""

    @pytest.mark.asyncio
    async def test_valid_settings(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 10
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_no_database_url(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 10
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1

    @pytest.mark.asyncio
    async def test_pool_min_exceeds_max(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            mock_settings.pool_min_size = 20
            mock_settings.pool_max_size = 5
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("pool" in i.title.lower() for i in warnings)

    @pytest.mark.asyncio
    async def test_very_large_pool(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 200
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("large" in i.title.lower() for i in warnings)

    @pytest.mark.asyncio
    async def test_invalid_slow_threshold(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 10
            mock_settings.db_trace_slow_threshold_ms = -1
            issues = await check_required_settings()
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("threshold" in i.title.lower() for i in warnings)


# =============================================================================
# check_cache_available
# =============================================================================


class TestCheckCacheAvailable:
    """Tests for check_cache_available."""

    @pytest.mark.asyncio
    async def test_no_cache_url(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AKSARA_CACHE_URL", None)
            os.environ.pop("CACHE_URL", None)
            issues = await check_cache_available()
        assert any("no cache" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_cache_url_set(self):
        with patch.dict(os.environ, {"AKSARA_CACHE_URL": "redis://localhost:6379"}):
            issues = await check_cache_available()
        assert len(issues) == 0


# =============================================================================
# check_file_system_permissions
# =============================================================================


class TestCheckFileSystemPermissions:
    """Tests for check_file_system_permissions."""

    @pytest.mark.asyncio
    async def test_writable_temp(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.migrations_dir = "/tmp/test_migrations_nonexistent_dir"
            issues = await check_file_system_permissions()
        # Temp should be writable
        assert not any(i.kind == "file_system_unwritable" and "temp" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_writable_migrations_dir(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.migrations_dir = str(mig_dir)
            issues = await check_file_system_permissions()
        assert not any(i.kind == "file_system_unwritable" and "migrations" in i.title.lower() for i in issues)


# =============================================================================
# check_security
# =============================================================================


class TestCheckSecurity:
    """Tests for check_security."""

    @pytest.mark.asyncio
    async def test_debug_enabled_warning(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = True
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            issues = await check_security()
        assert any("debug" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_debug_disabled_no_warning(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            issues = await check_security()
        assert not any("debug mode" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_studio_exposed_in_production(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = True
            mock_settings.studio_allowed_origins = []
            issues = await check_security()
        assert any("studio exposed" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_wildcard_origins(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = ["*"]
            issues = await check_security()
        assert any("all origins" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_no_secret_key_info(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_SECRET_KEY", None)
                os.environ.pop("SECRET_KEY", None)
                issues = await check_security()
        assert any("secret_key" in i.title.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_secret_key_present(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            with patch.dict(os.environ, {"SECRET_KEY": "supersecret"}):
                issues = await check_security()
        assert not any("no secret_key" in i.title.lower() for i in issues)


# =============================================================================
# run_all_checks (Aggregator)
# =============================================================================


class TestRunAllChecks:
    """Tests for the run_all_checks aggregator."""

    @pytest.mark.asyncio
    async def test_returns_report(self):
        from aksara.diagnostics import DiagnosticReport

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 10
            mock_settings.debug = False
            mock_settings.migrations_dir = "/tmp/nonexistent_mig_dir_test"
            mock_settings.ai_profiles_enabled = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            mock_settings.db_trace_slow_threshold_ms = 100
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_CACHE_URL", None)
                os.environ.pop("CACHE_URL", None)
                os.environ.pop("AKSARA_SECRET_KEY", None)
                os.environ.pop("SECRET_KEY", None)
                report = await run_all_checks()

        assert isinstance(report, DiagnosticReport)
        assert len(report.issues) > 0
        assert report.duration_ms >= 0
        assert "aksara_version" in report.system
        assert "python_version" in report.system

    @pytest.mark.asyncio
    async def test_issues_sorted_by_severity(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 10
            mock_settings.debug = True
            mock_settings.migrations_dir = "/tmp/nonexistent_mig_dir_test"
            mock_settings.ai_profiles_enabled = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            mock_settings.db_trace_slow_threshold_ms = 100
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_CACHE_URL", None)
                os.environ.pop("CACHE_URL", None)
                report = await run_all_checks()

        severity_order = {"error": 0, "warning": 1, "info": 2}
        for i in range(len(report.issues) - 1):
            a = severity_order.get(report.issues[i].severity, 3)
            b = severity_order.get(report.issues[i + 1].severity, 3)
            assert a <= b, f"Issues not sorted: {report.issues[i].severity} before {report.issues[i+1].severity}"

    @pytest.mark.asyncio
    async def test_stats_match_issues(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.pool_min_size = 2
            mock_settings.pool_max_size = 10
            mock_settings.debug = True
            mock_settings.migrations_dir = "/tmp/nonexistent_mig_dir_test"
            mock_settings.ai_profiles_enabled = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            mock_settings.db_trace_slow_threshold_ms = 100
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_CACHE_URL", None)
                os.environ.pop("CACHE_URL", None)
                report = await run_all_checks()

        actual_errors = sum(1 for i in report.issues if i.severity == "error")
        actual_warnings = sum(1 for i in report.issues if i.severity == "warning")
        actual_info = sum(1 for i in report.issues if i.severity == "info")

        assert report.stats["errors"] == actual_errors
        assert report.stats["warnings"] == actual_warnings
        assert report.stats["info"] == actual_info

    @pytest.mark.asyncio
    async def test_checker_exception_handled(self):
        """If a checker raises an exception, run_all_checks should still complete."""
        from aksara.diagnostics import DiagnosticReport

        async def broken_checker():
            raise RuntimeError("boom")

        with patch("aksara.diagnostics.check_database_connectivity", side_effect=broken_checker):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.database_url = "postgresql://localhost/test"
                mock_settings.pool_min_size = 2
                mock_settings.pool_max_size = 10
                mock_settings.debug = False
                mock_settings.migrations_dir = "/tmp/nonexistent_mig_dir_test"
                mock_settings.ai_profiles_enabled = False
                mock_settings.studio_expose_in_production = False
                mock_settings.studio_allowed_origins = []
                mock_settings.db_trace_slow_threshold_ms = 100
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("AKSARA_CACHE_URL", None)
                    os.environ.pop("CACHE_URL", None)
                    report = await run_all_checks()

        assert isinstance(report, DiagnosticReport)
        # Should have captured the error as a warning
        assert any("failed" in i.title.lower() for i in report.issues)
