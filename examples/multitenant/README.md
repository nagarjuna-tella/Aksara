# Aksara Example: Multitenant

> **Known limitation — do not use as a production isolation reference.**
> The example middleware currently exempts every request because its `/`
> exemption uses prefix matching. A request to `/api/projects/` therefore skips
> tenant resolution. Header-based tenant selection also needs authenticated
> membership verification. Use the [Support Desk reference](../support_desk/README.md)
> for server-owned identity and restricted-role forced-RLS guidance. A behavioral
> correction requires a separate patch; v0.7.1 does not change this middleware.

## Purpose and status

This historical example contains Tenant, User and Project models and routing
ideas. It is **replaced as the recommended isolation example** by Support Desk
and the [ticket-desk tenancy chapter](../../docs/docs/tutorials/ticket-desk-tenancy.md).
It remains in the repository for inspection; its startup success is not tenant
isolation evidence.

A second limitation was reproduced in the installed template's migration flow:
the built-in auth `User` replaces the same-named example model in discovery,
so `tenant_users` is missing despite successful migration commands
(MIGRATION-001). See the [pattern status](../../docs/docs/patterns/multitenant.md)
for the exact boundary. Verify generated operations and actual tables; this
example is not a complete working tenant application.

## Run for local inspection only

From the repository root, with `DATABASE_URL` set to a dedicated disposable
PostgreSQL database:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export AKSARA_DATABASE_URL="$DATABASE_URL"
aksara makemigrations --app examples.multitenant.models --output examples/multitenant/migrations
aksara migrate --migrations-dir examples/multitenant/migrations
aksara run examples.multitenant.main:app --host 127.0.0.1 --port 8000
```

Use the explicit package path instead of relying on `aksara dev` discovery.
`aksara doctor launch-check` can inspect project setup, but cannot establish
that this middleware resolves or enforces tenant membership.

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/openapi.json
```

## Seed and tenant boundary

No seed flow in this README is claimed to establish safe tenancy. In particular,
a header naming a tenant is not proof of membership, and the middleware's
current prefix exemption bypasses its resolver. Follow the replacement tutorial
for authenticated identities, forced RLS and denied cross-tenant requests.

## Optional surfaces

Studio at `/studio/ui` and AI Console features are experimental. The
`/ai/tools/mcp` inspection catalog is not an authorization test or the protocol
transport. Official clients use `/mcp/`; do not expose this example as a safe
MCP tenant backend based on its model metadata.
