"""
Tests for aksara.gapanalysis — v0.5.26 Gap Analysis Engine

Covers:
  - Unit tests for all eight check categories
  - Integration tests for run_gap_analysis orchestrator
  - Pydantic model tests (GapIssue, GapAnalysisStats, GapAnalysisReport)
  - build_fix_plan helper
  - Studio model and utils builders
  - CLI commands via CliRunner
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def run_async(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1. Pydantic Model Tests
# ---------------------------------------------------------------------------


class TestGapFixCommand:
    """Tests for GapFixCommand model."""

    def test_basic_construction(self):
        from aksara.gapanalysis import GapFixCommand

        cmd = GapFixCommand(description="Install foo", command="pip install foo")
        assert cmd.description == "Install foo"
        assert cmd.command == "pip install foo"
        assert cmd.env_required == []

    def test_env_required_list(self):
        from aksara.gapanalysis import GapFixCommand

        cmd = GapFixCommand(
            description="Set env",
            command='echo "KEY=val" >> .env',
            env_required=["KEY"],
        )
        assert "KEY" in cmd.env_required

    def test_empty_env_required_default(self):
        from aksara.gapanalysis import GapFixCommand

        cmd = GapFixCommand(description="d", command="c")
        assert isinstance(cmd.env_required, list)
        assert len(cmd.env_required) == 0


class TestGapIssue:
    """Tests for GapIssue model."""

    def test_construction_minimal(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(
            category="db",
            severity="error",
            code="DB_NO_URL",
            title="No DB URL",
            message="DATABASE_URL not set",
        )
        assert issue.category == "db"
        assert issue.severity == "error"
        assert issue.code == "DB_NO_URL"
        assert issue.hint is None
        assert issue.fix_commands == []
        assert issue.meta is None

    def test_is_blocking_critical(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(category="db", severity="critical", code="C", title="t", message="m")
        assert issue.is_blocking is True

    def test_is_blocking_error(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(category="db", severity="error", code="C", title="t", message="m")
        assert issue.is_blocking is True

    def test_is_not_blocking_warning(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(category="db", severity="warning", code="C", title="t", message="m")
        assert issue.is_blocking is False

    def test_is_not_blocking_info(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(category="db", severity="info", code="C", title="t", message="m")
        assert issue.is_blocking is False

    def test_short_code(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(
            category="imports",
            severity="critical",
            code="IMPORT_MISSING_ASYNCPG",
            title="t",
            message="m",
        )
        assert issue.short_code == "IMPORT"

    def test_fix_commands_list(self):
        from aksara.gapanalysis import GapFixCommand, GapIssue

        issue = GapIssue(
            category="db",
            severity="critical",
            code="C",
            title="t",
            message="m",
            fix_commands=[GapFixCommand(description="d", command="pip install foo")],
        )
        assert len(issue.fix_commands) == 1
        assert issue.fix_commands[0].command == "pip install foo"

    def test_meta_dict(self):
        from aksara.gapanalysis import GapIssue

        issue = GapIssue(
            category="environment",
            severity="warning",
            code="C",
            title="t",
            message="m",
            meta={"env_var": "DATABASE_URL"},
        )
        assert issue.meta["env_var"] == "DATABASE_URL"


class TestGapAnalysisStats:
    """Tests for GapAnalysisStats model."""

    def test_initial_zeros(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats()
        assert s.critical == 0
        assert s.error == 0
        assert s.warning == 0
        assert s.info == 0
        assert s.total == 0

    def test_increment_critical(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats()
        s.increment("critical")
        assert s.critical == 1
        assert s.total == 1

    def test_increment_multiple(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats()
        s.increment("error")
        s.increment("error")
        s.increment("warning")
        assert s.error == 2
        assert s.warning == 1
        assert s.total == 3

    def test_has_blocking_critical(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats(critical=1)
        assert s.has_blocking is True

    def test_has_blocking_error(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats(error=1)
        assert s.has_blocking is True

    def test_not_has_blocking_warning_only(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats(warning=3)
        assert s.has_blocking is False

    def test_overall_status_clean(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats()
        assert s.overall_status == "clean"

    def test_overall_status_warning(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats(warning=1)
        assert s.overall_status == "warning"

    def test_overall_status_error(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats(error=1)
        assert s.overall_status == "error"

    def test_overall_status_critical_priority(self):
        from aksara.gapanalysis import GapAnalysisStats

        s = GapAnalysisStats(critical=1, error=2, warning=3)
        assert s.overall_status == "critical"


class TestGapAnalysisReport:
    """Tests for GapAnalysisReport model."""

    def test_add_issue_updates_stats(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="error", code="C", title="t", message="m"))
        assert report.stats.error == 1
        assert report.stats.total == 1

    def test_add_multiple_severities(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="critical", code="C1", title="t", message="m"))
        report.add(GapIssue(category="db", severity="warning", code="C2", title="t", message="m"))
        report.add(GapIssue(category="imports", severity="info", code="C3", title="t", message="m"))
        assert report.stats.critical == 1
        assert report.stats.warning == 1
        assert report.stats.info == 1
        assert report.stats.total == 3

    def test_by_severity_filter(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="error", code="E", title="t", message="m"))
        report.add(GapIssue(category="db", severity="warning", code="W", title="t", message="m"))
        errors = report.by_severity("error")
        assert len(errors) == 1
        assert errors[0].code == "E"

    def test_by_category_filter(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="error", code="D", title="t", message="m"))
        report.add(GapIssue(category="imports", severity="info", code="I", title="t", message="m"))
        db_issues = report.by_category("db")
        assert len(db_issues) == 1
        assert db_issues[0].code == "D"

    def test_summary_line_all_clear(self):
        from aksara.gapanalysis import GapAnalysisReport

        report = GapAnalysisReport()
        assert "All clear" in report.summary_line

    def test_summary_line_with_issues(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="critical", code="C", title="t", message="m"))
        report.add(GapIssue(category="db", severity="warning", code="W", title="t", message="m"))
        line = report.summary_line
        assert "2 issues" in line
        assert "critical" in line
        assert "warning" in line

    def test_has_critical_true(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="critical", code="C", title="t", message="m"))
        assert report.has_critical is True

    def test_has_critical_false(self):
        from aksara.gapanalysis import GapAnalysisReport

        report = GapAnalysisReport()
        assert report.has_critical is False

    def test_has_errors_true_on_error(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="error", code="E", title="t", message="m"))
        assert report.has_errors is True

    def test_has_errors_true_on_critical(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="critical", code="C", title="t", message="m"))
        assert report.has_errors is True

    def test_has_errors_false_warning_only(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="warning", code="W", title="t", message="m"))
        assert report.has_errors is False

    def test_overall_status_delegates_to_stats(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="critical", code="C", title="t", message="m"))
        assert report.overall_status == "critical"

    def test_categories_checked_stored(self):
        from aksara.gapanalysis import GapAnalysisReport

        report = GapAnalysisReport(categories_checked=["db", "imports"])
        assert "db" in report.categories_checked
        assert "imports" in report.categories_checked


# ---------------------------------------------------------------------------
# 2. Category Check Tests — check_imports
# ---------------------------------------------------------------------------


class TestCheckImports:
    """Tests for the imports category checker."""

    def test_no_issues_when_all_importable(self):
        """When all required packages import successfully, no issues should be returned."""
        import aksara.gapanalysis as ga

        original = ga._REQUIRED_PACKAGES
        try:
            # Use a single package that is definitely available
            ga._REQUIRED_PACKAGES = [("sys", "sys", "critical")]
            issues = run_async(ga.check_imports())
            assert len(issues) == 0
        finally:
            ga._REQUIRED_PACKAGES = original

    def test_missing_package_returns_critical(self):
        """A missing critical package should produce a critical issue."""
        import aksara.gapanalysis as ga

        original = ga._REQUIRED_PACKAGES
        try:
            ga._REQUIRED_PACKAGES = [("_nonexistent_pkg_xyz_", "_nonexistent_pkg_xyz_", "critical")]
            issues = run_async(ga.check_imports())
            assert len(issues) == 1
            assert issues[0].severity == "critical"
            assert issues[0].category == "imports"
            assert "_NONEXISTENT_PKG_XYZ_" in issues[0].code
        finally:
            ga._REQUIRED_PACKAGES = original

    def test_missing_package_returns_warning_when_configured_warning(self):
        """A warning-level missing package should produce a warning issue."""
        import aksara.gapanalysis as ga

        original = ga._REQUIRED_PACKAGES
        try:
            ga._REQUIRED_PACKAGES = [("_nonexistent_pkg_xyz_", "_nonexistent_pkg_xyz_", "warning")]
            issues = run_async(ga.check_imports())
            assert len(issues) == 1
            assert issues[0].severity == "warning"
        finally:
            ga._REQUIRED_PACKAGES = original

    def test_missing_package_has_fix_command(self):
        """Fix commands should include a pip install command."""
        import aksara.gapanalysis as ga

        original = ga._REQUIRED_PACKAGES
        try:
            ga._REQUIRED_PACKAGES = [("_nonexistent_pkg_xyz_", "my-special-package", "error")]
            issues = run_async(ga.check_imports())
            assert len(issues) == 1
            assert len(issues[0].fix_commands) > 0
            assert "my-special-package" in issues[0].fix_commands[0].command
        finally:
            ga._REQUIRED_PACKAGES = original

    def test_multiple_missing_packages(self):
        """Multiple missing packages should each produce an issue."""
        import aksara.gapanalysis as ga

        original = ga._REQUIRED_PACKAGES
        try:
            ga._REQUIRED_PACKAGES = [
                ("_pkg_a_", "_pkg_a_", "critical"),
                ("_pkg_b_", "_pkg_b_", "error"),
            ]
            issues = run_async(ga.check_imports())
            assert len(issues) == 2
        finally:
            ga._REQUIRED_PACKAGES = original


# ---------------------------------------------------------------------------
# 3. Category Check Tests — check_db
# ---------------------------------------------------------------------------


class TestCheckDb:
    """Tests for the db category checker."""

    def _mock_settings(self, **kwargs):
        m = MagicMock()
        m.database_url = kwargs.get("database_url", None)
        m.pool_min_size = kwargs.get("pool_min_size", 1)
        m.pool_max_size = kwargs.get("pool_max_size", 10)
        return m

    def test_no_url_produces_critical(self):
        settings = self._mock_settings(database_url=None)
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch.dict(os.environ, {}, clear=False):
                if "DATABASE_URL" in os.environ:
                    del os.environ["DATABASE_URL"]
                issues = run_async(__import__("aksara.gapanalysis", fromlist=["check_db"]).check_db())
        assert any(i.code == "DB_NO_URL" for i in issues)
        assert any(i.severity == "critical" for i in issues)

    def test_valid_postgresql_url_no_issues(self):
        settings = self._mock_settings(database_url="postgresql://user:pass@localhost/db")
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert not any(i.code == "DB_NO_URL" for i in issues)
        assert not any(i.code == "DB_INVALID_SCHEME" for i in issues)

    def test_invalid_scheme_produces_error(self):
        settings = self._mock_settings(database_url="mysql://user:pass@localhost/db")
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert any(i.code == "DB_INVALID_SCHEME" for i in issues)

    def test_asyncpg_scheme_is_valid(self):
        """postgresql+asyncpg:// is a valid scheme."""
        settings = self._mock_settings(database_url="postgresql+asyncpg://user:pass@localhost/db")
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert not any(i.code == "DB_INVALID_SCHEME" for i in issues)

    def test_pool_inverted_produces_error(self):
        settings = self._mock_settings(
            database_url="postgresql://u:p@h/db",
            pool_min_size=10,
            pool_max_size=5,
        )
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert any(i.code == "DB_POOL_INVERTED" for i in issues)

    def test_pool_valid_no_issue(self):
        settings = self._mock_settings(
            database_url="postgresql://u:p@h/db",
            pool_min_size=2,
            pool_max_size=20,
        )
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert not any(i.code == "DB_POOL_INVERTED" for i in issues)
        assert not any(i.code == "DB_POOL_VERY_LARGE" for i in issues)

    def test_pool_very_large_produces_warning(self):
        settings = self._mock_settings(
            database_url="postgresql://u:p@h/db",
            pool_min_size=1,
            pool_max_size=200,
        )
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert any(i.code == "DB_POOL_VERY_LARGE" for i in issues)

    def test_settings_load_failure_produces_critical(self):
        def _fail():
            raise ImportError("settings broken")

        with patch("aksara.gapanalysis._lazy_settings", side_effect=ImportError("broken")):
            from aksara.gapanalysis import check_db
            issues = run_async(check_db())
        assert any(i.code == "DB_SETTINGS_LOAD_FAILED" for i in issues)


