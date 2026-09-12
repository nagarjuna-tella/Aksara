# MCP protocol server

Aksara v0.7 retains generated application capabilities through the official
Model Context Protocol Python SDK. When `mcp_enabled=True`, a Streamable HTTP
server is mounted at `/mcp/`. The existing JSON catalog remains available at
`GET /ai/tools/mcp` for inspection and compatibility.

The protocol server supports initialization, capability negotiation,
`tools/list`, `tools/call`, structured results and errors, sessions, request
cancellation, and clean application lifecycle shutdown. Aksara v0.7 uses
`mcp>=2.0.0,<2.1.0`; that SDK negotiates the MCP protocol version with the
client. Streamable HTTP is the supported deployment transport.

## Configure the boundary

```python
from aksara import Aksara, configure

configure(
    mcp_enabled=True,
    mcp_token_audience="billing-service",
    mcp_approval_secret="load-this-from-a-secret-manager",
)

app = Aksara()
```

Use authentication middleware to resolve every bearer credential into a
server-owned `Principal`. An MCP principal should have an agent ID, its human or
service owner, a tenant, token ID, expiry, audience, roles, and narrow scopes
such as `mcp:read:invoice` or `mcp:write:invoice`.

Relevant settings include:

| Setting | Default | Purpose |
| --- | --- | --- |
| `mcp_path` | `/mcp` | ASGI mount path |
| `mcp_token_audience` | unset | Required credential audience when configured |
| `mcp_require_scoped_tokens` | `True` | Require generated per-resource read/write scopes |
| `mcp_max_request_body_size` | `1048576` | Protocol request body limit in bytes |
| `mcp_tool_timeout_seconds` | `30` | Hard limit for one tool execution |
| `mcp_replay_ttl_seconds` | `300` | Process-local duplicate tool-call ID window |
| `mcp_allowed_hosts` | local hosts | DNS rebinding host allowlist |
| `mcp_allowed_origins` | local origins | DNS rebinding origin allowlist |
| `mcp_approval_secret` | unset | HMAC key for bounded approval grants |

Production diagnostics also expect MCP authentication, a credential TTL,
audience enforcement, tenant-bound tokens for multi-tenant deployments, and an
explicit review of AI-writable fields.

## Generated tools

Registered, AI-exposed `ModelViewSet` classes generate list, retrieve, create,
update, and delete tools. Tool JSON Schemas carry required and nullable fields,
enums, JSON, arrays, vectors, relations, descriptions, and representable field
constraints. They exclude sensitive, read-only, non-writable, tenant-owned, and
server-controlled fields from mutations. `additionalProperties: false` blocks
mass assignment.

Discovery is filtered for convenience. Every invocation rechecks the actual
principal, scope, audience, expiry, tenant, ViewSet permissions, object rules,
`PolicyEngine` field policy, and ORM validation on the integrated route.
PostgreSQL RLS adds database enforcement when the deployment configures it with
a restricted role and the required policies. MCP invokes the
same generated API route in-process, so it does not maintain a second, weaker
authorization implementation.

## Human approval

Mark generated CRUD actions on a ViewSet:

```python
class PaymentViewSet(ModelViewSet):
    model = Payment
    mcp_approval_required_actions = {"delete"}
```

Custom actions can use `@action(..., requires_approval=True)`. After the
application has obtained a real human decision, issue a short-lived grant:

```python
token = app.mcp_runtime.approvals.issue(
    principal=agent_principal,
    tool_name="payment_delete",
    arguments={"pk": payment_id},
    approved_by=current_user.id,
    ttl_seconds=300,
)
```

Pass the grant as `_approval_token`. Its signature binds the exact tool,
arguments, principal, tenant, approver, and expiry. Changed arguments, another
principal or tenant, rejection, expiry, and invalid signatures fail before any
mutation. Authorization runs again when the approved operation executes.

This is a signed, stateless execution grant. It does not provide durable approval
workflow storage, cross-worker single use, or restart-safe replay state. v0.7
adds a separate [Durable Operations](../advanced/durable-operations.md) path with
persisted, input-bound approval decisions and reauthorization at execution.
A synchronous `_approval_token` does not turn a normal tool call into a Durable
Operation. Applications still own the human approval interface and decision
authority.

## Audit and errors

Each resolved `tools/call` emits one `MCPExecutionAuditEvent` with principal,
tenant, tool, operation, object ID, safe hashed argument summary, policy and
approval decisions, outcome, error, timing, and request/run/tool-call IDs.
Values and approval tokens are not stored. The default sink logs JSON;
`JsonlMCPAuditSink` and the `MCPAuditSink` protocol support application-owned
storage or observability systems.

Tool errors use stable categories: `client`, `authorization`, `transient`, and
`internal`. Failed generated mutations run inside a database transaction and
roll back when the API rejects or fails the request.

## Stable and experimental surfaces

The stable synchronous MCP contract covers `Principal` propagation, generated MCP CRUD
tools, protocol discovery and invocation, execution-time authorization,
tenant and field enforcement, structured errors, audit events, runtime limits,
and the stateless approval grant described above.

Planner behavior, investigation quality, provider-specific behavior,
autonomous loops, persistent conversations, memory, multi-agent workflows,
durable autonomous workflows, and Studio AI internals remain experimental.
Investigation and MCP session/replay state is process-local.

See the [security boundary](../security/ai-mcp-boundaries.md) and
[v0.7 stability contract](../roadmap/v0-7-stability-contract.md). Protocol-level
MCP Tasks are not provided; synchronous MCP sessions are not durable workers.
