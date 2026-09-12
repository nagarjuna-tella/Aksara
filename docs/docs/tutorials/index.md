# Tutorials and application guides

The canonical tutorial grows one [ticket desk](../getting-started/first-project.md).
Each chapter provides the files to write and tests to run against the same
application. Start there if you are new to Aksara.

| Chapter | Application behavior |
| --- | --- |
| [First project](../getting-started/first-project.md) | Models, migrations, protected REST and tests |
| [Relations and validation](ticket-desk.md) | Agent assignment and input validation |
| [Tenant isolation](ticket-desk-tenancy.md) | Customer membership, permissions and PostgreSQL RLS |
| [Background reports](ticket-desk-reports.md) | Queued reports with protected CSV download |
| [Durable actions](ticket-desk-durable.md) | Idempotency, workers, retry, cancellation and current authorization |
| [Optional MCP client](ticket-desk-mcp.md) | Synchronous tool execution with the official client |

The tutorial uses Python 3.11+ and PostgreSQL. The
[installation guide](../getting-started/installation.md) covers setup. The
[production guide](deployment.md) covers deployment responsibilities after the
application works locally; it is a how-to, not another starter application.

## Other examples

[Blog API](blog-api.md) and [multi-tenant application](multi-tenant.md) are
separate examples, not continuations of the ticket desk. Consult their scope
notes before combining their snippets with an existing application.
[AI integration](ai-integration.md) concerns optional experimental features.

The [example catalog](../getting-started/examples.md) describes the repository's
sample applications and known limitations. No separate examples repository is
required for the ticket desk: its source and tests are included in the chapters.
