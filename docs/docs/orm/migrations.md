# Migrations

Aksara uses a project-wide directory of versioned migration files. Generate
schema changes from models, review the result, then apply them with migration
credentials before starting the application under its restricted role.
The [first-project tutorial](../getting-started/first-project.md) demonstrates
this workflow for a running application.

## Generate and apply

From the project directory, with the environment and database configured:

```bash
aksara makemigrations --app app.models
aksara migrate --dry-run
aksara migrate
aksara status
```

`--app` names an importable models module. The default directory is `migrations`;
configure `AKSARA_MIGRATIONS_DIR` through the supported
[settings path](../reference/settings-reference.md). A bare variable in `settings.py` is
not automatically a settings override.

Useful generation options:

```bash
aksara makemigrations --app app.models --name add_priority
aksara makemigrations --app app.models --stdout
aksara makemigrations --app app.models --output custom_migrations
```

Pair a custom output directory with `aksara migrate --migrations-dir
custom_migrations`, or configure the directory consistently for generation,
application and status. `--sql` selects the legacy SQL output format; review its
contents rather than assuming it provides the Python migration graph's full
model-state history.

A dry run previews application migrations. It still imports migration files,
connects to PostgreSQL and can initialize migration-tracking metadata. It is
not a sandbox or a proof that the SQL will apply successfully. It also does not
replace the real executor's integrity checks or its bundled internal migrations.

## Runtime fields and migration operations are different

Use `aksara.fields` in model classes. Migration files use field operations from
`aksara.migrations.operations`, such as `op.StringField` and `op.UUIDField`.
Operations take actual database table/column names, not `model_name=`.

The following two complete files form a small standalone ticket-schema example.
Use a fresh disposable database/schema to try them. They are an alternative
learning fixture, not files to append to an already migrated Ticket Desk project.
For your application, retain the dependencies and table names generated from
its own history.

```python title="migrations/0001_ticket_schema.py"
from aksara.migrations import Migration as BaseMigration
from aksara.migrations import operations as op


class Migration(BaseMigration):
    dependencies = []
    operations = [
        op.CreateTable(
            name="migration_demo_tickets",
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("subject", op.StringField(max_length=200)),
                ("resolved", op.BooleanField(default=False)),
            ],
        ),
    ]
```

```python title="migrations/0002_ticket_priority.py"
from aksara.migrations import Migration as BaseMigration
from aksara.migrations import operations as op


class Migration(BaseMigration):
    dependencies = ["0001_ticket_schema"]
    operations = [
        op.AddField(
            table="migration_demo_tickets",
            name="priority",
            field=op.StringField(max_length=20, nullable=True),
        ),
        op.RunSQL(
            sql="UPDATE migration_demo_tickets SET priority = 'normal' WHERE priority IS NULL"
        ),
        op.AlterFieldNull(
            table="migration_demo_tickets", name="priority", nullable=False
        ),
        op.AlterFieldDefault(
            table="migration_demo_tickets", name="priority", new_default="normal"
        ),
        op.AddIndex(
            index=op.IndexOp(
                name="migration_demo_tickets_priority_idx",
                table="migration_demo_tickets",
                columns=["priority"],
            )
        ),
    ]
```

The second file safely handles existing rows: add a nullable column, populate
it, then require a value and establish the database default for future inserts.
Its operations share one transaction. For a large production table, assess locks
and backfill cost; split the rollout into compatible deployment stages when a
single migration would hold locks too long. A default is a business decision,
not a substitute for determining correct historical values.

## Available operation shapes

| Operation | Constructor shape |
|---|---|
| Create table | `CreateTable(name, fields, indexes=None, if_not_exists=True)`; optional arguments are keyword-only |
| Drop table | `DropTable(name, if_exists=True, cascade=False)`; options are keyword-only |
| Add column | `AddField(table, name, field)` |
| Remove column | `RemoveField(table, name, if_exists=True)`; option is keyword-only |
| Rename column | `RenameField(table, old_name, new_name)` |
| Change type | `AlterFieldType(table, name, new_field, using=None)`; `using` is keyword-only |
| Change nullability | `AlterFieldNull(table, name, nullable)` |
| Change default | `AlterFieldDefault(table, name, new_default=..., field=..., drop_default=False)`; options are keyword-only |
| Add index | `AddIndex(index=IndexOp(name, table, columns), concurrently=False, if_not_exists=True)` |
| Remove index | `RemoveIndex(name, table, if_exists=True, concurrently=False)`; options are keyword-only |
| Add constraint | `AddConstraint(table, name, constraint_sql)` |
| Remove constraint | `RemoveConstraint(table, name, if_exists=True)`; option is keyword-only |
| SQL/data change | `RunSQL(sql, reverse_sql=None, dangerous=False)`; options are keyword-only |

`constraint_sql` and type-conversion `using` expressions are reviewed migration
SQL, not values to take from requests. `IndexOp` also supports keyword-only
`unique`, `where` and `method` options. PostgreSQL still validates the resulting
index definition. `concurrently=True` cannot run inside the canonical executor's
per-migration transaction; it does not create an automatic non-transactional
migration mode.

There is no generic `AlterField` or `RunPython` operation in this release. Use
the specific change operations and `RunSQL` for supported data changes. A
`reverse_sql` attribute does not imply a public automatic rollback command or
that lost data can be reconstructed.

## Dependencies and merge migrations

Python `dependencies` entries are filename stems. Keep generated dependencies
when editing an unapplied migration. Aksara loads the dependency graph and orders
pending files accordingly; incompatible branches must be reconciled before
application.

```bash
aksara makemigrations --merge
```

A merge migration joins graph heads. An empty merge does not reconcile SQL that
changes the same column incompatibly. Review both branches and test the merged
history on a disposable database with representative data. Do not rewrite files
already applied in a shared environment to make the graph appear clean.

## Integrity and failure handling

The canonical file executor uses an advisory lock and a transaction per migration.
Earlier successful migrations remain committed if a later one fails. The failing
migration rolls back its supported PostgreSQL work and is not recorded as
applied; subsequent pending migrations are reported as unattempted.

Checksums detect edits to present files that have a recorded checksum. Missing
files and historical NULL checksums are warning cases, not complete integrity
proof. Preserve released migration files. See [migration safety](migration-safety.md)
for the precise boundaries and the legacy bootstrap path.

Use `--fake` only when you have independently verified that the intended schema
and data changes already exist. It records application without doing the work;
it is not a general repair for an out-of-sync database and can cause future
migrations or application startup to fail.

For destructive operations, back up and test recovery first. `RunSQL` can require
`AKSARA_ALLOW_DANGEROUS_MIGRATIONS` for operations flagged as dangerous. This is
an execution guard, not a security review, and cannot make destructive SQL safe.
Never put credentials or untrusted dynamic input into migration files.

## Verify a migration

Test a fresh database and an upgrade with representative existing rows. Inspect
the stored values and catalog constraints/defaults, rerun to prove no pending
work, and inject failure to verify rollback and tracking behavior. Do not test
only whether a model can be instantiated.

For application integration tests, own the disposable database/schema and stop
workers before cleanup. For production, use a separate migration job with the
appropriate role, then verify deployment readiness. See
[testing](../advanced/testing.md), [deployment](../tutorials/deployment.md), and
[upgrading from v0.6](../operations/upgrade-v07.md).
