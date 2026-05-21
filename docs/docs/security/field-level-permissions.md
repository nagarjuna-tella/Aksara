# Field-Level Permissions

> **Status:** This document is part of the Aksara security-hardening milestone (Round 1).
> Field-level metadata exists today; runtime enforcement is planned for Round 2.

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
| Enforced | Schema-time only (NOT at runtime as of Round 1) |

```python
class PatientRecord(AksaraModel):
    ssn: str = Field(ai_sensitive=True)  # Hidden from AI schemas
```

### `ai_agent_writable`

| Default | `True` |
|---------|--------|
| Meaning | If `False`, AI agents should not be able to write this field |
| Enforced | Schema-time only — field excluded from MCP create/update tool input schemas |

```python
class Invoice(AksaraModel):
    internal_review_flag: bool = Field(ai_agent_writable=False)
```

### Read-only fields

Fields can be marked read-only in serializers, which excludes them from create/update input
schemas. Same limitation applies: crafted payloads can bypass schema-level read-only enforcement.

## The Schema-Bypass Gap

This is the key unresolved risk as of Round 1:

```
Client sends:
POST /api/invoices/
{"title": "Test", "internal_review_flag": true}
                     ↑
            This field is ai_agent_writable=False
            and excluded from generated schemas.
            But the server currently accepts it.
```

The scenario `rest_update_hidden_field_raw_payload` in `security_matrix.yml` tracks this gap
with `status: planned` — test coverage and enforcement are planned for Round 2.

## Surfaces Where Field Enforcement Is Needed

Every write surface must eventually enforce field-level permissions:

| Surface | Current Gap |
|---------|-------------|
| REST create | Schema excludes fields; runtime does not reject |
| REST update / patch | Same |
| Studio create | Same |
| Studio update | Same |
| MCP create tool | Same |
| MCP update tool | Same |
| Bulk update | Same |
| Upsert | Same |
| Background task mutation | No field-level check at all |
| SDK-generated client | Not yet implemented |

## Planned Runtime Enforcement (Round 2)

All create/update/upsert/bulk paths will validate payloads against a central policy engine:

```python
# Planned Round 2 implementation
def validate_write_payload(principal: Principal, model_class, payload: dict) -> dict:
    """Strip or raise on fields the principal cannot write."""
    writable = policy.writable_fields(principal, model_class)
    forbidden = set(payload.keys()) - writable
    if forbidden:
        raise PermissionDenied(f"Fields not writable: {forbidden}")
    return {k: v for k, v in payload.items() if k in writable}
```

This enforcement will run server-side regardless of what the client sends or what the
generated schema says.

## Interim Mitigation

Until Round 2, mitigate the schema-bypass gap by:

1. Using `DenyAI` permission class on sensitive viewsets to block AI agents entirely.
2. Explicitly marking all sensitive fields `ai_sensitive=True` and `ai_agent_writable=False`.
3. Adding custom serializer validation for fields that must never be written by clients.
4. Monitoring for unexpected field writes in application logs.
