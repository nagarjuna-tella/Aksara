"""
Tests for aksara.security.decisions — PolicyDecision.

Round 2: structured policy evaluation result.
"""

from __future__ import annotations

import pytest

from aksara.security.decisions import PolicyDecision


class TestAllowDecision:
    def test_allow_decision(self):
        d = PolicyDecision.allow("Permitted.")
        assert d.allowed
        assert not d.denied
        assert d.effect == "allow"
        assert d.reason == "Permitted."

    def test_allow_with_fields(self):
        d = PolicyDecision.allow("ok", allowed_fields=("name", "amount"))
        assert "name" in d.allowed_fields
        assert "amount" in d.allowed_fields

    def test_allow_with_action(self):
        d = PolicyDecision.allow("ok", action="update")
        assert d.action == "update"

    def test_allow_with_metadata(self):
        d = PolicyDecision.allow("ok", metadata={"filters": {"tenant_id": "t1"}})
        assert d.metadata["filters"]["tenant_id"] == "t1"


class TestDenyDecision:
    def test_deny_decision(self):
        d = PolicyDecision.deny("Not allowed.")
        assert d.denied
        assert not d.allowed
        assert d.effect == "deny"
        assert d.reason == "Not allowed."

    def test_deny_includes_reason(self):
        d = PolicyDecision.deny("Missing scopes.")
        assert "Missing scopes" in d.reason

    def test_deny_with_denied_fields(self):
        d = PolicyDecision.deny("Fields forbidden.", denied_fields=("internal_notes",))
        assert "internal_notes" in d.denied_fields

    def test_deny_with_missing_scopes(self):
        d = PolicyDecision.deny(
            "Scope required.",
            required_scopes=("mcp:write:invoice",),
            missing_scopes=("mcp:write:invoice",),
        )
        assert "mcp:write:invoice" in d.missing_scopes
        assert "mcp:write:invoice" in d.required_scopes


class TestPartialDecision:
    def test_partial_decision(self):
        d = PolicyDecision.partial(
            "Some fields denied.",
            allowed_fields=("name", "amount"),
            denied_fields=("internal_notes",),
        )
        assert d.is_partial
        assert not d.allowed
        assert not d.denied
        assert d.effect == "partial"

    def test_partial_includes_allowed_and_denied_fields(self):
        d = PolicyDecision.partial(
            "Mixed.",
            allowed_fields=("a", "b"),
            denied_fields=("c",),
        )
        assert "a" in d.allowed_fields
        assert "b" in d.allowed_fields
        assert "c" in d.denied_fields


class TestWarnDecision:
    def test_warn_decision(self):
        d = PolicyDecision.warn("Advisory warning.")
        assert d.is_warning
        assert not d.denied
        assert not d.allowed
        assert d.effect == "warn"

    def test_warn_with_reason(self):
        d = PolicyDecision.warn("No tenant context — cross-tenant data possible.")
        assert "cross-tenant" in d.reason


class TestDecisionImmutability:
    def test_decision_is_frozen(self):
        d = PolicyDecision.allow("ok")
        with pytest.raises((AttributeError, TypeError)):
            d.effect = "deny"  # type: ignore[misc]

    def test_decision_repr(self):
        d = PolicyDecision.allow("ok", action="read")
        r = repr(d)
        assert "allow" in r
        assert "read" in r