# ---------------------------------------------------------------------------
# 4. Category Check Tests — check_migrations
# ---------------------------------------------------------------------------


class TestCheckMigrations:
    """Tests for the migrations category checker."""

    def _mock_settings(self, migrations_dir: str):
        m = MagicMock()
        m.migrations_dir = migrations_dir
        return m

    def test_missing_dir_produces_warning(self, tmp_path):
        missing = str(tmp_path / "nonexistent_migrations")
        settings = self._mock_settings(missing)
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_migrations
            issues = run_async(check_migrations())
        assert any(i.code == "MIGRATIONS_DIR_MISSING" for i in issues)

    def test_empty_dir_produces_info(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        settings = self._mock_settings(str(mig_dir))
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.gapanalysis.discover_migrations", return_value=[], create=True):
                from aksara.gapanalysis import check_migrations
                issues = run_async(check_migrations())
        assert any(i.code == "MIGRATIONS_EMPTY" for i in issues)

    def test_existing_migrations_no_warning(self, tmp_path):
        """When valid migrations exist with no conflicts, no issues."""
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        # Create a dummy migration file
        (mig_dir / "0001_initial.py").write_text("# migration")

        settings = self._mock_settings(str(mig_dir))
        fake_migs = [("0001_initial", mig_dir / "0001_initial.py")]

        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.migrations.executor.discover_migrations", return_value=fake_migs):
                with patch("aksara.migrations.executor.build_migration_graph", return_value=MagicMock()):
                    with patch("aksara.migrations.graph.find_conflicts", return_value=[]):
                        from aksara.gapanalysis import check_migrations
                        issues = run_async(check_migrations())
        # Should have no MIGRATIONS_CONFLICT issues
        assert not any(i.code == "MIGRATIONS_CONFLICT" for i in issues)


# ---------------------------------------------------------------------------
# 5. Category Check Tests — check_routers
# ---------------------------------------------------------------------------


class TestCheckRouters:
    """Tests for the routers category checker."""

    def _mock_settings(self, apps: list):
        m = MagicMock()
        m.apps = apps
        return m

    def test_no_apps_produces_warning(self):
        settings = self._mock_settings([])
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_routers
            issues = run_async(check_routers())
        assert any(i.code == "ROUTERS_NO_APPS" for i in issues)

    def test_app_with_missing_models_produces_warning(self):
        settings = self._mock_settings(["nonexistent_app_xyz"])
        mock_registry = MagicMock()
        mock_registry.all.return_value = {"SomeModel": MagicMock()}
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.gapanalysis._lazy_registry", return_value=mock_registry):
                from aksara.gapanalysis import check_routers
                issues = run_async(check_routers())
        assert any(i.code == "ROUTERS_MISSING_MODELS_MODULE" for i in issues)

    def test_no_registered_models_produces_warning(self):
        settings = self._mock_settings(["some_app"])
        mock_registry = MagicMock()
        mock_registry.all.return_value = {}
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.gapanalysis._lazy_registry", return_value=mock_registry):
                from aksara.gapanalysis import check_routers
                issues = run_async(check_routers())
        assert any(i.code == "ROUTERS_NO_MODELS_REGISTERED" for i in issues)


# ---------------------------------------------------------------------------
# 6. Category Check Tests — check_providers
# ---------------------------------------------------------------------------


class TestCheckProviders:
    """Tests for the providers category checker."""

    def _mock_settings(self, ai_enabled=True):
        m = MagicMock()
        m.ai_enabled = ai_enabled
        return m

    def test_ai_disabled_produces_info(self):
        settings = self._mock_settings(ai_enabled=False)
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_providers
            issues = run_async(check_providers())
        assert any(i.code == "PROVIDERS_AI_DISABLED" for i in issues)
        assert all(i.severity == "info" for i in issues)

    def test_ai_enabled_with_no_secrets(self):
        settings = self._mock_settings(ai_enabled=True)
        # Fake a required secret hint
        mock_hint = MagicMock()
        mock_hint.env_var = "OPENAI_API_KEY"
        mock_hint.provider_name = "OpenAI"
        mock_hint.required = True

        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.ai.providers.build_secret_hints_from_settings", return_value=[mock_hint]):
                with patch.dict(os.environ, {}, clear=False):
                    if "OPENAI_API_KEY" in os.environ:
                        del os.environ["OPENAI_API_KEY"]
                    from aksara.gapanalysis import check_providers
                    issues = run_async(check_providers())
        assert any("OPENAI_API_KEY" in i.code for i in issues)
        assert any(i.severity == "error" for i in issues)

    def test_ai_enabled_secrets_present_no_error(self):
        settings = self._mock_settings(ai_enabled=True)
        mock_hint = MagicMock()
        mock_hint.env_var = "OPENAI_API_KEY"
        mock_hint.provider_name = "OpenAI"
        mock_hint.required = True

        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.ai.providers.build_secret_hints_from_settings", return_value=[mock_hint]):
                with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
                    from aksara.gapanalysis import check_providers
                    issues = run_async(check_providers())
        # Should not have an error for OPENAI_API_KEY since it's set
        assert not any("OPENAI_API_KEY" in i.code and i.severity == "error" for i in issues)


# ---------------------------------------------------------------------------
# 7. Category Check Tests — check_studio
# ---------------------------------------------------------------------------


class TestCheckStudio:
    """Tests for the studio category checker."""

    def _mock_settings(self, enable_studio=True, secret_key=None):
        m = MagicMock()
        m.enable_studio = enable_studio
        m.secret_key = secret_key
        return m

    def test_studio_disabled_produces_info(self):
        settings = self._mock_settings(enable_studio=False)
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_studio
            issues = run_async(check_studio())
        assert any(i.code == "STUDIO_DISABLED" for i in issues)

    def test_missing_static_dir_produces_error(self, tmp_path):
        settings = self._mock_settings(enable_studio=True, secret_key="mysecret")
        fake_static_dir = tmp_path / "nonexistent_static"

        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.studio.fastapi.get_static_dir", return_value=fake_static_dir):
                from aksara.gapanalysis import check_studio
                issues = run_async(check_studio())
        assert any(i.code == "STUDIO_STATIC_DIR_MISSING" for i in issues)

    def test_no_secret_key_produces_warning(self, tmp_path):
        settings = self._mock_settings(enable_studio=True, secret_key=None)
        fake_static_dir = tmp_path / "static"
        fake_static_dir.mkdir()
        (fake_static_dir / "index.html").write_text("<html/>")

        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.studio.fastapi.get_static_dir", return_value=fake_static_dir):
                with patch.dict(os.environ, {}, clear=False):
                    if "AKSARA_SECRET_KEY" in os.environ:
                        del os.environ["AKSARA_SECRET_KEY"]
                    from aksara.gapanalysis import check_studio
                    issues = run_async(check_studio())
        assert any(i.code == "STUDIO_NO_SECRET_KEY" for i in issues)

    def test_all_configured_no_warning(self, tmp_path):
        settings = self._mock_settings(enable_studio=True, secret_key="supersecret!")
        fake_static_dir = tmp_path / "static"
        fake_static_dir.mkdir()
        (fake_static_dir / "index.html").write_text("<html/>")

        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch("aksara.studio.fastapi.get_static_dir", return_value=fake_static_dir):
                from aksara.gapanalysis import check_studio
                issues = run_async(check_studio())
        assert not any(i.code in ("STUDIO_DISABLED", "STUDIO_STATIC_DIR_MISSING", "STUDIO_NO_SECRET_KEY") for i in issues)


# ---------------------------------------------------------------------------
# 8. Category Check Tests — check_environment
# ---------------------------------------------------------------------------


class TestCheckEnvironment:
    """Tests for the environment category checker."""

    def test_python_too_old_produces_error(self):
        with patch.object(sys, "version_info", (3, 9, 0)):
            from aksara.gapanalysis import check_environment
            issues = run_async(check_environment())
        assert any(i.code == "ENV_PYTHON_VERSION_TOO_OLD" for i in issues)

    def test_python_modern_no_version_error(self):
        with patch.object(sys, "version_info", (3, 11, 0)):
            from aksara.gapanalysis import check_environment
            with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
                issues = run_async(check_environment())
        assert not any(i.code == "ENV_PYTHON_VERSION_TOO_OLD" for i in issues)

    def test_debug_in_production_produces_error(self):
        settings = MagicMock()
        settings.database_url = "postgresql://u:p@h/db"
        settings.secret_key = "secret"
        settings.debug = True
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch.dict(os.environ, {"AKSARA_ENV": "production"}):
                from aksara.gapanalysis import check_environment
                issues = run_async(check_environment())
        assert any(i.code == "ENV_DEBUG_IN_PRODUCTION" for i in issues)

    def test_missing_database_url_produces_critical(self):
        settings = MagicMock()
        settings.database_url = None
        settings.secret_key = "secret"
        settings.debug = False
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch.dict(os.environ, {}, clear=False):
                env_backup = os.environ.pop("DATABASE_URL", None)
                try:
                    from aksara.gapanalysis import check_environment
                    issues = run_async(check_environment())
                finally:
                    if env_backup:
                        os.environ["DATABASE_URL"] = env_backup
        assert any(i.code == "ENV_MISSING_DATABASE_URL" for i in issues)


# ---------------------------------------------------------------------------
# 9. Category Check Tests — check_ai_pipeline
# ---------------------------------------------------------------------------


class TestCheckAiPipeline:
    """Tests for the ai_pipeline category checker."""

    def _mock_settings(self, ai_enabled=True, mcp_enabled=False):
        m = MagicMock()
        m.ai_enabled = ai_enabled
        m.mcp_enabled = mcp_enabled
        return m

    def test_ai_disabled_returns_empty(self):
        settings = self._mock_settings(ai_enabled=False)
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            from aksara.gapanalysis import check_ai_pipeline
            issues = run_async(check_ai_pipeline())
        assert len(issues) == 0

    def test_mcp_enabled_but_not_installed_produces_warning(self):
        settings = self._mock_settings(ai_enabled=True, mcp_enabled=True)
        with patch("aksara.gapanalysis._lazy_settings", return_value=settings):
            with patch.dict(sys.modules, {"mcp": None}):
                from aksara.gapanalysis import check_ai_pipeline
                issues = run_async(check_ai_pipeline())
        assert any(i.code == "AI_PIPELINE_MCP_NOT_INSTALLED" for i in issues)


# ---------------------------------------------------------------------------
# 10. Integration Tests — run_gap_analysis orchestrator
# ---------------------------------------------------------------------------


class TestRunGapAnalysis:
    """Integration tests for the run_gap_analysis orchestrator."""

    def test_returns_report_instance(self):
        from aksara.gapanalysis import run_gap_analysis, GapAnalysisReport

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            report = run_async(run_gap_analysis())
        assert isinstance(report, GapAnalysisReport)

    def test_all_categories_checked_by_default(self):
        from aksara.gapanalysis import run_gap_analysis, _CATEGORY_CHECKERS

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            report = run_async(run_gap_analysis())
        for cat in _CATEGORY_CHECKERS:
            assert cat in report.categories_checked

    def test_categories_filter_respected(self):
        from aksara.gapanalysis import run_gap_analysis

        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://u:p@h/db"
        mock_settings.pool_min_size = 1
        mock_settings.pool_max_size = 10

        with patch("aksara.gapanalysis._lazy_settings", return_value=mock_settings):
            report = run_async(run_gap_analysis(categories=["db"]))
        assert "db" in report.categories_checked
        assert "imports" not in report.categories_checked

    def test_duration_ms_set(self):
        from aksara.gapanalysis import run_gap_analysis

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            report = run_async(run_gap_analysis())
        assert report.duration_ms >= 0

    def test_system_info_populated(self):
        from aksara.gapanalysis import run_gap_analysis

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            report = run_async(run_gap_analysis())
        assert "python_version" in report.system

    def test_failing_checker_does_not_crash_analysis(self):
        """If one checker raises, the analysis should continue and report a warning."""
        from aksara.gapanalysis import run_gap_analysis

        async def _bad_checker():
            raise RuntimeError("Simulated checker failure")

        import aksara.gapanalysis as ga

        original = ga._CATEGORY_CHECKERS.copy()
        try:
            ga._CATEGORY_CHECKERS = {"imports": _bad_checker}
            report = run_async(run_gap_analysis(categories=["imports"]))
            # The orchestrator should catch the exception and add a warning
            assert report.stats.warning >= 1
            assert any("CHECKER_FAILED" in i.code for i in report.issues)
        finally:
            ga._CATEGORY_CHECKERS = original

    def test_empty_categories_list_runs_all(self):
        """None categories should run all checkers."""
        from aksara.gapanalysis import run_gap_analysis, _CATEGORY_CHECKERS

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            report = run_async(run_gap_analysis(categories=None))
        assert len(report.categories_checked) == len(_CATEGORY_CHECKERS)


# ---------------------------------------------------------------------------
# 11. build_fix_plan Helper
# ---------------------------------------------------------------------------


class TestBuildFixPlan:
    """Tests for the build_fix_plan helper function."""

    def test_returns_list(self):
        from aksara.gapanalysis import GapAnalysisReport, build_fix_plan

        report = GapAnalysisReport()
        plan = build_fix_plan(report)
        assert isinstance(plan, list)

    def test_only_includes_issues_with_commands(self):
        from aksara.gapanalysis import GapIssue, GapFixCommand, GapAnalysisReport, build_fix_plan

        report = GapAnalysisReport()
        # Issue with fix command
        report.add(
            GapIssue(
                category="db",
                severity="error",
                code="E",
                title="t",
                message="m",
                fix_commands=[GapFixCommand(description="d", command="pip install foo")],
            )
        )
        # Issue without fix command
        report.add(GapIssue(category="db", severity="warning", code="W", title="t", message="m"))

        plan = build_fix_plan(report)
        assert len(plan) == 1
        assert plan[0]["code"] == "E"

    def test_sorted_by_severity(self):
        from aksara.gapanalysis import GapIssue, GapFixCommand, GapAnalysisReport, build_fix_plan

        cmd = [GapFixCommand(description="d", command="c")]
        report = GapAnalysisReport()
        report.add(GapIssue(category="db", severity="warning", code="W", title="t", message="m", fix_commands=cmd))
        report.add(GapIssue(category="db", severity="critical", code="C", title="t", message="m", fix_commands=cmd))
        report.add(GapIssue(category="db", severity="error", code="E", title="t", message="m", fix_commands=cmd))

        plan = build_fix_plan(report)
        assert plan[0]["severity"] == "critical"
        assert plan[1]["severity"] == "error"
        assert plan[2]["severity"] == "warning"

    def test_plan_item_structure(self):
        from aksara.gapanalysis import GapIssue, GapFixCommand, GapAnalysisReport, build_fix_plan

        report = GapAnalysisReport()
        report.add(
            GapIssue(
                category="db",
                severity="error",
                code="MY_CODE",
                title="My Title",
                message="m",
                fix_commands=[
                    GapFixCommand(
                        description="Install it",
                        command="pip install foo",
                        env_required=["MY_VAR"],
                    )
                ],
            )
        )
        plan = build_fix_plan(report)
        item = plan[0]
        assert item["code"] == "MY_CODE"
        assert item["title"] == "My Title"
        assert len(item["commands"]) == 1
        assert item["commands"][0]["command"] == "pip install foo"
        assert "MY_VAR" in item["commands"][0]["env_required"]


# ---------------------------------------------------------------------------
# 12. run_gap_analysis_for_category Helper
# ---------------------------------------------------------------------------


class TestRunGapAnalysisForCategory:
    """Tests for the run_gap_analysis_for_category convenience function."""

    def test_returns_list_of_issues(self):
        from aksara.gapanalysis import run_gap_analysis_for_category, GapIssue

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            issues = run_async(run_gap_analysis_for_category("db"))
        assert isinstance(issues, list)

    def test_unknown_category_returns_empty(self):
        from aksara.gapanalysis import run_gap_analysis_for_category

        issues = run_async(run_gap_analysis_for_category("nonexistent_category"))  # type: ignore
        assert issues == []

    def test_checker_exception_returns_empty(self):
        """If a checker raises, the helper swallows the error and returns empty."""
        import aksara.gapanalysis as ga

        original = ga._CATEGORY_CHECKERS.copy()
        try:
            async def _fail():
                raise ValueError("boom")
            ga._CATEGORY_CHECKERS["imports"] = _fail
            issues = run_async(ga.run_gap_analysis_for_category("imports"))
            assert issues == []
        finally:
            ga._CATEGORY_CHECKERS = original


# ---------------------------------------------------------------------------
# 13. Studio Model Tests
# ---------------------------------------------------------------------------


class TestStudioGapModels:
    """Tests for Studio-layer gap analysis Pydantic models."""

    def test_studio_gap_fix_command(self):
        from aksara.studio.models import StudioGapFixCommand

        cmd = StudioGapFixCommand(description="Install X", command="pip install x")
        assert cmd.description == "Install X"
        assert cmd.env_required == []

    def test_studio_gap_issue_construction(self):
        from aksara.studio.models import StudioGapIssue

        issue = StudioGapIssue(
            category="db",
            severity="error",
            code="DB_NO_URL",
            title="No URL",
            message="DATABASE_URL not set",
        )
        assert issue.is_blocking is False  # default

    def test_studio_gap_analysis_stats(self):
        from aksara.studio.models import StudioGapAnalysisStats

        stats = StudioGapAnalysisStats(critical=1, error=2, warning=3, info=4, total=10)
        assert stats.total == 10

    def test_studio_gap_analysis_report(self):
        from aksara.studio.models import StudioGapAnalysisReport, StudioGapAnalysisStats

        report = StudioGapAnalysisReport(
            issues=[],
            stats=StudioGapAnalysisStats(),
            categories_checked=["db"],
            summary_line="All clear",
            timestamp="2024-01-01T00:00:00Z",
            duration_ms=42.0,
        )
        assert report.summary_line == "All clear"
        assert report.duration_ms == 42.0

    def test_studio_gap_analysis_run_response_ok(self):
        from aksara.studio.models import StudioGapAnalysisRunResponse

        resp = StudioGapAnalysisRunResponse(
            triggered_at="2024-01-01T00:00:00Z",
            status="ok",
        )
        assert resp.status == "ok"
        assert resp.error is None

    def test_studio_gap_analysis_run_response_error(self):
        from aksara.studio.models import StudioGapAnalysisRunResponse

        resp = StudioGapAnalysisRunResponse(
            triggered_at="2024-01-01T00:00:00Z",
            status="error",
            error="Something went wrong",
        )
        assert resp.status == "error"
        assert resp.error == "Something went wrong"


# ---------------------------------------------------------------------------
# 14. Studio Utils Builder Tests
# ---------------------------------------------------------------------------


class TestStudioGapUtils:
    """Tests for studio utils builder functions."""

    def _make_issue(self, severity="warning", category="db"):
        from aksara.gapanalysis import GapIssue

        return GapIssue(
            category=category,
            severity=severity,
            code=f"TEST_{severity.upper()}",
            title="Test Issue",
            message="Test message",
        )

    def _make_report(self, issues=None):
        from aksara.gapanalysis import GapAnalysisReport

        report = GapAnalysisReport(categories_checked=["db"])
        for issue in (issues or []):
            report.add(issue)
        return report

    def test_build_studio_gap_issue_basic(self):
        from aksara.studio.utils import build_studio_gap_issue

        issue = self._make_issue()
        studio_issue = build_studio_gap_issue(issue)
        assert studio_issue.category == "db"
        assert studio_issue.severity == "warning"
        assert studio_issue.code == "TEST_WARNING"

    def test_build_studio_gap_issue_is_blocking_inherited(self):
        from aksara.studio.utils import build_studio_gap_issue

        issue = self._make_issue(severity="critical")
        studio_issue = build_studio_gap_issue(issue)
        assert studio_issue.is_blocking is True

    def test_build_studio_gap_analysis_report_structure(self):
        from aksara.studio.utils import build_studio_gap_analysis_report

        report = self._make_report([self._make_issue("error")])
        studio_report = build_studio_gap_analysis_report(report)
        assert len(studio_report.issues) == 1
        assert studio_report.stats.error == 1
        assert studio_report.stats.total == 1
        assert "db" in studio_report.categories_checked

    def test_build_studio_gap_analysis_report_summary_line(self):
        from aksara.studio.utils import build_studio_gap_analysis_report

        report = self._make_report()
        studio_report = build_studio_gap_analysis_report(report)
        assert "All clear" in studio_report.summary_line

    def test_build_studio_gap_analysis_report_timestamp_is_str(self):
        from aksara.studio.utils import build_studio_gap_analysis_report

        report = self._make_report()
        studio_report = build_studio_gap_analysis_report(report)
        assert isinstance(studio_report.timestamp, str)
        assert len(studio_report.timestamp) > 0

    def test_run_and_build_gap_analysis_returns_studio_report(self):
        from aksara.studio.utils import run_and_build_gap_analysis
        from aksara.studio.models import StudioGapAnalysisReport

        with patch("aksara.gapanalysis._lazy_settings", return_value=MagicMock()):
            studio_report = run_async(run_and_build_gap_analysis(categories=["imports"]))
        assert isinstance(studio_report, StudioGapAnalysisReport)


# ---------------------------------------------------------------------------
# 15. CLI Command Tests
# ---------------------------------------------------------------------------


class TestGapsCliRun:
    """Tests for `aksara gaps run` command."""

    def _get_cli(self):
        from aksara.cli.main import cli
        return cli

    def test_gaps_run_pretty_no_issues(self):
        """When no issues found, should print 'No gaps found' and exit 0."""
        from aksara.gapanalysis import GapAnalysisReport

        mock_report = GapAnalysisReport()
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "run"])
        assert result.exit_code == 0
        assert "No gaps" in result.output or "All clear" in result.output or "clean" in result.output.lower()

    def test_gaps_run_exits_0_warning_only(self):
        """Warnings should not cause non-zero exit."""
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="warning", code="W", title="Warn", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "run"])
        assert result.exit_code == 0

    def test_gaps_run_exits_1_on_error(self):
        """Error severity should cause exit 1."""
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="error", code="E", title="Err", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "run"])
        assert result.exit_code == 1

    def test_gaps_run_exits_1_on_critical(self):
        """Critical severity should cause exit 1."""
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="critical", code="C", title="Crit", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "run"])
        assert result.exit_code == 1

    def test_gaps_run_json_output(self):
        """--format json should produce valid JSON."""
        import json

        from aksara.gapanalysis import GapAnalysisReport

        mock_report = GapAnalysisReport()
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            with patch("aksara.studio.utils.build_studio_gap_analysis_report") as mock_build:
                from aksara.studio.models import StudioGapAnalysisReport, StudioGapAnalysisStats

                mock_build.return_value = StudioGapAnalysisReport(
                    summary_line="All clear",
                    timestamp="2024-01-01T00:00:00Z",
                    stats=StudioGapAnalysisStats(),
                )
                runner = CliRunner()
                result = runner.invoke(self._get_cli(), ["gaps", "run", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary_line" in data

    def test_gaps_run_categories_option(self):
        """--categories option should be accepted."""
        from aksara.gapanalysis import GapAnalysisReport

        mock_report = GapAnalysisReport()
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report) as mock_func:
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "run", "--categories", "db,imports"])
        assert result.exit_code == 0


