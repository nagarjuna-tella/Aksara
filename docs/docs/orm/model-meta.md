# Model metadata and introspection

Use a model's `meta` attribute to inspect its declared fields and relationships.
This is useful for developer tools and diagnostics. It describes the Python model;
it does not query PostgreSQL to confirm that migrations, indexes, or constraints
have been applied. It is not an authorization-filtered API schema.

## Inspect a model

This example runs without a database connection. It uses a concrete related
model so introspection does not depend on resolving a lazy relation.

```python title="inspect_models.py"
from aksara import Model, fields


class MetadataOwner(Model):
    name = fields.String(max_length=80)


class MetadataDocument(Model):
    title = fields.String(max_length=200)
    owner = fields.ForeignKey(MetadataOwner, related_name="documents")

    class Meta:
        table_name = "metadata_documents"
        app_label = "documents"


def describe_document():
    meta = MetadataDocument.meta
    title = meta.get_field("title")
    return {
        "name": meta.name,
        "table": meta.table_name,
        "app": meta.app_label,
        "primary_key": meta.pk_name,
        "title_limit": title.max_length,
        "owner_is_foreign_key": isinstance(
            meta.foreign_keys["owner"], fields.ForeignKey
        ),
        "field_names": meta.field_names,
    }
```

`describe_document()` reports `MetadataDocument`, `metadata_documents`,
`documents`, primary key `id`, a title limit of 200, and a foreign-key flag of
`True`. The field names include framework-added fields as well as your declarations.

## Interface

| Member | Result |
| --- | --- |
| `name` | Python model class name |
| `table_name` | Declared/inferred SQL table name |
| `app_label` | Explicit `Meta.app_label`, otherwise inferred from the module path |
| `fields` | New list of the model's actual field objects |
| `field_names` | New list of declared field names |
| `pk`, `pk_name` | Primary-key field and its name, or `None` |
| `get_field(name)` | Field object, or `None` if absent |
| `has_field(name)` | Whether the declared field exists |
| `relations` | Cached name-to-field dictionary combining forward FK and M2M fields |
| `foreign_keys` | Copy of the name-to-field dictionary for foreign keys, including one-to-one fields |
| `many_to_many` | Copy of the name-to-field dictionary for many-to-many fields |
| `to_dict()` | Metadata dictionary with model, field, primary-key, and relation descriptions |

Treat all returned field objects and the cached `relations` dictionary as
read-only. Copying a list or dictionary does not clone the fields inside it.
`meta` does not expose a `reverse_relations` collection or the old reference's
`model_name`, `db_table`, `concrete_fields`, and `FieldInfo` abstractions.

Use `isinstance(field, fields.ForeignKey)` to distinguish types. Common field
attributes include `name`, `column_name`, `nullable`, `unique`, `primary_key`,
and `default`; attributes such as `max_length` depend on the concrete field type.
Use [relations](relations.md) for supported relationship declarations and access.

`to_dict()` is a descriptive representation, not OpenAPI or JSON Schema. It
includes field type names and selected attributes; it does not encode every
validator or permission. Do not assume arbitrary defaults or choices are JSON
serializable. Inspect and normalize your application's values before exporting
metadata. Avoid exposing schema information to unauthorized callers.

## Nested `Meta` declarations

`Meta.table_name` overrides the inferred snake-case plural table name.
`Meta.app_label` controls the metadata label; without it, a module ending in
`.models` uses the preceding component, and other module paths use their first
component. A label does not create a database schema or enforce tenancy.

The previous reference listed Django-style `ordering`, `unique_together`,
`indexes`, `verbose_name`, `verbose_name_plural`, and `abstract` as supported
options. They are not implemented as those model behaviors in v0.7.0. Adding
arbitrary attributes to the nested class does not make Aksara enforce them.
Specify ordering explicitly on queries and review generated migrations for
actual database constraints. See [models](models.md) and
[migrations](migrations.md).

AI-oriented model declarations are separate from `meta`: model construction
reads `ai_name`, `ai_description`, `ai_agent_exposed`, and `ai_permissions` into
its AI metadata. These labels are not a replacement for execution-time
permissions, field policy, or tenant enforcement. Do not rely on the historical
`ai_visible=False` example as a security boundary; consult the
[MCP guide](../ai-mode/mcp.md) for the supported tool exposure and authorization path.
