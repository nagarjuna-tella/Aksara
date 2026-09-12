# Deploy an Aksara application

**Stable within the documented production profile.** Start with a working
application from the [first-project guide](../getting-started/first-project.md).
Deployment adds an explicit migration step, restricted database credentials,
process supervision, and operational checks.

Aksara provides application and execution boundaries. You provide PostgreSQL,
TLS termination, secrets, backups, process supervision, monitoring, and any
external identity provider. Durability does not require Redis or a separate
workflow service.

## 1. Configure the application

Use deployment environment variables and the global `aksara.conf.settings`
object. An `AKSARA` dictionary or a new settings subclass does not configure
that object. See the authoritative [settings reference](../reference/settings-reference.md)
for defaults and precedence.

Configure these values in your deployment's secret/configuration store:

```dotenv
AKSARA_ENV=production
AKSARA_DEBUG=false
AKSARA_COOKIE_SECURE=true
AKSARA_ADMIN_RATE_LIMIT_ENABLED=true
AKSARA_MCP_ENABLED=false
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOW_CREDENTIALS=false
```

Also provide `AKSARA_SECRET_KEY` with a unique, securely generated value and
`AKSARA_DATABASE_URL` with your restricted application-role connection URL.
Do not commit their values. `AKSARA_DATABASE_URL` takes precedence over
`DATABASE_URL`; configure one source consistently so an old alias cannot send
migrations or application traffic to the wrong database.

Keep the generated project's settings import, including its explicit
`configure(installed_apps=...)`, before constructing the application. Environment
configuration does not discover your application's model modules automatically.

## 2. Separate migrations from application credentials

Create a migration role allowed to own and change the application schema, and
an application login with `NOSUPERUSER NOBYPASSRLS`. The application role should
have only the schema access, table DML, and sequence privileges its work needs.
Provision these roles through your PostgreSQL administrator; do not run the
web application as the migration owner or a database superuser.

In the deployment migration job, set `AKSARA_DATABASE_URL` to the migration
role's URL. From the project directory, apply the versioned migration files:

```bash
aksara migrate
```

Run this before starting the new application version. Grant the restricted
role access to newly migrated application and internal runtime tables and
sequences. Review default privileges for future migrations under the actual
migration owner. Successful migration under an administrator login does not
prove the application role can operate the resulting schema.

Switch the application processes back to their restricted-role URL. Avoid
running migrations independently in each web or worker process. Durable
Operations require their internal migrations before execution; they do not
create their schema as a startup convenience.

## 3. Establish tenant isolation

If the application is multi-tenant, resolve its tenant from authenticated,
server-owned identity. A user-supplied header or JSON tenant ID is not evidence
of membership. Apply and force PostgreSQL RLS on tenant tables and test with
the restricted application role.

`AKSARA_MULTI_TENANT=true` and `AKSARA_RLS_ENABLED=true` declare the deployment
posture to diagnostics. They do not create policies, verify credentials, or
turn an unrestricted database login into an isolated role. Follow
[multi-tenancy](../security/multi-tenancy.md) and exercise cross-tenant denial
before serving traffic. The [ticket-desk tenancy chapter](ticket-desk-tenancy.md)
provides an executed role, policy and cross-tenant test example.

## 4. Run diagnostics and serve

Provide `AKSARA_SECURITY_MATRIX_PATH` pointing to your reviewed deployment
security matrix. [Security matrix enforcement](../security/production-hardening.md#security-matrix-enforcement)
links the format and explains the coverage statuses. The example contains
planned scenarios and cannot pass release policy unchanged; its assertions
are not proof that your own application has passed the listed scenarios.

```bash
aksara doctor production-check --release
aksara run main:app --host 127.0.0.1 --port 8000
```

`main:app` is the generated application's import path. Substitute your actual
module when it differs. Put the server behind your TLS proxy and supervise it
with the deployment's process manager. Select bind address and worker count
for that environment; do not enable development reload in production.

Release-mode Doctor fails on warnings, failures, blocks, skipped checks, and
unknown results. Investigate them rather than suppressing the gate. Doctor
checks configuration and declared security coverage; it is not a penetration
test or a substitute for a real request through your restricted database role.

The separate `aksara doctor launch-check` helps diagnose project layout and
local startup. It may recommend optional development surfaces that you have
intentionally disabled in production.

## 5. Start background execution explicitly

A database-backed `Aksara` lifespan automatically starts its ordinary
`TaskWorker` when `tasks_enabled=True` (the default). Load the application's
task registrations and account for a worker in each such application process.
If you choose dedicated task-worker processes, explicitly disable the embedded
worker in the web process and follow the task guide for your worker entry point. Follow [background tasks](../advanced/background-tasks.md). Persisted
tenant identity in an ordinary task is not a stored Principal or automatic
current authorization for arbitrary task code.

For [Durable Operations](../advanced/durable-operations.md), deploy an explicit
worker entry point which constructs the same service configuration, registers
all needed actions and principal resolvers, connects its database, and runs
`DurableOperationWorker` for the intended tenant. Supervise that process
separately from web workers. Aksara does not enumerate tenants or start a fleet
of durable workers for you.

Before enabling claims, use the [durable preflight recipe](../advanced/durable-operations.md#history-export-and-retention)
to call `check_durable_operations()` for each deployed application namespace
and tenant profile. This is a separate Python service check, not part of the
Doctor production security command. Keep old action/resolver versions
registered while nonterminal Operations reference them. Verify cancellation,
revocation, and worker restart behavior with your actual business handlers.

## 6. Operate retention and external effects

Run an application-owned outbox exporter and bounded pruning schedule if you
adopt durability. Set retention and idempotency windows to match the promises
your API makes. Exported history is operational evidence, not a tamper-resistant
compliance ledger. Preserve any longer-lived records in your own retention
system.

Monitor stuck or expired leases, retry exhaustion, authorization failures,
outbox backlog, database pool pressure, and `external_outcome_unknown` results.
An unknown provider outcome needs the application's reconciliation process;
blindly resubmitting the effect can duplicate it. Cancellation does not undo
an already committed database mutation or an issued provider request.

Back up PostgreSQL and test restoration. Include uploaded media and retained
audit exports in the application's recovery plan. Define readiness checks that
exercise the deployed schema and required services; framework configuration
checks alone do not establish service health.

## 7. Upgrade deliberately

Apply migrations before new processes start. Review compatibility with old
processes during a rolling deployment, retain referenced action/resolver
versions, and test the upgrade against a restored database before production.
Do not assume downgrading the wheel reverses schema or external effects.

Follow the [v0.6.x to v0.7.x upgrade guide](../operations/upgrade-v07.md).
See the [v0.7 stability contract](../roadmap/v0-7-stability-contract.md) for
migration and operational prerequisites, and the
[v0.6 production contract](../roadmap/v0-6-stability-contract.md) for the
foundation that remains in force.

The [Support Desk reference](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/support_desk)
shows server-owned identities, restricted roles, forced RLS, readiness, tasks,
and synchronous MCP. Its environment-backed identities are an example adapter;
replace them with your real credential verification and membership source.
