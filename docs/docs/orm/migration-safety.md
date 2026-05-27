# Migration Safety

Aksara applies migrations through a single, canonical execution path designed to
be safe to run repeatedly, safe to run from more than one place, and safe to run
against a database that already has data. This page explains what that path does
and why, so you can reason about what happens when you run `aksara migrate`.

If you are looking for how to *write* migrations — operations, dependencies, data
migrations — see [Migrations](migrations.md). This page is about how migrations
are *applied* and verified.

---

## Canonical executor path

Every migration run goes through the same executor in
`aksara.migrations.executor`:

- `aksara migrate` applies migrations through it.
- The testing helpers (for example, applying migrations in a test database) use
  the same executor.

Because there is one path, local, CI, and production runs get the same
guarantees: transactions, the advisory lock, SQL statement splitting, checksum
recording, and checksum verification. There is no "lighter" code path that skips
safety checks.

The `aksara migrate --dry-run` preview path does not apply anything — it only
shows what would run — and is unchanged.

---

## Transactional migration application

A Python migration's operations and the row that records the migration as applied
run inside a **single transaction**.

- If every operation succeeds, the migration is recorded as applied and the
  transaction commits.
- If any operation fails, the entire migration rolls back. Partial operations are
  not left behind, and the migration is **not** recorded as applied.

This means a failed migration leaves your schema as it was before that migration
started. You fix the cause and re-run; you do not have to manually undo a
half-applied migration.

---

## Advisory lock

Before inspecting which migrations are applied and running the pending ones, the
executor acquires a **PostgreSQL advisory lock**.

This prevents two processes — two deploy steps, a deploy racing a developer, two
CI jobs — from running migrations against the same database at the same time. The
second runner does not proceed concurrently; it is told the lock is held. The
lock is always released when the run finishes, including when a run fails.

---

## SQL migration statement handling

SQL migrations are split into individual statements and executed one at a time,
inside the same transaction as the recording step.

This matters because the underlying driver runs only the first statement of a
multi-statement string. Splitting ensures a SQL migration with several statements
applies completely, not just up to the first `;`.

---

## Checksums and applied migration integrity

When a migration is applied, Aksara stores a checksum of the migration (both
Python and SQL migrations store one). Before running any pending migrations, the
executor verifies the checksum of every **already-applied** migration against the
file currently on disk.

If an already-applied migration file has changed since it was applied, the
checksums no longer match and the run fails with the migration name and clear next
steps. This catches the case where an applied migration was edited in place —
which would otherwise drift your code and your database apart silently.

The rule this enforces is the same one in [Migrations](migrations.md): **do not
edit a migration that has already been applied.** Create a new migration instead.

---

## Handling historical NULL checksums

Migrations that were applied before checksums were recorded have no stored
checksum. These rows are still valid — they are **not** rejected. The executor
reports them with a warning so you know which historical migrations cannot be
integrity-checked, and continues.

There is intentionally no automatic backfill of these checksums (see
[Deferred metadata work](#deferred-metadata-work)).

---

## Failure reporting

Two behaviors make failures easier to understand:

- **Strict graph loading by default.** If a migration file cannot be loaded
  (import error, bad definition), the run fails with a clear error naming the
  migration, its path, and the underlying cause — instead of silently skipping
  it and applying an incomplete set. A non-strict mode remains available for
  tooling that needs to inspect a partially broken graph.
- **Skipped pending migrations are reported.** When a migration fails, the
  pending migrations that were not attempted are reported, and the CLI shows you
  which migrations were skipped, so you know exactly where the run stopped.

---

## Adding non-null fields without defaults

Adding a `nullable=False` column with no default fails on a table that already
contains rows — PostgreSQL cannot fill the existing rows.

When a generated migration contains such a field, Aksara emits a warning comment
on it. The comment points you to a safe rollout:

1. Add the column as nullable, or with a temporary default.
2. Backfill the existing rows.
3. Then enforce non-null in a follow-up migration.

Primary-key fields are exempt from the warning.

---

## SQL-generation guardrails

The DDL Aksara generates is hardened against malformed and unsafe identifiers:

- **Many-to-many constraints and columns.** Join-table constraint names are
  deterministic, double-quoted, and bounded to PostgreSQL's identifier length
  limit; source and target column references are quoted.
- **Partial-index predicates.** An index `where` predicate is validated when it
  is defined. Obvious unsafe patterns — statement terminators, comments, and
  DDL/DML keywords — are rejected. Ordinary predicates such as
  `created_at > NOW()` are unaffected.
- **Array field types.** An array field's SQL type is validated against an
  allowlist of PostgreSQL base types and normalised to a canonical form. For
  example, `ArrayField(sql_type="text[]")` normalises to `"TEXT[]"`. A base type
  that is not on the allowlist raises an error when the field is defined; open an
  issue to have additional types added.

---

## Deferred metadata work

Some migration-metadata features are intentionally **not** implemented yet. They
are called out here so you do not assume behavior that does not exist:

- **Migration metadata schema versioning** — there is no `schema_version` column
  on the tracking table.
- **App-label / name identity split** — there is no `app_label` column and no
  `UNIQUE(app_label, name)` redesign of the tracking table.
- **Automatic checksum backfill** — historical NULL-checksum rows are not
  backfilled automatically. Doing so would bless already-edited files with their
  current checksum and defeat tamper detection.
- **A migration verify/backfill command** — there is no dedicated command for
  this yet.

The internal `aksara_migrations` tracking table layout may change when this work
lands. See the [v0.6 Stability Contract](../roadmap/v0-6-stability-contract.md)
for what is and is not a stable contract.

---

## Related Documentation

- [Migrations](migrations.md) — writing migrations, operations, dependencies
- [CLI Reference](../cli/index.md) — `aksara migrate` and `aksara status`
- [v0.6 Stability Contract](../roadmap/v0-6-stability-contract.md) — what is stable
