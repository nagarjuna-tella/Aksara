# Model Inspector

> **v0.5.21** — Deep model introspection for schema analysis, AI context, and CLI.

The **Model Inspector** provides structured metadata about every registered Aksara model — fields, relationships, constraints, timestamps, primary keys, and auto-generated diagnostic comments.

---

## Quick Start

### Python API

```python
from aksara.inspectors.models import inspect_model, inspect_all_models
from aksara.registry import ModelRegistry

# Inspect a single model
model_cls = ModelRegistry.get("User")
summary = inspect_model(model_cls)

print(summary.name)              # "User"
print(summary.table_name)        # "users"
print(summary.num_fields)        # 5
print(summary.has_timestamps)    # True
print(summary.comments)          # ["✓ Timestamps (created_at, updated_at) detected"]

# Inspect all models
all_summaries = inspect_all_models()
for s in all_summaries:
    print(f"{s.name}: {s.num_fields} fields, {s.num_relationships} rels")
```

### CLI

```bash
# List all models
aksara inspect models

# Inspect a single model with field details
aksara inspect models --model User

# Show fields and relationships
aksara inspect models --fields --relationships

# JSON output for piping
aksara inspect models --json

# Pipe to agent for schema review
aksara inspect models --json | aksara agent prompt -g "Review schema design"
```

### Studio API

```bash
# Single model
curl http://localhost:8000/studio/models/inspect/User

# All models
curl http://localhost:8000/studio/models/inspect/all
```

---

## Models

### `ModelInspectorField`

| Field            | Type           | Description                      |
|------------------|----------------|----------------------------------|
| `name`           | `str`          | Field name on the model class    |
| `column_name`    | `str`          | Database column name             |
| `field_type`     | `str`          | Aksara field class name          |
| `python_type`    | `str`          | Expected Python type             |
| `nullable`       | `bool`         | Whether NULL is allowed          |
| `primary_key`    | `bool`         | Is the primary key               |
| `unique`         | `bool`         | Has UNIQUE constraint            |
| `has_default`    | `bool`         | Whether a default is set         |
| `default_repr`   | `str | None`   | String repr of default           |
| `max_length`     | `int | None`   | Max length for string fields     |
| `choices`        | `list | None`  | Enum/choice values               |
| `is_relation`    | `bool`         | FK or M2M field                  |
| `ai_description` | `str`          | AI-facing description            |
| `ai_sensitive`   | `bool`         | Holds sensitive data             |
| `auto_generated` | `str`          | Inspector auto-comment           |

### `ModelInspectorRelationship`

| Field          | Type           | Description                 |
|----------------|----------------|-----------------------------|
| `field_name`   | `str`          | Field name on source model  |
| `kind`         | `str`          | `fk`, `m2m`, or `o2o`      |
| `target_model` | `str`          | Target model class name     |
| `target_table` | `str`          | Target database table       |
| `on_delete`    | `str`          | CASCADE, SET_NULL, RESTRICT |
| `through_table`| `str | None`   | Junction table for M2M      |
| `related_name` | `str | None`   | Reverse accessor name       |
| `nullable`     | `bool`         | FK column nullable          |

### `ModelInspectorConstraint`

| Field         | Type        | Description                         |
|---------------|-------------|-------------------------------------|
| `kind`        | `str`       | `primary_key`, `unique`, `index`, `check` |
| `columns`     | `List[str]` | Columns involved                    |
| `name`        | `str | None`| Constraint name                     |
| `description` | `str`       | Human-readable description          |

### `ModelInspectorSummary`

| Field              | Type           | Description                           |
|--------------------|----------------|---------------------------------------|
| `name`             | `str`          | Model class name                      |
| `table_name`       | `str`          | Database table name                   |
| `app_label`        | `str | None`   | Application label                     |
| `num_fields`       | `int`          | Total fields                          |
| `num_relationships`| `int`          | Total relationships                   |
| `has_timestamps`   | `bool`         | Has created_at/updated_at             |
| `pk_field`         | `str | None`   | Primary key field name                |
| `pk_type`          | `str`          | Primary key field type                |
| `fields`           | `List[Field]`  | All fields with metadata              |
| `relationships`    | `List[Rel]`    | All relationships                     |
| `constraints`      | `List[Con]`    | Inferred constraints                  |
| `ai_description`   | `str`          | AI-level model description            |
| `ai_agent_exposed` | `bool`         | Whether AI agents can access model    |
| `create_table_sql` | `str`          | CREATE TABLE SQL                      |
| `comments`         | `List[str]`    | Auto-generated inspector notes        |

---

## Auto-Generated Comments

The inspector automatically generates diagnostic comments:

| Comment                                    | When                              |
|--------------------------------------------|-----------------------------------|
| ⚠️ Model has no fields defined             | No fields found                   |
| ⚠️ No explicit primary key detected        | No PK field                       |
| ✓ Timestamps (created_at, updated_at)      | Both auto-timestamp fields exist  |
| Relations: 2 FK(s), 1 M2M(s)              | Has relationships                 |
| ⚠️ Has sensitive fields                    | Any field marked `ai_sensitive`   |
| 🔒 Not exposed to AI agents               | `ai_agent_exposed = False`        |

---

## Studio Integration

### Inspector Tab

The Studio UI includes a dedicated **Inspector** tab (keyboard shortcut: `9`) with:

- **Summary Cards** — Total models, fields, and relationships
- **Model Cards** — Expandable per-model detail with field tables, relationship tables, and CREATE TABLE SQL
- **Auto-generated Comments** — Diagnostic notes for each model

### Agent Context

The `schema_analysis` section (section 11 of 11) is included in agent context, providing:

- `total_models`, `total_fields`, `total_relationships`
- Per-model summary with name, table, field count, relationship count, timestamps, and comments
