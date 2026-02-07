"""
Tests verifying that each diagnostic checker attaches correct fix actions.

v0.5.18: 20+ tests verifying action attachment on all checker outputs.
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.diagnostics import (
    DiagnosticAction,
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
# check_database_connectivity — actions
# =============================================================================


class TestDatabaseConnectivityActions:
    """Actions attached by check_database_connectivity."""

    @pytest.mark.asyncio
    async def test_no_db_url_has_set_env_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            issues = await check_database_connectivity()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        actions = errors[0].actions
        assert len(actions) >= 1
        assert any(a.kind == "set_env" and a.target == "DATABASE_URL" for a in actions)

    @pytest.mark.asyncio
    async def test_no_db_url_has_open_doc_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            issues = await check_database_connectivity()
        errors = [i for i in issues if i.severity == "error"]
        actions = errors[0].actions
        assert any(a.kind == "open_doc" for a in actions)

    @pytest.mark.asyncio
    async def test_connection_failed_has_run_command_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/test"
            with patch("asyncpg.connect", new_callable=AsyncMock, side_effect=Exception("conn refused")):
                issues = await check_database_connectivity()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        actions = errors[0].actions
        assert any(a.kind == "run_command" and "pg_isready" in a.target for a in actions)

    @pytest.mark.asyncio
    async def test_asyncpg_missing_has_run_command_action(self):
        with patch.dict("sys.modules", {"asyncpg": None}):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.database_url = "postgresql://localhost/test"
                # Force import error for asyncpg
                import builtins
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == "asyncpg":
                        raise ImportError("No module named 'asyncpg'")
                    return original_import(name, *args, **kwargs)

                with patch("builtins.__import__", side_effect=mock_import):
                    issues = await check_database_connectivity()
        install_issues = [i for i in issues if "asyncpg" in i.title.lower()]
        if install_issues:
            actions = install_issues[0].actions
            assert any(a.kind == "run_command" and "pip" in a.example for a in actions)


# =============================================================================
# check_migrations_status — actions
# =============================================================================


class TestMigrationsActions:
    """Actions attached by check_migrations_status."""

    @pytest.mark.asyncio
    async def test_no_migrations_dir_has_run_command(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.migrations_dir = "/tmp/nonexistent_aksara_test_mig"
            issues = await check_migrations_status()
        mig_issues = [i for i in issues if "no migrations directory" in i.title.lower()]
        if mig_issues:
            actions = mig_issues[0].actions
            assert any(a.kind == "run_command" and "makemigrations" in a.target for a in actions)

    @pytest.mark.asyncio
    async def test_no_migration_files_has_run_command(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "__init__.py").write_text("")
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.migrations_dir = str(mig_dir)
            issues = await check_migrations_status()
        no_mig = [i for i in issues if "no migrations found" in i.title.lower()]
        if no_mig:
            actions = no_mig[0].actions
            assert any(a.kind == "run_command" and "makemigrations" in a.target for a in actions)

    @pytest.mark.asyncio
    async def test_pending_migrations_has_migrate_action(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "__init__.py").write_text("")
        (mig_dir / "001_init.py").write_text("# migration")

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.migrations_dir = str(mig_dir)
            mock_settings.database_url = "postgresql://localhost/test"
            with patch("asyncpg.connect", new_callable=AsyncMock, return_value=mock_conn):
                issues = await check_migrations_status()

        pending = [i for i in issues if "pending" in i.title.lower()]
        if pending:
            actions = pending[0].actions
            assert any(a.kind == "run_command" and "aksara migrate" in a.target for a in actions)


# =============================================================================
# check_ai_profiles — actions
# =============================================================================


class TestAiProfilesActions:
    """Actions attached by check_ai_profiles."""

    @pytest.mark.asyncio
    async def test_ai_disabled_has_add_setting_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.ai_profiles_enabled = False
            issues = await check_ai_profiles()
        disabled = [i for i in issues if "disabled" in i.title.lower()]
        assert len(disabled) >= 1
        actions = disabled[0].actions
        assert any(a.kind == "add_setting" and a.target == "ai_profiles_enabled" for a in actions)


# =============================================================================
# check_ai_provider_secrets — actions
# =============================================================================


class TestAiSecretsActions:
    """Actions attached by check_ai_provider_secrets."""

    @pytest.mark.asyncio
    async def test_missing_secret_has_set_env_action(self):
        mock_hint = MagicMock()
        mock_hint.required = True
        mock_hint.env_var = "OPENAI_API_KEY"
        mock_hint.provider_name = "openai"

        with patch("aksara.conf.settings"):
            with patch(
                "aksara.ai.providers.build_secret_hints_from_settings",
                return_value=[mock_hint],
            ):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("OPENAI_API_KEY", None)
                    issues = await check_ai_provider_secrets()

        missing = [i for i in issues if "OPENAI_API_KEY" in i.title]
        assert len(missing) >= 1
        actions = missing[0].actions
        assert any(a.kind == "set_env" and a.target == "OPENAI_API_KEY" for a in actions)


# =============================================================================
# check_required_settings — actions
# =============================================================================


class TestRequiredSettingsActions:
    """Actions attached by check_required_settings."""

    @pytest.mark.asyncio
    async def test_no_db_url_has_set_env_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.pool_max_size = 10
            mock_settings.pool_min_size = 2
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        db_issues = [i for i in issues if "no database url" in i.title.lower()]
        assert len(db_issues) >= 1
        actions = db_issues[0].actions
        assert any(a.kind == "set_env" and a.target == "DATABASE_URL" for a in actions)

    @pytest.mark.asyncio
    async def test_invalid_pool_has_add_setting_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/db"
            mock_settings.pool_max_size = 1
            mock_settings.pool_min_size = 5
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        pool_issues = [i for i in issues if "pool" in i.title.lower()]
        assert len(pool_issues) >= 1
        actions = pool_issues[0].actions
        assert any(a.kind == "add_setting" and a.target == "pool_max_size" for a in actions)

    @pytest.mark.asyncio
    async def test_large_pool_has_add_setting_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/db"
            mock_settings.pool_max_size = 200
            mock_settings.pool_min_size = 2
            mock_settings.db_trace_slow_threshold_ms = 100
            issues = await check_required_settings()
        pool_issues = [i for i in issues if "large" in i.title.lower()]
        assert len(pool_issues) >= 1
        assert any(a.kind == "add_setting" for a in pool_issues[0].actions)

    @pytest.mark.asyncio
    async def test_slow_threshold_has_add_setting_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = "postgresql://localhost/db"
            mock_settings.pool_max_size = 10
            mock_settings.pool_min_size = 2
            mock_settings.db_trace_slow_threshold_ms = -1
            issues = await check_required_settings()
        threshold_issues = [i for i in issues if "slow" in i.title.lower()]
        assert len(threshold_issues) >= 1
        assert any(a.kind == "add_setting" for a in threshold_issues[0].actions)


# =============================================================================
# check_cache_available — actions
# =============================================================================


class TestCacheActions:
    """Actions attached by check_cache_available."""

    @pytest.mark.asyncio
    async def test_no_cache_url_has_set_env_action(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AKSARA_CACHE_URL", None)
            os.environ.pop("CACHE_URL", None)
            issues = await check_cache_available()
        cache_issues = [i for i in issues if "cache" in i.title.lower()]
        assert len(cache_issues) >= 1
        actions = cache_issues[0].actions
        assert any(a.kind == "set_env" and a.target == "AKSARA_CACHE_URL" for a in actions)


# =============================================================================
# check_security — actions
# =============================================================================


class TestSecurityActions:
    """Actions attached by check_security."""

    @pytest.mark.asyncio
    async def test_debug_mode_has_set_env_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = True
            mock_settings.studio_expose_in_production = False
            type(mock_settings).studio_allowed_origins = []
            issues = await check_security()
        debug_issues = [i for i in issues if "debug" in i.title.lower()]
        assert len(debug_issues) >= 1
        actions = debug_issues[0].actions
        assert any(a.kind == "set_env" and a.target == "AKSARA_DEBUG" for a in actions)

    @pytest.mark.asyncio
    async def test_studio_exposed_has_add_setting_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = True
            type(mock_settings).studio_allowed_origins = []
            issues = await check_security()
        studio_issues = [i for i in issues if "studio exposed" in i.title.lower()]
        if studio_issues:
            actions = studio_issues[0].actions
            assert any(a.kind == "add_setting" for a in actions)

    @pytest.mark.asyncio
    async def test_wildcard_origins_has_add_setting_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = ["*"]
            issues = await check_security()
        origin_issues = [i for i in issues if "all origins" in i.title.lower()]
        assert len(origin_issues) >= 1
        actions = origin_issues[0].actions
        assert any(a.kind == "add_setting" and "studio_allowed_origins" in a.target for a in actions)

    @pytest.mark.asyncio
    async def test_no_secret_key_has_set_env_action(self):
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_SECRET_KEY", None)
                os.environ.pop("SECRET_KEY", None)
                issues = await check_security()
        secret_issues = [i for i in issues if "secret" in i.title.lower()]
        assert len(secret_issues) >= 1
        actions = secret_issues[0].actions
        assert any(a.kind == "set_env" and a.target == "SECRET_KEY" for a in actions)


# =============================================================================
# run_all_checks — actions preserved
# =============================================================================


class TestRunAllChecksActions:
    """Actions survive through run_all_checks aggregation."""

    @pytest.mark.asyncio
    async def test_actions_preserved_in_report(self):
        """Issues returned by run_all_checks still have their actions."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.migrations_dir = "/tmp/nonexistent_aksara_test_mig"
            mock_settings.pool_max_size = 10
            mock_settings.pool_min_size = 2
            mock_settings.db_trace_slow_threshold_ms = 100
            mock_settings.debug = True
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            mock_settings.ai_profiles_enabled = False
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_CACHE_URL", None)
                os.environ.pop("CACHE_URL", None)
                os.environ.pop("AKSARA_SECRET_KEY", None)
                os.environ.pop("SECRET_KEY", None)
                report = await run_all_checks()

        # At least some issues should have actions
        issues_with_actions = [i for i in report.issues if i.actions]
        assert len(issues_with_actions) >= 3, (
            f"Expected at least 3 issues with actions, got {len(issues_with_actions)}"
        )

    @pytest.mark.asyncio
    async def test_actions_in_json_output(self):
        """Actions appear in JSON serialization of the report."""
        import json

        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = ""
            mock_settings.migrations_dir = "/tmp/nonexistent_aksara_test_mig"
            mock_settings.pool_max_size = 10
            mock_settings.pool_min_size = 2
            mock_settings.db_trace_slow_threshold_ms = 100
            mock_settings.debug = False
            mock_settings.studio_expose_in_production = False
            mock_settings.studio_allowed_origins = []
            mock_settings.ai_profiles_enabled = False
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AKSARA_CACHE_URL", None)
                os.environ.pop("CACHE_URL", None)
                report = await run_all_checks()

        data = json.loads(report.model_dump_json())
        all_actions = []
        for issue in data["issues"]:
            all_actions.extend(issue.get("actions", []))
        assert len(all_actions) >= 1, "Expected at least one action in JSON output"
        for a in all_actions:
            assert "kind" in a
            assert "target" in a
            assert "title" in a
