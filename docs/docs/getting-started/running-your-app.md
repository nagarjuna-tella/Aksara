# Running your app

Run these commands from the generated project directory after configuring
PostgreSQL and applying migrations.

## Development server

```bash
aksara doctor launch-check
aksara dev
```

`aksara dev` runs `main:app` with reload enabled. Use an explicit import path or
network options when needed:

```bash
aksara run main:app --host 127.0.0.1 --port 8000
aksara run main:app --host 0.0.0.0 --port 8000 --reload
```

The stable endpoints in a basic project are:

| URL | Purpose |
| --- | --- |
| `/` | generated welcome page |
| `/docs` | REST OpenAPI UI |
| `/redoc` | REST reference |
| `/health` | generated-project database health probe |
| `/admin/` | Admin in the configured debug/admin profile |
| `/ai/tools/mcp` | HTTP JSON tool inspection catalog |

`/mcp/` exists only when `AKSARA_MCP_ENABLED=true`. Add trusted server-side
Principal resolution before enabling it. Official MCP clients use `/mcp/`, not
`/ai/tools/mcp`.

Studio is experimental and appears at `/studio/ui` only when explicitly enabled
with its required secret and exposure settings.

## Production startup

Run migrations with a migration role before application processes start. Run
the application with its restricted database role and complete release policy:

```bash
aksara migrate
aksara doctor production-check --release
aksara run main:app --host 0.0.0.0 --port 8000
```

The production command shown here demonstrates Aksara's process entry point; an
operator remains responsible for process supervision, TLS termination,
credential verification, database role separation, secrets, observability, and
capacity settings.

## Shutdown

`SIGINT` and `SIGTERM` run the ASGI lifespan shutdown path. Aksara stops the MCP
session manager and task worker, then disconnects the PostgreSQL pool.
