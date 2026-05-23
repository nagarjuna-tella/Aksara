# AI and MCP Security Boundaries

> **Status:** Updated through Round 5 of the Aksara security-hardening milestone.
> Runtime field enforcement is **implemented** for REST surfaces (Round 3).
> MCP credential hardening (scope, audience, tenant enforcement) is **implemented** (Round 4).

## Core Principle

**Generated schemas are not security controls. Runtime enforcement is required.**

When Aksara generates an MCP tool schema or an AI prompt pack, it filters out fields
marked `ai_sensitive=True` or `ai_agent_writable=False`. However, that schema is a
*hint* to clients — it is not enforced at the server.

A malicious or misconfigured client can send a payload containing forbidden fields.
As of Round 3, the REST viewset layer enforces field-level permissions at runtime and
rejects forbidden fields with a structured 403 error before any database write.

## Current Controls

### MCP disabled by default

`mcp_enabled=False` in `aksara/conf.py`. MCP tools are only active when explicitly
enabled via `AKSARA_MCP_ENABLED=true`.

### AI field metadata controls

Two field-level flags control AI surface exposure:

```python
# In model field definitions:
class Invoice(AksaraModel):
    internal_notes: str = Field(
        ai_sensitive=True,       # Exclude from AI/MCP schemas and prompt exports
        ai_agent_writable=False, # Mark as read-only for AI agents
    )
```

| Flag | Default | Meaning |
|------|---------|---------|
| `ai_sensitive` | `False` | If `True`, field is excluded from AI/MCP schemas and prompt packs |
| `ai_agent_writable` | `True` | If `False`, field cannot be written by AI agents |

**Current enforcement:** Schema-time + runtime. Forbidden fields are excluded from generated
schemas, and crafted REST payloads are rejected at runtime (Round 3).

### HMAC agent token authentication

AI/MCP agents must present an `X-Aksara-AI-Token` header containing a short-lived
HMAC-SHA256 token. Token format: `header.payload.signature` (compact JWS-style).
Default TTL: 300 seconds.

Tokens are validated by `AIAgentMiddleware` via `verify_agent_token()` in
`aksara/ai/auth.py`.

### `DenyAI` permission class

Routes or viewsets can apply `DenyAI` to block all AI agent access:

```python
from aksara.permissions import DenyAI

class SensitiveResource(AksaraViewSet):
    permission_classes = [IsAuthenticated, DenyAI]
```

## Known Gaps (as of Round 5)

| Gap | Severity | Planned Round |
|-----|----------|---------------|
| Field-level audit logging (fields_requested / fields_allowed / fields_denied) | High | Future |
| Direct MCP tool call enforcement (without REST) | High | Future |
| Manager-level bulk update / upsert principal enforcement | Medium | Future |
| Scoped/audience-bound token issuance in core | Medium | Future |
| OpenAPI/Schemathesis fuzzing wired into CI | Medium | Round 6 |

## Runtime Enforcement (Round 3)

As of Round 3, REST create and update paths enforce field-level policy before any database write.
The enforcement runs through `aksara/security/enforcement.py`:

```python
enforce_request_payload_policy(
    request=request,
    action="create",  # or "update"
    model=self.model,
    payload=data,
    surface="rest_create",
)
```

When a principal sends a field they cannot write, the server responds:

```
HTTP 403 Forbidden
{
    "detail": "Payload contains fields not writable by this principal.",
    "reason": "Field 'internal_notes' is not writable by AI agents.",
    "denied_fields": ["internal_notes"],
    "required_scopes": [],
    "missing_scopes": []
}
```

This enforcement is wired into `ModelViewSet.create()` and `ModelViewSet.update()`.
MCP agents that use the REST surface are automatically covered.

## Security Testing Matrix (current coverage)

