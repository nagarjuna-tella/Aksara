# Advanced Field Policy

!!! info "Historical design and compatibility record"
    This page records the v0.5.55 field-policy design, including proposals phrased
    as “should” and the candidate clarifications below. It is not a complete
    current API reference. Use [Fields](fields.md), [Relations](relations.md),
    [Bulk operations](bulk-operations.md), and the
    [v0.7 stability contract](../roadmap/v0-7-stability-contract.md) for current
    usage and supported boundaries.

Advanced Field Policy defines Aksara's runtime contract for advanced ORM fields
in v0.5.55 and later. It describes how `Array`, `Vector`, `JSON`,
`FileField`, and `ImageField` values are validated, serialized, and exposed
through model attributes, APIs, and database writes.

The goal is clarity over ambiguous persistence. When a value cannot be
represented safely, Aksara should raise an explicit validation error before
database execution.

---

## Scope

This policy covers:

- `Array` item typing and nested array behavior
- `Vector` precision and special float handling
- `FileField` and `ImageField` conversion and wrapper behavior
- `JSON` top-level scalar behavior
- Relation features that remain deferred

It does not change the v0.5.54 relation contract: forward FK/O2O attributes and
their `*_id` aliases expose the stored FK id, and related objects should be
loaded explicitly or with `select_related()` plus `get_related()`.

---

## Compatibility Principles

Aksara is still pre-1.0, so v0.5.55 may choose correctness over preserving
ambiguous behavior. Compatibility notes for each field below should be used in
the changelog and migration notes.

Implementation should follow these principles:

- Normalize values before SQL generation.
- Reject unsafe or unsupported values before database execution.
- Keep model attributes, generated API schemas, and database values consistent.
- Avoid silent coercion when it changes meaning.
- Keep advanced relation features out of this field-policy release.

---

## Array Policy

`Array` is a homogeneous, one-dimensional PostgreSQL array field.

### Constructor Contract

The canonical public option is `item_type`:

```python
tags = fields.Array(item_type=str, default=list)
scores = fields.Array(item_type=int, nullable=True)
flags = fields.Array(item_type=bool, default=list)
```

Supported item types:

| `item_type` | PostgreSQL type |
|-------------|-----------------|
| `str` | `TEXT[]` |
| `int` | `INTEGER[]` |
| `float` | `DOUBLE PRECISION[]` |
| `bool` | `BOOLEAN[]` |
| `uuid.UUID` | `UUID[]` |

`base_type=` was never an accepted `Array` constructor argument; some earlier
docs used it incorrectly. v0.5.55 resolves this by updating all field docs and
examples to the canonical `item_type=` form rather than introducing a
`base_type` alias. New examples should use `item_type`.

### Value Contract

- The stored Python value is a `list`.
- `None` means SQL `NULL` and is allowed only when the field is nullable.
- An empty list means an empty PostgreSQL array, not `NULL`.
- Array items must match the configured `item_type`.
- `None` items are not supported in v0.5.55. Use `JSON` if null elements are
  required.
- Nested lists/tuples are not supported in v0.5.55. Use `JSON` for nested or
  heterogeneous structures.

### Type Validation

Recommended validation:

| Item type | Accepted values |
|-----------|-----------------|
| `str` | strings only |
| `int` | integers, excluding `bool`; non-integral floats rejected |
| `float` | finite `int`/`float` values, excluding `bool` |
| `bool` | strict boolean values; string parsing should match `Boolean` field policy only if explicitly supported |
| `uuid.UUID` | UUID instances or parseable UUID strings |

Direct ORM assignment should prefer explicit Python lists. If string input is
kept for admin/form compatibility, conversion should happen at the adapter
boundary, not by silently treating arbitrary strings as arrays in core ORM
validation.

### Nested Arrays

Nested PostgreSQL arrays are deferred. `Array(item_type=list)`,
`Array(item_type=Array(...))`, and values such as `[["a"], ["b"]]` should raise
a clear error:

