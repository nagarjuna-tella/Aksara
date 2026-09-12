# CLI workflows

This page connects common commands to application tasks. The
[generated reference](../reference/cli-reference.md) lists the installed parser's
exact command names, arguments, flags, and defaults.

## Create a project

```bash
aksara startproject ticketdesk
cd ticketdesk
```

Follow the generated README and [first-project tutorial](../getting-started/first-project.md)
to configure PostgreSQL and add a model. `startapp` creates additional app
files; creating files does not automatically install the app or register its
ViewSets. Read the generated files before integrating them.

```bash
aksara startapp billing
```

Use `--help` to inspect template choices and target-directory arguments. Do not
infer template features or security defaults from their names.

## Generate and apply migrations

Run these from the configured project directory after adding the tutorial's
`app.models`:

```bash
aksara makemigrations --app app.models
aksara migrate --migrations-dir migrations --dry-run
aksara migrate --migrations-dir migrations
aksara status
```

Review generated migration files before applying them. `makemigrations --stdout`
prints generated content; it is not a CI drift-detection exit-code contract.
There is no `makemigrations --check` or `--empty` option in 0.7.0.

File-based migrations use the canonical executor with transactions, an advisory
lock, and applied-file checksum checks. Ensure migration files exist: the legacy
bootstrap fallback when files are absent is not the same integrity contract.
`--fake` records migrations without executing their changes and requires a
separately verified schema reconciliation. See [migration safety](../orm/migration-safety.md)
and the [production guide](../tutorials/deployment.md).

Database options accept explicit `--database-url`; environment bindings prefer
`AKSARA_DATABASE_URL` over `DATABASE_URL`. Keep credentials out of shell history
and shared logs. See [configuration precedence](../reference/settings-reference.md).
`dbsetup` is an interactive local setup helper, not production role provisioning.

## Run the application

```bash
aksara dev main:app
aksara run main:app --host 127.0.0.1 --port 8000
```

`dev` enables reload by default; `run` does not. Both expect an importable ASGI
application. `run dev` delegates to the development path. Multi-worker serving
is not a substitute for durable worker processes or a complete deployment plan.

## Inspect health

```bash
aksara info
aksara doctor launch-check --format json
aksara doctor production-check --format json
```

Read the [Doctor policies](../diagnostics.md) before turning these into a release
gate. A report can expose missing configuration without proving deployment
isolation, backup recovery, or every optional service.

## Run background work

```bash
aksara tasks list --help
aksara tasks stats --help
aksara tasks reenqueue --help
aksara tasks purge --help
```

These inspect or manage **ordinary tasks**. Reenqueue and purge can change data;
review filters and confirmations before using them. They do not operate on
Durable Operations. Durable action/resolver registration, worker startup,
tenant scope, and retention use the separate
[durable operations interface](../advanced/durable-operations.md); follow the
[executable tutorial](../tutorials/ticket-desk-durable.md) before operating one.

## Generate a client

```bash
aksara generate sdk --help
```

The TypeScript generator is **Evolving** and the public 0.7.0 output has a known
strict-compilation failure. Read the [TypeScript guide](../how-to/typescript-client.md)
for the reproducible limitation and application-import requirements.

## Optional AI tooling

AI and Studio command families are **Experimental**. They are not required to
build or serve a backend, and do not replace synchronous MCP authorization.
Use the [AI command guide](ai-commands.md) and actual subcommand help instead of
historical `ai query`, `ai generate`, or `ai doctor` examples, which are not
registered commands in 0.7.0.
