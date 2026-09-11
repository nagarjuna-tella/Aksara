# Start building with Aksara

Aksara is a Python application backend for PostgreSQL. Models define stored
records, migrations evolve tables, and ViewSets expose REST endpoints. Your
application verifies credentials and supplies identity; permissions, policy and
tenant boundaries control what that identity can do.

Start with [First project: a ticket desk](first-project.md). It takes an empty
project through installation, a model, migration, protected API, server startup
and runnable tests. You need Python 3.11+ and a local PostgreSQL database; see
[installation](installation.md) and [runtime compatibility](../reference/runtime-compatibility.md)
for the supported environment. No AI provider is required.

## Grow one application

Follow these chapters in order. Each continues the same files and database.

| Chapter | What you build |
| --- | --- |
| [1. First project](first-project.md) | Ticket model, migrations, authenticated REST and tests |
| [2. Relations and validation](../tutorials/ticket-desk.md) | Assign tickets to agents and validate input |
| [3. Tenant isolation](../tutorials/ticket-desk-tenancy.md) | Customer boundaries, permissions and restricted-role PostgreSQL RLS |
| [4. Background reports](../tutorials/ticket-desk-reports.md) | Queued work, protected status and CSV download |
| [5. Durable actions](../tutorials/ticket-desk-durable.md) | Idempotent ticket resolution, retries, cancellation and current authority |
| [6. Optional MCP client](../tutorials/ticket-desk-mcp.md) | Authenticated tool calls through the official MCP client |

The first chapter is sufficient for a small local REST application. Later
chapters introduce a capability when the application needs it. The local token
adapter teaches the authentication boundary; it is not a production identity
service.

## Find an explanation or a specific task

- [Application boundaries](../concepts/application-boundaries.md) explains how models,
  identity, policy, Tasks and Operations fit together.
- [Project layout](project-layout.md) explains where application code belongs.
- [Configuration reference](../reference/settings-reference.md) defines environment
  variables, precedence and explicit application settings.
- [Production deployment](../tutorials/deployment.md) covers database roles,
  worker processes, diagnostics and operator responsibilities.
- [Stability labels](../concepts/stability.md) distinguishes supported backend
  contracts from evolving and experimental surfaces.
- [Examples](examples.md) identifies other examples and their limitations.

Studio and provider-backed AI have a separate experimental learning path. They
are optional consumers and development tools, not prerequisites for the tutorial.
