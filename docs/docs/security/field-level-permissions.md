# Field-Level Permissions

> **Status:** Updated through Round 5 of the Aksara security-hardening milestone.
> Field-level metadata exists and runtime enforcement is **implemented** for REST surfaces.
> See [Runtime Enforcement](#runtime-enforcement-round-3) for covered and remaining surfaces.

## Core Principle

**Field-level visibility and writability must be enforced at runtime, not only in generated schemas.**

Aksara generates schemas for REST (OpenAPI), MCP tool definitions, Studio forms, and AI prompt
packs. These schemas filter out restricted fields. However, a client sending a crafted raw JSON
payload can include any field — including those hidden from the schema.

Until runtime enforcement is added (Round 2), the schema-time filtering is a user-experience
control, not a security boundary.

## Current Field Metadata

### `ai_sensitive`

| Default | `False` |
|---------|---------|
| Meaning | If `True`, field is excluded from AI/MCP tool schemas and AI prompt pack exports |
| Enforced | Schema-time + runtime (Round 3): REST create/update reject writes from AI agents |

```python
class PatientRecord(AksaraModel):
    ssn: str = Field(ai_sensitive=True)  # Hidden from AI schemas
```

### `ai_agent_writable`

| Default | `True` |
|---------|--------|
| Meaning | If `False`, AI agents cannot write this field |
| Enforced | Schema-time (field excluded from MCP tool schemas) + runtime (Round 3): REST viewset rejects writes |

```python
class Invoice(AksaraModel):
    internal_review_flag: bool = Field(ai_agent_writable=False)
```

### Read-only fields

Fields can be marked read-only, which excludes them from create/update input schemas. As of Round 3,
attempts to write `read_only=True` fields via REST are rejected at runtime with a 403.

## The Schema-Bypass Gap

This was the key unresolved risk as of Round 1 / Round 2:

```
Client sends:
POST /api/invoices/
{"title": "Test", "internal_review_flag": true}
                     ↑
            This field is ai_agent_writable=False
            and excluded from generated schemas.
            As of Round 3, the server REJECTS this
            with HTTP 403 + denied_fields list.
```

The scenario `rest_update_hidden_field_raw_payload` in `security_matrix.yml` tracks this —
now `status: covered` as of Round 3.

## Runtime Enforcement (Round 3)

Round 3 closes the schema-bypass gap for REST surfaces. The central enforcement helpers live
in `aksara/security/enforcement.py`:

```python
from aksara.security.enforcement import (
    enforce_request_payload_policy,
    policy_denied_to_error_payload,
)
from aksara.security.exceptions import PolicyDenied
from fastapi import HTTPException

# In a viewset create() or update():
try:
    enforce_request_payload_policy(
        request=request,
        action="create",
        model=self.model,
        payload=data,
        surface="rest_create",
    )
except PolicyDenied as exc:
    raise HTTPException(status_code=403, detail=policy_denied_to_error_payload(exc))
```

The 403 response body has a structured shape:

```json
{
    "detail": "Payload contains fields not writable by this principal.",
    "reason": "...",
    "denied_fields": ["internal_review_flag"],
    "required_scopes": [],
    "missing_scopes": []
}
```

### Principal resolution in enforcement

The enforcement helper resolves the principal in this priority order — never as system:

1. `request.state.principal` — pre-resolved by `AIAgentMiddleware`
2. `principal_from_request(request)` — full resolution from request state/user
3. `Principal.anonymous()` — if request is None or resolution fails

### PolicyEngine is the single source of truth

`enforce_request_payload_policy` delegates to `PolicyEngine.validate_payload()`, which applies
the same rules as `PolicyEngine.writable_fields()`. Adding a rule in one place covers all surfaces.

## Round 5: Fuzzing and Generated Surface Hardening

Round 5 adds bounded adversarial tests for field-level enforcement and generated write surfaces.
The tests live in `tests/security/fuzz/` and can be run separately:

```bash
python -m pytest tests/security/fuzz/ -q
```

Covered:

- Raw payload enforcement bypass attempts.
- Nested payloads containing forbidden fields.
- Aliases, weird casing, dotted paths, JSON path-like keys, and extra fields.
- Serializer payloads and oversized strings.
- Helper-level bulk/upsert payload shapes.

Security invariants:

- Forbidden fields never mutate.
- Tenant fields cannot be overridden through body, nested payload, aliases, or bulk/upsert-shaped payloads.
- `ai_agent_writable=False`, `read_only=True`, and `system_only=True` fields are denied where policy denies them.
- Malformed and oversized payloads fail safely.

Round 5 also adds `validate_bulk_payload_policy()` and `validate_upsert_payload_policy()` helper-level validation in `aksara/security/enforcement.py`. These helpers prove the enforcement pattern for bulk/upsert-shaped payloads, but they do not claim manager-level principal enforcement for direct `Manager.bulk_update()` or `Manager.upsert()` calls.

## Surfaces: Covered and Remaining

| Surface | Round 5 Status |
|---------|---------------|
| REST create | **Covered** — `ViewSet.create()` enforces via `enforce_request_payload_policy()` |
| REST update / patch | **Covered** — `ViewSet.update()` enforces via `enforce_request_payload_policy()` |
| MCP agents via REST | **Covered** — MCP agents using REST go through the same viewset |
| Studio create / update | **Remaining** — internal tooling, no user-data CRUD in current codebase |
| MCP direct tool call | **Partial** — schema excludes fields; direct tool calls not wired yet |
| Bulk update | **Partial** — helper-level payload validation added; direct manager operation has no request context |
| Upsert | **Partial** — helper-level insert/update/conflict-target validation added; direct manager operation has no request context |
| Background task mutation | **Remaining** — no request/principal context in task signature |
| SDK-generated client | **Not implemented** — surface not yet in codebase |

> Bulk update and upsert are called programmatically from internal code (trusted callers).
> HTTP-originated writes reach these only after going through a viewset first. When these
> surfaces need a public HTTP path, wire enforcement at the viewset layer.
