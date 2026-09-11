# MCP quickstart

**Stable synchronous MCP execution.** Aksara generates tools from an explicitly
exposed ViewSet and invokes them through the **same application path** as REST.
MCP does not require a model provider, planner or Studio.

Use the [ticket-desk MCP chapter](../tutorials/ticket-desk-mcp.md) for complete,
executable files and an official-client test. It continues one application with
existing permissions, tenant isolation, validation and a restricted PostgreSQL
role. If you are starting from an empty directory, begin with
[First project](first-project.md) and follow the linked chapters in order.

## Resolve credentials on the server

The application validates a credential and constructs its MCP-agent Principal:
agent ID, human owner, tenant, current roles, scopes, audience and expiry. Those
values come from server-owned identity data, not client headers or tool arguments.
An ordinary human Principal is not automatically an MCP-agent Principal.

The tutorial uses distinct local write, read-only and expired-test credentials.
It reloads current membership and tests revocation after tool discovery. Replace
that local adapter with your real identity integration before production use.

## Enable only the intended tools

Enable MCP explicitly in application settings and set `ai_exposed=True` only on
the relevant ViewSet. The ticket-desk example leaves agent administration out of
discovery and reuses the same request/object permissions as REST.

Review `ai_sensitive`, `ai_agent_writable`, read-only and server-owned fields
before exposing a model. Discovery is not permission: execution checks authority
again. Custom endpoints and actions still need application-owned authorization.

## Use the protocol endpoint

| Path | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/mcp/` | Streamable HTTP endpoint for official MCP clients |
| `/ai/tools/mcp` | Separate permission-filtered inspection catalog |

The supported MCP SDK 2.0 transport uses `httpx2.AsyncClient`. The tutorial's
`connect()` helper shows the complete `Client(streamable_http_client(...))`
context-manager pattern, including authentication and protocol negotiation.
The package supplies this SDK dependency; no AI provider configuration is needed.

From the running tutorial project, execute the public application tests:

```bash
python -m unittest discover -s tests -v
```

The MCP tests create/update/delete a ticket and read its state through REST.
They also prove scope, expiry, tenant, field, current-role and Principal-type
denial. A successfully opened connection alone is not proof of tool execution;
inspect each result's `is_error` and `structured_content`.

## Keep execution guarantees distinct

These are synchronous tools. Protocol-level **MCP Tasks are not advertised**.
Enabling MCP does not start a durable worker or turn a tool call into a Durable
Operation. The tutorial deliberately keeps its human-only durable resolver
separate from machine credentials.

For bounded approval grants, audit sinks, structured errors and limits, read
[MCP protocol server](../ai-mode/mcp.md). For current-authority recovery across
time, read [Durable Operations](../advanced/durable-operations.md). Production
also needs the [deployment profile](../tutorials/deployment.md); sessions and
replay tracking do not provide cross-worker durable continuity.
