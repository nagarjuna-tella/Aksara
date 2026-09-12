# Build a tenant-scoped application

Use the [ticket-desk tenancy chapter](ticket-desk-tenancy.md) for the complete
runnable implementation. It continues the same application used in the
[first project](../getting-started/first-project.md) and demonstrates trusted
membership, permissions, migration, restricted database roles, forced RLS and
cross-tenant denial tests.

This page replaces the older standalone SaaS tutorial. That version combined
legacy configuration, unimplemented helper APIs and header-selected tenancy
without a complete authenticated membership boundary. It must not be used as
an isolation guarantee.

## What establishes the boundary

A tenant is an application-defined customer or organization. In the documented
shared-database design, tenant records share tables and each row carries tenant
identity. Correct isolation requires the following pieces together:

| Piece | Responsibility |
| --- | --- |
| Credential verifier | Verify who made the request |
| Membership resolver | Establish which tenant the verified identity may act in |
| Principal and request context | Carry that trusted identity and tenant through the request |
| Application permissions and policy | Decide whether this actor may perform the requested operation |
| Tenant-aware data access | Apply the intended tenant scope to queries and writes |
| Restricted PostgreSQL role and forced RLS | Enforce the declared database isolation boundary |
| Tests | Prove both permitted requests and denied cross-tenant access |

A subdomain or header may be an input to tenant selection, but is not proof of
membership. Validate the selected tenant against server-owned identity before
establishing context. Clear context at the end of the request so it cannot leak
into another request.

`TenantModel` is one part of this design. It does not provision database roles,
create your application RLS policies, validate credentials or review custom
handlers. The diagnostics flags `AKSARA_MULTI_TENANT` and `AKSARA_RLS_ENABLED`
declare posture; they do not perform those steps.

## Follow the tested implementation

The [tenancy chapter](ticket-desk-tenancy.md) provides exact files and commands:

1. Add tenant identity to the application's models and generate a migration.
2. Deliberately backfill existing rows before enforcing non-null identity.
3. Apply and force RLS using the documented tenant session setting.
4. Grant a restricted application role only the required privileges.
5. Resolve membership from verified credentials and apply application permissions.
6. Validate related-object ownership before accepting a foreign key.
7. Run allowed and denied requests under the restricted role.

The tutorial's one-tenant backfill is a local learning assumption. For a real
application, determine each existing row's correct owner and test the migration
on a restored database. Never assign all production rows to an arbitrary tenant
just to satisfy a constraint.

## Required denial cases

Before deploying your adaptation, retain tests for:

- Tenant A cannot list, retrieve, update or delete tenant B's records.
- A reader cannot write, and missing tenant context fails closed.
- A caller cannot choose ownership through a JSON field or forged header.
- A foreign key cannot connect a record to another tenant's object.
- Interleaved requests do not inherit another request's tenant context.

The tutorial exercises these cases; a green test for its implementation does
not certify a different identity adapter or custom route. PostgreSQL foreign-key
integrity alone does not prove application tenant membership.

## Background work and operations

Ordinary tasks can persist tenant identity, but do not automatically persist
and revalidate a full Principal. Use the [reports chapter](ticket-desk-reports.md)
for tenant-scoped task results and protected downloads. Use
[Durable Operations](ticket-desk-durable.md) when the operation must re-check
current authority across retries and time.

For production role separation, backups and monitoring, follow
[deployment](deployment.md). The historical `examples/multitenant` middleware
has a documented exemption defect; it is not the reference implementation for
this guide. Use the tested chapter or the Support Desk reference instead.
