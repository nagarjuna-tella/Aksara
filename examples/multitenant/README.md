# Aksara Example: Multitenant

This example demonstrates:
- Models
- ViewSets
- Migrations
- Studio
- MCP tools
- AI Console usage

Tenant-aware application structure. It includes tenants, tenant-bound users/projects, tenant filtering, request middleware, and a basic tenant isolation explanation.

## Run

```bash
cd examples/multitenant
python -m venv .venv
source .venv/bin/activate
pip install -e ../..
aksara doctor launch-check
aksara migrate
aksara dev
```

Set `DATABASE_URL` if your local PostgreSQL credentials differ from the development default:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aksara_multitenant"
```

## Seed

No seed command is required. Create a first tenant through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/tenants/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","slug":"acme-corp","plan":"pro"}'
```

## Open

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* MCP: http://127.0.0.1:8000/ai/tools/mcp

## Test API

```bash
curl http://127.0.0.1:8000/api/tenants/
curl http://127.0.0.1:8000/api/users/ -H "X-Tenant-Slug: acme-corp"
curl http://127.0.0.1:8000/api/projects/ -H "X-Tenant-Slug: acme-corp"
```

## Test MCP

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

Confirm tenant-scoped models are visible and review custom actions before exposing them to agents.

## Tenant Isolation

Tenant context is resolved from `X-Tenant-ID`, `X-Tenant-Slug`, or host-based routing. Tenant-bound models include a tenant foreign key so APIs and AI/MCP flows can stay scoped to one organization at a time.

## Try in AI Console

Ask:

```text
Explain the tenant-bound models
Review tenant isolation risks
Investigate this project
```

AI provider setup is optional for first launch. Do not send cross-tenant data to external AI providers unless your deployment policy allows it.
