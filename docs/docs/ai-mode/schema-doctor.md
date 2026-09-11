# Schema analysis

!!! warning "Experimental analysis surface"
    Analysis output is outside the stable migration contract. It provides
    findings for review; it is not an automatic schema repair or a replacement
    for versioned migrations and deployment checks.

The installed CLI command is `aksara ai schema-health`. Run it from an
application with its model registry and PostgreSQL connection configured:

```bash
aksara ai schema-health --format json
aksara ai schema-issues --format json
aksara ai schema-issues --severity danger
```

Health statuses are `healthy`, `degraded` and `danger`. Issue severity uses
`info`, `warning` and `danger`. Filters for `schema-issues` include `--severity`,
`--kind`, `--table` and `--app-label`; inspect `--help` for the exact options.

The former `aksara ai doctor` and `aksara ai doctor --fix` examples were not
valid v0.7.0 commands. There is no `SchemaDoctor` class to instantiate.
Do not interpret a generated suggestion as an applied migration.

## Python integration

The actual async API is:

```python
from aksara.ai import analyze_schema_health

report = await analyze_schema_health(app)
print(report.status)
```

This is an integration snippet, not a standalone program: `app` is your running
application, the database must already be connected and the intended models
must be registered. It compares the model schema map with database
introspection. A missing database is a configuration finding, not proof that
all application tables are absent.

Review the concrete findings against your migration history. Generate and
review a migration using the [migration guide](../orm/migrations.md), then
apply it through the [production deployment process](../tutorials/deployment.md).
Schema analysis cannot establish authorization, correct RLS policy, backup
recoverability or the safety of an arbitrary migration.

For production security posture use [Doctor](../diagnostics.md). For durable
schema and registration readiness use the separate
[durable preflight](../advanced/durable-operations.md#history-export-and-retention).
