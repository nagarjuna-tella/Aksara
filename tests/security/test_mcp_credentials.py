"""
Tests for MCP credential helpers — Round 4.

Covers: MCPCredentialClaims, require_scope/require_any_scope/require_all_scopes,
require_mcp_audience, require_mcp_tenant, policy.can() with required_audience,
principal_from_mcp_claims audience normalization.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aksara.security.context import principal_from_mcp_claims
from aksara.security.mcp import (
    MCPCredentialClaims,
    require_all_scopes,
    require_any_scope,
    require_mcp_audience,
    require_mcp_tenant,
    require_scope,
)
from aksara.security.policy import PolicyEngine
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# MCPCredentialClaims
# ---------------------------------------------------------------------------


class TestMCPCredentialClaims:
    def test_from_claims_dict_parses_subject(self):
        claims = MCPCredentialClaims.from_claims_dict({"sub": "user-1"})
        assert claims.subject == "user-1"

    def test_from_claims_dict_parses_tenant_id(self):
        claims = MCPCredentialClaims.from_claims_dict({"tenant_id": "t1"})
        assert claims.tenant_id == "t1"

    def test_from_claims_dict_parses_scopes_list(self):
        claims = MCPCredentialClaims.from_claims_dict({"scopes": ["mcp:read:invoice"]})
        assert "mcp:read:invoice" in claims.scopes

    def test_from_claims_dict_parses_scopes_space_string(self):
        claims = MCPCredentialClaims.from_claims_dict({"scope": "mcp:read:invoice mcp:write:invoice"})
        assert "mcp:read:invoice" in claims.scopes
        assert "mcp:write:invoice" in claims.scopes

    def test_from_claims_dict_normalizes_aud_claim(self):
        claims = MCPCredentialClaims.from_claims_dict({"aud": "mcp-service"})
        assert claims.audience == "mcp-service"

    def test_from_claims_dict_normalizes_audience_claim(self):
        claims = MCPCredentialClaims.from_claims_dict({"audience": "mcp-service"})
        assert claims.audience == "mcp-service"

    def test_from_claims_dict_parses_token_id_from_jti(self):
        claims = MCPCredentialClaims.from_claims_dict({"jti": "tok-123"})
        assert claims.token_id == "tok-123"

    def test_from_claims_dict_parses_expiry(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        claims = MCPCredentialClaims.from_claims_dict({"exp": future.timestamp()})
        assert claims.expires_at is not None
        assert not claims.expired

    def test_mcp_claims_expired_property_true_when_past(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        claims = MCPCredentialClaims.from_claims_dict({"exp": past.timestamp()})
        assert claims.expired

    def test_mcp_claims_expired_property_false_when_no_expiry(self):
        claims = MCPCredentialClaims.from_claims_dict({})
        assert not claims.expired

    def test_from_claims_dict_extra_keys_in_metadata(self):
        claims = MCPCredentialClaims.from_claims_dict({"custom_key": "val"})
        assert claims.metadata.get("custom_key") == "val"

    def test_from_claims_dict_known_keys_excluded_from_metadata(self):
        claims = MCPCredentialClaims.from_claims_dict({"sub": "u1", "tenant_id": "t1", "aud": "a"})
        assert "sub" not in claims.metadata
        assert "tenant_id" not in claims.metadata
        assert "aud" not in claims.metadata


# ---------------------------------------------------------------------------
# require_scope
# ---------------------------------------------------------------------------


class TestRequireScope:
    def test_mcp_principal_exact_scope_allowed(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice"])
        d = require_scope(p, "mcp:read:invoice")
        assert d.allowed

    def test_mcp_principal_missing_scope_denied(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice"])
        d = require_scope(p, "mcp:write:invoice")
        assert d.denied
        assert "mcp:write:invoice" in d.missing_scopes

    def test_mcp_wildcard_scope_allowed(self):
        p = Principal.for_mcp_agent(scopes=["mcp:update:*"])
        d = require_scope(p, "mcp:update:invoice")
        assert d.allowed

    def test_require_scope_requires_scope_in_result(self):
        p = Principal.for_mcp_agent(scopes=[])
        d = require_scope(p, "mcp:read:invoice")
        assert "mcp:read:invoice" in d.required_scopes


# ---------------------------------------------------------------------------
# require_any_scope / require_all_scopes
# ---------------------------------------------------------------------------


class TestRequireAnyScope:
    def test_require_any_scope_allows_with_one_match(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice"])
        d = require_any_scope(p, ["mcp:read:invoice", "mcp:write:invoice"])
        assert d.allowed

    def test_require_any_scope_denies_when_none_match(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:user"])
        d = require_any_scope(p, ["mcp:write:invoice", "mcp:delete:invoice"])
        assert d.denied


class TestRequireAllScopes:
    def test_require_all_scopes_allows_when_all_present(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice", "mcp:write:invoice"])
        d = require_all_scopes(p, ["mcp:read:invoice", "mcp:write:invoice"])
        assert d.allowed

    def test_require_all_scopes_denies_partial_match(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice"])
        d = require_all_scopes(p, ["mcp:read:invoice", "mcp:write:invoice"])
        assert d.denied
        assert "mcp:write:invoice" in d.missing_scopes


# ---------------------------------------------------------------------------
# require_mcp_audience
# ---------------------------------------------------------------------------


class TestRequireMCPAudience:
    def test_mcp_correct_audience_allowed(self):
        p = Principal.for_mcp_agent(metadata={"audience": "mcp-service"})
        d = require_mcp_audience(p, "mcp-service")
        assert d.allowed

    def test_mcp_wrong_audience_denied(self):
        p = Principal.for_mcp_agent(metadata={"audience": "other-service"})
        d = require_mcp_audience(p, "mcp-service")
        assert d.denied
        assert "mcp-service" in d.metadata["required_audience"]

    def test_mcp_missing_audience_denied_when_required(self):
        p = Principal.for_mcp_agent(metadata={})
        d = require_mcp_audience(p, "mcp-service")
        assert d.denied

    def test_mcp_audience_via_aud_key_in_metadata(self):
        p = Principal.for_mcp_agent(metadata={"aud": "mcp-service"})
        d = require_mcp_audience(p, "mcp-service")
        assert d.allowed


# ---------------------------------------------------------------------------
# require_mcp_tenant
# ---------------------------------------------------------------------------


class TestRequireMCPTenant:
    def test_mcp_tenant_bound_claim_sets_principal_tenant(self):
        p = principal_from_mcp_claims({"tenant_id": "tenant-x"})
        assert p.tenant_id == "tenant-x"

    def test_mcp_without_tenant_denied_for_tenant_required(self):
        p = Principal.for_mcp_agent(tenant_id=None)
        d = require_mcp_tenant(p, tenant_required=True)
        assert d.denied

    def test_mcp_with_tenant_allowed_when_tenant_required(self):
        p = Principal.for_mcp_agent(tenant_id="tenant-a")
        d = require_mcp_tenant(p, tenant_required=True)
        assert d.allowed

    def test_mcp_tenant_not_required_always_allowed(self):
        p = Principal.for_mcp_agent(tenant_id=None)
        d = require_mcp_tenant(p, tenant_required=False)
        assert d.allowed


# ---------------------------------------------------------------------------
# principal_from_mcp_claims — audience normalization
# ---------------------------------------------------------------------------


class TestMCPClaimsAudienceNormalization:
    def test_mcp_audience_claim_normalized_in_principal_from_claims(self):
        p = principal_from_mcp_claims({"aud": "mcp-service"})
        assert p.metadata.get("audience") == "mcp-service"
        assert "aud" not in p.metadata

    def test_mcp_audience_key_normalized_in_principal_from_claims(self):
        p = principal_from_mcp_claims({"audience": "mcp-service"})
        assert p.metadata.get("audience") == "mcp-service"
        assert "audience" not in p.metadata or p.metadata.get("audience") == "mcp-service"

    def test_mcp_token_id_is_preserved_in_principal(self):
        p = principal_from_mcp_claims({"jti": "tok-abc"})
        assert p.token_id == "tok-abc"

    def test_mcp_tenant_claim_preserved_as_principal_tenant_id(self):
        p = principal_from_mcp_claims({"tenant_id": "t42"})
        assert p.tenant_id == "t42"


# ---------------------------------------------------------------------------
# PolicyEngine.can() with required_audience
# ---------------------------------------------------------------------------


class TestPolicyCanRequiredAudience:
    def test_policy_can_with_required_audience_allows_correct(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(metadata={"audience": "mcp-service"})
        d = engine.can(p, "read", required_audience="mcp-service")
        assert d.allowed

    def test_policy_can_with_required_audience_denies_wrong(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(metadata={"audience": "other-service"})
        d = engine.can(p, "read", required_audience="mcp-service")
        assert d.denied

    def test_policy_can_with_required_audience_denies_missing(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(metadata={})
        d = engine.can(p, "read", required_audience="mcp-service")
        assert d.denied


# ---------------------------------------------------------------------------
# PolicyEngine.can() with expired token
# ---------------------------------------------------------------------------


class TestPolicyCanMCPExpiry:
    def test_mcp_expired_token_denied(self):
        engine = PolicyEngine()
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        p = Principal.for_mcp_agent(expires_at=past)
        d = engine.can(p, "read")
        assert d.denied
        assert "expired" in d.reason.lower()

    def test_mcp_future_expiration_allowed(self):
        engine = PolicyEngine()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice"], expires_at=future)
        d = engine.can(p, "read")
        assert d.allowed


# ---------------------------------------------------------------------------
# PolicyEngine.can() — tenant_required for MCP agent
# ---------------------------------------------------------------------------


class TestPolicyCanTenantRequiredMCP:
    def test_mcp_without_tenant_denied_for_tenant_required_action(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(tenant_id=None)
        d = engine.can(p, "list", tenant_required=True)
        assert d.denied
        assert "tenant" in d.reason.lower()
