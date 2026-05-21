"""
Tests for aksara.security.policy — PolicyEngine.

Round 2: central authorization engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import pytest

from aksara.security.policy import PolicyEngine, default_policy
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@dataclass
class FakeField:
    name: str
    ai_sensitive: bool = False
    ai_agent_writable: bool = True
    read_only: bool = False
    system_only: bool = False


@dataclass
class FakeModel:
    fields: List[FakeField]
    tenant_id: Any = None


@dataclass
class FakeResource:
    tenant_id: Any = None
    ai_allow: Any = None


# ---------------------------------------------------------------------------
# can() tests
# ---------------------------------------------------------------------------


class TestCanProtectedActions:
    def test_can_denies_anonymous_for_protected_action(self):
        engine = PolicyEngine()
        p = Principal.anonymous()
        d = engine.can(p, "update")
        assert d.denied
        assert "anonymous" in d.reason.lower()

    def test_can_denies_anonymous_for_create(self):
        engine = PolicyEngine()
        p = Principal.anonymous()
        d = engine.can(p, "create")
        assert d.denied

    def test_can_allows_anonymous_for_public_read(self):
        engine = PolicyEngine()
        p = Principal.anonymous()
        d = engine.can(p, "list")
        assert d.allowed

    def test_can_allows_system_for_internal_action(self):
        engine = PolicyEngine()
        p = Principal.system()
        d = engine.can(p, "doctor_run")
        assert d.allowed

    def test_can_allows_system_for_migration(self):
        engine = PolicyEngine()
        p = Principal.system()
        d = engine.can(p, "migration_execute")
        assert d.allowed

    def test_can_allows_authenticated_user_for_protected_action(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        d = engine.can(p, "update")
        assert d.allowed


class TestCanExpiredToken:
    def test_can_denies_expired_token(self):
        from datetime import datetime, timezone
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(expires_at=past)
        d = engine.can(p, "read")
        assert d.denied
        assert "expired" in d.reason.lower()

    def test_can_allows_non_expired_token(self):
        from datetime import datetime, timedelta, timezone
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(
            scopes=["mcp:read:invoice"],
            expires_at=future,
        )
        d = engine.can(p, "read", required_scopes=["mcp:read:invoice"])
        assert d.allowed


class TestCanRequiredScopes:
    def test_can_denies_missing_required_scope(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(scopes=["mcp:read:invoice"])
        d = engine.can(p, "update", required_scopes=["mcp:write:invoice"])
        assert d.denied
        assert "mcp:write:invoice" in d.missing_scopes

    def test_can_allows_when_required_scope_present(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(scopes=["mcp:write:invoice"])
        d = engine.can(p, "update", required_scopes=["mcp:write:invoice"])
        assert d.allowed

    def test_can_includes_required_scopes_in_decision(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(scopes=[])
        d = engine.can(p, "read", required_scopes=["mcp:read:invoice"])
        assert "mcp:read:invoice" in d.required_scopes
        assert "mcp:read:invoice" in d.missing_scopes

    def test_can_allows_with_wildcard_scope(self):
        engine = PolicyEngine()
        p = Principal.for_mcp_agent(scopes=["mcp:write:*"])
        d = engine.can(p, "update", required_scopes=["mcp:write:invoice"])
        assert d.allowed


class TestCanCrossTenant:
    def test_can_denies_cross_tenant_resource(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-b")
        d = engine.can(p, "read", resource=resource)
        assert d.denied
        assert "tenant" in d.reason.lower()

    def test_can_allows_same_tenant_resource(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id="tenant-a")
        d = engine.can(p, "read", resource=resource)
        assert d.allowed

    def test_system_can_access_cross_tenant(self):
        engine = PolicyEngine()
        p = Principal.system()
        resource = FakeResource(tenant_id="any-tenant")
        d = engine.can(p, "read", resource=resource)
        assert d.allowed

    def test_can_allows_when_no_resource_tenant(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        resource = FakeResource(tenant_id=None)
        d = engine.can(p, "read", resource=resource)
        assert d.allowed


class TestCanAIAgent:
    def test_can_denies_ai_agent_write_when_resource_ai_allow_false(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        resource = FakeResource(ai_allow=False)
        d = engine.can(p, "update", resource=resource)
        assert d.denied

    def test_can_allows_ai_agent_read(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent(scopes=["mcp:read:invoice"])
        d = engine.can(p, "read")
        assert d.allowed

    def test_can_allows_ai_agent_write_when_resource_has_no_restriction(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        resource = FakeResource(ai_allow=None)
        d = engine.can(p, "update", resource=resource)
        assert d.allowed


# ---------------------------------------------------------------------------
# visible_fields() tests
# ---------------------------------------------------------------------------


class TestVisibleFields:
    def test_visible_fields_hides_ai_sensitive_for_ai_agent(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="internal_notes", ai_sensitive=True),
        ])
        d = engine.visible_fields(p, model)
        assert "name" in d.allowed_fields
        assert "internal_notes" in d.denied_fields

    def test_visible_fields_allows_normal_fields_for_ai_agent(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="amount"),
        ])
        d = engine.visible_fields(p, model)
        assert "name" in d.allowed_fields
        assert "amount" in d.allowed_fields
        assert not d.denied_fields

    def test_visible_fields_allows_system_to_see_all(self):
        engine = PolicyEngine()
        p = Principal.system()
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="secret", ai_sensitive=True, system_only=True),
        ])
        d = engine.visible_fields(p, model)
        assert "name" in d.allowed_fields
        assert "secret" in d.allowed_fields
        assert not d.denied_fields

    def test_visible_fields_hides_system_only_from_normal_user(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="internal_flag", system_only=True),
        ])
        d = engine.visible_fields(p, model)
        assert "name" in d.allowed_fields
        assert "internal_flag" in d.denied_fields

    def test_visible_fields_all_visible_returns_allow(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[FakeField(name="name"), FakeField(name="amount")])
        d = engine.visible_fields(p, model)
        assert d.allowed
        assert not d.is_partial


# ---------------------------------------------------------------------------
# writable_fields() tests
# ---------------------------------------------------------------------------


class TestWritableFields:
    def test_writable_fields_denies_read_only_fields(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="created_at", read_only=True),
        ])
        d = engine.writable_fields(p, model)
        assert "name" in d.allowed_fields
        assert "created_at" in d.denied_fields

    def test_writable_fields_denies_ai_agent_writable_false_for_ai_agent(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        model = FakeModel(fields=[
            FakeField(name="status"),
            FakeField(name="amount", ai_agent_writable=False),
        ])
        d = engine.writable_fields(p, model)
        assert "status" in d.allowed_fields
        assert "amount" in d.denied_fields

    def test_writable_fields_denies_tenant_id_for_normal_user(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="t1")
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="tenant_id"),
        ])
        d = engine.writable_fields(p, model)
        assert "name" in d.allowed_fields
        assert "tenant_id" in d.denied_fields

    def test_writable_fields_allows_tenant_id_for_system(self):
        engine = PolicyEngine()
        p = Principal.system()
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="tenant_id"),
        ])
        d = engine.writable_fields(p, model)
        assert "name" in d.allowed_fields
        assert "tenant_id" in d.allowed_fields

    def test_writable_fields_denies_system_only_for_normal_user(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="is_deleted", system_only=True),
        ])
        d = engine.writable_fields(p, model)
        assert "name" in d.allowed_fields
        assert "is_deleted" in d.denied_fields

    def test_writable_fields_all_writable_returns_allow(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[FakeField(name="name"), FakeField(name="amount")])
        d = engine.writable_fields(p, model)
        assert d.allowed
        assert not d.is_partial

    def test_writable_fields_ai_agent_writable_false_allowed_for_user(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[
            FakeField(name="amount", ai_agent_writable=False),
        ])
        d = engine.writable_fields(p, model)
        assert "amount" in d.allowed_fields


# ---------------------------------------------------------------------------
# validate_payload() tests
# ---------------------------------------------------------------------------


class TestValidatePayload:
    def test_validate_payload_allows_allowed_fields(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="amount"),
        ])
        d = engine.validate_payload(p, "update", model, {"name": "Acme", "amount": 100})
        assert d.allowed
        assert "name" in d.allowed_fields
        assert "amount" in d.allowed_fields

    def test_validate_payload_denies_forbidden_fields(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        model = FakeModel(fields=[
            FakeField(name="status"),
            FakeField(name="internal_flag", ai_agent_writable=False),
        ])
        d = engine.validate_payload(p, "update", model, {"status": "active", "internal_flag": True})
        assert d.is_partial
        assert "internal_flag" in d.denied_fields

    def test_validate_payload_reports_denied_fields(self):
        engine = PolicyEngine()
        p = Principal.for_ai_agent()
        model = FakeModel(fields=[
            FakeField(name="name"),
            FakeField(name="secret", ai_agent_writable=False),
        ])
        payload = {"name": "Test", "secret": "hidden"}
        d = engine.validate_payload(p, "update", model, payload)
        assert "secret" in d.denied_fields
        assert "name" in d.allowed_fields

    def test_validate_payload_denies_when_action_denied(self):
        engine = PolicyEngine()
        p = Principal.anonymous()
        model = FakeModel(fields=[FakeField(name="name")])
        d = engine.validate_payload(p, "update", model, {"name": "Test"})
        assert d.denied

    def test_validate_payload_fallback_when_no_field_metadata(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1")
        # Empty model with no fields
        model = FakeModel(fields=[])
        d = engine.validate_payload(p, "update", model, {"name": "Test"})
        assert d.allowed


# ---------------------------------------------------------------------------
# query_filter() tests
# ---------------------------------------------------------------------------


class TestQueryFilter:
    def test_query_filter_returns_tenant_filter_metadata(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="t1")
        model = FakeModel(fields=[FakeField(name="tenant_id")])
        d = engine.query_filter(p, model)
        assert d.allowed
        assert d.metadata["filters"]["tenant_id"] == "t1"

    def test_query_filter_warns_missing_tenant_when_not_required(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id=None)
        model = FakeModel(fields=[FakeField(name="tenant_id")])
        d = engine.query_filter(p, model)
        assert d.is_warning

    def test_query_filter_denies_missing_tenant_when_required(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id=None)
        model = FakeModel(fields=[FakeField(name="tenant_id")])
        d = engine.query_filter(p, model, tenant_required=True)
        assert d.denied

    def test_query_filter_system_with_tenant(self):
        engine = PolicyEngine()
        p = Principal.system(tenant_id="t1")
        model = FakeModel(fields=[FakeField(name="tenant_id")])
        d = engine.query_filter(p, model)
        assert d.allowed
        assert d.metadata["filters"]["tenant_id"] == "t1"

    def test_query_filter_system_no_tenant(self):
        engine = PolicyEngine()
        p = Principal.system()
        model = FakeModel(fields=[])
        d = engine.query_filter(p, model)
        assert d.allowed
        assert d.metadata["filters"] == {}

    def test_query_filter_non_tenant_model_returns_no_filter(self):
        engine = PolicyEngine()
        p = Principal.for_user(user_id="u1", tenant_id="t1")
        model = FakeModel(fields=[FakeField(name="name"), FakeField(name="amount")])
        d = engine.query_filter(p, model)
        assert d.allowed


# ---------------------------------------------------------------------------
# default_policy singleton
# ---------------------------------------------------------------------------


class TestDefaultPolicy:
    def test_default_policy_is_engine_instance(self):
        assert isinstance(default_policy, PolicyEngine)

    def test_get_policy_engine_returns_default(self):
        from aksara.security.policy import get_policy_engine
        assert get_policy_engine() is default_policy
