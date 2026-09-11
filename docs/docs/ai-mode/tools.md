# Application tools and AI development helpers

Aksara's stable synchronous MCP tools and its experimental AI development
helpers are different surfaces. Do not assume a tool-shaped JSON example is
an executable protocol contract.

## Generated application tools

Selected ViewSets expose generated CRUD and custom-action tools through the
[MCP protocol server](mcp.md). The actual names and input schemas come from
client discovery. For example, the [ticket-desk client](../tutorials/ticket-desk-mcp.md)
discovers names such as `ticket_create`; there is no universal `create_record`
MCP command that accepts an arbitrary model name.

Use `/mcp/` with the official client. `/ai/tools/mcp` is a separate HTTP JSON
inspection catalog. Discovery visibility does not replace execution-time
identity, permission, policy, tenant and field enforcement. Your application
must verify credentials and resolve the server-owned Principal.

The ticket-desk chapter executes real tool calls and tests denied writes,
expired credentials, changed permissions and tenant boundaries. It needs no
LLM provider. Synchronous MCP does not automatically turn these calls into
Durable Operations or protocol-level MCP Tasks.

## Experimental development helpers

Context export, schema analysis, prompt packs, plans and code patches belong to
the experimental development surfaces. Their data structures are not a generic
MCP command catalog. In particular, names such as `generate_test`, `get_settings`
or `run_migration` in a conceptual plan do not imply an exposed application tool.

Use the specific guide for the intended operation:

- [Schema analysis](schema-doctor.md) compares registered models and PostgreSQL.
- [Route hints](hints.md) attach descriptive metadata.
- [Context export](context-engine.md) prepares application context.
- [Plan handling](planner.md) describes the actual plan model and handlers.
- [Code generation](codegen.md) and [patches](patch-engine.md) describe preview and mutation boundaries.

Do not expose development or migration capabilities to an agent merely because
it can describe them in a prompt. An application-owned custom tool needs a
reviewed execution and authorization path just like any other endpoint.
