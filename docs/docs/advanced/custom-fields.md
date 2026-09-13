# Application-specific fields

**Evolving extension surface.** Prefer a built-in field plus explicit application
validation when it expresses your requirement. If you need reusable conversion,
subclass a compatible built-in field and test every persistence path you use.
A working subclass does not automatically establish support for a new PostgreSQL
type, migration reconstruction, Admin widget, serializer, or SDK type.

The [field reference](../orm/fields.md) covers existing types, including Slug,
Enum, Decimal, Array, File and Image. Reimplementing these in a custom field can
lose validation and database conversion already supplied by Aksara.

## A reusable ticket code

Save this as `app/fields.py`. It stores a normalized ASCII code in a VARCHAR
column and inherits the built-in string field's length and choice checks.

```python title="app/fields.py"
import re

from aksara import fields


class TicketCode(fields.String):
    def __init__(self, max_length=24, **kwargs):
        super().__init__(max_length=max_length, **kwargs)

    def to_db(self, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Ticket code must be a string")
        code = value.strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9-]*", code):
            raise ValueError("Ticket code must start with a letter and use ASCII letters, digits or hyphens")
        return super().to_db(code)

    def to_python(self, value):
        return self.to_db(value)

    async def async_prepare(self, value, *, instance=None):
        return self.to_db(value)
```

The `None` branch preserves database NULL conversion; the model's non-nullable
check and the database constraint decide whether NULL is allowed. A field
conversion call by itself is not a complete model validation pass.

Use it in a separate application model:

```python title="app/models.py"
from aksara import Model
from .fields import TicketCode


class TicketReference(Model):
    code = TicketCode(unique=True)

    class Meta:
        table_name = "ticket_references"
```

Import the model in your application's model-discovery path, generate and review
its migration, then apply it before persistence. `unique=True` describes a
constraint; model declaration alone does not install it. The normalized key
makes inputs such as `" help-12 "` and `"HELP-12"` conflict once the unique
constraint exists. This example does not generate codes or retry collisions.

## The actual field hooks

| Hook | Contract |
|---|---|
| `sql_type` property | PostgreSQL type string; abstract on `Field`, inherited as `VARCHAR(max_length)` here |
| `to_db(value)` | Synchronous conversion for database parameters; called by multiple write paths |
| `to_python(value)` | Synchronous conversion when loading database values |
| `async_prepare(value, *, instance=None)` | Async preparation on save/create and bulk-create paths; returns the value to store on the instance |
| `get_default_value()` | Gets or calls a default; built-in handling copies mutable defaults |
| `validate(value)` when supplied | Optional field validation; model validation calls it but does not assign its return value back to the instance |

The base field accepts `nullable`, not `null`. It has no `from_db()`,
`get_db_type()`, `get_default()`, `contribute_to_class()`, or `deconstruct()`
contract. A Python method with one of those names will not become an ORM hook
merely because it appears on your subclass. Do not use `Field[T]` as though the
runtime base class were a generic field API.

The example repeats normalization in `to_db()` and `async_prepare()` on purpose:
preparation updates the in-memory value during save, while direct update and
upsert paths still need conversion. Conversion should be deterministic and safe
to call more than once. Keep network calls and irreversible side effects out of
these synchronous conversion methods.

## Validation boundaries

Aksara model validation catches `ValueError` from a field and aggregates it into
`aksara.exceptions.ValidationError`. Direct calls to this example's `to_db()`
raise `ValueError`. They do not require a database connection.

The `async_prepare()` hook can fail before model validation aggregates errors;
do not assume every invalid input on every write path has the same exception
class. Test the exact path and map application errors at your public boundary.

A generated API may validate an input through its Pydantic model before ORM
conversion, and a serializer may have additional rules. A custom conversion
method does not automatically become a public input schema constraint. Use an
explicit serializer hook when API validation must expose the same rule and
verify both HTTP responses and stored values.

`bulk_update()` and `upsert()` do not run full save preparation. The text-only
conversion here can be used by those paths. `bulk_update()` casts converted
values to each field's declared PostgreSQL type; custom fields must therefore
return values compatible with their `sql_type`. See
[field typing in bulk updates](../orm/bulk-operations.md#field-typing-in-bulk-updates).
Upsert callers must also supply required insertion values such as `updated_at`;
an `auto_now` model field does not make that timestamp an automatic database
default. See the bulk/upsert guide for the complete insertion contract.
Database raw SQL can bypass Python conversion entirely, so put required
cross-client invariants in database constraints too.

## Migrations and compatibility

Aksara's migrations describe database schema changes; they do not use Django's
field `deconstruct()` protocol. Keeping this example on an existing VARCHAR
representation avoids introducing a new database codec. Review generated SQL,
constraints and defaults, and test the migration against PostgreSQL. Changing a
normalization rule can change uniqueness behavior without changing SQL type;
plan and validate existing-data conversion separately.

Custom encrypted, money and array examples require more than conversion methods.
Key rotation, exact numeric representation, array escaping, filtering and schema
compatibility need their own contracts. Use supported built-ins where possible;
Aksara does not supply an `ENCRYPTION_KEY` setting or a generic encrypted-field
recipe here.

## What to verify

Test valid and invalid conversion, nullable behavior, maximum length, model
save/reload, uniqueness after normalization, and the direct update, bulk and
upsert paths your application uses. Also test migration output and API input/
output separately; direct field tests do not prove either one. See
[application testing](testing.md) for fixture ownership and real PostgreSQL
integration guidance.
