# Validation

Validation checks whether input is acceptable. It is separate from deciding
who may write, which tenant owns a record, and whether concurrent writes can
violate an invariant.

## Choose the validation boundary

| Requirement | Supported approach | Limit |
| --- | --- | --- |
| Field shape, size, or range | Type-specific [field options](../orm/fields.md) | Constructor options differ by field type. |
| Normalize API input or compare supplied fields | Synchronous [ModelSerializer hooks](../api/serializers.md) | Not a hook for asynchronous database queries. |
| Check a related row's tenant or ownership | Explicit application checks in the write path | Validation must use current trusted identity and tenant context. |
| Keep an invariant true under concurrent writes | PostgreSQL constraints and appropriate transactions/locking | A prior lookup alone cannot prevent a race. |
| Normalize an individual model save | An explicit save override or [pre_save receiver](../orm/signals.md) | Does not automatically cover queryset, bulk, or raw writes. |

## Field-level validation

Use supported constructor parameters such as `String(max_length=...)`,
`String(min_length=...)`, `String(regex=...)`, and
`Integer(min_value=..., max_value=...)`. `String`, `Integer`, and supported
integer variants also accept `choices`. These options are not universal
base-field parameters. Use `nullable=True`, not `null=True`.

There is no general `aksara.validation.Validator` API or universal
`validators=[...]`/`error_messages={...}` field contract. A constructor accepting
an option on one field does not establish support on other types.

Individual `Model.save()` prepares and validates fields before writing.
Bulk operations and queryset writes have their own behavior; see
[bulk operations](../orm/bulk-operations.md). Database constraints remain
necessary for rules that must hold across every write path.

## Serializer hooks

Define synchronous `validate_<field>(value)` methods and
`validate(data)`. Return the normalized value or dictionary. Do not use
`async def` for these hooks: the serializer does not await them.
The [serializer guide](../api/serializers.md) provides an executable
TicketCreateSerializer, including blank-subject rejection and error behavior.

For partial updates, distinguish absent fields from supplied values and from
explicit `None`. `ModelSerializer(partial=True)` is not supported. The
[ticket desk tutorial](../tutorials/ticket-desk.md) demonstrates custom validation
on the generated PATCH path without assuming a DRF serializer contract.

Reusable normalization can be an ordinary Python function called explicitly
from a hook. It does not need a framework decorator or base validator class.
Keep database I/O in an explicit async application operation, outside the
synchronous validation hook.

## Cross-field and database-dependent checks

A method named `clean()` is not automatically invoked by the base Model.
If an application defines one, it must call it explicitly in each relevant
write path. Overriding `save()` only covers callers that use that method.

For database-dependent rules, first validate input shape, then resolve related
records and authorize the operation on the server. Perform the mutation inside
the transaction or locking boundary required by the invariant. The
[tenant chapter](../tutorials/ticket-desk-tenancy.md) checks that a related Agent
belongs to the same tenant as the Ticket; a client-supplied identifier does not
prove that relationship.

A uniqueness lookup can give a helpful early error, but another writer may
insert before the current write. Apply a unique constraint through migrations
and handle its database error. Likewise, reading an object's current status
before validation does not make a state transition atomic with a later save.

## Validation errors

Use the actual error type for the layer being handled. Aksara's
`aksara.exceptions.ValidationError` supports field errors, while Pydantic
validation errors follow Pydantic's contract. `ModelSerializer.is_valid()` is
synchronous; custom Aksara validation errors may propagate rather than being
converted to a false result. The [serializer reference](../api/serializers.md)
explains this distinction and the generated HTTP 422 path.

Custom FastAPI handlers must explicitly map their errors and enforce
permissions. Returning `(body, 400)` does not set an HTTP status under the
framework's response contract. See [custom actions](../api/actions.md) before
adding a write endpoint.

## Test the rule where it matters

Test accepted and rejected inputs through the actual entry point: a direct
validator unit test alone does not prove a ViewSet calls it. Include omitted
fields, explicit nulls, another tenant's identifiers, and concurrent writes
when those cases affect the invariant. Keep authentication, permissions, and
field-write policy tests alongside validation tests; valid data can still be
unauthorized.
