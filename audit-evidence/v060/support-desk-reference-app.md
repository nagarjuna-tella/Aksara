# Packaged support desk production gate

Date: 2026-09-09 (America/Detroit)

The candidate wheel was installed into a fresh virtual environment and its
bundled `aksara._examples.support_desk` application was run as real Uvicorn
processes against the local `aksara_test` PostgreSQL database. The gate created
a temporary schema and a random `NOSUPERUSER NOBYPASSRLS` login, granted the
application role DML access only, and removed the role and schema afterward.
No credential is stored in the evidence.

Command shape:

```text
DATABASE_URL=<local-admin-url> python scripts/run_support_desk_gate.py \
  --wheel <candidate-wheel>
```

Result: **PASS**, 33/33 assertions using the `0.6.0rc1` wheel. The
machine-readable result and candidate
wheel SHA-256 are in `support-desk-gate.json`.

Covered behavior:

- isolated wheel import and production configuration rejection;
- database-unavailable and unapplied-migration startup failure;
- fresh internal/application migration, existing-row upgrade, and idempotent
  migration replay;
- forced PostgreSQL RLS on all tenant tables under a role that cannot bypass
  RLS;
- same-pool tenant switching and context reset plus transaction rollback;
- liveness, readiness, generated APIs, model relations, Admin, and disabled
  Studio production exposure;
- strict Doctor release diagnostics plus packaged-app launch inspection against
  the current schema;
- anonymous, forged-tenant, and cross-tenant request denial;
- MCP catalog discovery, expiring/audience/tenant-bound claims, same-tenant
  scoped mutation, and denied cross-tenant mutation through the
  catalog-described REST operation;
- tenant-aware task enqueue, task-status isolation, failed attempt, process
  crash, retry after worker/app restart, and durable delivery state;
- database pool recovery after backend termination;
- 24 concurrent writes across two application instances;
- normal shutdown, a blocked in-flight request drained during shutdown, and
  zero remaining application-role connections.

The gate exposed two release-blocking lifecycle gaps before it passed. Aksara
did not release the database/worker when user lifespan startup failed, and its
runtime table helpers repeated DDL during every startup or task operation. The
candidate now cleans partial startup state, provisions framework runtime tables
through an internal migration, and takes a schema-ready fast path that works
with DML-only application grants.

This evidence is bounded failure testing, not a soak test. The MCP assertion
covers the route-derived catalog and its described REST operation; Aksara does
not claim a protocol-level MCP transport in v0.6.
