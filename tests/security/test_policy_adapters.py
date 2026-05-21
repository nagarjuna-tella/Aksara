"""
Tests for aksara.security.adapters — compatibility bridge.

Round 2: adapters between new Principal/PolicyDecision and existing
BasePermission / ai_allow / ai_sensitive patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from aksara.security.adapters import (
    annotate_request_state,
    decision_from_base_permission,
    decision_from_permission_classes,
    field_visible_to_ai,
    field_writable_by_ai,
    principal_allows_ai_access,
    principal_from_request_state,
)
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# Fake permission classes (DRF-style BasePermission)
# ---------------------------------------------------------------------------


class AlwaysAllow:
    def has_permission(self, request: Any, view: Any) -> bool:
        return True


class AlwaysDeny:
    message = "Explicitly denied."

    def has_permission(self, request: Any, view: Any) -> bool:
        return False


class RaisingPermission:
    def has_permission(self, request: Any, view: Any) -> bool:
        raise RuntimeError("DB is down")


class DenyAI:
    ai_allow = False

    def has_permission(self, request: Any, view: Any) -> bool:
        return True


# ---------------------------------------------------------------------------
# Fake field objects
# ---------------------------------------------------------------------------


@dataclass
class FakeField:
    name: str
    ai_sensitive: bool = False
    ai_agent_writable: bool = True


# ---------------------------------------------------------------------------
# Fake request state
# ---------------------------------------------------------------------------


@dataclass
class FakeState:
    principal: Any = None
    is_ai_agent: bool = False
    user_id: Any = None
    tenant_id: Any = None


@dataclass
class FakeRequest:
    state: Any = None


# ---------------------------------------------------------------------------
# decision_from_base_permission
# ---------------------------------------------------------------------------


class TestDecisionFromBasePermission:
    def test_allow_converts_to_allow_decision(self):
        perm = AlwaysAllow()
        d = decision_from_base_permission(perm, request=None, view=None)
        assert d.allowed
        assert "AlwaysAllow" in d.reason

    def test_deny_converts_to_deny_decision(self):
        perm = AlwaysDeny()
        d = decision_from_base_permission(perm, request=None, view=None)
        assert d.denied
        assert "Explicitly denied" in d.reason

    def test_exception_converts_to_deny(self):
        perm = RaisingPermission()
        d = decision_from_base_permission(perm, request=None, view=None)
        assert d.denied
        assert "exception" in d.reason.lower()

    def test_action_propagated(self):
        perm = AlwaysAllow()
        d = decision_from_base_permission(perm, request=None, view=None, action="read")
        assert d.action == "read"

    def test_deny_uses_permission_message(self):
        perm = AlwaysDeny()
        d = decision_from_base_permission(perm, request=None, view=None)
        assert d.reason == "Explicitly denied."


# ---------------------------------------------------------------------------
# decision_from_permission_classes
# ---------------------------------------------------------------------------


class TestDecisionFromPermissionClasses:
    def test_all_allow(self):
        d = decision_from_permission_classes([AlwaysAllow, AlwaysAllow], request=None, view=None)
        assert d.allowed

    def test_first_deny_stops_evaluation(self):
        d = decision_from_permission_classes([AlwaysDeny, AlwaysAllow], request=None, view=None)
        assert d.denied

    def test_empty_list_allows(self):
        d = decision_from_permission_classes([], request=None, view=None)
        assert d.allowed

    def test_accepts_class_instances(self):
        d = decision_from_permission_classes([AlwaysAllow()], request=None)
        assert d.allowed

    def test_action_propagated(self):
        d = decision_from_permission_classes([AlwaysAllow], request=None, action="update")
        assert d.action == "update"


# ---------------------------------------------------------------------------
# principal_allows_ai_access
# ---------------------------------------------------------------------------


class TestPrincipalAllowsAIAccess:
    def test_non_ai_principal_always_allowed(self):
        p = Principal.for_user(user_id="u1")
        assert principal_allows_ai_access(p)

    def test_ai_agent_allowed_when_no_restriction(self):
        p = Principal.for_ai_agent()
        assert principal_allows_ai_access(p)

    def test_ai_agent_denied_when_view_ai_allow_false(self):
        p = Principal.for_ai_agent()
        view = MagicMock()
        view.ai_allow = False
        assert not principal_allows_ai_access(p, view_or_resource=view)

    def test_ai_agent_allowed_when_view_ai_allow_true(self):
        p = Principal.for_ai_agent()
        view = MagicMock()
        view.ai_allow = True
        assert principal_allows_ai_access(p, view_or_resource=view)

    def test_ai_agent_denied_when_permission_class_denies_ai(self):
        p = Principal.for_ai_agent()
        assert not principal_allows_ai_access(p, permission_classes=[DenyAI])

    def test_ai_agent_denied_by_deny_ai_instance(self):
        p = Principal.for_ai_agent()
        assert not principal_allows_ai_access(p, permission_classes=[DenyAI()])


# ---------------------------------------------------------------------------
# field_visible_to_ai / field_writable_by_ai
# ---------------------------------------------------------------------------


class TestFieldMetadataAdapters:
    def test_visible_to_ai_default(self):
        f = FakeField(name="normal")
        assert field_visible_to_ai(f)

    def test_hidden_when_ai_sensitive(self):
        f = FakeField(name="secret", ai_sensitive=True)
        assert not field_visible_to_ai(f)

    def test_writable_by_ai_default(self):
        f = FakeField(name="status")
        assert field_writable_by_ai(f)

    def test_not_writable_when_ai_agent_writable_false(self):
        f = FakeField(name="amount", ai_agent_writable=False)
        assert not field_writable_by_ai(f)

    def test_visible_fallback_for_object_without_attribute(self):
        obj = object()
        assert field_visible_to_ai(obj)

    def test_writable_fallback_for_object_without_attribute(self):
        obj = object()
        assert field_writable_by_ai(obj)


# ---------------------------------------------------------------------------
# annotate_request_state
# ---------------------------------------------------------------------------


class TestAnnotateRequestState:
    def test_annotate_writes_principal(self):
        state = FakeState()
        request = FakeRequest(state=state)
        p = Principal.for_ai_agent(agent_id="a1", tenant_id="t1")
        annotate_request_state(request, p)
        assert state.principal is p

    def test_annotate_sets_is_ai_agent(self):
        state = FakeState()
        request = FakeRequest(state=state)
        p = Principal.for_ai_agent()
        annotate_request_state(request, p)
        assert state.is_ai_agent is True

    def test_annotate_sets_tenant_id(self):
        state = FakeState()
        request = FakeRequest(state=state)
        p = Principal.for_user(user_id="u1", tenant_id="t1")
        annotate_request_state(request, p)
        assert state.tenant_id == "t1"

    def test_annotate_no_state_is_noop(self):
        request = FakeRequest(state=None)
        p = Principal.for_user(user_id="u1")
        annotate_request_state(request, p)  # should not raise

    def test_annotate_does_not_overwrite_existing_is_ai_agent(self):
        state = FakeState(is_ai_agent=True)
        request = FakeRequest(state=state)
        p = Principal.for_user(user_id="u1")
        annotate_request_state(request, p)
        assert state.is_ai_agent is True  # unchanged

    def test_annotate_does_not_overwrite_existing_user_id(self):
        state = FakeState(user_id="existing-u1")
        request = FakeRequest(state=state)
        p = Principal.for_user(user_id="new-u1")
        annotate_request_state(request, p)
        assert state.user_id == "existing-u1"


# ---------------------------------------------------------------------------
# principal_from_request_state
# ---------------------------------------------------------------------------


class TestPrincipalFromRequestState:
    def test_returns_principal_if_set(self):
        p = Principal.for_user(user_id="u1")
        state = FakeState(principal=p)
        request = FakeRequest(state=state)
        result = principal_from_request_state(request)
        assert result is p

    def test_returns_none_if_not_set(self):
        state = FakeState()
        request = FakeRequest(state=state)
        result = principal_from_request_state(request)
        assert result is None

    def test_returns_none_when_no_state(self):
        request = FakeRequest(state=None)
        result = principal_from_request_state(request)
        assert result is None
