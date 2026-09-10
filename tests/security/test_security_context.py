"""
Tests for aksara.security.context — context resolvers.

Round 2: principal resolution from requests, users, and MCP claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from aksara.security.context import (
    anonymous_principal,
    principal_from_ai_agent,
    principal_from_mcp_claims,
    principal_from_request,
    principal_from_user,
    system_principal,
)
from aksara.security.principal import Principal

# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeState:
    user: Any = None
    tenant_id: Any = None
    is_ai_agent: bool = False
    ai_agent_id: Any = None
    ai_agent_human_owner: Any = None
    ai_agent_token_id: Any = None
    auth_method: Any = None
    request_id: Any = None


@dataclass
class FakeUser:
    id: Any = None
    is_authenticated: bool = True
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    is_admin: bool = False


@dataclass
class FakeRequest:
    state: Any = None
    user: Any = None
    headers: dict = field(default_factory=dict)
    tenant_id: Any = None


# ---------------------------------------------------------------------------
# anonymous_principal
# ---------------------------------------------------------------------------


class TestAnonymousPrincipalHelper:
    def test_returns_anonymous(self):
        p = anonymous_principal()
        assert p.is_anonymous
        assert p.auth_method == "anonymous"

    def test_is_not_authenticated(self):
        p = anonymous_principal()
        assert not p.is_authenticated


# ---------------------------------------------------------------------------
# system_principal
# ---------------------------------------------------------------------------


class TestSystemPrincipalHelper:
    def test_returns_system(self):
        p = system_principal()
        assert p.is_system
        assert p.is_authenticated

    def test_with_reason(self):
        p = system_principal("cron-job")
        assert p.metadata.get("reason") == "cron-job"

    def test_with_tenant_id(self):
        p = system_principal(tenant_id="t1")
        assert p.tenant_id == "t1"
        assert p.is_system


# ---------------------------------------------------------------------------
# principal_from_user
# ---------------------------------------------------------------------------


class TestPrincipalFromUser:
    def test_none_user_returns_anonymous(self):
        p = principal_from_user(None)
        assert p.is_anonymous

    def test_unauthenticated_user_returns_anonymous(self):
        user = FakeUser(is_authenticated=False)
        p = principal_from_user(user)
        assert p.is_anonymous

    def test_authenticated_user(self):
        user = FakeUser(id="u1")
        p = principal_from_user(user)
        assert p.is_authenticated
        assert p.user_id == "u1"
        assert p.auth_method == "session"

    def test_superuser_gets_admin_role(self):
        user = FakeUser(id="u1", is_superuser=True)
        p = principal_from_user(user)
        assert "admin" in p.roles

    def test_admin_user_gets_admin_role(self):
        user = FakeUser(id="u1", is_admin=True)
        p = principal_from_user(user)
        assert "admin" in p.roles

    def test_staff_gets_staff_role(self):
        user = FakeUser(id="u1", is_staff=True)
        p = principal_from_user(user)
        assert "staff" in p.roles

    def test_explicit_roles_override(self):
        user = FakeUser(id="u1", is_superuser=True)
        p = principal_from_user(user, roles=["editor"])
        assert "editor" in p.roles
        assert "admin" not in p.roles

    def test_explicit_tenant_id(self):
        user = FakeUser(id="u1")
        p = principal_from_user(user, tenant_id="t1")
        assert p.tenant_id == "t1"

    def test_explicit_auth_method(self):
        user = FakeUser(id="u1")
        p = principal_from_user(user, auth_method="jwt")
        assert p.auth_method == "jwt"

    def test_user_id_stringified(self):
        user = FakeUser(id=42)
        p = principal_from_user(user)
        assert p.user_id == "42"


# ---------------------------------------------------------------------------
# principal_from_request
# ---------------------------------------------------------------------------


class TestPrincipalFromRequest:
    def test_anonymous_request(self):
        request = FakeRequest()
        p = principal_from_request(request)
        assert p.is_anonymous

    def test_starlette_request_without_authentication_middleware_is_anonymous(self):
        from starlette.requests import Request

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/mcp/",
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
                "scheme": "http",
            }
        )
        with pytest.raises(AssertionError):
            _ = request.user

        assert principal_from_request(request).is_anonymous

    def test_ai_agent_in_state(self):
        state = FakeState(
            is_ai_agent=True,
            ai_agent_id="agent-1",
            ai_agent_human_owner="u1",
            tenant_id="t1",
        )
        request = FakeRequest(state=state)
        p = principal_from_request(request)
        assert p.is_ai_agent
        assert p.agent_id == "agent-1"
        assert p.human_owner_id == "u1"
        assert p.tenant_id == "t1"
        assert p.auth_method == "ai_agent"

    def test_authenticated_user_in_state(self):
        user = FakeUser(id="u1")
        state = FakeState(user=user, tenant_id="t2")
        request = FakeRequest(state=state)
        p = principal_from_request(request)
        assert p.is_authenticated
        assert p.user_id == "u1"
        assert p.tenant_id == "t2"

    def test_user_on_request_directly(self):
        user = FakeUser(id="u2")
        request = FakeRequest(user=user)
        p = principal_from_request(request)
        assert p.is_authenticated
        assert p.user_id == "u2"

    def test_tenant_not_taken_from_headers(self):
        user = FakeUser(id="u1")
        state = FakeState(user=user, tenant_id=None)
        request = FakeRequest(
            state=state,
            headers={"X-Tenant-Id": "injected-tenant"},
        )
        p = principal_from_request(request)
        assert p.tenant_id is None

    def test_auth_method_from_bearer_header(self):
        user = FakeUser(id="u1")
        state = FakeState(user=user)
        request = FakeRequest(state=state, headers={"Authorization": "Bearer tok"})
        p = principal_from_request(request)
        assert p.auth_method == "jwt"

    def test_auth_method_from_token_header(self):
        user = FakeUser(id="u1")
        state = FakeState(user=user)
        request = FakeRequest(state=state, headers={"Authorization": "Token tok"})
        p = principal_from_request(request)
        assert p.auth_method == "api_key"

    def test_ai_agent_token_id(self):
        state = FakeState(
            is_ai_agent=True,
            ai_agent_token_id="tok-xyz",
        )
        request = FakeRequest(state=state)
        p = principal_from_request(request)
        assert p.token_id == "tok-xyz"

    def test_request_id_in_metadata(self):
        state = FakeState(
            is_ai_agent=True,
            request_id="req-123",
        )
        request = FakeRequest(state=state)
        p = principal_from_request(request)
        assert p.metadata.get("request_id") == "req-123"


# ---------------------------------------------------------------------------
# principal_from_mcp_claims
# ---------------------------------------------------------------------------


class TestPrincipalFromMcpClaims:
    def test_basic_claims(self):
        now = datetime.now(tz=timezone.utc)
        exp = (now + timedelta(seconds=300)).timestamp()
        claims = {
            "sub": "user-1",
            "tenant_id": "t1",
            "agent_id": "agent-1",
            "token_id": "tok-1",
            "scopes": ["mcp:read:invoice"],
            "exp": exp,
        }
        p = principal_from_mcp_claims(claims)
        assert p.auth_method == "mcp_token"
        assert p.human_owner_id == "user-1"
        assert p.tenant_id == "t1"
        assert p.agent_id == "agent-1"
        assert p.token_id == "tok-1"
        assert "mcp:read:invoice" in p.scopes
        assert not p.is_expired

    def test_user_id_fallback(self):
        claims = {"user_id": "u2", "scopes": []}
        p = principal_from_mcp_claims(claims)
        assert p.human_owner_id == "u2"

    def test_jti_as_token_id(self):
        claims = {"sub": "u1", "jti": "jwt-token-id", "scopes": []}
        p = principal_from_mcp_claims(claims)
        assert p.token_id == "jwt-token-id"

    def test_scopes_as_string(self):
        claims = {"sub": "u1", "scopes": "mcp:read:invoice mcp:write:invoice"}
        p = principal_from_mcp_claims(claims)
        assert "mcp:read:invoice" in p.scopes
        assert "mcp:write:invoice" in p.scopes

    def test_expired_claims(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
        claims = {"sub": "u1", "scopes": [], "exp": past}
        p = principal_from_mcp_claims(claims)
        assert p.is_expired

    def test_extra_claims_in_metadata(self):
        claims = {"sub": "u1", "scopes": [], "custom_claim": "my-value"}
        p = principal_from_mcp_claims(claims)
        assert p.metadata.get("custom_claim") == "my-value"

    def test_missing_sub_gives_none_owner(self):
        claims = {"scopes": ["mcp:read:invoice"]}
        p = principal_from_mcp_claims(claims)
        assert p.human_owner_id is None


# ---------------------------------------------------------------------------
# principal_from_ai_agent
# ---------------------------------------------------------------------------


class TestPrincipalFromAIAgent:
    def test_from_kwargs_only(self):
        p = principal_from_ai_agent(
            agent_id="agent-1",
            human_owner_id="u1",
            tenant_id="t1",
            scopes=["mcp:read:invoice"],
        )
        assert p.is_ai_agent
        assert p.agent_id == "agent-1"
        assert p.human_owner_id == "u1"
        assert p.tenant_id == "t1"
        assert "mcp:read:invoice" in p.scopes

    def test_from_agent_object(self):
        @dataclass
        class FakeAgentObj:
            agent_id: str = "obj-agent"
            human_owner_id: str = "u-owner"
            tenant_id: str = "t-obj"
            scopes: list = field(default_factory=lambda: ["mcp:read:*"])

        agent = FakeAgentObj()
        p = principal_from_ai_agent(agent)
        assert p.agent_id == "obj-agent"
        assert p.human_owner_id == "u-owner"
        assert p.tenant_id == "t-obj"
        assert "mcp:read:*" in p.scopes

    def test_kwargs_override_agent_object(self):
        @dataclass
        class FakeAgentObj:
            agent_id: str = "obj-agent"
            human_owner_id: str = "u-owner"
            tenant_id: str = "t-obj"
            scopes: list = field(default_factory=list)

        agent = FakeAgentObj()
        p = principal_from_ai_agent(agent, agent_id="override-id", tenant_id="t-override")
        assert p.agent_id == "override-id"
        assert p.tenant_id == "t-override"

    def test_no_args_returns_ai_agent(self):
        p = principal_from_ai_agent()
        assert p.is_ai_agent
        assert p.agent_id is None
