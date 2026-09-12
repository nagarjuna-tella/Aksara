# Historical multitenant example

**Known limitation — not the recommended isolation pattern.** Use
[Ticket Desk tenant isolation](../tutorials/ticket-desk-tenancy.md) for a working
application with server-owned tenant identity and restricted-role PostgreSQL
RLS. Use the [production guide](../tutorials/deployment.md) for operational roles
and deployment checks.

## Why this example is retained

The historical template contains `Tenant`, `User`, and `Project` models,
serializers, ViewSets, and middleware that attempts to resolve a tenant from
request headers or a host name. It is useful for understanding an earlier
application design, not for proving safe SaaS isolation.

Its middleware exempts paths by prefix and includes `/` in that exemption list.
Every normal request therefore skips the tenant resolver. This is the known
EX-001 defect; it remains unchanged in the documentation release. Startup and
OpenAPI success do not prove tenant selection or isolation.

Even after a resolver correction, a client-supplied tenant ID, slug, or host is
not proof that the authenticated actor belongs to that tenant. Application
membership checks and the database role/RLS configuration must be designed and
tested together. The template does not supply the canonical tutorial's
restricted-role, forced-RLS evidence.

There is also a migration discovery limitation: the registry keys models by
class name. In the installed v0.7.0 CLI flow, discovery of the built-in auth
`User` replaces this example's `User`. Migration generation and application
return success, but the declared `tenant_users` table is absent. This is
MIGRATION-001; the inspection commands below do not produce a complete working
tenant application. Changing `Meta.table_name` alone does not disambiguate a
class-name collision. Use distinct application model names and inspect the
actual migration operations and resulting tables.

## Generate only for local inspection

Use an environment with [Aksara installed](../getting-started/installation.md)
and export `DATABASE_URL` for a dedicated local PostgreSQL database. The example
prefers it over `AKSARA_DATABASE_URL`; keep them consistent.

```bash
aksara startproject tenant_demo --template multitenant
cd tenant_demo
aksara makemigrations --app models --output migrations
aksara migrate --migrations-dir migrations
aksara run main:app --host 127.0.0.1 --port 8000
```

This template copies flat modules and does not generate a `pyproject.toml`,
`.env`, or `app/` package. Use these commands rather than the generic
editable-install and `app.models` instructions printed after generation.

In another terminal, inspect startup only:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/openapi.json
```

Do not interpret a successful response or an `ai_exposed` flag as authorization
or isolation evidence. This guide intentionally provides no tenant seed/write
flow that could be mistaken for a safe production path.

## Build the supported path instead

Follow the tenancy chapter in order: establish the actor's identity, derive
its allowed tenant on the server, scope model access, and apply/test PostgreSQL
RLS using an application role that cannot bypass it. Test two tenants and
negative access, including attempts to supply a different tenant in input.

For a custom endpoint, follow the synchronous query hooks and explicit
permission checks in the [ViewSet reference](../api/viewsets.md). The older
pattern's asynchronous `get_queryset` recipe is not the current hook contract.
For work that continues later, propagate identity through the
[durable-action tutorial](../tutorials/ticket-desk-durable.md) rather than assuming
a request header survives as trusted worker context.

Schema-per-tenant and database-per-tenant routing are not implementations provided
by this example. The supported production path documented here remains shared
PostgreSQL tables with explicitly verified application and RLS boundaries.
