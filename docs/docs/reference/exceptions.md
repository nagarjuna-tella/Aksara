# Exceptions and error responses

Aksara has several error boundaries: ORM/database exceptions, query lookup
exceptions, Python/Pydantic validation, and HTTP errors. They do not share one
universal base class or response shape. Catch the specific error that your
operation can produce, and preserve unexpected failures.

## ORM exception families

These classes are in `aksara.exceptions`:

| Class | Base | Purpose / useful attributes |
| --- | --- | --- |
| `AksaraError` | `Exception` | Base for this module's ORM/configuration family; `message` |
| `ConfigurationError` | `AksaraError` | Invalid configuration |
| `ImproperlyConfigured` | `ConfigurationError` | Feature configuration error |
| `DatabaseError` | `AksaraError` | Mapped database failure; `original_exception`, `query`, `params` |
| `ConnectionError` | `DatabaseError` | Pool connection failure; distinct from Python's built-in `ConnectionError` |
| `UniqueConstraintError` | `DatabaseError` | Unique violation; optional `field_name`, `value` |
| `ForeignKeyConstraintError` | `DatabaseError` | Foreign-key violation; optional `field_name`, `referenced_table` |
| `NotNullConstraintError` | `DatabaseError` | Not-null violation; optional `field_name` |
| `CheckConstraintError` | `DatabaseError` | Available class with optional `constraint_name`; see mapping limitation below |
| `QueryError` | `DatabaseError` | Available query-error class; not a promise that all SQL errors use it |
| `ValidationError` | `AksaraError` | `message`, `errors` mapping and optional `field_name` |
| `RestrictedError` | `AksaraError` | Protected deletion; `model_name`, `related_model`, `related_count` |

This is the application ORM/configuration family, not every exception exported
by experimental or durable subsystems. In particular, `aksara.manager.DoesNotExist`
and `MultipleObjectsReturned` inherit directly from `Exception`, not
`AksaraError`. There are no model-specific `User.DoesNotExist` classes to catch.

`await Model.objects.get(...)` raises `DoesNotExist` for no match and
`MultipleObjectsReturned` for multiple matches. Use unique lookup criteria.
`get_or_none(...)` currently returns the first match or `None`; it does not
assert uniqueness. See [querying](../orm/querying.md).

The module does **not** provide the legacy `IntegrityError`, `OperationalError`,
`APIException`, `NotFound`, `PermissionDenied`, `NotAuthenticated`,
`MethodNotAllowed`, `Throttled`, `MigrationError`, `ConflictingMigrations`, or
`MigrationNotFound` APIs shown in older conceptual examples.

## Database mapping

Aksara's database execute/fetch helpers wrap underlying failures through
`map_database_error()`. The mapper recognizes asyncpg unique, foreign-key,
not-null and PostgreSQL connection errors; it also has message-based fallback
matching for some constraints. Otherwise it returns `DatabaseError`.

**A PostgreSQL CHECK violation currently maps to generic `DatabaseError`, even
though `CheckConstraintError` exists.** When an application specifically needs
to distinguish it, inspect `original_exception` for the actual asyncpg
`CheckViolationError`. Do not infer a mapper branch merely from a class name.
Likewise, using a raw asyncpg connection can expose driver exceptions directly.

`DatabaseError` can retain SQL, parameters and driver messages. Do not send
`str(exc)`, `query`, `params` or an original exception to an untrusted client.
Use an application-owned public message; keep diagnostic data in appropriately
protected logs. `field_name` and similar parsed metadata can be `None` and must
not be required for recovery logic.

Catch transaction failures outside the transaction context so it can roll back.
A retry policy must account for the specific error and operation's idempotency;
catching every database error and repeating writes is not a recovery guarantee.
See [transactions](../orm/expressions-and-transactions.md).

## Validation is layer-specific

Construct Aksara validation errors using keyword `errors`, for example
`ValidationError("Invalid ticket", errors={"subject": "Required"})`. Its fields
are `message`, `errors`, and `field_name`; it has no automatic `detail` or
`status_code` attribute. Passing a dictionary positionally is not the documented
field-error constructor.

