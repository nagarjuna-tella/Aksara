# Authentication Security

> **Status:** Updated through Round 4 of the Aksara security-hardening milestone.
> The `Principal` object (Round 2) and MCP claims normalization (Round 4) are implemented.

## Overview

Aksara exposes data across multiple surfaces, each with its own authentication mechanism.
As of Round 2, all surfaces resolve a `Principal` object via a central policy engine.
Round 4 adds MCP claims normalization and per-tool scope/audience/tenant enforcement helpers.

## Supported Auth Surfaces

### REST endpoints

REST endpoints use Aksara's `BasePermission` system (modeled after Django REST Framework):

```python
from aksara.permissions import IsAuthenticated, IsActiveUser

class InvoiceViewSet(AksaraViewSet):
    permission_classes = [IsAuthenticated, IsActiveUser]
```

Built-in permission classes:
- `AllowAny` — no auth required
- `IsAuthenticated` — requires valid session or token
- `IsAdminUser` — requires admin role
- `IsActiveUser` — requires active account
- `IsOwnerOrReadOnly` — owner can mutate; others read-only
- `DenyAI` — blocks all AI agent identities

### Studio

Studio uses a shared bearer token (`AKSARA_STUDIO_AUTH_TOKEN`) validated by
`studio_require_auth=True` (default). Additionally, `studio_expose_in_production=False`
(default) prevents Studio from being accessible in production unless explicitly enabled.

**Key fix (v0.5.47):** Debug-mode auth bypass in Studio was patched. Studio now always
enforces auth regardless of debug mode.

### MCP tools

MCP agents must present an `X-Aksara-AI-Token` header. Tokens are HMAC-SHA256 signed
with `AKSARA_AI_AGENT_TOKEN` (shared secret) and include:
- `issued_at`: Unix timestamp
- `ttl`: token lifetime (default 300s)

Validated by `AIAgentMiddleware` → `verify_agent_token()` in `aksara/ai/auth.py`.

MCP is **disabled by default** (`mcp_enabled=False`).

### AI Console

AI Console is not yet implemented. When added, it will require explicit opt-in with
mandatory authentication (`AKSARA_AI_CONSOLE_AUTH_REQUIRED=true`).

### Background / system tasks

Background tasks do not have external auth — they run as trusted internal actors.
Security control: `tenant_id` is captured from trusted server-side context at enqueue
time. Tasks must not accept tenant identity from external input.

## MCP Claims Normalization (Round 4)

`principal_from_mcp_claims()` normalizes the `aud` and `audience` JWT claims into
`principal.metadata["audience"]` so that `require_mcp_audience()` and `PolicyEngine.can()`
can reliably find it regardless of which claim key was used:

```python
from aksara.security.context import principal_from_mcp_claims

# "aud" claim → principal.metadata["audience"]
principal = principal_from_mcp_claims({"aud": "mcp-service", "tenant_id": "t1"})
assert principal.metadata["audience"] == "mcp-service"
assert "aud" not in principal.metadata  # normalized out
```

## MCP Credential Enforcement Helpers (Round 4)

```python
from aksara.security import (
    require_scope,
    require_any_scope,
    require_all_scopes,
    require_mcp_audience,
    require_mcp_tenant,
    MCPCredentialClaims,
)

# Scope enforcement
d = require_scope(principal, "mcp:write:invoice")
d = require_any_scope(principal, ["mcp:read:invoice", "mcp:write:invoice"])
d = require_all_scopes(principal, ["mcp:read:invoice", "mcp:write:invoice"])

# Audience enforcement
d = require_mcp_audience(principal, expected_audience="mcp-service")

# Tenant enforcement
d = require_mcp_tenant(principal, tenant_required=True)

# Parse raw claims into structured form
claims = MCPCredentialClaims.from_claims_dict(raw_claims)
if claims.expired:
    raise ValueError("Token expired")
```

`PolicyEngine.can()` also accepts `required_audience` and `tenant_required` context kwargs:

```python
d = engine.can(principal, "update",
               required_scopes=["mcp:write:invoice"],
               required_audience="mcp-service",
               tenant_required=True)
```

## Known Gaps

| Gap | Severity | Round |
|-----|----------|-------|
| No audience-bound MCP token issuance in core | Medium | Round 5 |
| No scoped token issuance in core (issue-side) | High | Round 5 |
| No consistent auth check order across all generated surfaces | Low | Ongoing |

