"""
Tests for aksara.security.enforcement — runtime payload enforcement helpers.

Round 3: server-side enforcement of field-level write restrictions.
Generated schemas are not security controls; this layer enforces at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

import pytest

from aksara.security.enforcement import (
    enforce_payload_policy,
    enforce_request_payload_policy,
    policy_denied_to_error_payload,
)
from aksara.security.exceptions import PolicyDenied
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# Fake field / model / request fixtures
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
    """Simulates an Aksara model class with a _fields dict."""
    _fields: dict = field(default_factory=dict)

    @classmethod
    def with_fields(cls, *fields_list: FakeField) -> "FakeModel":
        return cls(_fields={f.name: f for f in fields_list})


@dataclass
class FakeState:
    principal: Any = None
    is_ai_agent: bool = False
    user: Any = None
    tenant_id: Any = None


@dataclass
class FakeRequest:
    state: Any = None
    user: Any = None
    headers: dict = field(default_factory=dict)


@dataclass
class FakeUser:
    is_authenticated: bool = True
    id: str = "u1"


# ---------------------------------------------------------------------------
# enforce_payload_policy tests
# ---------------------------------------------------------------------------


class TestEnforcePayloadPolicyAllows:
    def test_enforce_payload_policy_allows_allowed_payload(self):
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(FakeField(name="name"), FakeField(name="amount"))
        decision = enforce_payload_policy(
            principal=p,
            action="update",
            model=model,
            payload={"name": "Acme", "amount": 100},
        )
        assert decision.allowed

    def test_enforce_payload_policy_allows_empty_payload(self):
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(FakeField(name="name"))
        decision = enforce_payload_policy(
            principal=p,
            action="update",
            model=model,
            payload={},
        )
        assert decision.allowed

    def test_enforce_payload_policy_allows_system_for_tenant_field(self):
        p = Principal.system()
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="tenant_id"),
        )
        decision = enforce_payload_policy(
            principal=p,
            action="update",
            model=model,
            payload={"name": "x", "tenant_id": "t-new"},
        )
        assert decision.allowed


class TestEnforcePayloadPolicyDenies:
    def test_enforce_payload_policy_denies_forbidden_field(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(
            FakeField(name="status"),
            FakeField(name="internal_flag", ai_agent_writable=False),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"status": "ok", "internal_flag": True},
            )
        assert "internal_flag" in exc_info.value.denied_fields

    def test_enforce_payload_policy_denies_read_only_field(self):
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="created_at", read_only=True),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "Acme", "created_at": "2026-01-01"},
            )
        assert "created_at" in exc_info.value.denied_fields

    def test_enforce_payload_policy_denies_tenant_id_for_normal_user(self):
        p = Principal.for_user(user_id="u1", tenant_id="t1")
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="tenant_id"),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "Acme", "tenant_id": "other-tenant"},
            )
        assert "tenant_id" in exc_info.value.denied_fields

    def test_enforce_payload_policy_denies_tenant_id_for_mcp_agent(self):
        p = Principal.for_mcp_agent(tenant_id="t1", scopes=["mcp:write:invoice"])
        model = FakeModel.with_fields(
            FakeField(name="amount"),
            FakeField(name="tenant_id"),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"amount": 100, "tenant_id": "attacker-tenant"},
            )
        assert "tenant_id" in exc_info.value.denied_fields

    def test_enforce_payload_policy_denies_system_only_for_normal_user(self):
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="is_deleted", system_only=True),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "Acme", "is_deleted": True},
            )
        assert "is_deleted" in exc_info.value.denied_fields

    def test_enforce_payload_policy_denies_anonymous_for_protected_action(self):
        p = Principal.anonymous()
        model = FakeModel.with_fields(FakeField(name="name"))
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="create",
                model=model,
                payload={"name": "Acme"},
            )

    def test_enforce_payload_policy_raises_policy_denied(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(
            FakeField(name="notes", ai_agent_writable=False),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"notes": "injected"},
            )
        exc = exc_info.value
        assert isinstance(exc, PolicyDenied)
        assert exc.decision is not None

    def test_enforce_payload_policy_includes_denied_fields(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="secret", ai_agent_writable=False),
            FakeField(name="internal", ai_agent_writable=False),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "x", "secret": "s", "internal": "i"},
            )
        denied = exc_info.value.denied_fields
        assert "secret" in denied
        assert "internal" in denied
        assert "name" not in denied

    def test_enforce_payload_policy_reports_all_denied_fields(self):
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="tenant_id"),
            FakeField(name="created_at", read_only=True),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "x", "tenant_id": "t-evil", "created_at": "2020-01-01"},
            )
        denied = exc_info.value.denied_fields
        assert "tenant_id" in denied
        assert "created_at" in denied


# ---------------------------------------------------------------------------
# enforce_request_payload_policy tests
# ---------------------------------------------------------------------------


class TestEnforceRequestPayloadPolicy:
    def test_enforce_request_payload_policy_uses_request_state_principal(self):
        p = Principal.for_user(user_id="u1")
        state = FakeState(principal=p)
        request = FakeRequest(state=state)
        model = FakeModel.with_fields(FakeField(name="name"))
        # Should succeed — uses the cached principal from state
        decision = enforce_request_payload_policy(
            request=request,
            action="update",
            model=model,
            payload={"name": "Acme"},
        )
        assert decision.allowed

    def test_enforce_request_payload_policy_falls_back_to_principal_from_request(self):
        user = FakeUser()
        state = FakeState(user=user)
        request = FakeRequest(state=state)
        model = FakeModel.with_fields(FakeField(name="name"))
        decision = enforce_request_payload_policy(
            request=request,
            action="update",
            model=model,
            payload={"name": "Acme"},
        )
        assert decision.allowed

    def test_enforce_request_payload_policy_does_not_treat_missing_principal_as_system(self):
        # No state, no user → anonymous → create is protected → denied
        request = FakeRequest(state=None)
        model = FakeModel.with_fields(FakeField(name="name"))
        with pytest.raises(PolicyDenied):
            enforce_request_payload_policy(
                request=request,
                action="create",
                model=model,
                payload={"name": "Acme"},
            )

    def test_enforce_request_payload_policy_uses_ai_agent_principal(self):
        p = Principal.for_ai_agent()
        state = FakeState(principal=p)
        request = FakeRequest(state=state)
        model = FakeModel.with_fields(
            FakeField(name="status"),
            FakeField(name="sensitive_flag", ai_agent_writable=False),
        )
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_request_payload_policy(
                request=request,
                action="update",
                model=model,
                payload={"status": "ok", "sensitive_flag": True},
            )
        assert "sensitive_flag" in exc_info.value.denied_fields

    def test_enforce_request_payload_policy_none_request_denies_protected(self):
        model = FakeModel.with_fields(FakeField(name="name"))
        with pytest.raises(PolicyDenied):
            enforce_request_payload_policy(
                request=None,
                action="create",
                model=model,
                payload={"name": "Acme"},
            )

    def test_enforce_request_payload_policy_allows_read_action_for_anonymous(self):
        request = FakeRequest(state=None)
        model = FakeModel.with_fields(FakeField(name="name"))
        # "read" is not protected, anonymous should be able to validate payload
        # (empty payload on a read is trivially allowed)
        decision = enforce_request_payload_policy(
            request=request,
            action="read",
            model=model,
            payload={},
        )
        assert decision.allowed


# ---------------------------------------------------------------------------
# policy_denied_to_error_payload tests
# ---------------------------------------------------------------------------


class TestPolicyDeniedToErrorPayload:
    def test_error_payload_shape(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(FakeField(name="secret", ai_agent_writable=False))
        try:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"secret": "x"},
            )
            pytest.fail("Expected PolicyDenied")
        except PolicyDenied as exc:
            payload = policy_denied_to_error_payload(exc)

        assert "detail" in payload
        assert "reason" in payload
        assert "denied_fields" in payload
        assert "required_scopes" in payload
        assert "missing_scopes" in payload

    def test_error_payload_includes_denied_fields(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(FakeField(name="internal", ai_agent_writable=False))
        try:
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"internal": "bypass"},
            )
        except PolicyDenied as exc:
            payload = policy_denied_to_error_payload(exc)
        assert "internal" in payload["denied_fields"]

    def test_error_payload_denied_fields_is_list(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(FakeField(name="f", ai_agent_writable=False))
        try:
            enforce_payload_policy(
                principal=p, action="update", model=model, payload={"f": "v"}
            )
        except PolicyDenied as exc:
            payload = policy_denied_to_error_payload(exc)
        assert isinstance(payload["denied_fields"], list)


# ---------------------------------------------------------------------------
# PolicyDenied exception properties tests
# ---------------------------------------------------------------------------


class TestPolicyDeniedProperties:
    def test_policy_denied_has_reason(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(FakeField(name="x", ai_agent_writable=False))
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p, action="update", model=model, payload={"x": 1}
            )
        assert exc_info.value.reason != ""
        assert isinstance(exc_info.value.reason, str)

    def test_policy_denied_has_denied_fields(self):
        p = Principal.for_ai_agent()
        model = FakeModel.with_fields(FakeField(name="locked", ai_agent_writable=False))
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p, action="update", model=model, payload={"locked": True}
            )
        assert "locked" in exc_info.value.denied_fields

    def test_policy_denied_str_message(self):
        p = Principal.anonymous()
        model = FakeModel.with_fields(FakeField(name="name"))
        with pytest.raises(PolicyDenied) as exc_info:
            enforce_payload_policy(
                principal=p, action="create", model=model, payload={"name": "x"}
            )
        msg = str(exc_info.value)
        assert "denied" in msg.lower() or "anonymous" in msg.lower()


# ---------------------------------------------------------------------------
# Adversarial: raw payload bypass attempts
# ---------------------------------------------------------------------------


class TestAdversarialBypass:
    """Prove that raw payload bypass attempts fail at runtime."""

    def test_ai_agent_cannot_bypass_ai_agent_writable_false(self):
        """An AI agent sending ai_agent_writable=False field must be rejected."""
        p = Principal.for_ai_agent(scopes=["mcp:write:invoice"])
        model = FakeModel.with_fields(
            FakeField(name="invoice_number"),
            FakeField(name="internal_notes", ai_agent_writable=False),
        )
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={
                    "invoice_number": "INV-1001",
                    "internal_notes": "I should not be able to write this",
                },
            )

    def test_normal_user_cannot_bypass_tenant_id(self):
        """A normal user sending tenant_id must be rejected."""
        p = Principal.for_user(user_id="u1", tenant_id="tenant-a")
        model = FakeModel.with_fields(
            FakeField(name="invoice_number"),
            FakeField(name="tenant_id"),
        )
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="create",
                model=model,
                payload={
                    "invoice_number": "INV-1001",
                    "tenant_id": "other-tenant",
                },
            )

    def test_mcp_agent_cannot_bypass_tenant_id(self):
        """An MCP agent cannot change tenant_id even with write scope."""
        p = Principal.for_mcp_agent(
            tenant_id="t1", scopes=["mcp:write:invoice"]
        )
        model = FakeModel.with_fields(
            FakeField(name="amount"),
            FakeField(name="tenant_id"),
        )
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"amount": 999, "tenant_id": "attacker-t2"},
            )

    def test_read_only_field_cannot_be_written_by_anyone(self):
        """read_only field is rejected even for admin users."""
        p = Principal.for_user(user_id="admin", roles=["admin"])
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="created_at", read_only=True),
        )
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "Acme", "created_at": "2000-01-01"},
            )

    def test_system_only_field_cannot_be_written_by_normal_user(self):
        """system_only field is rejected for any non-system principal."""
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="is_deleted", system_only=True),
        )
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="update",
                model=model,
                payload={"name": "Acme", "is_deleted": True},
            )

    def test_allowed_payload_succeeds_after_adversarial_test(self):
        """Confirm enforcement does not block legitimate payloads."""
        p = Principal.for_user(user_id="u1")
        model = FakeModel.with_fields(
            FakeField(name="name"),
            FakeField(name="amount"),
        )
        decision = enforce_payload_policy(
            principal=p,
            action="update",
            model=model,
            payload={"name": "Acme Corp", "amount": 500},
        )
        assert decision.allowed

    def test_anonymous_cannot_write_to_protected_action(self):
        """Anonymous principal is denied any protected write action."""
        p = Principal.anonymous()
        model = FakeModel.with_fields(FakeField(name="name"))
        with pytest.raises(PolicyDenied):
            enforce_payload_policy(
                principal=p,
                action="create",
                model=model,
                payload={"name": "Exploit"},
            )
