"""Server-side bearer-token authentication and tenant resolution."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from aksara.context_state import tenant_id_var, user_id_var
from aksara.security.context import principal_from_mcp_claims
from aksara.security.principal import Principal


@dataclass(frozen=True)
class _TokenIdentity:
    token: str
    tenant_id: str
    user_id: str
    role: str
    mcp: bool = False


def _configured_identities() -> tuple[_TokenIdentity, ...]:
    tenant_a = os.getenv("SUPPORT_DESK_TENANT_A_ID", "00000000-0000-0000-0000-000000000001")
    tenant_b = os.getenv("SUPPORT_DESK_TENANT_B_ID", "00000000-0000-0000-0000-000000000002")
    return (
        _TokenIdentity(
            os.getenv("SUPPORT_DESK_TENANT_A_TOKEN", "development-tenant-a-token"),
            tenant_a,
            "support-user-a",
            "admin",
        ),
        _TokenIdentity(
            os.getenv("SUPPORT_DESK_TENANT_B_TOKEN", "development-tenant-b-token"),
            tenant_b,
            "support-user-b",
            "agent",
        ),
        _TokenIdentity(
            os.getenv("SUPPORT_DESK_MCP_TOKEN", "development-mcp-agent-token"),
            tenant_a,
            "support-mcp-owner",
            "mcp",
            mcp=True,
        ),
    )


def _bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _resolve_identity(token: str | None) -> _TokenIdentity | None:
    if token is None:
        return None
    for identity in _configured_identities():
        if hmac.compare_digest(token, identity.token):
            return identity
    return None


class SupportDeskAuthMiddleware(BaseHTTPMiddleware):
    """Resolve identity and tenant from a server-owned token mapping."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        identity = _resolve_identity(_bearer_token(request))
        if identity is None:
            principal = Principal.anonymous()
            user = SimpleNamespace(
                id=None,
                role=None,
                is_authenticated=False,
                is_staff=False,
                is_superuser=False,
            )
        elif identity.mcp:
            expires_at = float(
                os.getenv("SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT", "0")
            )
            principal = principal_from_mcp_claims(
                {
                    "jti": "support-desk-mcp",
                    "sub": identity.user_id,
                    "agent_id": "support-desk-reference-agent",
                    "tenant_id": identity.tenant_id,
                    "scopes": ("mcp:read:ticket", "mcp:write:ticket"),
                    "aud": os.getenv(
                        "SUPPORT_DESK_MCP_AUDIENCE",
                        "support-desk",
                    ),
                    "exp": expires_at,
                }
            )
            if principal.is_expired:
                principal = Principal.anonymous()
            user = SimpleNamespace(
                id=None if principal.is_anonymous else identity.user_id,
                role=None if principal.is_anonymous else identity.role,
                is_authenticated=not principal.is_anonymous,
                is_staff=False,
                is_superuser=False,
            )
        else:
            principal = Principal.for_user(
                identity.user_id,
                tenant_id=identity.tenant_id,
                roles=(identity.role,),
                auth_method="api_key",
            )
            user = SimpleNamespace(
                id=identity.user_id,
                role=identity.role,
                is_authenticated=True,
                is_staff=identity.role == "admin",
                is_superuser=False,
            )

        request.state.user = user
        request.state.principal = principal
        request.state.tenant_id = principal.tenant_id
        request.state.auth_method = principal.auth_method
        request.state.is_ai_agent = principal.is_ai_agent
        tenant_token = tenant_id_var.set(principal.tenant_id)
        user_token = user_id_var.set(principal.user_id or principal.human_owner_id)
        try:
            return await call_next(request)
        finally:
            user_id_var.reset(user_token)
            tenant_id_var.reset(tenant_token)
