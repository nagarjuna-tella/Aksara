"""
Aksara Security — Compatibility Adapters

Bridge between the new Principal/PolicyEngine model and existing
Aksara permission primitives (BasePermission, ai_allow, ai_sensitive,
ai_agent_writable).

Round 2: creates the bridge so existing code is not broken while the
new canonical model is introduced. Existing permission classes are
NOT removed or mass-replaced — they continue to work. The adapters
allow the new system to read existing metadata and decisions.

Future rounds will progressively migrate surfaces to the new model.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from aksara.security.decisions import PolicyDecision
from aksara.security.principal import Principal

# ---------------------------------------------------------------------------
# BasePermission bridge
# ---------------------------------------------------------------------------


def decision_from_base_permission(
    permission_instance: Any,
    request: Any,
    view: Any = None,
    *,
    action: Optional[str] = None,
) -> PolicyDecision:
    """
    Convert an existing BasePermission result into a PolicyDecision.

    This lets new code that expects PolicyDecision objects consume the
    result of existing BasePermission.has_permission() calls without
    rewriting the permission class.

    If the permission grants access → PolicyDecision.allow(...)
    If the permission denies access → PolicyDecision.deny(...)
    """
    try:
        granted = permission_instance.has_permission(request, view)
    except Exception as exc:
        return PolicyDecision.deny(
            f"Permission check raised an exception: {exc}",
            action=action,
        )

    if granted:
        return PolicyDecision.allow(
            f"{type(permission_instance).__name__} granted access.",
            action=action,
        )
    return PolicyDecision.deny(
        getattr(permission_instance, "message", "Permission denied."),
        action=action,
    )


def decision_from_permission_classes(
    permission_classes: Sequence[Any],
    request: Any,
    view: Any = None,
    *,
    action: Optional[str] = None,
) -> PolicyDecision:
    """
    Evaluate a list of existing permission classes (AND semantics).

    All must pass. Returns the first denial encountered, or allow if all pass.
    """
    for cls in permission_classes:
        # Support both class objects and instances
        perm = cls() if isinstance(cls, type) else cls
        result = decision_from_base_permission(perm, request, view, action=action)
        if result.denied:
            return result
    return PolicyDecision.allow(
        "All permission classes granted access.",
        action=action,
    )


# ---------------------------------------------------------------------------
# AI metadata bridge
# ---------------------------------------------------------------------------


def principal_allows_ai_access(
    principal: Principal,
    view_or_resource: Any = None,
    *,
    permission_classes: Sequence[Any] = (),
) -> bool:
    """
    Return True if an AI agent principal should be allowed to access a resource,
    based on existing ai_allow metadata and DenyAI permission class patterns.

    Reads:
    - ``view_or_resource.ai_allow`` attribute (if set)
    - Any permission class with ``ai_allow = False`` (e.g. DenyAI)
    - Principal.is_ai_agent

    This adapts the existing ``ai_allow`` metadata pattern into the new model
    without removing the old pattern.
    """
    if not principal.is_ai_agent:
        return True  # Not an AI agent — ai_allow doesn't apply

    # Check resource/view-level ai_allow attribute
    if view_or_resource is not None:
        ai_allow = getattr(view_or_resource, "ai_allow", None)
        if ai_allow is False:
            return False

    # Check permission classes for DenyAI-like pattern (ai_allow=False)
    for cls in permission_classes:
        perm = cls() if isinstance(cls, type) else cls
        if getattr(perm, "ai_allow", True) is False:
            return False

    return True


def field_visible_to_ai(field_obj: Any) -> bool:
    """
    Return True if a field is visible to AI/MCP agents.

    Reads existing ai_sensitive metadata. Preserves the current default
    (ai_sensitive=False means visible).
    """
    return not bool(getattr(field_obj, "ai_sensitive", False))


def field_writable_by_ai(field_obj: Any) -> bool:
    """
    Return True if a field is writable by AI/MCP agents.

    Reads existing ai_agent_writable metadata. Preserves the current
    default (ai_agent_writable=True means writable).
    """
    return bool(getattr(field_obj, "ai_agent_writable", True))


# ---------------------------------------------------------------------------
# Principal → legacy request state bridge
# ---------------------------------------------------------------------------


def annotate_request_state(request: Any, principal: Principal) -> None:
    """
    Write principal attributes back to request.state for backwards
    compatibility with existing code that reads request.state.is_ai_agent,
    request.state.user_id, etc.

    Safe no-op if request has no state.
    """
    state = getattr(request, "state", None)
    if state is None:
        return

    try:
        state.principal = principal
        # Preserve existing attributes that middleware may have set
        if principal.is_ai_agent and not getattr(state, "is_ai_agent", False):
            state.is_ai_agent = True
        if principal.user_id and not getattr(state, "user_id", None):
            state.user_id = principal.user_id
        if principal.tenant_id and not getattr(state, "tenant_id", None):
            state.tenant_id = principal.tenant_id
    except (AttributeError, TypeError):
        pass  # Some mock/test request objects may not accept attribute writes


def principal_from_request_state(request: Any) -> Optional[Principal]:
    """
    Retrieve a previously resolved Principal from request.state.principal.

    Returns None if not set (caller should then use principal_from_request()).
    """
    state = getattr(request, "state", None)
    if state is None:
        return None
    return getattr(state, "principal", None)
