# Diagnostics and Doctor

Doctor helps inspect an application, diagnose local setup and check deployment
configuration. Choose the command for the question you need answered: a local
launch check and a strict production gate have different exit policies.

## Choose a check

| Question | Command | Result policy |
| --- | --- | --- |
| Can this project start locally? | `aksara doctor launch-check` | 0 ready, 1 partial with warnings, 2 blocked |
| What general health issues exist? | `aksara doctor run --format json` | 1 for errors; warnings alone do not fail |
| What is the security posture? | `aksara doctor security-check --format json` | Inspection report; use production-check for enforcement |
| Are production blockers present? | `aksara doctor production-check --format json` | 1 for blocking or failing results |
| Does every release-policy check pass? | `aksara doctor production-check --release --format json` | 1 for warnings, failures, blocks, skips or unknown results |

Run commands with the application's deployment environment. Read
[configuration precedence](reference/settings-reference.md#precedence) when a
result differs from the settings you expected. For local layout and migrations,
start with the [first-project guide](getting-started/first-project.md).

`launch-check` reports project structure, imports, database connectivity,
migrations and optional development surfaces. Studio or provider warnings can
make a valid REST-only development application PARTIAL; they are not a reason
to enable those features in production.

## Production release policy

Follow [production deployment](tutorials/deployment.md) for migration and
application roles, RLS, secrets and worker startup. Use this command in the
deployment validation job after configuring the intended environment:

```bash
aksara doctor production-check --release --format json
```

The report contains `policy`, `status`, `results`, `summary`, `exit_code` and
`release_ready`. Preserve its process exit status in CI. This command checks
security configuration and declared coverage; it does not execute your
application's adversarial tests, validate a live RLS policy or prove backups.

Set `AKSARA_SECURITY_MATRIX_PATH` to your application's reviewed matrix.
[Security matrix enforcement](security/production-hardening.md#security-matrix-enforcement)
explains the schema and examples. Release policy requires completed coverage
entries for implemented surfaces; the example's `planned` scenarios deliberately
do not satisfy that policy. Mark a scenario covered only after its real test
passes. Do not use the framework's release matrix as evidence for your own app.

## Durable-operation preflight

Doctor's production security report is separate from the durable service
preflight. After migrations, call public `check_durable_operations()` with your
connected service, registered action/resolver versions and tenant. The
[durable guide](advanced/durable-operations.md#history-export-and-retention)
shows the call and release-ready check.

This preflight examines the durable schema, referenced versions, ownership,
outbox backlog and retention configuration. It does not start workers, enumerate
tenants, deliver exports or run a restore drill. Run it for each application
namespace and tenant profile you deploy. The
[durable ticket-desk chapter](tutorials/ticket-desk-durable.md) provides a working
service and explicit worker entry point.

## General diagnostics

`aksara doctor run` examines database connectivity, migration state, settings,
AI configuration, cache availability, filesystem access and security. Its issue
severities are `error`, `warning` and `info`.

```python
from aksara.diagnostics import run_all_checks

report = await run_all_checks()
print(report.overall_status)
for issue in report.issues:
    print(issue.severity, issue.title, issue.message)
```

This is an asynchronous application snippet; call it from an async entry point.
`report.stats` contains `errors`, `warnings` and `info` counts. Each issue also
has a `kind`, optional `hint` and `meta`, and a list of suggested `actions`.
The report includes timestamp, duration and system metadata. Review output for
application details before publishing it.

For focused inspection and suggested repairs:

```bash
aksara doctor db
aksara doctor ai
aksara doctor summary
aksara doctor fix-plan --format json
aksara doctor fix-plan --only-errors --only-with-actions
```

A fix plan describes actions; inspect each before applying it. The
[autoremediation guide](debugging/autoremediation.md) describes the hints.

## Optional Studio display

Studio can display diagnostics through its dashboard and `/studio/diagnostics`.
Studio is an experimental development surface and is not required for Doctor.
Do not expose it merely to run a production check. Consult
[Studio configuration](studio/configuration.md) if you intentionally use it.
