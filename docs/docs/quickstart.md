# Quickstart

Build a protected ticket API with one model, a migration, generated REST,
server-owned identity and runnable tests. Python 3.11–3.14 and PostgreSQL are required.

Start with [First project: a ticket desk](getting-started/first-project.md).
It is the canonical step-by-step guide, including the exact files to create.
Use a disposable local database; it keeps AI and advanced tenancy out of the
initial learning path.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "aksara-framework==0.7.1"
aksara startproject ticket_desk
cd ticket_desk
aksara dbsetup
```

Then follow the guide to define `Ticket`, protect its ViewSet, add a local
bearer-token adapter, apply migrations, start the server and run authenticated
CRUD tests. Creating a model does not automatically apply a database migration,
and exposing an endpoint does not itself verify a user's credentials.

## After the first application

Read [application boundaries](concepts/application-boundaries.md) to distinguish
models, permission, tenant scope, Tasks and durable Operations. Use the
[production guide](tutorials/deployment.md) before exposing the app publicly.

When you need agent access, [MCP](getting-started/mcp.md) is an optional next step:
`/mcp/` is the Streamable HTTP protocol endpoint, while `/ai/tools/mcp` is a
separate HTTP inspection catalog. They are not interchangeable URLs.
Provider-backed AI and Studio remain experimental. Neither is required for the
stable REST, MCP or durable-operation boundary.
