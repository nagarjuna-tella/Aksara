"""
Aksara Security — PolicyDecision

Structured result of every policy evaluation. Every call to the policy engine
returns a PolicyDecision so that callers can inspect, log, and act on the
decision consistently.

Round 2: introduces PolicyDecision as the return type for all policy methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

DecisionEffect = Literal["allow", "deny", "partial", "warn"]


@dataclass(frozen=True)
class PolicyDecision:
    """
    Immutable result of a policy evaluation.

    Always includes:
      - effect: the outcome (allow / deny / partial / warn)
      - reason: human-readable explanation
    """

    effect: DecisionEffect
    reason: str
    action: str | None = None
    resource: str | None = None
    allowed_fields: tuple[str, ...] = ()
    denied_fields: tuple[str, ...] = ()
    required_scopes: tuple[str, ...] = ()
    missing_scopes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def allowed(self) -> bool:
        """True when the decision permits the action."""
        return self.effect == "allow"

    @property
    def denied(self) -> bool:
        """True when the decision blocks the action."""
        return self.effect == "deny"

    @property
    def is_partial(self) -> bool:
        """True when some fields are allowed and some are denied."""
        return self.effect == "partial"

    @property
    def is_warning(self) -> bool:
        """True for advisory decisions that do not hard-block."""
        return self.effect == "warn"

    def __repr__(self) -> str:
        return (
            f"PolicyDecision(effect={self.effect!r}, reason={self.reason!r}, "
            f"action={self.action!r})"
        )

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def allow(
        cls,
        reason: str = "Allowed",
        *,
        action: str | None = None,
        resource: str | None = None,
        allowed_fields: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "PolicyDecision":
        return cls(
            effect="allow",
            reason=reason,
            action=action,
            resource=resource,
            allowed_fields=allowed_fields,
            metadata=metadata or {},
        )

    @classmethod
    def deny(
        cls,
        reason: str,
        *,
        action: str | None = None,
        resource: str | None = None,
        denied_fields: tuple[str, ...] = (),
        required_scopes: tuple[str, ...] = (),
        missing_scopes: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "PolicyDecision":
        return cls(
            effect="deny",
            reason=reason,
            action=action,
            resource=resource,
            denied_fields=denied_fields,
            required_scopes=required_scopes,
            missing_scopes=missing_scopes,
            metadata=metadata or {},
        )

    @classmethod
    def partial(
        cls,
        reason: str,
        *,
        action: str | None = None,
        resource: str | None = None,
        allowed_fields: tuple[str, ...] = (),
        denied_fields: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "PolicyDecision":
        return cls(
            effect="partial",
            reason=reason,
            action=action,
            resource=resource,
            allowed_fields=allowed_fields,
            denied_fields=denied_fields,
            metadata=metadata or {},
        )

    @classmethod
    def warn(
        cls,
        reason: str,
        *,
        action: str | None = None,
        resource: str | None = None,
        allowed_fields: tuple[str, ...] = (),
        denied_fields: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "PolicyDecision":
        return cls(
            effect="warn",
            reason=reason,
            action=action,
            resource=resource,
            allowed_fields=allowed_fields,
            denied_fields=denied_fields,
            metadata=metadata or {},
        )