```text
Nested Array fields are not supported yet; use JSON for nested lists.
```

### Compatibility Impact

Potential v0.5.55 behavior changes:

- Code assigning comma-separated strings directly to `Array` fields may need to
  assign lists instead.
- Code relying on null array elements will need `JSON`.
- Code relying on undocumented nested arrays will fail clearly.
- If `base_type=` is accepted as an alias, it should be documented as
  compatibility-only and `item_type` should remain canonical.

---

## Vector Policy

`Vector` stores embedding values through PostgreSQL `pgvector`.

### Value Contract

- The stored Python value is `list[float]`.
- Values must be finite numbers.
- `NaN`, `Infinity`, and `-Infinity` are invalid everywhere.
- `bool` is not a valid vector item, even though Python treats it as an integer
  subclass.
- `None` means SQL `NULL` and is allowed only when the field is nullable.
- Empty vectors should be rejected. A vector must have at least one dimension.
- If `dimensions` is set, every write path must enforce that exact length.

This policy applies consistently to:

- `create()`
- `save()`
- `bulk_create()`
- `QuerySet.update()`
- `bulk_update()`
- `upsert()`
- expression/vector-distance helpers
- migration defaults
- asyncpg vector codecs

### Precision Contract

Python exposes vector items as `float`. PostgreSQL `pgvector` stores vector
items with its own floating-point precision, so exact decimal round-tripping is
not guaranteed.

Aksara should not reduce precision before handing values to PostgreSQL. Runtime
serialization should use a high-precision representation such as `repr(float)`
or an equivalent format, rather than a short six-significant-digit format.

Tests should compare persisted vector values with tolerance when precision is
the subject under test.

### Compatibility Impact

Potential v0.5.55 behavior changes:

- Existing code that passes `NaN`, infinities, booleans, or empty vectors should
  now fail before SQL execution.
- Stored/retrieved vector string representations may show more precision than
  older output.
- Tests that expected exact string formatting for vectors may need to compare
  numeric values instead.

---

## FileField and ImageField Policy

`FileField` and `ImageField` store storage-relative path strings in PostgreSQL.
Model attribute access returns a wrapper object for convenience.

### Storage Contract

Internal model state and database rows store only:

- a normalized storage-relative path string, or
- `None` for nullable/empty values.

`to_python()` should normalize database values to that scalar path string. It
should not return a wrapper.

`to_db()` should accept only a prepared path string, a `FieldFile` wrapper, or
`None`. Upload-like objects must be prepared before database writes.

### Model Attribute Contract

On model instances:

```python
document.attachment.name
document.attachment.url
await document.attachment.read()
```

The public model attribute returns a `FieldFile` wrapper. The raw path is
available as `document.attachment.name` or `str(document.attachment)`.

Assigning a `FieldFile` stores its `.name`. Assigning upload-like values is
allowed only through write paths that run `async_prepare()`, such as `save()`,
`create()`, and `bulk_create()`.

`QuerySet.update()` and `bulk_update()` should reject unresolved upload-like
objects with a clear error because those paths cannot safely persist file
content.

### ImageField Contract

`ImageField` has the same storage and wrapper contract as `FileField`.
Additionally:

- upload-like values are validated with Pillow before storage;
- stored path strings are not re-opened or revalidated on every model load;
- extension checks are filename checks and image validation is content-based.

### API and Serializer Contract

Generated API schemas should expose file and image fields as strings or
nullable strings. They should not expose `FieldFile` as a transport type.

### Compatibility Impact

Potential v0.5.55 behavior changes:

- Code comparing `model.file == "path"` should use `model.file.name` or
  `str(model.file)`.
- Direct update paths that pass upload-like objects should fail clearly.
- File/image schema output remains string-based, so API clients should not need
  wrapper-specific changes.

---

## JSON Policy

`JSON` maps to PostgreSQL `JSONB`.

### Value Contract

Aksara should support all JSON-compatible values:

- objects: `dict[str, JSONValue]`
- arrays: `list[JSONValue]`
- strings
- numbers
- booleans
- nested `None` values inside objects/arrays

