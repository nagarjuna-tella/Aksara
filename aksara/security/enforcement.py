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
