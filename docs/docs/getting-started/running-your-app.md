# Run the application

Run from the project directory after configuring PostgreSQL, applying reviewed
migrations and completing the application's authentication setup. The
[first-project tutorial](first-project.md) provides that complete sequence.

## Local development

```bash
aksara doctor launch-check
aksara dev
```

Doctor reports the configured project's checks; read its failures and warnings
rather than treating package installation as readiness. `aksara dev` defaults
to `main:app`, `127.0.0.1:8000` and reload enabled. Keep a local tutorial on
loopback. To run without the reload watcher or with an explicit import path:

```bash
aksara dev main:app --no-reload
aksara run main:app --host 127.0.0.1 --port 8000
```

The basic scaffold's configured development profile exposes these surfaces:

| URL | Purpose and limit |
| --- | --- |
| `/` | Welcome response; not application readiness evidence. |
| `/docs` and `/redoc` | REST schema viewers. |
| `/health` | Generated database probe; inspect its response, not only the status. |
| `/admin/` | Admin/login in the generated admin profile; authentication is still required. |
| `/ai/tools/mcp` | HTTP JSON tool inspection catalog, not the MCP transport. |

The bare scaffold does not provide a domain API until you add and register one.
The generated health endpoint queries `SELECT 1` when a database is configured;
its unconfigured response can still use HTTP 200. It is not a substitute for
deployment checks or an application-specific readiness endpoint.

`/mcp/` is optional and requires MCP enablement plus trusted Principal
resolution. Official MCP clients use that transport, not the inspection catalog.
Studio is experimental; its UI requires explicit enablement and the documented
secret/exposure configuration. See [MCP setup](mcp.md) and [Studio](studio.md)
only when the application needs them.

## Production entry point

Use the [production guide](../tutorials/deployment.md) for role separation,
configuration and operational checks. In the separate migration job, select
the migration-role URL and apply versioned files:

```bash
aksara migrate
```

Then select the restricted application-role URL for application processes,
complete production configuration and run:

```bash
aksara doctor production-check --release
aksara run main:app --host 0.0.0.0 --port 8000
```

The bind address exposes the process on its available network interfaces; use
it only within the intended deployment network. The server command does not
supply TLS termination, process supervision, secret storage, backup/restore,
capacity planning or a production identity service. Do not use reload in
production. Multiple server processes each have their own pools and process
state.

## Shutdown and background work

Allow normal ASGI lifespan shutdown when stopping the server. Participating
Aksara runtime services and the pool are cleaned up through that path. A forced
kill cannot run cleanup callbacks; server shutdown is not proof that external
work completed.

Ordinary tasks and durable workers have separate execution and recovery
contracts. Follow [background reports](../tutorials/ticket-desk-reports.md) or
[durable actions](../tutorials/ticket-desk-durable.md) for their setup and
[production operations](../tutorials/deployment.md) for worker supervision.
Starting a web server does not automatically establish a durable worker fleet.
