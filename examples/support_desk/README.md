# Multi-tenant support desk reference app

This is Aksara's production-shaped reference application. It uses PostgreSQL,
generated CRUD APIs, bearer authentication, role and MCP-scope permissions,
`TenantModel`, forced PostgreSQL row-level security, model relations, Admin,
durable background tasks, and an explicit migration readiness check.

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

Review every field on an AI-exposed model and set `ai_agent_writable` explicitly.
Then configure the release diagnostics, apply the schema, and launch the
service:

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
aksara migrate
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

`GET /ai/tools/mcp` returns the catalog of generated, AI-exposed operations.
The MCP token is bound to tenant A, an audience, explicit read/write scopes,
and an expiry no more than one hour in the future. The app builds its principal
from those server-owned claims and rejects expired, wrong-audience, or
tenantless MCP principals. That principal can call catalog-described REST
operations within tenant A. Aksara v0.6 does not ship a protocol-level MCP
transport, so this example does not claim one.

## Migration and operations gate

The repository gate runs the packaged wheel against a restricted PostgreSQL
role and covers fresh install, existing schema, upgrade, unapplied migration
failure, concurrent requests, pool reuse, rollback, tenant switching, task
retry and worker restart, MCP-authorized mutation, graceful shutdown, requests
during shutdown, connection cleanup, database reconnection, app restart, and
both Doctor release and launch inspection.
