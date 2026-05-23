"""
Tests for aksara doctor security-check.

Round 1: config-level checks, matrix validation, CLI integration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.security.checks import (
    SecurityCheckReport,
    check_ai_field_defaults,
    check_cookies,
    check_cors,
    check_debug_mode,
    check_mcp_exposure,
    check_rate_limits,
    check_secret_key,
    check_security_matrix,
    check_studio_exposure,
    looks_like_weak_secret,
    run_security_checks,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_MATRIX_PATH = REPO_ROOT / "security" / "security_matrix.example.yml"


# ---------------------------------------------------------------------------
# Unit tests for individual checks
# ---------------------------------------------------------------------------


class TestLooksLikeWeakSecret:
    def test_none_is_weak(self):
        assert looks_like_weak_secret(None)

    def test_empty_string_is_weak(self):
        assert looks_like_weak_secret("")

    def test_known_defaults_are_weak(self):
        for val in ("change-me", "changeme", "secret", "dev", "development",
                    "test", "your-secret-key", "replace-me"):
            assert looks_like_weak_secret(val), f"Expected '{val}' to be weak"

    def test_short_value_is_weak(self):
        assert looks_like_weak_secret("abc123")  # < 32 chars
        assert looks_like_weak_secret("x" * 31)  # exactly 31

    def test_strong_key_is_not_weak(self):
        strong = "a" * 64
        assert not looks_like_weak_secret(strong)

    def test_random_token_is_not_weak(self):
        import secrets
        token = secrets.token_urlsafe(48)
        assert not looks_like_weak_secret(token)


class TestCheckSecretKey:
    def test_no_secret_key_fails(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove both possible env vars
            env = {k: v for k, v in os.environ.items()
                   if k not in ("AKSARA_SECRET_KEY", "SECRET_KEY")}
            with patch.dict(os.environ, env, clear=True):
                result = check_secret_key()
        assert result.status in ("fail", "block")
        assert result.severity == "critical"

    def test_weak_secret_key_fails(self):
        with patch.dict(os.environ, {"SECRET_KEY": "change-me"}, clear=False):
            result = check_secret_key()
        assert result.status in ("fail", "block")
        assert result.severity == "critical"

    def test_strong_secret_key_passes(self):
        with patch.dict(os.environ, {"SECRET_KEY": "a" * 64}, clear=False):
            result = check_secret_key()
        assert result.status == "pass"


class TestCheckDebugMode:
    def test_debug_true_warns_in_dev(self):
        mock_settings = MagicMock()
        mock_settings.debug = True
        with patch("aksara.security.checks.get_setting", return_value=True):
            result = check_debug_mode(is_production=False)
        assert result.status == "warn"

    def test_debug_true_blocks_in_production(self):
        with patch("aksara.security.checks.get_setting", return_value=True):
            result = check_debug_mode(is_production=True)
        assert result.status == "block"

    def test_debug_false_passes(self):
        with patch("aksara.security.checks.get_setting", return_value=False):
            result = check_debug_mode(is_production=False)
        assert result.status == "pass"


class TestCheckCors:
    def test_wildcard_with_credentials_fails(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL_ORIGINS": "true", "CORS_ALLOW_CREDENTIALS": "true"}):
            result = check_cors(is_production=False)
        assert result.status in ("fail", "block")

    def test_wildcard_with_credentials_blocks_in_production(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL_ORIGINS": "true", "CORS_ALLOW_CREDENTIALS": "true"}):
            result = check_cors(is_production=True)
        assert result.status == "block"

    def test_wildcard_without_credentials_warns(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL_ORIGINS": "true", "CORS_ALLOW_CREDENTIALS": "false"}):
            result = check_cors(is_production=False)
        assert result.status == "warn"

    def test_no_cors_issues_passes(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL_ORIGINS": "false", "CORS_ALLOW_CREDENTIALS": "false"}):
            with patch("aksara.security.checks.get_setting", return_value=[]):
                result = check_cors(is_production=False)
        assert result.status == "pass"


class TestCheckStudioExposure:
    def test_studio_exposed_without_auth_fails(self):
        def fake_get_setting(name, default=None):
            return {
                "enable_studio": True,
                "studio_expose_in_production": True,
                "studio_require_auth": False,
            }.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            result = check_studio_exposure(is_production=False)
        assert result.status in ("fail", "block")

    def test_studio_exposed_without_auth_blocks_in_production(self):
        def fake_get_setting(name, default=None):
            return {
                "enable_studio": True,
                "studio_expose_in_production": True,
                "studio_require_auth": False,
            }.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            result = check_studio_exposure(is_production=True)
        assert result.status == "block"

    def test_studio_not_exposed_passes(self):
        def fake_get_setting(name, default=None):
            return {
                "enable_studio": False,
                "studio_expose_in_production": False,
                "studio_require_auth": True,
            }.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            result = check_studio_exposure(is_production=False)
        assert result.status == "pass"


class TestCheckMcpExposure:
    def test_mcp_enabled_without_token_warns_in_dev(self):
        def fake_get_setting(name, default=None):
            return {"mcp_enabled": True, "ai_agent_token": None}.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            with patch.dict(os.environ, {}, clear=False):
                result = check_mcp_exposure(is_production=False)
        assert result.status == "warn"

    def test_mcp_enabled_without_token_blocks_in_production(self):
        def fake_get_setting(name, default=None):
            return {"mcp_enabled": True, "ai_agent_token": None}.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            with patch.dict(os.environ, {"AKSARA_MCP_REQUIRE_AUTH": "false", "AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "false"}):
                result = check_mcp_exposure(is_production=True)
        assert result.status == "block"

    def test_mcp_disabled_passes(self):
        def fake_get_setting(name, default=None):
            return {"mcp_enabled": False, "ai_agent_token": None}.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            result = check_mcp_exposure()
        assert result.status == "pass"

    def test_mcp_enabled_with_token_passes(self):
        def fake_get_setting(name, default=None):
            return {"mcp_enabled": True, "ai_agent_token": "strong-secret-token-abc"}.get(name, default)
        with patch("aksara.security.checks.get_setting", side_effect=fake_get_setting):
            result = check_mcp_exposure()
        assert result.status == "pass"


class TestCheckSecurityMatrix:
    def test_valid_matrix_passes(self):
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=EXAMPLE_MATRIX_PATH):
            result = check_security_matrix(is_production=False)
        assert result.status == "pass", f"Expected pass but got {result.status}: {result.message}"

    def test_missing_matrix_warns_in_dev(self, tmp_path, monkeypatch):
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "false"}):
                result = check_security_matrix(is_production=False)
        assert result.status == "warn"

    def test_missing_matrix_warns_in_production(self):
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "false"}):
                result = check_security_matrix(is_production=True)
        assert result.status == "warn"

    def test_missing_matrix_blocks_when_require_flag_set(self):
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "true"}):
                result = check_security_matrix(is_production=False)
        assert result.status == "block"

    def test_missing_matrix_blocks_in_production_when_require_flag_set(self):
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=None):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "true"}):
                result = check_security_matrix(is_production=True)
        assert result.status == "block"

    def test_invalid_matrix_fails_in_dev(self, tmp_path):
        bad = tmp_path / "security_matrix.yml"
        bad.write_text("version: 1\n", encoding="utf-8")
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=bad):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "false"}):
                result = check_security_matrix(is_production=False)
        assert result.status in ("fail", "block")

    def test_invalid_matrix_fails_in_production(self, tmp_path):
        bad = tmp_path / "security_matrix.yml"
        bad.write_text("version: 1\n", encoding="utf-8")
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=bad):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "false"}):
                result = check_security_matrix(is_production=True)
        assert result.status == "fail"

    def test_invalid_matrix_blocks_when_require_flag_set(self, tmp_path):
        bad = tmp_path / "security_matrix.yml"
        bad.write_text("version: 1\n", encoding="utf-8")
        with patch("aksara.security.matrix._find_default_matrix_path", return_value=bad):
            with patch.dict(os.environ, {"AKSARA_REQUIRE_SECURITY_MATRIX": "true"}):
                result = check_security_matrix(is_production=True)
        assert result.status == "block"


# ---------------------------------------------------------------------------
# Aggregator tests
# ---------------------------------------------------------------------------


class TestRunSecurityChecks:
    def test_returns_report_with_results(self):
        report = run_security_checks(is_production=False)
        assert isinstance(report, SecurityCheckReport)
        assert len(report.results) > 0

    def test_safe_config_produces_no_blocks(self):
        """A minimal safe config should not produce blocking issues."""
        def safe_get_setting(name, default=None):
            return {
                "debug": False,
                "studio_expose_in_production": False,
                "enable_studio": False,
                "studio_require_auth": True,
                "mcp_enabled": False,
                "ai_agent_token": None,
                "studio_allowed_origins": [],
                "cookie_secure": True,
                "admin_rate_limit_enabled": True,
            }.get(name, default)

        with patch("aksara.security.checks.get_setting", side_effect=safe_get_setting):
            with patch.dict(os.environ, {"SECRET_KEY": "a" * 64,
                                          "CORS_ALLOW_ALL_ORIGINS": "false",
                                          "CORS_ALLOW_CREDENTIALS": "false",
                                          "AKSARA_REQUIRE_SECURITY_MATRIX": "false"}):
                report = run_security_checks(is_production=False)

        blocks = [r for r in report.results if r.status == "block"]
        assert blocks == [], f"Unexpected blocks with safe config: {[b.id for b in blocks]}"


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestDoctorSecurityCheckCLI:
    """Tests for `aksara doctor security-check` CLI command."""

    def test_security_check_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "security-check", "--help"])
        assert result.exit_code == 0
        assert "security" in result.output.lower()

    def test_security_check_runs_and_produces_output(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "security-check"])
        # Should run and produce some output regardless of exit code
        assert len(result.output) > 0

    def test_security_check_json_output(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "security-check", "--format", "json"])
        # Exit code may be 0 or 1 depending on local config; just check JSON structure
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail(f"security-check --format json produced invalid JSON: {result.output!r}")
        assert "check" in data
        assert data["check"] == "security-check"
        assert "results" in data
        assert "status" in data
        assert "summary" in data

    def test_security_check_json_has_required_fields(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "security-check", "--format", "json"])
        data = json.loads(result.output)
        assert isinstance(data["results"], list)
        if data["results"]:
            first = data["results"][0]
            for field in ("id", "title", "severity", "status", "message", "recommendation"):
                assert field in first, f"Missing field '{field}' in result"

    def test_security_check_reports_missing_secret_key(self):
        runner = CliRunner()
        # Clear both SECRET_KEY env vars
        env = {k: v for k, v in os.environ.items()
               if k not in ("AKSARA_SECRET_KEY", "SECRET_KEY")}
        with patch.dict(os.environ, env, clear=True):
            result = runner.invoke(cli, ["doctor", "security-check", "--format", "json"])
        data = json.loads(result.output)
        secret_result = next((r for r in data["results"] if r["id"] == "security.secret_key"), None)
        assert secret_result is not None
        assert secret_result["status"] in ("fail", "block", "warn")

    def test_security_check_reports_weak_secret_key(self):
        runner = CliRunner()
        with patch.dict(os.environ, {"SECRET_KEY": "weak"}, clear=False):
            result = runner.invoke(cli, ["doctor", "security-check", "--format", "json"])
        data = json.loads(result.output)
        secret_result = next((r for r in data["results"] if r["id"] == "security.secret_key"), None)
        assert secret_result is not None
        assert secret_result["status"] in ("fail", "block")

    def test_security_check_warns_on_debug_true(self):
        runner = CliRunner()
        with patch("aksara.security.checks.get_setting") as mock_get:
            def side_effect(name, default=None):
                if name == "debug":
                    return True
                return default
            mock_get.side_effect = side_effect
            result = runner.invoke(cli, ["doctor", "security-check", "--format", "json"])
        data = json.loads(result.output)
        debug_result = next((r for r in data["results"] if r["id"] == "security.debug_mode"), None)
        assert debug_result is not None
        assert debug_result["status"] in ("warn", "fail", "block")

    def test_security_check_reports_cors_wildcard_with_credentials(self):
        runner = CliRunner()
        with patch.dict(os.environ, {"CORS_ALLOW_ALL_ORIGINS": "true", "CORS_ALLOW_CREDENTIALS": "true"}):
            result = runner.invoke(cli, ["doctor", "security-check", "--format", "json"])
        data = json.loads(result.output)
        cors_result = next((r for r in data["results"] if r["id"] == "security.cors"), None)
        assert cors_result is not None
        assert cors_result["status"] in ("fail", "block")