## Current Status

| Feature | Status |
|---------|--------|
| Unified `Principal` object | Implemented (Round 2) |
| `PolicyEngine.can()` / `writable_fields()` / `visible_fields()` | Implemented (Round 2) |
| REST runtime field enforcement | Implemented (Round 3) |
| MCP claims normalization (`aud` → `audience`) | Implemented (Round 4) |
| Per-tool scope helpers (`require_scope`, etc.) | Implemented (Round 4) |
| Audience binding (`require_mcp_audience`) | Implemented (Round 4) |
| Tenant-required enforcement (`require_mcp_tenant`) | Implemented (Round 4) |
| MCP hardening doctor check | Implemented (Round 4) |
| Scoped/audience-bound token issuance | Planned Round 5 |

## Overview

Aksara exposes data across multiple surfaces, each with its own authentication mechanism.
A long-term goal of the hardening milestone is to unify all surfaces under a single
`Principal` object resolved by a central policy engine. That work is planned for Round 2.

## Supported Auth Surfaces

### REST endpoints

REST endpoints use Aksara's `BasePermission` system (modeled after Django REST Framework):

```python
from aksara.permissions import IsAuthenticated, IsActiveUser

class InvoiceViewSet(AksaraViewSet):
    permission_classes = [IsAuthenticated, IsActiveUser]
```

Built-in permission classes:
- `AllowAny` — no auth required
- `IsAuthenticated` — requires valid session or token
- `IsAdminUser` — requires admin role
- `IsActiveUser` — requires active account
- `IsOwnerOrReadOnly` — owner can mutate; others read-only
- `DenyAI` — blocks all AI agent identities

### Studio

Studio uses a shared bearer token (`AKSARA_STUDIO_AUTH_TOKEN`) validated by
`studio_require_auth=True` (default). Additionally, `studio_expose_in_production=False`
(default) prevents Studio from being accessible in production unless explicitly enabled.

**Key fix (v0.5.47):** Debug-mode auth bypass in Studio was patched. Studio now always
enforces auth regardless of debug mode.

### MCP tools

MCP agents must present an `X-Aksara-AI-Token` header. Tokens are HMAC-SHA256 signed
with `AKSARA_AI_AGENT_TOKEN` (shared secret) and include:
- `issued_at`: Unix timestamp
- `ttl`: token lifetime (default 300s)

Validated by `AIAgentMiddleware` → `verify_agent_token()` in `aksara/ai/auth.py`.

MCP is **disabled by default** (`mcp_enabled=False`).

### AI Console

AI Console is not yet implemented. When added, it will require explicit opt-in with
mandatory authentication (`AKSARA_AI_CONSOLE_AUTH_REQUIRED=true`).

### Background / system tasks

Background tasks do not have external auth — they run as trusted internal actors.
Security control: `tenant_id` is captured from trusted server-side context at enqueue
time. Tasks must not accept tenant identity from external input.

## Known Gaps

| Gap | Severity | Round |
|-----|----------|-------|
| No unified `Principal` object | High | Round 2 |
| Each surface resolves auth independently | High | Round 2 |
| No scoped MCP credentials (per-tool scope claims) | High | Round 3 |
| No short-lived audience-bound MCP tokens | Medium | Round 3 |
| No consistent auth check order across all generated surfaces | Medium | Round 2 |

## Planned Direction (Round 2+)

All surfaces should eventually resolve an incoming request to a common `Principal`:

```python
# Planned Round 2 structure
@dataclass
class Principal:
    user_id: str | None
    tenant_id: str | None
    roles: list[str]
    scopes: list[str]
    auth_method: str  # "session" | "jwt" | "api_key" | "mcp_token" | "system"
    is_ai_agent: bool
```

Then every surface — REST, Studio, MCP, Admin, background task — will call the same
policy engine:

```python
# Planned Round 2 API
policy.can(principal, action="update", resource=invoice)
policy.visible_fields(principal, resource=invoice)
policy.writable_fields(principal, resource=invoice)
```

This eliminates per-surface auth logic and closes the class of bugs (like the v0.5.47
X-User-Id impersonation issue) that arise from distributed, inconsistent auth checks.
