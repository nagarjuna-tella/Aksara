# Fixtures

Fixtures are application-level records for controlled development seeding and
selected data export. They are not PostgreSQL backups: they do not preserve
schema, roles, policies, file contents, or a consistent database snapshot.
Use your database backup and restore procedure for recovery.

## Seed new rows with JSON

Use trusted input and an already migrated, connected application database. This
example defines a small model and helper; place the model in your application's
model module and generate/review its migration first.

```python title="fixture_notes.py"
import json

from aksara import Model, fields
from aksara.fixtures import dump_data, load_data


class FixtureNote(Model):
    title = fields.String()


async def seed_note(title):
    payload = [{"model": "FixtureNote", "fields": {"title": title}}]
    return await load_data(json.dumps(payload), strict=True)


async def export_notes():
    return await dump_data(FixtureNote, fields=["title"], format="json")
```

Omitting `pk` creates a new row. Repeating `seed_note` creates another row; this
is not idempotent seeding. Inspect the returned `loaded`, `errors`, and `skipped`
counts when using lenient mode.

A nonempty `pk` means **update an existing row**, not insert-or-update. If that
primary key is missing, loading fails. Exports include a `pk` even when `fields`
selects only particular fields, so exporting and loading into an empty table is
not a supported restore path in v0.7.0. Do not simply remove identifiers from
relational fixtures: doing so changes identities and can break references.

## Export selected records

`dump_data(model, filters=None, fields=None, format="json")` returns a string.
Filters use the model's query API. A nonempty `fields` list selects non-primary
fields; `None` or an empty list exports all of them. Model names and primary keys
are always included. UUIDs and datetimes are encoded as strings in JSON; other
field types need application-specific verification. Foreign keys are identifiers,
not recursively exported related objects.

`dump_database(models=["FixtureNote"], format="json")` exports explicitly named
registered models. Despite its name, it does not traverse database tables or
provide backup guarantees. In v0.7.0 its default registry iteration fails when
models are registered; supply explicit model names. Export filtering still obeys
normal manager behavior, including exclusion of soft-deleted rows.

## Errors and transaction boundaries

`load_data(..., strict=False)` counts record failures and continues; do not expect
per-record error logging. Missing `model` names are skipped, while unknown model
names raise registry lookup errors that are counted as errors in lenient mode.
Malformed JSON or YAML fails before record processing, even in lenient mode.

`strict=True` raises on the first failing record. It does not automatically undo
earlier successful writes. Use a supported outer
[transaction](expressions-and-transactions.md) when the entire import must roll
back together, and let failures leave that transaction.

The optional `models` mapping selects supplied classes for matching names, but
falls back to the global registry for other names. It is **not an allowlist**.
These helpers do not apply REST serializer, Principal, or PolicyEngine checks.
Restrict who can invoke imports and validate permitted models, fields, tenant
identifiers, and data before calling them. Do not expose raw fixture loading as
an authenticated user's general upload endpoint.

## YAML limitation

YAML requires PyYAML. In v0.7.0, `dump_data(..., format="yaml")` emits Python UUID
tags that `load_data(..., format="yaml")` rejects with its safe loader. Prefer
JSON for the limited workflow above. Do not switch to an unsafe YAML loader to
work around this. The explicit-model `dump_database` path first converts through
JSON and has different serialization behavior; it still does not fix the
missing-primary-key restore limitation.

The missing-row restore, single-model YAML round-trip, and default registry
iteration defects require separately scoped runtime patches. This documentation
release changes none of those behaviors.
