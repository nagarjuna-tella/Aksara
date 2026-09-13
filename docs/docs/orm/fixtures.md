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

Omitting `pk` has **seed** semantics: it creates a row and lets the model generate
its primary key. Repeating `seed_note` creates another row, so seeding is not
idempotent. A fixture with `pk` has **restore** semantics: it updates the row when
that primary key exists and inserts it with the supplied identity when it does
not. The primary key is therefore the conflict identity; these helpers do not
merge records by another unique field. Inspect the returned `loaded`, `errors`,
and `skipped` counts when using lenient mode.

## Export selected records

`dump_data(model, filters=None, fields=None, format="json")` returns a string.
Filters use the model's query API. A nonempty `fields` list selects non-primary
fields; `None` or an empty list exports all of them. Model references and primary
keys are always included. UUID, date, time, and datetime values use portable
strings; nested lists and dictionaries are converted recursively. Foreign keys
are identifiers rather than recursively exported related objects. Load referenced
records before dependants; `dump_database()` orders selected registered models by
their foreign-key dependencies when the dependency graph permits it.

`dump_database(models=["FixtureNote"], format="json")` exports explicitly named
registered models. Omitting `models` exports every registered model. A simple
model name works when unique. When two registered classes share a name, use the
qualified identity shown by `aksara inspect models`, such as
`tenant.models.User`. Despite its name, this helper does not traverse arbitrary
database tables or provide backup guarantees. Export filtering still obeys normal
manager behavior, including exclusion of soft-deleted rows.

## Errors and transaction boundaries

`load_data(..., strict=False)` counts record failures and continues; do not expect
per-record error logging. Missing `model` names are skipped, while unknown model
names raise registry lookup errors that are counted as errors in lenient mode.
Malformed JSON or YAML fails before record processing, even in lenient mode.

`strict=True` raises on the first failing record. It does not automatically undo
earlier successful writes. Use a supported outer
[transaction](expressions-and-transactions.md) when the entire import must roll
back together, and let failures leave that transaction.

The optional `models` mapping selects supplied classes for matching references, but
falls back to the global registry for other names. It is **not an allowlist**.
These helpers do not apply REST serializer, Principal, or PolicyEngine checks.
Restrict who can invoke imports and validate permitted models, fields, tenant
identifiers, and data before calling them. Do not expose raw fixture loading as
an authenticated user's general upload endpoint.

## YAML fixtures

YAML requires PyYAML. The exporter emits the same portable scalar structure as
JSON and the loader uses `yaml.safe_load`; UUIDs and temporal values do not use
Python-specific object tags. Do not switch to an unsafe YAML loader.

Fixture loading validates and saves records one at a time. Cyclic foreign keys,
schema creation, roles, policies, large-data consistency, and files remain outside
this utility's contract. Use PostgreSQL backup tooling for disaster recovery.
