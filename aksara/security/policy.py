"""
Aksara Security — PolicyEngine

Central policy engine. All generated surfaces should eventually resolve an
actor into a Principal and then call this engine for authorization decisions.

Round 2: introduces the engine with can(), visible_fields(), writable_fields(),
query_filter(), and validate_payload(). Full cross-surface enforcement comes in Round 3.

Design philosophy:
- Every method returns a PolicyDecision, never a raw bool.
- Decisions include reason, allowed/denied fields, and metadata.
- The engine inspects field metadata (ai_sensitive, ai_agent_writable, read_only)
  without importing ORM or model internals.
- When in doubt, the engine preserves existing behavior rather than
  introducing new denials in Round 2.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

from aksara.security.decisions import PolicyDecision
from aksara.security.principal import Principal

# ---------------------------------------------------------------------------
# Field metadata inspection helpers
# ---------------------------------------------------------------------------

_TENANT_FIELD_NAMES = frozenset({"tenant_id", "tenant", "organisation_id", "org_id"})
_SYSTEM_FIELD_NAMES = frozenset({"id", "created_at", "updated_at", "deleted_at"})


def _get_field_attr(field_obj: Any, attr: str, default: Any = None) -> Any:
    """Safely retrieve an attribute from a field object."""
    return getattr(field_obj, attr, default)


def _iter_fields(model_or_fields: Any) -> Iterable[Any]:
    """
    Yield field objects from a model class or a collection of fields.

    Supports:
    - objects with a ``fields`` attribute (list/tuple)
    - dict mapping name -> field_obj
    - plain iterables of field objects
    """
    if hasattr(model_or_fields, "fields"):
        src = model_or_fields.fields
    elif isinstance(model_or_fields, dict):
        src = model_or_fields.values()
    elif hasattr(model_or_fields, "__iter__"):
        src = model_or_fields
    else:
        return
    yield from src


def _field_name(field_obj: Any) -> str:
    return str(_get_field_attr(field_obj, "name", "unknown"))


def _is_ai_sensitive(field_obj: Any) -> bool:
    return bool(_get_field_attr(field_obj, "ai_sensitive", False))


def _is_ai_agent_writable(field_obj: Any) -> bool:
    return bool(_get_field_attr(field_obj, "ai_agent_writable", True))


def _is_read_only(field_obj: Any) -> bool:
    return bool(_get_field_attr(field_obj, "read_only", False))


def _is_system_only(field_obj: Any) -> bool:
    return bool(_get_field_attr(field_obj, "system_only", False))


def _is_tenant_field(field_obj: Any) -> bool:
    return _field_name(field_obj) in _TENANT_FIELD_NAMES


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """
    Central policy engine for Aksara.

    Usage::

        from aksara.security.policy import default_policy
        from aksara.security.context import principal_from_request

        principal = principal_from_request(request)
        decision = default_policy.can(principal, "update", resource=invoice)
        if decision.denied:
            raise PolicyDenied(decision)

    All methods return PolicyDecision — never a raw bool.
    """

    # ------------------------------------------------------------------
    # can()
    # ------------------------------------------------------------------

    def can(
        self,
        principal: Principal,
        action: str,
        resource: Any = None,
        *,
        required_scopes: Sequence[str] = (),
        tenant_id: Optional[str] = None,
        **context: Any,
    ) -> PolicyDecision:
        """
        Determine whether a principal may perform an action on a resource.

        Standard actions:
          create, read, list, update, partial_update, delete,
          bulk_update, upsert, mcp_call, studio_access, ai_prompt_export,
          doctor_run, migration_generate, migration_execute,
          background_task_run

        Round 2 rules:
        - Anonymous principals are denied protected actions.
        - Expired tokens are denied.
        - Missing required scopes deny.
        - Cross-tenant resource access denies.
        - System principals are allowed for internal actions.
        - AI agents are not allowed write actions unless existing behavior
          already permits them.
        """
        # Expired token — deny before anything else
        if principal.is_expired:
            return PolicyDecision.deny(
                f"Token expired for action '{action}'.",
                action=action,
            )

        # Anonymous — deny protected actions
        protected = _is_protected_action(action)
        if principal.is_anonymous and protected:
            return PolicyDecision.deny(
                f"Anonymous principal cannot perform '{action}'.",
                action=action,
            )

        # Required scopes check
        if required_scopes:
            missing = tuple(s for s in required_scopes if not principal.has_scope(s))
            if missing:
                return PolicyDecision.deny(
                    f"Missing required scopes for '{action}': {list(missing)}.",
                    action=action,
                    required_scopes=tuple(required_scopes),
                    missing_scopes=missing,
                )

        # Cross-tenant resource check
        effective_tenant = tenant_id or principal.tenant_id
        resource_tenant = _resource_tenant(resource)
        if (
            resource_tenant is not None
            and effective_tenant is not None
            and resource_tenant != effective_tenant
            and not principal.is_system
        ):
            return PolicyDecision.deny(
                f"Cross-tenant access denied: principal tenant '{effective_tenant}' "
                f"!= resource tenant '{resource_tenant}'.",
                action=action,
                resource=_resource_label(resource),
                metadata={"principal_tenant": effective_tenant, "resource_tenant": resource_tenant},
            )

        # AI agents: deny write actions by default unless they are AI-explicitly-allowed.
        if principal.is_ai_agent and _is_write_action(action):
            # Allow if the resource or model has ai_allow=True or no restriction set.
            resource_ai_allow = _get_field_attr(resource, "ai_allow", None)
            if resource_ai_allow is False:
                return PolicyDecision.deny(
                    f"AI agent is not allowed to perform '{action}' on this resource (ai_allow=False).",
                    action=action,
                    resource=_resource_label(resource),
                )

        # System principal: allow most actions (trusts tenant context is already bound)
        if principal.is_system:
            return PolicyDecision.allow(
                f"System principal allowed for '{action}'.",
                action=action,
                resource=_resource_label(resource),
            )

        # Authenticated user or agent — allow (Round 2 preserves existing behavior)
        if principal.is_authenticated:
            return PolicyDecision.allow(
                f"Authenticated principal allowed for '{action}'.",
                action=action,
                resource=_resource_label(resource),
            )

        # Anonymous + non-protected (e.g. public read) — allow
        return PolicyDecision.allow(
            f"Action '{action}' permitted for anonymous principal.",
            action=action,
        )

    # ------------------------------------------------------------------
    # visible_fields()
    # ------------------------------------------------------------------

    def visible_fields(
        self,
        principal: Principal,
        resource_or_model: Any,
        **context: Any,
    ) -> PolicyDecision:
        """
        Return which fields of a model/resource are visible to the principal.

        Rules:
        - ai_sensitive=True fields are hidden from AI/MCP principals.
        - system_only=True fields are hidden from non-system principals.
        - System principals can see all fields.
        - Normal users see all non-system-only fields.
        """
        allowed: list[str] = []
        denied: list[str] = []

        for f in _iter_fields(resource_or_model):
            name = _field_name(f)

            if _is_system_only(f) and not principal.is_system:
                denied.append(name)
                continue

            if _is_ai_sensitive(f) and principal.is_ai_agent:
                denied.append(name)
                continue

            allowed.append(name)

        reason = (
            "All fields visible."
            if not denied
            else f"{len(denied)} field(s) hidden from this principal."
        )

        if denied:
            return PolicyDecision.partial(
                reason,
                allowed_fields=tuple(allowed),
                denied_fields=tuple(denied),
            )
        return PolicyDecision.allow(
            reason,
            allowed_fields=tuple(allowed),
        )

    # ------------------------------------------------------------------
    # writable_fields()
    # ------------------------------------------------------------------

    def writable_fields(
        self,
        principal: Principal,
        resource_or_model: Any,
        **context: Any,
    ) -> PolicyDecision:
        """
        Return which fields the principal may write.

        Rules:
        - read_only=True fields are never writable.
        - system_only=True fields are only writable by system principals.
        - Tenant fields (tenant_id, etc.) are not writable by normal/AI clients.
        - ai_agent_writable=False fields are not writable by AI/MCP agents.
        - System principal may write system/tenant fields.
        """
        allowed: list[str] = []
        denied: list[str] = []

        for f in _iter_fields(resource_or_model):
            name = _field_name(f)

            # read_only — never writable
            if _is_read_only(f):
                denied.append(name)
                continue

            # system_only — only writable by system
            if _is_system_only(f):
                if principal.is_system:
                    allowed.append(name)
                else:
                    denied.append(name)
                continue

            # tenant fields — not writable by normal or AI clients
            if _is_tenant_field(f):
                if principal.is_system:
                    allowed.append(name)
                else:
                    denied.append(name)
                continue

            # ai_agent_writable=False — not writable by AI/MCP agents
            if principal.is_ai_agent and not _is_ai_agent_writable(f):
                denied.append(name)
                continue

            allowed.append(name)

        if denied:
            return PolicyDecision.partial(
                f"{len(denied)} field(s) not writable by this principal.",
                allowed_fields=tuple(allowed),
                denied_fields=tuple(denied),
            )
        return PolicyDecision.allow(
            "All fields writable.",
            allowed_fields=tuple(allowed),
        )

    # ------------------------------------------------------------------
    # query_filter()
    # ------------------------------------------------------------------

    def query_filter(
        self,
        principal: Principal,
        model: Any,
        *,
        tenant_required: bool = False,
        **context: Any,
    ) -> PolicyDecision:
        """
        Return the required query constraints for a principal.

        If the principal has a tenant_id, returns metadata with
        the tenant filter that must be applied.
        If tenant is required but missing, returns a deny/warn decision.
        """
        # Detect tenant awareness on the model
        model_is_tenant_aware = _model_is_tenant_aware(model)

        if principal.is_system and principal.tenant_id:
            # System operating within a specific tenant
            return PolicyDecision.allow(
                "System principal with tenant context.",
                metadata={"filters": {"tenant_id": principal.tenant_id}},
            )

        if principal.is_system:
            # System with no tenant — cross-tenant access
            return PolicyDecision.allow(
                "System principal with no tenant constraint.",
                metadata={"filters": {}},
            )

        if principal.tenant_id and model_is_tenant_aware:
            return PolicyDecision.allow(
                "Tenant filter applied.",
                metadata={"filters": {"tenant_id": principal.tenant_id}},
            )

        if model_is_tenant_aware and not principal.tenant_id:
            if tenant_required:
                return PolicyDecision.deny(
                    "Tenant-aware model requires tenant context, but principal has no tenant_id.",
                    metadata={"filters": {}},
                )
            return PolicyDecision.warn(
                "Model appears tenant-aware but principal has no tenant_id. "
                "Query may return cross-tenant data.",
                metadata={"filters": {}},
            )

        return PolicyDecision.allow(
            "No tenant filter required.",
            metadata={"filters": {}},
        )

    # ------------------------------------------------------------------
    # validate_payload()
    # ------------------------------------------------------------------

    def validate_payload(
        self,
        principal: Principal,
        action: str,
        model: Any,
        payload: Mapping[str, Any],
        **context: Any,
    ) -> PolicyDecision:
        """
        Determine whether a write payload contains fields the principal cannot write.

        Returns allow if all payload fields are writable.
        Returns partial if some fields are forbidden (with denied_fields).
        Returns deny if the principal cannot perform the action at all.

        Note: Round 2 computes decisions but does NOT enforce rejection on
        every write surface yet. Wiring happens in Round 3.
        """
        # Can the principal perform this action at all?
        action_decision = self.can(principal, action, model, **context)
        if action_decision.denied:
            return PolicyDecision.deny(
                action_decision.reason,
                action=action,
                denied_fields=tuple(payload.keys()),
            )

        # Compute writable field set
        writable_decision = self.writable_fields(principal, model, **context)
        writable_set = set(writable_decision.allowed_fields)

        # If no field metadata available, fall back to allowing everything
        # to avoid false denials during the transition period.
        if not writable_decision.allowed_fields and not writable_decision.denied_fields:
            return PolicyDecision.allow(
                "No field metadata available; payload allowed (Round 2 fallback).",
                action=action,
                allowed_fields=tuple(payload.keys()),
            )

        forbidden = tuple(k for k in payload if k not in writable_set)
        allowed_in_payload = tuple(k for k in payload if k in writable_set)

        if forbidden:
            return PolicyDecision.partial(
                f"{len(forbidden)} field(s) in payload are not writable by this principal.",
                action=action,
                allowed_fields=allowed_in_payload,
                denied_fields=forbidden,
            )

        return PolicyDecision.allow(
            "All payload fields are writable.",
            action=action,
            allowed_fields=allowed_in_payload,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PROTECTED_ACTIONS = frozenset({
    "create", "update", "partial_update", "delete",
    "bulk_update", "upsert", "mcp_call", "studio_access",
    "migration_execute", "doctor_run",
})

_WRITE_ACTIONS = frozenset({
    "create", "update", "partial_update", "delete",
    "bulk_update", "upsert",
})


def _is_protected_action(action: str) -> bool:
    return action in _PROTECTED_ACTIONS


def _is_write_action(action: str) -> bool:
    return action in _WRITE_ACTIONS


def _resource_tenant(resource: Any) -> Optional[str]:
    if resource is None:
        return None
    tid = getattr(resource, "tenant_id", None)
    if tid is not None:
        return str(tid)
    return None


def _resource_label(resource: Any) -> Optional[str]:
    if resource is None:
        return None
    name = getattr(resource, "__name__", None) or getattr(resource, "__class__", None)
    if name and not isinstance(name, str):
        name = getattr(name, "__name__", None)
    return str(name) if name else None


def _model_is_tenant_aware(model: Any) -> bool:
    """Heuristic: model is tenant-aware if it has a tenant_id field."""
    if model is None:
        return False
    # Check for field named tenant_id
    for f in _iter_fields(model):
        if _field_name(f) in _TENANT_FIELD_NAMES:
            return True
    # Check for a tenant_id attribute on the model class itself
    if hasattr(model, "tenant_id"):
        return True
    return False


# ---------------------------------------------------------------------------
# Default engine instance
# ---------------------------------------------------------------------------

default_policy = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    """Return the default policy engine instance."""
    return default_policy
