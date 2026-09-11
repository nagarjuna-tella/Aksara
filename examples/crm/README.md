# Aksara example: CRM

**Application demonstration; not the canonical starter or a production template.**
Use the [ticket desk tutorial](../../docs/docs/getting-started/first-project.md)
for a complete protected application with executable tests.

This example contains `Customer`, `Deal` and `Activity`, serializers and generated REST routes.
It is useful for inspecting model and API patterns. Optional Studio and AI
configuration in its settings is experimental and differs from the neutral
`startproject` defaults.

## Run locally from a source checkout

Use a dedicated PostgreSQL database. Set `DATABASE_URL` to its connection URL
in your shell before these commands; do not use a production database. The
example's own settings prefer `DATABASE_URL` over `AKSARA_DATABASE_URL`, unlike
the framework's normal environment precedence. Set them consistently.

Run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export AKSARA_DATABASE_URL="$DATABASE_URL"
aksara makemigrations --app examples.crm.models --output examples/crm/migrations
aksara migrate --migrations-dir examples/crm/migrations
aksara run examples.crm.main:app --host 127.0.0.1 --port 8000
```

The explicit module path preserves relative imports. `aksara dev` is a local
project convenience; the command above makes this repository example's entry
point unambiguous. `aksara doctor launch-check` is intended for a project layout
and is not proof that an example's mutations or security integration work.

## Inspect and test

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/openapi.json
```

Browse `http://127.0.0.1:8000/docs` to inspect the generated API. A startup or
OpenAPI success proves neither a working authenticated write path nor a safe
production deployment.

## Seed and mutation boundary

There is no complete authenticated seed flow in this example. The earlier
README's unauthenticated POST to `/api/customers/` returns **403** with v0.7.0;
it does not create a record. Do not disable permission checks to make it pass.
The example API-key dependency does not establish a server-owned Principal. Supplying its development X-API-Key header does not make generated writes an authenticated application journey.

The [ticket desk](../../docs/docs/getting-started/first-project.md) supplies the
missing identity adapter and positive/negative CRUD tests. Use that flow when
building a new application, or explicitly design equivalent authentication
and policy for your own adaptation.

## Optional development surfaces

Studio at `/studio/ui` and the AI Console are experimental. Their presence in
this example does not make them production requirements. The HTTP JSON tool
inspection catalog is `/ai/tools/mcp`; it is not the MCP protocol endpoint.
Official clients use `/mcp/` after server-owned Principal resolution is installed.
The [MCP tutorial](../../docs/docs/tutorials/ticket-desk-mcp.md) demonstrates that
full path. No provider was called by the local startup audit.
