"""
Tests for tenant isolation behaviors — Round 4 adversarial scenarios.

Covers: cross-tenant resource access, AI/MCP agent cross-tenant, tenant_required
fail-closed, query_filter, forged header ignored, body tenant_id override denied,
system principal behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from aksara.security.context import principal_from_request
from aksara.security.enforcement import enforce_payload_policy
from aksara.security.exceptions import PolicyDenied
from aksara.security.policy import PolicyEngine
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeResource:
    tenant_id: Any = None
    ai_allow: Any = None


@dataclass
class FakeField:
    name: str
    ai_sensitive: bool = False
    ai_agent_writable: bool = True
    read_only: bool = False
    system_only: bool = False


@dataclass
class FakeTenantModel:
    """Model with a tenant_id field so PolicyEngine detects it as tenant-aware."""
    fields: list = field(default_factory=lambda: [FakeField("tenant_id"), FakeField("title")])
    tenant_id: Any = None


@dataclass
class FakeState:
    user: Any = None
    tenant_id: Any = None
    is_ai_agent: bool = False


@dataclass
class FakeUser:
    id: Any = None
    is_authenticated: bool = True


@dataclass
class FakeRequest:
    state: Any = None
    user: Any = None
    headers: dict = field(default_factory=dict)
    tenant_id: Any = None


# ---------------------------------------------------------------------------
# Track A — cross-tenant resource access
# ---------------------------------------------------------------------------


class TestSameTenantAccess:
    def test_same_tenant_resource_read_allowed(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-a")
        d = engine.can(p, "read", resource=resource)
        assert d.allowed

    def test_same_tenant_resource_update_allowed(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-a")
        d = engine.can(p, "update", resource=resource)
        assert d.allowed


class TestCrossTenantResourceDenied:
    def test_cross_tenant_resource_read_denied(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-b")
        d = engine.can(p, "read", resource=resource)
        assert d.denied
        assert "tenant" in d.reason.lower()

    def test_cross_tenant_resource_update_denied(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-b")
        d = engine.can(p, "update", resource=resource)
        assert d.denied

    def test_cross_tenant_resource_delete_denied(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-b")
        d = engine.can(p, "delete", resource=resource)
        assert d.denied

    def test_ai_agent_cross_tenant_read_denied(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent(tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-b")
        d = engine.can(p, "read", resource=resource)
        assert d.denied
        assert "tenant" in d.reason.lower()

    def test_mcp_agent_cross_tenant_update_denied(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(tenant_id="tenant-a", scopes=["mcp:write:invoice"])
        resource = FakeResource(tenant_id="tenant-b")
        d = engine.can(p, "update", resource=resource)
        assert d.denied


# ---------------------------------------------------------------------------
# Track A — tenant_required fail-closed
# ---------------------------------------------------------------------------


class TestTenantRequired:
    def test_missing_tenant_context_denied_when_tenant_required(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id=None)
        d = engine.can(p, "list", tenant_required=True)
        assert d.denied
        assert "tenant" in d.reason.lower()

    def test_with_tenant_context_allowed_when_tenant_required(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        d = engine.can(p, "list", tenant_required=True)
        assert d.allowed

    def test_system_principal_without_tenant_returns_allow_when_tenant_required(self):
        # System principals bypass tenant_required — intentional for internal tooling.
        engine = PolicyEngine()
        p = Principal.system()
        d = engine.can(p, "list", tenant_required=True)
        assert d.allowed

    def test_system_principal_with_explicit_tenant_allowed(self):
        engine = PolicyEngine()
        p = Principal.system(tenant_id="tenant-a")
        d = engine.can(p, "update", tenant_id="tenant-a")
        assert d.allowed


# ---------------------------------------------------------------------------
# Track A — query_filter
# ---------------------------------------------------------------------------


class TestQueryFilter:
    def test_query_filter_returns_principal_tenant_filter(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        model = FakeTenantModel()
        d = engine.query_filter(p, model)
        assert d.allowed
        assert d.metadata["filters"]["tenant_id"] == "tenant-a"

    def test_query_filter_denies_missing_tenant_when_required(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id=None)
        model = FakeTenantModel()
        d = engine.query_filter(p, model, tenant_required=True)
        assert d.denied


# ---------------------------------------------------------------------------
# Track A — forged header ignored
# ---------------------------------------------------------------------------


class TestForgedTenantHeader:
    def test_forged_tenant_header_not_used_by_principal_from_request(self):
        # Client sends X-Tenant-Id header; it must NOT be trusted.
        user = FakeUser(id="u1")
        state = FakeState(user=user, tenant_id=None)
        request = FakeRequest(
            state=state,
            headers={"X-Tenant-Id": "injected-tenant"},
        )
        p = principal_from_request(request)
        assert p.tenant_id is None


# ---------------------------------------------------------------------------
# Track A — body tenant_id override denied by runtime enforcement
# ---------------------------------------------------------------------------


class TestBodyTenantIdOverride:
    def test_body_tenant_id_override_denied_by_runtime_enforcement(self):
        @dataclass
        class TField:
            name: str
            ai_sensitive: bool = False
            ai_agent_writable: bool = True
            read_only: bool = False
            system_only: bool = False

        @dataclass
        class TModel:
            _fields: dict = field(default_factory=dict)

        tenant_field = TField(name="tenant_id")
        title_field = TField(name="title")
        model = TModel(_fields={"tenant_id": tenant_field, "title": title_field})

        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        payload = {"title": "Test", "tenant_id": "tenant-b"}

        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(principal=p, action="create", model=model, payload=payload)

        assert "tenant_id" in exc_info.value.denied_fields
