# Aksara

## A Python application backend for PostgreSQL

Aksara brings models, migrations, generated REST APIs and authorization into one
backend. It is for Python developers building applications with persistent data,
customer boundaries and work that may need to continue after a request ends.

Instead of assembling persistence, API generation and application authorization
around FastAPI yourself, you can use Aksara's integrated conventions. You still
choose your identity service, write application permissions and policy, and own
your deployment. PostgreSQL is required.

[Build your first project](getting-started/first-project.md){ .md-button .md-button--primary }
[Understand the application boundary](concepts/application-boundaries.md){ .md-button }

## Build a backend before adding consumers

The [ticket desk tutorial](getting-started/index.md) grows one application from a
protected ticket API to relations, customer isolation, queued reports and durable
actions. An optional final chapter adds an official MCP client. You do not need
an AI provider to build or operate the backend.

Models and migrations define persistence. ViewSets expose REST behavior.
Authentication supplies a server-owned Principal; permissions and PolicyEngine
control access. Tenant scope and PostgreSQL RLS provide the declared database
isolation boundary when configured with a restricted role.

MCP exposes selected application tools through `/mcp/`, the Streamable HTTP
endpoint. `/ai/tools/mcp` is a separate inspection catalog. Generated REST and
MCP execution apply the covered authorization and field rules; exposing a tool
does not implement a credential verifier. See the
[MCP quickstart](getting-started/mcp.md) for the executable path.

## Work that survives a request

Use [ordinary tasks](advanced/background-tasks.md) for queued background work.
Use [Durable Authorized Operations](advanced/durable-operations.md) when a logical
action needs persisted identity, idempotency, attempts, current authorization,
cancellation or approval across time.

Released in v0.7.0, durable Operations can atomically commit a supported
PostgreSQL mutation and success state on one pinned transaction. External
effects have different recovery rules: an uncertain remote outcome may remain
explicitly unknown. Neither an approval nor a cancellation means permission is
permanent or a completed effect can be undone.

## Know the supported boundary

Aksara is pre-1.0. Evaluate the declared contract and deployment requirements
before production adoption.

| Classification | Meaning |
| --- | --- |
| Stable backend contracts | Declared ORM, migration, REST, identity, policy, tenant, task, CLI/Doctor and synchronous MCP boundaries in the [v0.6 contract](roadmap/v0-6-stability-contract.md) |
| Stable durable contract | Public Operation service and worker behavior within the [v0.7 contract](roadmap/v0-7-stability-contract.md) |
| Evolving surfaces | Features whose detailed interfaces are outside those guarantees; consult [stability labels](concepts/stability.md) before depending on them |
| Experimental | Provider-backed AI, planners, Studio AI and autonomous-workflow internals |

## Choose your next step

- **Evaluate:** read [application boundaries](concepts/application-boundaries.md),
  [stability](concepts/stability.md) and the [roadmap](roadmap.md).
- **Build:** follow the [ticket desk](getting-started/index.md), then consult
  [ORM](orm/index.md), [APIs](api/index.md) and [configuration](reference/settings-reference.md).
- **Connect tools:** use [MCP](getting-started/mcp.md) after the application works.
- **Operate:** use [production deployment](tutorials/deployment.md),
  [Doctor](diagnostics.md) and the [v0.7 upgrade guide](operations/upgrade-v07.md).
- **Contribute:** consult [release validation](releasing.md) and
  [security coverage](security/security-coverage.md).

The production guide separates migration and application database roles,
explains explicit durable-worker startup, and assigns retention, backup,
monitoring and external-effect recovery responsibilities to the operator.