Top-level `None` means SQL `NULL`, not JSON `null`. A distinct top-level JSON
`null` value is deferred unless Aksara introduces an explicit sentinel.

Non-JSON Python objects should raise clear validation errors. Non-finite floats
must be rejected because JSON does not portably represent `NaN` or infinity.

### Serialization Contract

Every non-`None` value should be serialized with `json.dumps(...,
allow_nan=False)` or equivalent validation before database writes. This must
apply to dicts, lists, and top-level scalars.

Examples:

| Python value | Stored JSONB meaning |
|--------------|----------------------|
| `{"a": 1}` | JSON object |
| `[1, 2]` | JSON array |
| `"draft"` | JSON string |
| `3.14` | JSON number |
| `True` | JSON boolean |
| `None` | SQL `NULL` |

### Schema Contract

Generated schemas should describe JSON fields as a recursive JSON value, not
only `dict | list`. If the runtime type system cannot express recursive JSON
cleanly, documentation should still state that scalars are accepted.

### Query Contract

Nested path filters remain intended for JSON objects and arrays:

```python
await User.objects.filter(metadata__preferences__theme="dark").all()
```

Top-level scalar JSON fields should support direct equality where PostgreSQL can
represent it safely. Path lookups on scalar values should return no match or
raise a clear validation error; they should not silently reinterpret scalar
values as objects.

### Compatibility Impact

Potential v0.5.55 behavior changes:

- Top-level scalar JSON values should become consistently supported.
- Non-JSON-serializable values should fail earlier.
- `NaN` and infinity in JSON payloads should fail before SQL execution.
- API schemas may broaden from object/array-only to full JSON values.

---

## Deferred Items

The following relation features should stay out of the v0.5.55 advanced field
policy implementation.

### Lazy Forward FK Object Loading

Deferred.

Current contract remains:

- `post.author` exposes the stored FK id.
- `post.author_id` exposes the same stored FK id.
- Related objects should be loaded explicitly:

```python
author = await Author.objects.get(id=post.author_id)
```

or eagerly:

```python
posts = await Post.objects.select_related("author").all()
author = posts[0].get_related("author")
```

Lazy object loading would need a separate relation-loading contract, async
attribute design, caching behavior, and N+1 query policy.

### Custom ManyToMany Through Models

Deferred.

`ManyToMany(..., through=...)` should continue to fail clearly while unsupported.
Custom through support requires a separate design for join model registration,
extra fields, migrations, manager APIs, serializers, admin behavior, and delete
semantics.

---

## Recommended v0.5.55 Scope

Implement the field-policy pieces only:

- Add shared validation helpers for `Array`, `Vector`, and `JSON`.
- Make all write paths use the same validation and serialization behavior.
- Add explicit errors for nested arrays, null array items, invalid vector
  values, unresolved file uploads in update-only paths, and invalid JSON values.
- Align generated API/Pydantic schema typing with the field contracts.
- Update field docs and examples to use canonical constructor options.
- Add unit and DB-backed regression tests for every compatibility point above.

Keep these out of v0.5.55:

- lazy FK object loading;
- custom many-to-many through models;
- storage backend redesign;
- multidimensional PostgreSQL arrays;
- a top-level JSON null sentinel, unless it receives a separate design.

## Candidate review clarifications

Generated CRUD schemas and `ModelSerializer` both apply advanced input validation
before Pydantic coercion. In particular, `true` is not an integer Array item or a
Vector component. JSON scalar API values retain their type. Array defaults use
this same policy: empty strings remain empty strings, quotes and UUIDs survive
DDL round trips, and invalid defaults fail before DDL. Unknown `item_type` values
are not silently mapped to `TEXT[]`.

Vector dimensions must be positive integers or `None`; boolean dimensions are
invalid. File/image stored paths must be strings or supported path objects at
normalization boundaries, and cannot contain parent traversal or null bytes.
These stricter checks may reject previously accepted ambiguous inputs.
