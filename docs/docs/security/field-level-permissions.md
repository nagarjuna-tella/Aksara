# Field-Level Permissions

!!! info "Stable boundary, explicit integration"
    Field policy applies on integrated request paths. It does not automatically
    authorize every ORM call or application-defined write.

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

AI-sensitive metadata is used by covered AI/MCP schema and context builders.
It is not encryption or a universal response-redaction mechanism; custom
responses and context builders must apply the appropriate visibility policy.
Fields with `ai_agent_writable=False` are not writable by AI/MCP principals.
Read-only fields are never writable through this policy, including by system
principals. System principals may write tenant and system-only fields; ordinary
users and AI agents may not.

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
- Generated MCP tools dispatched through the corresponding REST paths
- Helper-level bulk payload validation through `validate_bulk_payload_policy()`
- Helper-level upsert payload validation through `validate_upsert_payload_policy()`

## Known Limitations

- Bulk/upsert manager-level principal enforcement is not universal unless the
  application path integrates the helper-level validation.
- Generated `/mcp/` execution validates tool arguments and dispatches through
  the application ASGI routes. A custom route still owns any field enforcement
  missing from its handler; tool discovery alone does not secure its writes.
- If a model exposes no field metadata, `validate_payload()` allows the payload
  after its action check. It does not infer a restrictive schema for arbitrary
  objects. Use declared model fields and integrate enforcement explicitly.
- Applications should ensure custom write paths call the enforcement helpers.
- Ordinary background task bodies own their trusted principal/tenant context
  and write authorization. For authorization across retries and time, use the
  explicit [Durable Operations](../advanced/durable-operations.md) path; scheduling
  a task alone does not provide that contract.
