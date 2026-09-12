# Upgrade from v0.6.x to v0.7.x

**Stable backend upgrade; Durable Operations are opt-in.** You can upgrade an
existing application without turning REST requests, MCP calls or ordinary tasks
into Operations. Review the [runtime compatibility policy](../reference/runtime-compatibility.md)
and pin the chosen released version in the application's dependency lock.

## What changes

v0.7 adds durable action registration, current identity resolution, Operation
admission/status, workers, approvals, cancellation, recovery and bounded
retention. It bundles a new internal migration,
`aksara_core_migrations_0002_durable_operations`, after the runtime-table
migration. It does not automatically register your actions, enumerate tenants,
start durable workers or convert existing API routes.

The stable v0.6 synchronous REST/MCP, ORM, permission and task contracts remain
in force. A task's stored tenant context is still not a stored Principal.
Higher-level AI/workflow features remain outside the durable guarantee.

## 1. Rehearse against a restored database

Record the deployed wheel, dependency lock, applied migration history and
application code version. Take a backup and prove that it can be restored in
an isolated environment. Use that copy to test the upgrade with representative
application data and the actual restricted-role grants.

For the v0.7.0 baseline, install the published wheel in the rehearsal environment:

```bash
python -m pip install "aksara-framework==0.7.0"
aksara --version
```

For a later v0.7.x release, use its published version and release notes instead.
Do not use an unreviewed branch checkout as a production dependency. Keep
existing application model/migration files under version control; a framework
upgrade is not a reason to regenerate historical migrations.

## 2. Apply versioned migrations before startup

Use a schema-owning migration role and keep the application stopped during the
first rehearsal. Set `AKSARA_DATABASE_URL` to that role's connection URL in the
migration job. It takes priority over `DATABASE_URL`.

For a project with versioned application migration files:

```bash
aksara migrate
```

The file-based migration executor includes bundled internal migrations. Review
its output and failures. Grant the restricted application role the required
DML/schema/sequence access to newly created tables after migration.

**Legacy projects without migration files:** `aksara migrate` has a model-based
fallback; do not assume it runs the bundled internal migration sequence. Use the
public migration executor explicitly in a deployment script. This same explicit
path can be used for a migration job in a versioned project:

```python
# migrate_release.py — run from the project directory with migration credentials
import asyncio
from pathlib import Path

from aksara.conf import settings
from aksara.db import Database
from aksara.migrations import apply_migrations


async def main():
    if not settings.database_url:
        raise RuntimeError("Set AKSARA_DATABASE_URL before running migrations")
    database = Database(settings.database_url)
    await database.connect()
    try:
        result = await apply_migrations(
            database,
            Path(settings.migrations_dir),
            include_internal=True,
        )
        if result["errors"] or result["pending_skipped"]:
            raise RuntimeError("Migration failed; inspect the migration job output")
        print("Applied migration names:", result["applied"])
    finally:
        await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

Import your application's configuration module before this script's settings
use if your project has Python overrides; set the migration directory to the
actual versioned directory. The script applies existing files and internal
migrations. It does not generate a migration history for legacy model-only
schemas. Establish that history separately using the
[migration safety guide](../orm/migration-safety.md).

Do not use `--fake` merely to silence an error. It records migration state
without executing the schema change. A dry-run is a preview, not evidence that
the resulting schema or grants will work.

## 3. Verify the existing application first

Switch web and worker processes to restricted application credentials. Run:

```bash
aksara doctor production-check --release
```

Follow the [production guide](../tutorials/deployment.md) for the required
security matrix, tenant/RLS posture and operating configuration. Exercise
existing authenticated REST and MCP allow/deny paths, application migrations,
ordinary task execution, and a cross-tenant denial. Do not change auth or tenant
middleware merely because durability is now available.

A database-backed Aksara lifespan starts the ordinary task worker when
`tasks_enabled=True`. Account for that existing behavior when planning process
counts. A durable worker is a separate explicit application choice.

## 4. Adopt durability separately if needed

After the base upgrade is healthy, follow the
[Durable Operations guide](../advanced/durable-operations.md). Register versioned
actions and principal resolvers, construct the service with a stable application
namespace, and choose the correct effect class. Define current action policy,
retry classification and retention promises before accepting work.

Before starting a durable worker, call `check_durable_operations()` with its
service/tenant profile. Test permission revocation during delay, worker loss,
repeated idempotency keys, cancellation and the application's actual handler.
`postgres_atomic` requires the supported guarded connection in the same
database as the Operation state. External effects need a separate provider
idempotency/reconciliation contract.

## 5. Preserve compatibility through later deployments

Keep action and resolver versions registered while nonterminal Operations
reference them. Do not reinterpret old command payloads under a new handler
version. Configure web and worker namespace, identity mapping and retention
consistently. Include outbox export and pruning in the operating schedule.

Rehearse rolling deployment compatibility before allowing old and new workers
to overlap. If that has not been demonstrated, use a controlled stop/migrate/
start deployment instead. Downgrading a wheel does not undo a schema migration,
committed application data or an external effect. Choose a rehearsed restore
or forward-recovery plan for the failure you actually face.

## Acceptance checklist

The upgrade is complete when the chosen wheel reports the intended version,
migrations and grants are current, existing application behavior passes under
restricted roles, Doctor's release profile passes, and recovery has been
rehearsed. Durability additionally needs registered versions, worker/identity
failure tests and retention/export procedures. You do not need to read the ADR
or enable an AI provider to perform this upgrade.
