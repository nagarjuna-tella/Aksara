"""
Tests for aksara doctor production-check.

Round 1: production blocking conditions, CLI integration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.security.checks import run_security_checks

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_safe_settings():
    """Return safe get_setting mock values for a minimal production config."""
    return {
        "debug": False,
        "enable_studio": False,
        "studio_expose_in_production": False,
        "studio_require_auth": True,
        "mcp_enabled": False,
        "ai_agent_token": None,
        "studio_allowed_origins": [],
        "cookie_secure": True,
        "admin_rate_limit_enabled": True,
    }


def _patch_safe_env():
    """Return env vars for a safe production config."""
    return {
        "SECRET_KEY": "a" * 64,
        "CORS_ALLOW_ALL_ORIGINS": "false",
        "CORS_ALLOW_CREDENTIALS": "false",
        "AKSARA_MCP_REQUIRE_AUTH": "false",
        "AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "false",
        "AKSARA_AI_CONSOLE_ENABLED": "false",
        "AKSARA_REQUIRE_SECURITY_MATRIX": "false",
    }


# ---------------------------------------------------------------------------
# Unit tests for production-check blocking logic
# ---------------------------------------------------------------------------


class TestProductionCheckBlockingConditions:
    """Test that blocking conditions are correctly identified in production mode."""

    def test_debug_true_blocks_in_production(self):
        def fake_get_setting(name, default=None):
            s = dict(_make_safe_settings())
            s["debug"] = True
            return s.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            with patch.dict(os.environ, _patch_safe_env()):
                report = run_security_checks(is_production=True)
        blocked = [r for r in report.results if r.status == "block" and r.id == "security.debug_mode"]
        assert blocked, "Expected debug_mode to be blocked in production"

    def test_missing_secret_key_fails(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AKSARA_SECRET_KEY", "SECRET_KEY")}
        env.update({k: v for k, v in _patch_safe_env().items()
                    if k not in ("SECRET_KEY",)})
        with patch.dict(os.environ, env, clear=True):
            report = run_security_checks(is_production=True)
        sk_result = next((r for r in report.results if r.id == "security.secret_key"), None)
        assert sk_result is not None
        assert sk_result.status in ("fail", "block")

    def test_weak_secret_key_fails(self):
        safe = dict(_patch_safe_env())
        safe["SECRET_KEY"] = "short"
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, safe):
                report = run_security_checks(is_production=True)
        sk_result = next((r for r in report.results if r.id == "security.secret_key"), None)
        assert sk_result is not None
        assert sk_result.status in ("fail", "block")

    def test_cors_wildcard_with_credentials_blocks_in_production(self):
        safe_env = dict(_patch_safe_env())
        safe_env["CORS_ALLOW_ALL_ORIGINS"] = "true"
        safe_env["CORS_ALLOW_CREDENTIALS"] = "true"
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, safe_env):
                report = run_security_checks(is_production=True)
        cors_result = next((r for r in report.results if r.id == "security.cors"), None)
        assert cors_result is not None
        assert cors_result.status == "block"

    def test_studio_exposed_without_auth_blocks_in_production(self):
        settings = dict(_make_safe_settings())
        settings["enable_studio"] = True
        settings["studio_expose_in_production"] = True
        settings["studio_require_auth"] = False

        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: settings.get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                report = run_security_checks(is_production=True)
        studio_result = next((r for r in report.results if r.id == "security.studio_exposure"), None)
        assert studio_result is not None
        assert studio_result.status == "block"

    def test_mcp_enabled_without_auth_blocks_in_production(self):
        settings = dict(_make_safe_settings())
        settings["mcp_enabled"] = True
        settings["ai_agent_token"] = None

        safe_env = dict(_patch_safe_env())
        safe_env["AKSARA_MCP_REQUIRE_AUTH"] = "false"
        safe_env["AKSARA_MCP_REQUIRE_SCOPED_TOKENS"] = "false"

        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: settings.get(n, d)):
            with patch.dict(os.environ, safe_env):
                report = run_security_checks(is_production=True)
        mcp_result = next((r for r in report.results if r.id == "security.mcp_exposure"), None)
        assert mcp_result is not None
        assert mcp_result.status == "block"

    def test_missing_matrix_warns_in_production(self):
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch("aksara.security.checks.get_setting",
                       side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
                with patch.dict(os.environ, _patch_safe_env()):
                    report = run_security_checks(is_production=True)
        matrix_result = next((r for r in report.results if r.id == "security.matrix"), None)
        assert matrix_result is not None
        assert matrix_result.status == "warn"

    def test_missing_matrix_blocks_when_require_flag_set(self):
        safe_env = dict(_patch_safe_env())
        safe_env["AKSARA_REQUIRE_SECURITY_MATRIX"] = "true"
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch("aksara.security.checks.get_setting",
                       side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
                with patch.dict(os.environ, safe_env):
                    report = run_security_checks(is_production=True)
        matrix_result = next((r for r in report.results if r.id == "security.matrix"), None)
        assert matrix_result is not None
        assert matrix_result.status == "block"

    def test_invalid_matrix_fails_in_production(self, tmp_path):
        bad = tmp_path / "security_matrix.yml"
        bad.write_text("version: 1\n", encoding="utf-8")
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=bad):
            with patch("aksara.security.checks.get_setting",
                       side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
                with patch.dict(os.environ, _patch_safe_env()):
                    report = run_security_checks(is_production=True)
        matrix_result = next((r for r in report.results if r.id == "security.matrix"), None)
        assert matrix_result is not None
        assert matrix_result.status == "fail"

    def test_invalid_matrix_blocks_when_require_flag_set(self, tmp_path):
        bad = tmp_path / "security_matrix.yml"
        bad.write_text("version: 1\n", encoding="utf-8")
        safe_env = dict(_patch_safe_env())
        safe_env["AKSARA_REQUIRE_SECURITY_MATRIX"] = "true"
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=bad):
            with patch("aksara.security.checks.get_setting",
                       side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
                with patch.dict(os.environ, safe_env):
                    report = run_security_checks(is_production=True)
        matrix_result = next((r for r in report.results if r.id == "security.matrix"), None)
        assert matrix_result is not None
        assert matrix_result.status == "block"

    def test_report_has_failures_when_blocking(self):
        """Report.has_failures is True when any block exists."""
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: {**_make_safe_settings(), "debug": True}.get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                report = run_security_checks(is_production=True)
        assert report.has_failures or report.has_blocks

    def test_safe_production_config_has_no_blocks(self):
        """A clean production config should have no blocking results."""
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                report = run_security_checks(is_production=True)
        blocks = [r for r in report.results if r.status == "block"]
        assert blocks == [], f"Unexpected blocks with safe config: {[b.id for b in blocks]}"

    def test_production_report_should_exit_nonzero_when_blocked(self):
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: {**_make_safe_settings(), "debug": True}.get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                report = run_security_checks(is_production=True)
        assert report.should_exit_nonzero

    def test_production_report_should_exit_zero_when_safe(self):
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                report = run_security_checks(is_production=True)
        assert not report.should_exit_nonzero


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestDoctorProductionCheckCLI:
    """Tests for `aksara doctor production-check` CLI command."""

    def test_production_check_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "production-check", "--help"])
        assert result.exit_code == 0
        assert "production" in result.output.lower()

    def test_production_check_runs_and_produces_output(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "production-check"])
        assert len(result.output) > 0

    def test_production_check_json_output(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail(f"production-check --format json produced invalid JSON: {result.output!r}")
        assert data["check"] == "production-check"
        assert "results" in data
        assert "status" in data
        assert "summary" in data
        assert "exit_code" in data

    def test_production_check_json_exit_code_field(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert data["exit_code"] in (0, 1)
        # exit_code in JSON must match actual process exit code
        assert data["exit_code"] == result.exit_code

    def test_production_check_blocks_debug_true(self):
        runner = CliRunner()
        with patch("aksara.security.checks.get_setting") as mock_get:
            def side_effect(name, default=None):
                if name == "debug":
                    return True
                return _make_safe_settings().get(name, default)
            mock_get.side_effect = side_effect
            with patch.dict(os.environ, _patch_safe_env()):
                result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 1, "production-check must exit 1 when debug=True"
        debug_result = next((r for r in data["results"] if r["id"] == "security.debug_mode"), None)
        assert debug_result is not None
        assert debug_result["status"] == "block"

    def test_production_check_blocks_weak_secret_key(self):
        runner = CliRunner()
        safe_env = dict(_patch_safe_env())
        safe_env["SECRET_KEY"] = "weak"
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, safe_env):
                result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 1
        sk_result = next((r for r in data["results"] if r["id"] == "security.secret_key"), None)
        assert sk_result is not None
        assert sk_result["status"] in ("fail", "block")

    def test_production_check_blocks_cors_wildcard_with_credentials(self):
        runner = CliRunner()
        safe_env = dict(_patch_safe_env())
        safe_env["CORS_ALLOW_ALL_ORIGINS"] = "true"
        safe_env["CORS_ALLOW_CREDENTIALS"] = "true"
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, safe_env):
                result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 1
        cors_result = next((r for r in data["results"] if r["id"] == "security.cors"), None)
        assert cors_result is not None
        assert cors_result["status"] == "block"

    def test_production_check_blocks_studio_exposed_without_auth(self):
        runner = CliRunner()
        settings = {**_make_safe_settings(), "enable_studio": True,
                    "studio_expose_in_production": True, "studio_require_auth": False}
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: settings.get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 1

    def test_production_check_blocks_mcp_without_auth(self):
        runner = CliRunner()
        settings = {**_make_safe_settings(), "mcp_enabled": True, "ai_agent_token": None}
        safe_env = dict(_patch_safe_env())
        safe_env["AKSARA_MCP_REQUIRE_AUTH"] = "false"
        safe_env["AKSARA_MCP_REQUIRE_SCOPED_TOKENS"] = "false"
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: settings.get(n, d)):
            with patch.dict(os.environ, safe_env):
                result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 1

    def test_production_check_warns_missing_matrix(self):
        runner = CliRunner()
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch("aksara.security.checks.get_setting",
                       side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
                with patch.dict(os.environ, _patch_safe_env()):
                    result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        matrix_result = next((r for r in data["results"] if r["id"] == "security.matrix"), None)
        assert matrix_result is not None
        assert matrix_result["status"] == "warn"

    def test_production_check_blocks_missing_matrix_when_required(self):
        runner = CliRunner()
        safe_env = dict(_patch_safe_env())
        safe_env["AKSARA_REQUIRE_SECURITY_MATRIX"] = "true"
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch("aksara.security.checks.get_setting",
                       side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
                with patch.dict(os.environ, safe_env):
                    result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 1
        matrix_result = next((r for r in data["results"] if r["id"] == "security.matrix"), None)
        assert matrix_result is not None
        assert matrix_result["status"] == "block"

    def test_production_check_passes_with_safe_config(self):
        runner = CliRunner()
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: _make_safe_settings().get(n, d)):
            with patch.dict(os.environ, _patch_safe_env()):
                result = runner.invoke(cli, ["doctor", "production-check", "--format", "json"])
        data = json.loads(result.output)
        assert result.exit_code == 0, (
            f"Expected exit 0 with safe config but got {result.exit_code}. "
            f"Results: {[r for r in data['results'] if r['status'] in ('block', 'fail')]}"
        )
