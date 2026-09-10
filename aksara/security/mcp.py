"""
Aksara Security — MCP Credential Helpers

Structured representation of MCP/AI agent token claims and enforcement
helpers for scope, audience, and tenant validation.

Round 4: introduces MCPCredentialClaims and require_* helpers for
per-tool scope enforcement, audience binding, and tenant-required checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

from aksara.security.decisions import PolicyDecision
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# MCPCredentialClaims
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPCredentialClaims:
    """
    Structured representation of claims extracted from an MCP/AI agent token.

    Use ``from_claims_dict()`` to parse a raw claims mapping (e.g. decoded JWT payload).
    """

    subject: Optional[str] = None
    human_owner_id: Optional[str] = None
    agent_id: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    audience: Optional[str] = None
    token_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @classmethod
    def from_claims_dict(cls, claims: Mapping[str, Any]) -> "MCPCredentialClaims":
        subject = claims.get("sub") or claims.get("user_id")
        human_owner_id = claims.get("human_owner_id") or subject
        agent_id = claims.get("agent_id")
        tenant_id = claims.get("tenant_id")
        token_id = claims.get("token_id") or claims.get("jti")
        audience = claims.get("aud") or claims.get("audience")

        scopes_raw = claims.get("scopes") or claims.get("scope") or []
        if isinstance(scopes_raw, str):
            scopes_raw = scopes_raw.split()
        scopes = tuple(scopes_raw)
        roles_raw = claims.get("roles") or claims.get("role") or []
        if isinstance(roles_raw, str):
            roles_raw = roles_raw.split()
        roles = tuple(roles_raw)

        expires_at: Optional[datetime] = None
        exp = claims.get("exp")
        if exp is not None:
            try:
                expires_at = datetime.fromtimestamp(float(exp), tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                pass

        issued_at: Optional[datetime] = None
        iat = claims.get("iat")
        if iat is not None:
            try:
                issued_at = datetime.fromtimestamp(float(iat), tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                pass

        known_keys = frozenset({
            "sub", "user_id", "human_owner_id", "agent_id", "tenant_id",
            "token_id", "jti", "aud", "audience", "roles", "role",
            "scopes", "scope", "exp", "iat",
        })
        metadata = {k: v for k, v in claims.items() if k not in known_keys}

        return cls(
            subject=str(subject) if subject else None,
            human_owner_id=str(human_owner_id) if human_owner_id else None,
            agent_id=str(agent_id) if agent_id else None,
            tenant_id=str(tenant_id) if tenant_id else None,
            roles=roles,
            scopes=scopes,
            audience=str(audience) if audience else None,
            token_id=str(token_id) if token_id else None,
            expires_at=expires_at,
            issued_at=issued_at,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Scope enforcement helpers
# ---------------------------------------------------------------------------


def require_scope(principal: Principal, scope: str) -> PolicyDecision:
    """Deny if the principal does not hold the given scope."""
    if principal.has_scope(scope):
        return PolicyDecision.allow(
            f"Principal has required scope '{scope}'.",
        )
    return PolicyDecision.deny(
        f"Missing required scope '{scope}'.",
        required_scopes=(scope,),
        missing_scopes=(scope,),
    )


def require_any_scope(principal: Principal, scopes: Sequence[str]) -> PolicyDecision:
    """Deny if the principal holds none of the given scopes."""
    scopes_tuple = tuple(scopes)
    for scope in scopes_tuple:
        if principal.has_scope(scope):
            return PolicyDecision.allow(
                f"Principal has at least one required scope ('{scope}').",
            )
    return PolicyDecision.deny(
        f"Missing all required scopes: {list(scopes_tuple)}.",
        required_scopes=scopes_tuple,
        missing_scopes=scopes_tuple,
    )


def require_all_scopes(principal: Principal, scopes: Sequence[str]) -> PolicyDecision:
    """Deny if the principal is missing any of the given scopes."""
    scopes_tuple = tuple(scopes)
    missing = tuple(s for s in scopes_tuple if not principal.has_scope(s))
    if not missing:
        return PolicyDecision.allow(
            f"Principal has all required scopes: {list(scopes_tuple)}.",
        )
    return PolicyDecision.deny(
        f"Missing required scopes: {list(missing)}.",
        required_scopes=scopes_tuple,
        missing_scopes=missing,
    )


# ---------------------------------------------------------------------------
# Audience and tenant enforcement helpers
# ---------------------------------------------------------------------------


def require_mcp_audience(
    principal: Principal,
    expected_audience: str,
) -> PolicyDecision:
    """Deny if the principal's token audience does not match the expected value."""
    actual = principal.metadata.get("audience") or principal.metadata.get("aud")
    if actual is None:
        return PolicyDecision.deny(
            f"Token has no audience claim; expected '{expected_audience}'.",
            metadata={"required_audience": expected_audience, "actual_audience": None},
        )
    if actual != expected_audience:
        return PolicyDecision.deny(
            f"Token audience '{actual}' does not match required '{expected_audience}'.",
            metadata={"required_audience": expected_audience, "actual_audience": actual},
        )
    return PolicyDecision.allow(
        f"Token audience '{actual}' matches required '{expected_audience}'.",
        metadata={"audience": actual},
    )


def require_mcp_tenant(
    principal: Principal,
    *,
    tenant_required: bool = True,
) -> PolicyDecision:
    """Deny if tenant_required is True and the principal has no tenant_id."""
    if not tenant_required:
        return PolicyDecision.allow("Tenant binding not required.")
    if principal.tenant_id:
        return PolicyDecision.allow(
            f"Principal has tenant context '{principal.tenant_id}'.",
            metadata={"tenant_id": principal.tenant_id},
        )
    return PolicyDecision.deny(
        "Tenant context required, but principal has no tenant_id.",
        metadata={"tenant_required": True},
    )