class TestGapsCliSummary:
    """Tests for `aksara gaps summary` command."""

    def _get_cli(self):
        from aksara.cli.main import cli
        return cli

    def test_gaps_summary_no_issues(self):
        from aksara.gapanalysis import GapAnalysisReport

        mock_report = GapAnalysisReport()
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "summary"])
        assert result.exit_code == 0
        assert "All clear" in result.output or "clean" in result.output.lower() or "no gaps" in result.output.lower()

    def test_gaps_summary_shows_counts(self):
        from aksara.gapanalysis import GapIssue, GapAnalysisReport

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="warning", code="W", title="Warn", message="m"))
        mock_report.add(GapIssue(category="db", severity="warning", code="W2", title="Warn2", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "summary"])
        assert "2" in result.output


class TestGapsCliJson:
    """Tests for `aksara gaps json` command."""

    def _get_cli(self):
        from aksara.cli.main import cli
        return cli

    def test_gaps_json_output_is_valid_json(self):
        import json

        from aksara.gapanalysis import GapAnalysisReport

        mock_report = GapAnalysisReport()
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            with patch("aksara.studio.utils.build_studio_gap_analysis_report") as mock_build:
                from aksara.studio.models import StudioGapAnalysisReport, StudioGapAnalysisStats

                mock_build.return_value = StudioGapAnalysisReport(
                    summary_line="All clear",
                    timestamp="2024-01-01T00:00:00Z",
                    stats=StudioGapAnalysisStats(),
                )
                runner = CliRunner()
                result = runner.invoke(self._get_cli(), ["gaps", "json"])
        data = json.loads(result.output)
        assert isinstance(data, dict)


