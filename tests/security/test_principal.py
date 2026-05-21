"""
Tests for aksara.security.principal — Principal dataclass.

Round 2: canonical identity primitive.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aksara.security.principal import Principal, _scope_matches


class TestAnonymousPrincipal:
    def test_anonymous_principal_defaults(self):
        p = Principal.anonymous()
        assert p.is_anonymous
        assert not p.is_authenticated
        assert p.auth_method == "anonymous"
        assert not p.is_ai_agent
        assert not p.is_system
        assert p.user_id is None
        assert p.tenant_id is None
        assert p.roles == ()
        assert p.scopes == ()

    def test_anonymous_principal_is_not_expired(self):
        p = Principal.anonymous()
        assert not p.is_expired


class TestUserPrincipal:
    def test_user_principal_defaults(self):
        p = Principal.for_user(user_id="u123")
        assert p.is_authenticated
        assert not p.is_anonymous
        assert p.user_id == "u123"
        assert p.auth_method == "session"
        assert not p.is_ai_agent
        assert not p.is_system

    def test_user_principal_with_tenant_roles_scopes(self):
        p = Principal.for_user(
            user_id="u1",
            tenant_id="t1",
            roles=["admin", "editor"],
            scopes=["read:invoice", "write:invoice"],
        )
        assert p.tenant_id == "t1"
        assert "admin" in p.roles
        assert "editor" in p.roles
        assert "read:invoice" in p.scopes

    def test_user_principal_with_jwt_auth(self):
        p = Principal.for_user(user_id="u1", auth_method="jwt")
        assert p.auth_method == "jwt"

    def test_user_principal_is_frozen(self):
        p = Principal.for_user(user_id="u1")
        with pytest.raises((AttributeError, TypeError)):
            p.user_id = "changed"  # type: ignore[misc]

    def test_user_principal_has_role(self):
        p = Principal.for_user(user_id="u1", roles=["admin"])
        assert p.has_role("admin")
        assert not p.has_role("editor")

    def test_user_principal_has_any_role(self):
        p = Principal.for_user(user_id="u1", roles=["editor"])
        assert p.has_any_role(["admin", "editor"])
        assert not p.has_any_role(["superuser"])


class TestAIAgentPrincipal:
    def test_ai_agent_principal(self):
        p = Principal.for_ai_agent(agent_id="agent-1", human_owner_id="u1", tenant_id="t1")
        assert p.is_ai_agent
        assert p.is_authenticated
        assert p.auth_method == "ai_agent"
        assert p.agent_id == "agent-1"
        assert p.human_owner_id == "u1"
        assert p.tenant_id == "t1"
        assert not p.is_system
        assert not p.is_anonymous

    def test_ai_agent_with_scopes(self):
        p = Principal.for_ai_agent(scopes=["mcp:read:invoice"])
        assert "mcp:read:invoice" in p.scopes

    def test_ai_agent_is_frozen(self):
        p = Principal.for_ai_agent()
        with pytest.raises((AttributeError, TypeError)):
            p.is_ai_agent = False  # type: ignore[misc]


class TestMCPAgentPrincipal:
    def test_mcp_agent_principal(self):
        p = Principal.for_mcp_agent(
            token_id="tok-abc",
            human_owner_id="u1",
            tenant_id="t1",
            agent_id="mcp-agent",
            scopes=["mcp:read:invoice", "mcp:update:invoice.status"],
        )
        assert p.auth_method == "mcp_token"
        assert p.is_ai_agent
        assert p.token_id == "tok-abc"
        assert p.human_owner_id == "u1"
        assert p.tenant_id == "t1"
        assert p.agent_id == "mcp-agent"
        assert "mcp:read:invoice" in p.scopes

    def test_mcp_agent_principal_from_claims(self):
        from aksara.security.context import principal_from_mcp_claims
        now = datetime.now(tz=timezone.utc)
        exp = (now + timedelta(seconds=300)).timestamp()
        claims = {
            "sub": "user-123",
            "tenant_id": "t-456",
            "agent_id": "agent-789",
            "token_id": "tok-abc",
            "scopes": ["mcp:read:invoice"],
            "exp": exp,
        }
        p = principal_from_mcp_claims(claims)
        assert p.auth_method == "mcp_token"
        assert p.human_owner_id == "user-123"
        assert p.tenant_id == "t-456"
        assert p.agent_id == "agent-789"
        assert p.token_id == "tok-abc"
        assert p.has_scope("mcp:read:invoice")
        assert not p.is_expired

    def test_mcp_agent_with_expiration(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        p = Principal.for_mcp_agent(expires_at=past)
        assert p.is_expired

    def test_mcp_agent_not_expired_when_in_future(self):
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        p = Principal.for_mcp_agent(expires_at=future)
        assert not p.is_expired


class TestSystemPrincipal:
    def test_system_principal(self):
        p = Principal.system(reason="background-migration")
        assert p.is_system
        assert p.is_authenticated
        assert p.auth_method == "system"
        assert not p.is_ai_agent
        assert not p.is_anonymous
        assert p.metadata.get("reason") == "background-migration"

    def test_system_principal_with_tenant(self):
        from aksara.security.context import system_principal
        p = system_principal(tenant_id="t1")
        assert p.tenant_id == "t1"
        assert p.is_system

    def test_system_principal_is_frozen(self):
        p = Principal.system()
        with pytest.raises((AttributeError, TypeError)):
            p.is_system = False  # type: ignore[misc]


class TestScopeHelpers:
    def test_scope_exact_match(self):
        p = Principal.for_user(user_id="u1", scopes=["mcp:read:invoice"])
        assert p.has_scope("mcp:read:invoice")
        assert not p.has_scope("mcp:read:ticket")

    def test_scope_missing(self):
        p = Principal.for_user(user_id="u1", scopes=[])
        assert not p.has_scope("mcp:read:invoice")

    def test_has_any_scope(self):
        p = Principal.for_user(user_id="u1", scopes=["mcp:read:invoice"])
        assert p.has_any_scope(["mcp:read:invoice", "mcp:write:invoice"])
        assert not p.has_any_scope(["mcp:write:invoice", "mcp:delete:invoice"])

    def test_has_all_scopes(self):
        p = Principal.for_user(
            user_id="u1",
            scopes=["mcp:read:invoice", "mcp:write:invoice"],
        )
        assert p.has_all_scopes(["mcp:read:invoice", "mcp:write:invoice"])
        assert not p.has_all_scopes(["mcp:read:invoice", "mcp:delete:invoice"])

    def test_wildcard_segment_match(self):
        p = Principal.for_mcp_agent(scopes=["mcp:read:*"])
        assert p.has_scope("mcp:read:invoice")
        assert p.has_scope("mcp:read:ticket")
        assert not p.has_scope("mcp:write:invoice")

    def test_wildcard_prefix_match(self):
        p = Principal.for_mcp_agent(scopes=["mcp:*"])
        assert p.has_scope("mcp:read:invoice")
        assert p.has_scope("mcp:write:ticket")

    def test_global_wildcard_matches_all(self):
        p = Principal.system()
        p_with_star = Principal.system(metadata={"granted_scopes": ["*"]})
        # Use a principal that actually has * in scopes
        p2 = Principal.for_mcp_agent(scopes=["*"])
        assert p2.has_scope("mcp:read:invoice")
        assert p2.has_scope("anything")


class TestScopeMatchingFunction:
    def test_exact(self):
        assert _scope_matches("mcp:read:invoice", "mcp:read:invoice")

    def test_wildcard_last_segment(self):
        assert _scope_matches("mcp:read:*", "mcp:read:invoice")
        assert _scope_matches("mcp:read:*", "mcp:read:ticket")
        assert not _scope_matches("mcp:read:*", "mcp:write:invoice")

    def test_wildcard_middle(self):
        assert _scope_matches("mcp:*", "mcp:read:invoice")

    def test_global_wildcard(self):
        assert _scope_matches("*", "anything:at:all")

    def test_no_wildcard_no_match(self):
        assert not _scope_matches("mcp:read:invoice", "mcp:read:ticket")

    def test_different_length_no_match(self):
        assert not _scope_matches("mcp:read", "mcp:read:invoice")


class TestPrincipalRepr:
    def test_anonymous_repr(self):
        assert "anonymous" in repr(Principal.anonymous()).lower()

    def test_user_repr(self):
        p = Principal.for_user(user_id="u1", tenant_id="t1")
        r = repr(p)
        assert "u1" in r

    def test_system_repr(self):
        assert "system" in repr(Principal.system()).lower()

    def test_ai_agent_repr(self):
        p = Principal.for_ai_agent(agent_id="a1")
        r = repr(p)
        assert "a1" in r