`ModelSerializer.is_valid(raise_exception=True)` is **synchronous**. Its schema
validation can raise `pydantic.ValidationError`; missing data or a hook can raise
`ValueError`; a hook may deliberately raise `aksara.exceptions.ValidationError`.
These are distinct classes. Do not assume all validation is converted to one
exception or that `except AksaraError` catches them all. Follow the
[serializer contract](../api/serializers.md) and [validation guide](../advanced/validation.md).

## HTTP handlers on Aksara

With the standard `Aksara` application, these registered ORM handlers return:

| Exception | Status | JSON fields |
| --- | --- | --- |
| `aksara.manager.DoesNotExist` | 404 | `detail` |
| `aksara.manager.MultipleObjectsReturned` | 500 | `detail` |
| `UniqueConstraintError` | 409 | `detail`, `field`, `code="unique_constraint_violated"` |
| `aksara.exceptions.ValidationError` | 422 | `detail`, `errors`, `code="validation_error"` |
| `RestrictedError` | 409 | `detail`, `model`, `related_model`, `related_count`, `code="delete_restricted"` |

These mappings belong to the app, not to the exception objects themselves.
A bare FastAPI application or custom handlers can behave differently. Generated
ViewSets also translate some failures into `fastapi.HTTPException`, so the same
underlying lookup need not produce the same body through every route.

For explicit HTTP errors use `fastapi.HTTPException(status_code=..., detail=...)`.
In standard Aksara JSON responses, HTTP errors use an `error` object containing
`status`, `message` and `type="http_exception"`. Request-schema validation also
uses an `error` object, status 422, with a validation-error list. This differs
from Aksara's ORM `ValidationError` response above.

Send `Accept: application/json` when requesting the JSON HTTP-error format.
Browser-like Accept headers can select HTML error pages. Debug configuration
also affects diagnostic output. Keep debug disabled in production and test the
actual route, middleware, exception and Accept header used by your client.
There is no universal `{detail, code}` envelope across all failures.

## Executable handler example

This small application deliberately raises sample exceptions to demonstrate
response contracts; it performs no database operation. It is a reference
example, not an error endpoint to deploy in your application.

```python title="error_examples.py"
from fastapi import HTTPException
from starlette.responses import JSONResponse
from aksara import Aksara
from aksara.exceptions import UniqueConstraintError, ValidationError
from aksara.manager import DoesNotExist

app = Aksara(database_url=None, auto_discover_views=False, debug=False)


@app.get("/validation")
async def validation_example():
    raise ValidationError("Invalid ticket", errors={"subject": "Required"})


@app.get("/conflict")
async def conflict_example():
    raise UniqueConstraintError(field_name="reference")


@app.get("/missing")
async def missing_example():
    raise DoesNotExist("Ticket not found")


@app.get("/http")
async def http_example():
    raise HTTPException(status_code=403, detail="Not permitted")


class TicketClosed(Exception):
    pass


@app.exception_handler(TicketClosed)
async def ticket_closed_handler(request, exc):
    return JSONResponse(
        status_code=409,
        content={"code": "ticket_closed", "detail": "Ticket is closed"},
    )


@app.get("/custom")
async def custom_example():
    raise TicketClosed()
```

For `/validation`, the registered handler returns status 422 and:

```json
{
  "detail": "Invalid ticket (subject: Required)",
  "errors": {"subject": "Required"},
  "code": "validation_error"
}
```

The custom handler exposes a fixed application message instead of serializing
arbitrary exception details. Register it on the actual app handling the route;
creating an exception subclass alone does not install an HTTP contract.

## Other boundaries

Migration graph/executor failures use their actual Python/driver errors; consult
the [migration guide](../orm/migrations.md) rather than importing the legacy
fictional migration classes. Preserve the original failure when reporting a
failed migration.

MCP tool failure categories and Durable Operation states have their own
structured contracts. An HTTP 409 is not a durable retry decision, and catching
a Python exception does not resolve an unknown external outcome. See
[MCP boundaries](../security/ai-mcp-boundaries.md) and
[Durable Operations](../advanced/durable-operations.md).
