# Multi-tenant support desk reference app

This is Aksara's production-shaped reference application. It uses PostgreSQL,
generated CRUD APIs, bearer authentication, role and MCP-scope permissions,
`TenantModel`, forced PostgreSQL row-level security, model relations, Admin,
ordinary PostgreSQL-backed background tasks, and an explicit migration readiness check.
These task rows do not implement the v0.7 Durable Operation admission and
reauthorization contract. See the [durable ticket desk](../../docs/docs/tutorials/ticket-desk-durable.md)
for that separate learning tier.

The token-to-tenant mapping in `auth.py` is server-owned. Requests cannot choose
a tenant with a header or JSON field. In a real deployment, replace the small
environment-backed identity provider with your IdP while preserving the
`Principal` contract.

## Configure

Production startup requires all of these values. Use unique random tokens of at
least 24 characters; the values below are placeholders, not working secrets.

```bash
export AKSARA_ENV=production
export DATABASE_URL=postgresql://app_user:your-database-password@localhost/support_desk
export SUPPORT_DESK_TENANT_A_ID=11111111-1111-4111-8111-111111111111
export SUPPORT_DESK_TENANT_B_ID=22222222-2222-4222-8222-222222222222
export SUPPORT_DESK_TENANT_A_TOKEN=your-random-tenant-a-token
export SUPPORT_DESK_TENANT_B_TOKEN=your-random-tenant-b-token
export SUPPORT_DESK_MCP_TOKEN=your-random-mcp-agent-token
export SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT="$(($(date +%s) + 900))"
export SUPPORT_DESK_MCP_AUDIENCE=support-desk
```

The database login used by the service should be `NOSUPERUSER NOBYPASSRLS`.
Grant it DML access to the migrated tables. Run schema changes with a separate
migration role.

## Check, migrate, and run

These are source-checkout instructions run from the repository root, after
installing the framework with `python -m pip install -e .`. The packaged release
gate copies the example into an isolated installation instead.

Run the following in a separate migration job with `DATABASE_URL` set to the
migration role and `AKSARA_DATABASE_URL` set to the same URL:

```bash
aksara migrate --migrations-dir examples/support_desk/migrations
```

Grant the application role access to the migrated tables and sequences, then
restore its restricted URL in both environment variables for the web process.
The example prefers `DATABASE_URL`; do not leave conflicting URL aliases.

Review every field on an AI-exposed model and set `ai_agent_writable` explicitly.
Then configure the release diagnostics and launch the service:

```bash
export AKSARA_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export AKSARA_MCP_ENABLED=true
export AKSARA_AI_AGENT_TOKEN="$SUPPORT_DESK_MCP_TOKEN"
export AKSARA_MCP_REQUIRE_AUTH=true
export AKSARA_MCP_REQUIRE_SCOPED_TOKENS=true
export AKSARA_MCP_TOKEN_TTL_SECONDS=900
export AKSARA_MCP_REQUIRE_AUDIENCE=true
export AKSARA_MCP_TOKEN_AUDIENCE="$SUPPORT_DESK_MCP_AUDIENCE"
export AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS=true
export AKSARA_MULTI_TENANT=true
export AKSARA_RLS_ENABLED=true
export AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true
export AKSARA_SECURITY_MATRIX_PATH=/absolute/path/to/security_matrix.yml
aksara doctor production-check --release
aksara run examples.support_desk.main:app --host 127.0.0.1 --port 8000
```

`AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true` is an operator assertion. Set it
only after reviewing the concrete model fields, as this example does in
`models.py`. Run `aksara doctor launch-check` separately when checking a local
project layout; it may report expected development recommendations when Studio
and AI providers are disabled for production.

For local iteration, `aksara dev examples.support_desk.main:app` is available,
but the app itself keeps debug mode off. Startup fails with an actionable error
if either support desk migration is unapplied. Apply migrations as a separate
release step; application instances never change the schema on startup.

Readiness is at `/health/ready`, liveness is at `/health/live`, generated API
documentation is at `/docs`, and Admin login is at `/admin/login/`. Studio at
`/studio/ui` and the AI Console are intentionally disabled in production.

## Seed and exercise the API

Seed a ticket with the tenant A token:

```bash
curl -X POST http://127.0.0.1:8000/api/tickets/ \
  -H "Authorization: Bearer $SUPPORT_DESK_TENANT_A_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject":"Printer offline","description":"The third-floor printer is unreachable"}'
```

Use the returned ticket ID to enqueue a durable delivery:

```bash
curl -X POST "http://127.0.0.1:8000/api/tickets/TICKET_ID/deliver?fail_until_attempt=1" \
  -H "Authorization: Bearer $SUPPORT_DESK_TENANT_A_TOKEN"
```

The first attempt fails deterministically, the worker retries it, and the
tenant-scoped `DeliveryAttempt` records the recovery.

## MCP boundary

The official MCP server is available over Streamable HTTP at `/mcp/`.
`GET /ai/tools/mcp` remains an inspection catalog. The MCP token is bound to
tenant A, an audience, explicit read/write scopes, an agent and owner identity,
and a short expiry. Every protocol invocation rechecks those claims, ViewSet
permissions, field policy, tenant context, and forced PostgreSQL RLS through the
same generated route used by REST.

Ticket deletion is approval-required. The application must obtain a human
decision and issue a signed `app.mcp_runtime.approvals` grant bound to the exact
principal, tenant, tool, arguments, approver, and expiry. This grant is
stateless; the example does not claim durable workflow or cross-worker replay
storage. Set `SUPPORT_DESK_MCP_AUDIT_PATH` to append redacted, correlated MCP
execution events as JSONL.

## Migration and operations gate

The repository gate runs the packaged wheel against a restricted PostgreSQL
role and covers fresh install, existing schema, upgrade, unapplied migration
failure, concurrent requests, pool reuse, rollback, tenant switching, task
retry and worker restart, an official MCP client against the packaged wheel,
REST/MCP equivalence, scope and credential abuse, approval binding, concurrent
tenant isolation, redacted audit events, graceful shutdown, connection cleanup,
database reconnection, app restart, and both Doctor release and launch
inspection.