| Scenario | Status |
|----------|--------|
| MCP enabled without auth → `production-check` blocks | Covered (Round 1) |
| `ai_sensitive` field excluded from MCP schema | Covered (schema-time) |
| `ai_agent_writable=False` excluded from MCP schema | Covered (schema-time) |
| Crafted REST payload with `ai_agent_writable=False` field rejected | **Covered (Round 3)** |
| Crafted REST payload with `read_only` field rejected | **Covered (Round 3)** |
| tenant_id override attempt in REST payload rejected | **Covered (Round 3)** |
| System principal can write `system_only` fields | **Covered (Round 3)** |
| MCP missing scope denied | **Covered (Round 4)** |
| MCP wrong audience denied | **Covered (Round 4)** |
| MCP missing tenant denied for tenant-required action | **Covered (Round 4)** |
| Client tenant header not authoritative | **Covered (Round 4)** |
| AI-sensitive field ordering rejected for AI principal | **Covered (Round 5 fuzz)** |
| Runtime forbidden-field variants and nested payload bypasses rejected | **Covered (Round 5 fuzz)** |
| Helper-level bulk/upsert payload validation | **Covered (Round 5 helper-level)** |
| Cross-tenant access via MCP tool | Planned future round |
| Field-level audit trail per MCP call | Planned future round |

## MCP Credential Hardening (Round 4)

Round 4 adds per-tool scope enforcement, audience binding, and tenant-required checks
via helpers in `aksara/security/mcp.py`:

```python
from aksara.security import (
    require_scope,
    require_any_scope,
    require_all_scopes,
    require_mcp_audience,
    require_mcp_tenant,
    MCPCredentialClaims,
)

# In a viewset or MCP tool handler:
d = require_scope(principal, "mcp:write:invoice")
if d.denied:
    raise HTTPException(status_code=403, detail=d.reason)

d = require_mcp_audience(principal, expected_audience="mcp-service")
if d.denied:
    raise HTTPException(status_code=403, detail=d.reason)

d = require_mcp_tenant(principal, tenant_required=True)
if d.denied:
    raise HTTPException(status_code=403, detail=d.reason)
```

`PolicyEngine.can()` also accepts `required_audience` and `tenant_required` kwargs:

```python
d = engine.can(principal, "update",
               required_scopes=["mcp:write:invoice"],
               required_audience="mcp-service",
               tenant_required=True)
```

### Doctor check: `security.mcp_hardening`

`aksara doctor security-check` and `aksara doctor production-check` now include a
`check_mcp_hardening()` check that verifies (when MCP is enabled):

| Condition | Production | Dev |
|-----------|-----------|-----|
| `AKSARA_MCP_REQUIRE_SCOPED_TOKENS` not set | block | warn |
| `AKSARA_MCP_TOKEN_TTL_SECONDS` not set | block | warn |
| TTL > 3600 seconds | warn | warn |
| `AKSARA_MCP_REQUIRE_AUDIENCE` not set | block | warn |
| Multi-tenant + `AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS` not set | block | warn |

## Round 5: Fuzzing and Generated Surface Hardening

Round 5 adds adversarial and fuzzing coverage for generated framework surfaces that may be reached by AI/MCP clients through REST or future generated tools.

Covered:

- Filters and ordering, including tenant and AI-sensitive ordering attempts.
- Pagination/cursors where applicable.
- Serializer payloads and runtime field enforcement bypass attempts.
- Nested payloads, aliases, casing variants, dotted keys, and JSON path-like keys.
- Helper-level bulk/upsert payload shapes.
- Migration identifiers/defaults.
- Malformed and oversized payloads.
- OpenAPI fuzzing placeholder when Schemathesis is unavailable.

Security invariants:

- Forbidden fields never mutate.
- Tenant isolation is not bypassed.
- Hidden/sensitive fields do not leak through denied generated surfaces.
- Unsafe identifiers do not become unsafe SQL.
- Malformed inputs fail safely.
- Oversized inputs fail safely.

Remaining:

- Direct MCP tool-call runtime enforcement.
- Field-level MCP audit logs.
- Supply-chain CI.
- Release gates.
- External review.
- Full production-mode claim.

## Future Direction

The long-term design goal for Aksara's AI/MCP security:

1. **Deny-by-default in production mode.** `ai_exposed=False`, `ai_agent_writable=False`, `ai_sensitive=True` should be the production defaults. Developers must explicitly opt in.
2. **Scoped, short-lived credentials.** MCP tokens should carry per-tool scope claims (`mcp:read:invoice`, `mcp:update:invoice.status`) and `audience` binding.
3. **Runtime payload validation.** Every MCP tool call and REST write from an AI agent must be validated against a central policy engine, not just a generated schema. *(REST surfaces: done in Round 3.)*
4. **Audit logging.** Every tool call must log: actor, tool, tenant, fields_requested, fields_allowed, fields_denied, decision, and reason.

These controls continue across future hardening rounds. Round 5 does not claim production readiness.
