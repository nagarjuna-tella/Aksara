"""
Aksara Security — Runtime Payload Enforcement

Central helper for enforcing field-level write restrictions at runtime.

Round 3 closes the generated-schema gap: generated schemas are not security
controls. A malicious client can always send raw JSON. These helpers validate
the payload against the principal's writable fields BEFORE any database write.

Usage::

    # In a viewset or endpoint:
    from aksara.security.enforcement import enforce_request_payload_policy
    from aksara.security.exceptions import PolicyDenied

    try:
        enforce_request_payload_policy(
            request=request,
            action="create",
            model=self.model,
            payload=data,
            surface="rest_create",
        )
    except PolicyDenied as exc:
        raise HTTPException(403, detail=policy_denied_to_error_payload(exc))

Design rules:
- Never treat a missing principal as a system principal.
- Never silently strip forbidden fields — reject with a structured error.
- Use request.state.principal if set (by AIAgentMiddleware); otherwise resolve.
- policy.validate_payload() is the single source of truth for field rules.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from typing import Any, Mapping, Optional

from aksara.security.context import principal_from_request
from aksara.security.decisions import PolicyDecision
from aksara.security.exceptions import PolicyDenied
from aksara.security.policy import PolicyEngine, get_policy_engine
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# Public enforcement helpers
# ---------------------------------------------------------------------------


def enforce_payload_policy(
    *,
    principal: Principal,
    action: str,
    model: Any,
    payload: Mapping[str, Any],
    policy: Optional[PolicyEngine] = None,
    surface: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    """
    Validate that payload fields are writable by the principal.

    Raises PolicyDenied when forbidden fields are present or the action is
    outright denied. Returns the PolicyDecision on success.

    Args:
        principal: Resolved Principal for this request.
        action: Action string ("create", "update", "partial_update", …).
        model: The Aksara model class (fields inspected via _fields / fields).
        payload: The raw write payload dict.
        policy: Optional PolicyEngine override; defaults to the shared instance.
        surface: Optional surface label for logging/matrix (e.g. "rest_create").
        context: Optional extra context passed through to the policy engine.

    Raises:
        PolicyDenied: When the decision is denied or partial with denied fields.

    Returns:
        PolicyDecision: The allow decision when enforcement passes.
    """
    if not isinstance(payload, MappingABC):
        raise PolicyDenied(
            PolicyDecision.deny(
                "Payload must be a mapping.",
                action=action,
                metadata={"surface": surface, "payload_type": type(payload).__name__},
            )
        )

    engine = policy or get_policy_engine()
    extra = context or {}

    decision = engine.validate_payload(
        principal,
        action,
        model,
        payload,
        **extra,
    )

    if decision.denied or decision.is_partial:
        raise PolicyDenied(decision)

    return decision


def validate_bulk_payload_policy(
    *,
    principal: Principal,
    action: str,
    model: Any,
    payloads: SequenceABC[Mapping[str, Any]],
    policy: Optional[PolicyEngine] = None,
    surface: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    """
    Validate a batch of write payloads as one security boundary.

    Any denied item denies the whole batch. This helper intentionally lives at
    the enforcement layer; manager-level bulk_update/upsert integration remains
    a separate, explicit rollout decision.
    """
    if isinstance(payloads, (str, bytes)) or not isinstance(payloads, SequenceABC):
        raise PolicyDenied(
            PolicyDecision.deny(
                "Bulk payload must be a sequence of mapping items.",
                action=action,
                metadata={"surface": surface, "payload_type": type(payloads).__name__},
            )
        )

    if not payloads:
        return PolicyDecision.allow(
            "Empty bulk payload allowed.",
            action=action,
            metadata={"surface": surface, "items": 0},
        )

    engine = policy or get_policy_engine()
    extra = context or {}
    denied_fields: list[str] = []
    denied_items: list[int] = []

    for index, item in enumerate(payloads):
        if not isinstance(item, MappingABC):
            denied_items.append(index)
            denied_fields.append(f"[{index}]")
            continue

        decision = engine.validate_payload(principal, action, model, item, **extra)
        if decision.denied or decision.is_partial:
            denied_items.append(index)
            denied_fields.extend(str(field) for field in decision.denied_fields)

    if denied_items:
        unique_denied = tuple(dict.fromkeys(denied_fields))
        raise PolicyDenied(
            PolicyDecision.partial(
                "Bulk payload contains fields not writable by this principal.",
                action=action,
                denied_fields=unique_denied,
                metadata={
                    "surface": surface,
                    "denied_items": tuple(denied_items),
                    "items": len(payloads),
                },
            )
        )

    return PolicyDecision.allow(
        "All bulk payload items are writable.",
        action=action,
        metadata={"surface": surface, "items": len(payloads)},
    )


def validate_upsert_payload_policy(
    *,
    principal: Principal,
    model: Any,
    insert_payload: Mapping[str, Any],
    update_payload: Optional[Mapping[str, Any]] = None,
    conflict_target: SequenceABC[str] = (),
    policy: Optional[PolicyEngine] = None,
    surface: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    """
    Validate helper-level upsert-shaped payloads.

    Insert values are checked as ``create`` and update/default values as
    ``update``. Conflict targets are accepted only when they name real model
    fields, preventing raw identifier fragments from reaching ON CONFLICT.
    """
    if not isinstance(insert_payload, MappingABC):
        raise PolicyDenied(
            PolicyDecision.deny(
                "Upsert insert payload must be a mapping.",
                action="upsert",
                metadata={"surface": surface, "payload_type": type(insert_payload).__name__},
            )
        )
    if update_payload is not None and not isinstance(update_payload, MappingABC):
        raise PolicyDenied(
            PolicyDecision.deny(
                "Upsert update payload must be a mapping.",
                action="upsert",
                metadata={"surface": surface, "payload_type": type(update_payload).__name__},
            )
        )

    model_fields = getattr(model, "_fields", {}) or {}
    unsafe_targets = tuple(
        str(target)
        for target in conflict_target
        if not isinstance(target, str) or target not in model_fields
    )
    if unsafe_targets:
        raise PolicyDenied(
            PolicyDecision.deny(
                "Upsert conflict target must name known model fields.",
                action="upsert",
                denied_fields=unsafe_targets,
                metadata={"surface": surface, "conflict_target": tuple(conflict_target)},
            )
        )

    engine = policy or get_policy_engine()
    extra = context or {}
    denied_fields: list[str] = []

    insert_decision = engine.validate_payload(
        principal, "create", model, insert_payload, **extra
    )
    if insert_decision.denied or insert_decision.is_partial:
        denied_fields.extend(str(field) for field in insert_decision.denied_fields)

    if update_payload is not None:
        update_decision = engine.validate_payload(
            principal, "update", model, update_payload, **extra
        )
        if update_decision.denied or update_decision.is_partial:
            denied_fields.extend(str(field) for field in update_decision.denied_fields)

    if denied_fields:
        raise PolicyDenied(
            PolicyDecision.partial(
                "Upsert payload contains fields not writable by this principal.",
                action="upsert",
                denied_fields=tuple(dict.fromkeys(denied_fields)),
                metadata={"surface": surface},
            )
        )

    return PolicyDecision.allow(
        "Upsert payload is writable.",
        action="upsert",
        metadata={"surface": surface},
    )


def enforce_request_payload_policy(
    *,
    request: Any,
    action: str,
    model: Any,
    payload: Mapping[str, Any],
    surface: Optional[str] = None,
    policy: Optional[PolicyEngine] = None,
) -> PolicyDecision:
    """
    Resolve Principal from request, then enforce payload policy.

    Principal resolution priority:
    1. request.state.principal (set by AIAgentMiddleware — already resolved)
    2. principal_from_request(request) — full resolution from request state/user
    3. Principal.anonymous() — if request is None or resolution fails

    Never treats a missing principal as a system principal.

    Args:
        request: Starlette/FastAPI request (or any object with .state attribute).
        action: Action string ("create", "update", etc.).
        model: The Aksara model class.
        payload: The raw write payload dict.
        surface: Optional surface label for logging/matrix.
        policy: Optional PolicyEngine override.

    Raises:
        PolicyDenied: When enforcement fails.

    Returns:
        PolicyDecision: The allow decision when enforcement passes.
    """
    principal = _resolve_principal(request)
    return enforce_payload_policy(
        principal=principal,
        action=action,
        model=model,
        payload=payload,
        policy=policy,
        surface=surface,
    )


# ---------------------------------------------------------------------------
# Error translation helper
# ---------------------------------------------------------------------------


def policy_denied_to_error_payload(exc: PolicyDenied) -> dict[str, Any]:
    """
    Convert a PolicyDenied exception to a structured error response dict.

    Compatible with FastAPI's HTTPException detail parameter.

    Response shape::

        {
            "detail": "Payload contains fields not writable by this principal.",
            "reason": "...",
            "denied_fields": ["field_a", "field_b"],
            "required_scopes": [],
            "missing_scopes": [],
        }
    """
    decision = exc.decision
    return {
        "detail": "Payload contains fields not writable by this principal.",
        "reason": decision.reason,
        "denied_fields": list(decision.denied_fields),
        "required_scopes": list(decision.required_scopes),
        "missing_scopes": list(decision.missing_scopes),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_principal(request: Any) -> Principal:
    """
    Resolve the Principal from a request, never as system.

    Priority:
    1. request.state.principal (pre-resolved by AIAgentMiddleware)
    2. principal_from_request(request)
    3. Principal.anonymous() on any failure
    """
    if request is None:
        return Principal.anonymous()

    state = getattr(request, "state", None)
    if state is not None:
        cached = getattr(state, "principal", None)
        if cached is not None and isinstance(cached, Principal):
            return cached

    try:
        return principal_from_request(request)
    except Exception:
        return Principal.anonymous()