class TestGapsCliListErrors:
    """Tests for `aksara gaps list-errors` command."""

    def _get_cli(self):
        from aksara.cli.main import cli
        return cli

    def test_list_errors_no_errors_exits_0(self):
        from aksara.gapanalysis import GapAnalysisReport, GapIssue

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="info", code="I", title="t", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "list-errors"])
        assert result.exit_code == 0

    def test_list_errors_with_errors_exits_1(self):
        from aksara.gapanalysis import GapAnalysisReport, GapIssue

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="error", code="E", title="Err", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "list-errors"])
        assert result.exit_code == 1

    def test_list_errors_json_output(self):
        import json

        from aksara.gapanalysis import GapAnalysisReport, GapIssue

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="error", code="E", title="Err", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "list-errors", "--format", "json"])
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["code"] == "E"


class TestGapsCliListCritical:
    """Tests for `aksara gaps list-critical` command."""

    def _get_cli(self):
        from aksara.cli.main import cli
        return cli

    def test_list_critical_no_critical_exits_0(self):
        from aksara.gapanalysis import GapAnalysisReport, GapIssue

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="error", code="E", title="t", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "list-critical"])
        assert result.exit_code == 0

    def test_list_critical_with_critical_exits_1(self):
        from aksara.gapanalysis import GapAnalysisReport, GapIssue

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="critical", code="C", title="Crit", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "list-critical"])
        assert result.exit_code == 1


