"""
Tests for check_mcp_hardening — Round 4 doctor check.

Covers: production blocks for missing scoped tokens, TTL, audience, and
multi-tenant token binding; dev-mode warns; safe config passes;
MCP disabled auto-passes.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from aksara.security.checks import check_mcp_hardening, run_security_checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_settings():
    """Minimal safe settings dict — MCP disabled."""
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


def _mcp_enabled_settings():
    settings = _safe_settings()
    settings["mcp_enabled"] = True
    settings["ai_agent_token"] = "x" * 64
    return settings


_SAFE_MCP_ENV = {
    "SECRET_KEY": "a" * 64,
    "AKSARA_MCP_REQUIRE_AUTH": "true",
    "AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "true",
    "AKSARA_MCP_TOKEN_TTL_SECONDS": "900",
    "AKSARA_MCP_REQUIRE_AUDIENCE": "true",
    "AKSARA_MCP_TOKEN_AUDIENCE": "mcp",
    "AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS": "false",
    "AKSARA_MULTI_TENANT": "false",
    "CORS_ALLOW_ALL_ORIGINS": "false",
    "CORS_ALLOW_CREDENTIALS": "false",
    "AKSARA_AI_CONSOLE_ENABLED": "false",
}


def _patch_mcp_enabled(env_overrides=None):
    """Context manager combo: mcp_enabled settings + env."""
    env = {**_SAFE_MCP_ENV, **(env_overrides or {})}
    settings = _mcp_enabled_settings()
    return (
        patch("aksara.security.checks.get_setting",
              side_effect=lambda n, d=None: settings.get(n, d)),
        patch.dict(os.environ, env),
    )


# ---------------------------------------------------------------------------
# MCP disabled → always passes
# ---------------------------------------------------------------------------


class TestMCPHardeningDisabled:
    def test_mcp_disabled_hardening_check_passes(self):
        settings = _safe_settings()
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: settings.get(n, d)):
            with patch.dict(os.environ, _SAFE_MCP_ENV):
                result = check_mcp_hardening(is_production=True)
        assert result.status == "pass"
        assert result.id == "security.mcp_hardening"


# ---------------------------------------------------------------------------
# Production blocking conditions
# ---------------------------------------------------------------------------


class TestMCPHardeningProductionBlocks:
    def test_production_check_blocks_mcp_enabled_without_scoped_tokens(self):
        env = {**_SAFE_MCP_ENV, "AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "false"}
        sp, ep = _patch_mcp_enabled({"AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "false"})
        with sp, ep:
            result = check_mcp_hardening(is_production=True)
        assert result.status == "block"
        assert "scoped" in result.message.lower() or "token" in result.message.lower()

    def test_production_check_blocks_mcp_enabled_without_ttl(self):
        sp, ep = _patch_mcp_enabled({"AKSARA_MCP_TOKEN_TTL_SECONDS": ""})
        with sp:
            # Remove the TTL key entirely from env
            base = {k: v for k, v in _SAFE_MCP_ENV.items()
                    if k != "AKSARA_MCP_TOKEN_TTL_SECONDS"}
            with patch.dict(os.environ, base, clear=False):
                # Ensure the key is not present
                os.environ.pop("AKSARA_MCP_TOKEN_TTL_SECONDS", None)
                result = check_mcp_hardening(is_production=True)
        assert result.status == "block"
        assert "ttl" in result.message.lower() or "token_ttl" in result.message.lower() or "ttl" in result.title.lower()

    def test_production_check_blocks_mcp_enabled_without_audience(self):
        sp, ep = _patch_mcp_enabled({"AKSARA_MCP_REQUIRE_AUDIENCE": "false"})
        with sp, ep:
            result = check_mcp_hardening(is_production=True)
        assert result.status == "block"
        assert "audience" in result.message.lower()

    def test_production_check_blocks_multitenant_mcp_without_tenant_bound_tokens(self):
        env_overrides = {
            "AKSARA_MULTI_TENANT": "true",
            "AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS": "false",
        }
        sp, ep = _patch_mcp_enabled(env_overrides)
        with sp, ep:
            result = check_mcp_hardening(is_production=True)
        assert result.status == "block"
        assert "tenant" in result.message.lower()


# ---------------------------------------------------------------------------
# Dev-mode warns (not blocks)
# ---------------------------------------------------------------------------


class TestMCPHardeningDevWarns:
    def test_security_check_warns_mcp_enabled_without_scoped_tokens(self):
        sp, ep = _patch_mcp_enabled({"AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "false"})
        with sp, ep:
            result = check_mcp_hardening(is_production=False)
        assert result.status == "warn"
        assert result.status != "block"


# ---------------------------------------------------------------------------
# TTL too long — warn regardless of mode
# ---------------------------------------------------------------------------


class TestMCPHardeningTTLWarn:
    def test_production_check_warns_mcp_token_ttl_too_long(self):
        sp, ep = _patch_mcp_enabled({"AKSARA_MCP_TOKEN_TTL_SECONDS": "7200"})
        with sp, ep:
            result = check_mcp_hardening(is_production=True)
        assert result.status == "warn"
        assert "3600" in result.message or "ttl" in result.message.lower()


# ---------------------------------------------------------------------------
# Safe config passes
# ---------------------------------------------------------------------------


class TestMCPHardeningSafeConfig:
    def test_safe_mcp_production_config_has_no_mcp_hardening_blocks(self):
        settings = _mcp_enabled_settings()
        with patch("aksara.security.checks.get_setting",
                   side_effect=lambda n, d=None: settings.get(n, d)):
            with patch.dict(os.environ, _SAFE_MCP_ENV):
                result = check_mcp_hardening(is_production=True)
        assert result.status == "pass"
