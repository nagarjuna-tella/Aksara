"""
Aksara Security — Exceptions

Security-specific exception hierarchy. Round 3 will begin raising PolicyDenied
across generated write surfaces. In Round 2, these exceptions are defined and
available but not yet raised automatically everywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.security.decisions import PolicyDecision


class SecurityError(Exception):
    """Base class for all Aksara security errors."""


class PolicyDenied(SecurityError):
    """
    Raised when a policy engine decision denies an action.

    Round 3 will wire this into every generated write surface.
    In Round 2, it is available for explicit callers.

    Usage::

        decision = policy.can(principal, "update", resource)
        if decision.denied:
            raise PolicyDenied(decision)
    """

    def __init__(self, decision: "PolicyDecision") -> None:
        self.decision = decision
        super().__init__(
            f"Policy denied: {decision.reason} "
            f"(action={decision.action!r}, resource={decision.resource!r})"
        )


class PrincipalResolutionError(SecurityError):
    """Raised when a Principal cannot be resolved from a request or context."""


class TenantContextMissing(SecurityError):
    """
    Raised when tenant context is required but missing.

    Multi-tenant surfaces must fail closed rather than returning data
    for all tenants when tenant context is absent.
    """