class TestGapsCliFixPlan:
    """Tests for `aksara gaps fix-plan` command."""

    def _get_cli(self):
        from aksara.cli.main import cli
        return cli

    def test_fix_plan_no_actionable(self):
        from aksara.gapanalysis import GapAnalysisReport, GapIssue

        mock_report = GapAnalysisReport()
        mock_report.add(GapIssue(category="db", severity="warning", code="W", title="t", message="m"))
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "fix-plan"])
        assert result.exit_code == 0
        assert "No actionable" in result.output

    def test_fix_plan_with_actionable_shows_commands(self):
        from aksara.gapanalysis import GapAnalysisReport, GapIssue, GapFixCommand

        mock_report = GapAnalysisReport()
        mock_report.add(
            GapIssue(
                category="db",
                severity="error",
                code="E",
                title="Error title",
                message="m",
                fix_commands=[GapFixCommand(description="Install it", command="pip install foo")],
            )
        )
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "fix-plan"])
        assert "pip install foo" in result.output

    def test_fix_plan_json(self):
        import json

        from aksara.gapanalysis import GapAnalysisReport, GapIssue, GapFixCommand

        mock_report = GapAnalysisReport()
        mock_report.add(
            GapIssue(
                category="db",
                severity="error",
                code="E",
                title="t",
                message="m",
                fix_commands=[GapFixCommand(description="d", command="cmd")],
            )
        )
        with patch("aksara.cli.main._run_gap_analysis_sync", return_value=mock_report):
            runner = CliRunner()
            result = runner.invoke(self._get_cli(), ["gaps", "fix-plan", "--format", "json"])
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1


# ---------------------------------------------------------------------------
# 16. Version Bump Verification
# ---------------------------------------------------------------------------


class TestVersionBump:
    """Verify the version was correctly bumped to v0.5.27."""

    def test_library_version(self):
        from aksara._version import __version__

        assert __version__ == "0.6.0"

    def test_aksara_package_version(self):
        import aksara

        assert aksara.__version__ == "0.6.0"

    def test_cli_version(self):
        from aksara.cli.main import CLI_VERSION

        assert CLI_VERSION == "0.6.0"
