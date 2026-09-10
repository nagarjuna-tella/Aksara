"""
Aksara Security — Principal

The canonical identity primitive for Aksara's policy engine.
Every generated surface should eventually resolve an incoming caller
into a Principal before asking the policy engine for authorization.

Round 2: introduces Principal as the single representation of "who is acting."
Full cross-surface enforcement comes in Round 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Literal, Mapping, Optional

AuthMethod = Literal[
    "anonymous",
    "session",
    "jwt",
    "api_key",
    "mcp_token",
    "ai_agent",
    "system",
]

_PROTECTED_ACTIONS = frozenset({
    "create", "update", "partial_update", "delete",
    "bulk_update", "upsert", "mcp_call", "studio_access",
    "migration_execute", "doctor_run",
})


@dataclass(frozen=True)
class Principal:
    """
    Canonical identity for an incoming caller.

    Immutable (frozen=True). Create via class-method constructors.
    """

    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    auth_method: AuthMethod = "anonymous"
    is_authenticated: bool = False
    is_ai_agent: bool = False
    is_system: bool = False
    human_owner_id: Optional[str] = None
    agent_id: Optional[str] = None
    token_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated and self.auth_method == "anonymous"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from datetime import timezone
        now = datetime.now(tz=self.expires_at.tzinfo or timezone.utc)
        return now > self.expires_at

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: Iterable[str]) -> bool:
        return bool(set(roles) & set(self.roles))

    # ------------------------------------------------------------------
    # Scope helpers
    # ------------------------------------------------------------------

    def has_scope(self, scope: str) -> bool:
        """
        Return True if this principal has the given scope.

        Supports simple wildcard matching:
          - ``*``           matches any scope (only for system/explicit grant)
          - ``mcp:read:*``  matches ``mcp:read:invoice``, ``mcp:read:user``, …
          - ``mcp:*``       matches ``mcp:read:invoice``, ``mcp:write:ticket``, …
        """
        if scope in self.scopes:
            return True
        for granted in self.scopes:
            if _scope_matches(granted, scope):
                return True
        return False

    def has_any_scope(self, scopes: Iterable[str]) -> bool:
        return any(self.has_scope(s) for s in scopes)

    def has_all_scopes(self, scopes: Iterable[str]) -> bool:
        return all(self.has_scope(s) for s in scopes)

    # ------------------------------------------------------------------
    # Class-method constructors
    # ------------------------------------------------------------------

    @classmethod
    def anonymous(cls) -> "Principal":
        """Unauthenticated caller with no identity."""
        return cls(
            auth_method="anonymous",
            is_authenticated=False,
            is_ai_agent=False,
            is_system=False,
        )

    @classmethod
    def for_user(
        cls,
        user_id: str,
        *,
        tenant_id: Optional[str] = None,
        roles: Iterable[str] = (),
        scopes: Iterable[str] = (),
        auth_method: AuthMethod = "session",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "Principal":
        """Authenticated human user."""
        return cls(
            user_id=str(user_id),
            tenant_id=tenant_id,
            roles=tuple(roles),
            scopes=tuple(scopes),
            auth_method=auth_method,
            is_authenticated=True,
            is_ai_agent=False,
            is_system=False,
            metadata=metadata or {},
        )

    @classmethod
    def for_ai_agent(
        cls,
        *,
        agent_id: Optional[str] = None,
        human_owner_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        scopes: Iterable[str] = (),
        token_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        auth_method: AuthMethod = "ai_agent",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "Principal":
        """AI agent identity (non-MCP)."""
        return cls(
            tenant_id=tenant_id,
            scopes=tuple(scopes),
            auth_method=auth_method,
            is_authenticated=True,
            is_ai_agent=True,
            is_system=False,
            human_owner_id=human_owner_id,
            agent_id=agent_id,
            token_id=token_id,
            expires_at=expires_at,
            metadata=metadata or {},
        )

    @classmethod
    def for_mcp_agent(
        cls,
        *,
        token_id: Optional[str] = None,
        human_owner_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        roles: Iterable[str] = (),
        scopes: Iterable[str] = (),
        expires_at: Optional[datetime] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "Principal":
        """MCP client/agent identity."""
        return cls(
            tenant_id=tenant_id,
            roles=tuple(roles),
            scopes=tuple(scopes),
            auth_method="mcp_token",
            is_authenticated=True,
            is_ai_agent=True,
            is_system=False,
            human_owner_id=human_owner_id,
            agent_id=agent_id,
            token_id=token_id,
            expires_at=expires_at,
            metadata=metadata or {},
        )

    @classmethod
    def system(
        cls,
        reason: Optional[str] = None,
        *,
        tenant_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "Principal":
        """Trusted internal background/system task."""
        meta: dict[str, Any] = dict(metadata or {})
        if reason:
            meta["reason"] = reason
        return cls(
            tenant_id=tenant_id,
            auth_method="system",
            is_authenticated=True,
            is_ai_agent=False,
            is_system=True,
            metadata=meta,
        )

    def __repr__(self) -> str:
        if self.is_anonymous:
            return "Principal(anonymous)"
        if self.is_system:
            return f"Principal(system, tenant={self.tenant_id!r})"
        if self.is_ai_agent:
            kind = "mcp" if self.auth_method == "mcp_token" else "ai_agent"
            return f"Principal({kind}, agent_id={self.agent_id!r}, tenant={self.tenant_id!r})"
        return f"Principal(user_id={self.user_id!r}, tenant={self.tenant_id!r}, roles={list(self.roles)})"


# ---------------------------------------------------------------------------
# Scope matching helpers
# ---------------------------------------------------------------------------

def _scope_matches(granted: str, required: str) -> bool:
    """
    Match a granted scope against a required scope.

    Wildcard rules:
      - ``*`` matches any single-segment or multi-segment scope
      - ``mcp:read:*`` matches ``mcp:read:invoice``
      - ``mcp:*`` matches ``mcp:read:invoice``

    Only the granted scope may contain wildcards, not the required scope.
    """
    if granted == "*":
        return True
    if "*" not in granted:
        return granted == required

    granted_parts = granted.split(":")
    required_parts = required.split(":")

    for gp, rp in zip(granted_parts, required_parts):
        if gp == "*":
            return True
        if gp != rp:
            return False
    return len(granted_parts) == len(required_parts)
