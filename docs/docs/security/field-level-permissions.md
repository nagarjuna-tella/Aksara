# Field-Level Permissions

## Core Principle

Generated schemas are not security controls. Runtime enforcement is required.

Aksara generates schemas for REST, MCP tool descriptions, Studio/admin surfaces,
and AI context. Those schemas improve client behavior, but server-side runtime
policy is the security boundary.

## Controls

Aksara field-level policy considers:

- `ai_sensitive`
- `ai_agent_writable`
- Read-only fields
- Tenant-owned fields such as `tenant_id`
- System-only/internal fields where metadata exists

AI-sensitive fields are hidden from AI/MCP-visible schemas and AI context.
Fields with `ai_agent_writable=False` are not writable by AI/MCP principals.
Read-only, tenant, and system-only fields are denied according to the principal
type.

## Runtime Enforcement

The central enforcement APIs are:

- `PolicyEngine.validate_payload()`
- `enforce_payload_policy()`
- `enforce_request_payload_policy()`
- `PolicyDenied`
- `policy_denied_to_error_payload()`

When a payload contains forbidden fields, the request is rejected instead of
silently stripping fields. Error payloads include `denied_fields` so callers can
see which fields were blocked.

Example response detail:

```json
{
  "detail": "Payload contains fields not writable by this principal.",
  "reason": "1 field(s) in payload are not writable by this principal.",
  "denied_fields": ["internal_notes"],
  "required_scopes": [],
  "missing_scopes": []
}
```

## Covered Paths

- Generated REST create paths
- Generated REST update/patch paths
- MCP agents that write through the covered REST paths
- Helper-level bulk payload validation through `validate_bulk_payload_policy()`
- Helper-level upsert payload validation through `validate_upsert_payload_policy()`

## Known Limitations

- Bulk/upsert manager-level principal enforcement is not universal unless the
  application path integrates the helper-level validation.
- Direct MCP tool calls are only fully covered when they route through covered
  REST write paths or explicitly call enforcement helpers.
- Applications should ensure custom write paths call the enforcement helpers.
- Background task mutations run as trusted internal work and need explicit
  trusted principal/tenant context when tenant-scoped writes are performed.
