# Inspect model declarations

`inspect_model(model)` builds a Pydantic `ModelInspectorSummary` from a Python
model. It needs no database connection. `inspect_all_models()` inspects models
currently registered in the process, sorted by name; it silently skips models
whose inspection raises an exception, so its result is not a completeness check.

## Example

Run this as a standalone Python module after installing Aksara:

```python title="inspect_declared_model.py"
from aksara import Model, fields
from aksara.inspectors import inspect_model


class InspectedDocument(Model):
    title = fields.String(max_length=200, unique=True)


summary = inspect_model(InspectedDocument)
print(summary.name)
print(summary.table_name)
print(summary.pk_field)
print([field.name for field in summary.fields])
```

The model name is `InspectedDocument`, table name `inspected_documents`, and
primary key `id`. The field list includes framework-added fields. Inspect
`summary.model_dump()` when your tool needs a dictionary representation.

## What the result contains

| Attribute | Meaning |
| --- | --- |
| `name`, `table_name`, `app_label` | Model identity and declared/inferred labels |
| `fields`, `num_fields` | Inspector field descriptions and count |
| `relationships`, `num_relationships` | Forward relation descriptions and count |
| `pk_field`, `pk_type` | Inferred primary-key name and type label |
| `has_timestamps` | Whether both `created_at` and `updated_at` names exist |
| `constraints` | Inferred descriptions, not catalog results |
| `create_table_sql` | Generated declaration text, not a live schema dump |
| `comments` | Heuristic diagnostic notes |
| `ai_description`, `ai_agent_exposed` | Declared metadata, not proof of authorization |

Field descriptions include names, type labels, nullability, uniqueness, defaults,
and selected relation/AI attributes. These labels are not a replacement for field
validation or the generated API schema.

!!! warning "Declared constraints are not verified database constraints"
    The inspector synthesizes constraint names and foreign-key index descriptions.
    It does not query PostgreSQL catalogs to establish whether those indexes exist.
    A generated description can also differ from an application's custom column
    naming. Review migrations and the actual database schema before relying on an
    index, uniqueness constraint, or schema consistency.

Use [model metadata](../orm/model-meta.md) for the direct `Model.meta` interface,
[migrations](../orm/migrations.md) for schema changes, and
[production hardening](../security/production-hardening.md) for deployment checks.
