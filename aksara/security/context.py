"""
Aksara Security — Context Resolvers

Helpers for resolving a Principal from various request/context sources.
These are the entry points for creating a Principal from real Aksara requests.

Round 2: introduces principal_from_request(), principal_from_mcp_claims(),
principal_from_ai_agent(), and system_principal() as canonical resolver helpers.

Important: client-supplied tenant headers are NOT treated as authoritative.
Tenant context must come from server-side middleware state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

from aksara.security.principal import AuthMethod, Principal

# ---------------------------------------------------------------------------
# Basic constructors (re-exported for convenience)
# ---------------------------------------------------------------------------


def anonymous_principal() -> Principal:
    """Return a Principal representing an unauthenticated caller."""
    return Principal.anonymous()


def system_principal(
    reason: Optional[str] = None,
    *,
    tenant_id: Optional[str] = None,
) -> Principal:
    """Return a Principal representing a trusted internal system task."""
    return Principal.system(reason=reason, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# User-based resolver
# ---------------------------------------------------------------------------


def principal_from_user(
    user: Any,
    *,
    tenant_id: Optional[str] = None,
    roles: Iterable[str] = (),
    scopes: Iterable[str] = (),
    auth_method: AuthMethod = "session",
) -> Principal:
    """
    Build a Principal from a user object (AksaraUserProtocol or similar).

    Safe attribute lookups — no exception if an attribute is absent.
    """
    if user is None:
        return Principal.anonymous()

    is_auth = bool(getattr(user, "is_authenticated", False))
    if not is_auth:
        return Principal.anonymous()

    uid = getattr(user, "id", None) or getattr(user, "user_id", None)
    if uid is not None:
        uid = str(uid)

    # Derive roles from user if not explicitly supplied
    resolved_roles = list(roles)
    if not resolved_roles:
        if getattr(user, "is_superuser", False) or getattr(user, "is_admin", False):
            resolved_roles.append("admin")
        if getattr(user, "is_staff", False):
            resolved_roles.append("staff")

    return Principal.for_user(
        user_id=uid or "unknown",
        tenant_id=tenant_id,
        roles=resolved_roles,
        scopes=list(scopes),
        auth_method=auth_method,
    )


# ---------------------------------------------------------------------------
# Request-based resolver
# ---------------------------------------------------------------------------


def principal_from_request(request: Any) -> Principal:
    """
    Resolve a Principal from a Starlette/FastAPI request.

    Resolution order:
    1. If request.state.is_ai_agent == True → AI agent principal
    2. If request.state.user is set → user principal
    3. If request.user is set → user principal (Django-style compat)
    4. Otherwise → anonymous

    Tenant resolution (server-side only):
    - request.state.tenant_id (set by TenantMiddleware — TRUSTED)
    - request.tenant_id (Django-style attribute — TRUSTED)
    - client headers are NOT inspected; they are untrusted without middleware
      validation. If present in raw headers, they go into metadata only.

    Auth method detection:
    - request.state.auth_method if set by middleware
    - Otherwise "session" for user, "ai_agent" for AI agents
    """
    state = getattr(request, "state", None)

    # AI agent identity (set server-side by AIAgentMiddleware)
    if state is not None and getattr(state, "is_ai_agent", False) is True:
        tenant_id = _extract_tenant_id(request, state)
        agent_token_id = getattr(state, "ai_agent_token_id", None)
        return Principal.for_ai_agent(
            agent_id=getattr(state, "ai_agent_id", None),
            human_owner_id=getattr(state, "ai_agent_human_owner", None),
            tenant_id=tenant_id,
            token_id=agent_token_id,
            auth_method="ai_agent",
            metadata=_safe_request_metadata(request, state),
        )

    # Authenticated user
    user = _extract_user(request, state)
    if user is not None and getattr(user, "is_authenticated", False):
        tenant_id = _extract_tenant_id(request, state)
        auth_method: AuthMethod = _detect_auth_method(request, state)
        return principal_from_user(
            user,
            tenant_id=tenant_id,
            auth_method=auth_method,
        )

    # Anonymous
    return Principal.anonymous()


# ---------------------------------------------------------------------------
# MCP claims resolver
# ---------------------------------------------------------------------------


def principal_from_mcp_claims(claims: Mapping[str, Any]) -> Principal:
    """
    Build a Principal from MCP token claims.

    Expected claim keys:
      - sub or user_id: the human owner's user ID
      - tenant_id: tenant scope
      - agent_id: identifier for the specific agent
      - token_id: unique token ID (for revocation/audit)
      - scopes: list of granted scopes
      - exp: expiry Unix timestamp
      - iat: issued-at Unix timestamp
    """
    human_owner = (
        claims.get("sub") or claims.get("user_id") or claims.get("human_owner_id")
    )
    tenant_id = claims.get("tenant_id")
    agent_id = claims.get("agent_id")
    token_id = claims.get("token_id") or claims.get("jti")
    scopes_raw = claims.get("scopes", [])
    if isinstance(scopes_raw, str):
        scopes_raw = scopes_raw.split()
    scopes = list(scopes_raw)

    expires_at: Optional[datetime] = None
    exp = claims.get("exp")
    if exp is not None:
        try:
            expires_at = datetime.fromtimestamp(float(exp), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            pass

    audience = claims.get("aud") or claims.get("audience")
    metadata = {k: v for k, v in claims.items()
                if k not in ("sub", "user_id", "tenant_id", "agent_id",
                             "token_id", "jti", "scopes", "exp", "iat", "aud", "audience")}
    if audience:
        metadata["audience"] = audience

    return Principal.for_mcp_agent(
        token_id=token_id,
        human_owner_id=str(human_owner) if human_owner else None,
        tenant_id=str(tenant_id) if tenant_id else None,
        agent_id=str(agent_id) if agent_id else None,
        scopes=scopes,
        expires_at=expires_at,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# AI agent resolver
# ---------------------------------------------------------------------------


def principal_from_ai_agent(
    agent: Any = None,
    *,
    agent_id: Optional[str] = None,
    human_owner_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    scopes: Iterable[str] = (),
    token_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Principal:
    """
    Build a Principal for an AI agent from explicit kwargs or an agent object.

    If an ``agent`` object is provided, safe attribute lookups are used.
    Explicit kwargs take precedence.
    """
    if agent is not None:
        agent_id = agent_id or getattr(agent, "agent_id", None) or getattr(agent, "id", None)
        human_owner_id = human_owner_id or getattr(agent, "human_owner_id", None)
        tenant_id = tenant_id or getattr(agent, "tenant_id", None)
        if not list(scopes):
            raw = getattr(agent, "scopes", []) or []
            scopes = list(raw)

    return Principal.for_ai_agent(
        agent_id=str(agent_id) if agent_id else None,
        human_owner_id=str(human_owner_id) if human_owner_id else None,
        tenant_id=str(tenant_id) if tenant_id else None,
        scopes=list(scopes),
        token_id=token_id,
        expires_at=expires_at,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_user(request: Any, state: Any) -> Any:
    """Extract user from request, checking common locations."""
    if state is not None:
        user = getattr(state, "user", None)
        if user is not None:
            return user
    return getattr(request, "user", None)


def _extract_tenant_id(request: Any, state: Any) -> Optional[str]:
    """
    Extract tenant_id from trusted server-side sources only.

    Trusted:
      - request.state.tenant_id (set by TenantMiddleware)
      - request.tenant_id (set by middleware or dependency injection)

    NOT trusted (ignored):
      - raw request headers (client-controlled)
    """
    if state is not None:
        tid = getattr(state, "tenant_id", None)
        if tid is not None:
            return str(tid)
    tid = getattr(request, "tenant_id", None)
    if tid is not None:
        return str(tid)
    return None


def _detect_auth_method(request: Any, state: Any) -> AuthMethod:
    """Detect auth method from request state."""
    if state is not None:
        method = getattr(state, "auth_method", None)
        if method in ("session", "jwt", "api_key", "mcp_token", "ai_agent", "system"):
            return method  # type: ignore[return-value]
    # Heuristic: if there's an Authorization header, assume JWT/API key
    headers = getattr(request, "headers", {}) or {}
    auth_header = ""
    if hasattr(headers, "get"):
        auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return "jwt"
    if auth_header.startswith("Token "):
        return "api_key"
    return "session"


def _safe_request_metadata(request: Any, state: Any) -> dict[str, Any]:
    """Collect non-sensitive request metadata for the principal."""
    meta: dict[str, Any] = {}
    if state is not None:
        for attr in ("request_id", "correlation_id"):
            val = getattr(state, attr, None)
            if val is not None:
                meta[attr] = val
    return meta
