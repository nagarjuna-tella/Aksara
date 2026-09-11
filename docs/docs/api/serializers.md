# Model serializers

`ModelSerializer` derives input validation and output representation from an
Aksara model. It is useful for selecting fields and adding application
validation. It does not authenticate callers, establish tenant membership, or
make arbitrary ORM writes pass through the generated API policy boundary.

The [ticket-desk tutorial](../tutorials/ticket-desk.md) supplies a complete
serializer, model, migration, ViewSet wiring, and HTTP validation tests.

## Select fields explicitly

For the tutorial's Ticket model, save this as `app/serializers.py`:

```python title="app/serializers.py"
from aksara.api.serializers import ModelSerializer
from aksara.exceptions import ValidationError
from .models import Ticket


class TicketCreateSerializer(ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["id", "subject", "description", "resolved"]
        read_only_fields = ["id", "resolved"]

    def validate_subject(self, value):
        subject = value.strip()
        if not subject:
            raise ValidationError(
                "Invalid ticket subject",
                errors={"subject": "A visible subject is required"},
            )
        return subject
```

Set `create_serializer_class = TicketCreateSerializer` on the ViewSet. There is
no generic `serializer_class` switch on `ModelViewSet`; use the list, retrieve,
create, or update-specific attribute for the operation you are customizing.

## Validation and persistence

Construct a serializer with `data=...`, call synchronous `is_valid()`, inspect
`validated_data`, then `await serializer.save()` when persistence is intended.
For existing records, pass `instance=...`. The database must be connected and
migrations applied before saving. For reads, `.data` or `to_representation()`
returns the selected representation.

Validation first uses the generated Pydantic input model, then synchronous
`validate_<field>(value)` hooks, then synchronous `validate(data)`. Return the
normalized value or dictionary from each hook. Do not make these hooks async.

`is_valid()` catches Pydantic validation errors and `ValueError`; with
`raise_exception=True` it re-raises them. Aksara's separate `ValidationError`,
used above for structured application errors, propagates to the generated
router's HTTP 422 mapping. Do not assume every exception becomes a false return
or that a plain application `ValueError` has the same HTTP response contract.

## Supported configuration

| Setting | Meaning |
|---|---|
| `Meta.model` | Required Aksara model |
| `Meta.fields` | Explicit field list or `"__all__"` |
| `Meta.exclude` | Exclude selected model fields |
| `Meta.read_only_fields` | Omit fields from generated input validation |
| `Meta.expand` | Explicit relationship representation configuration |
| `context` constructor argument | Application context; generated ViewSets supply a request context |
| `many=True` | Validate/represent multiple items; not a bulk-transaction guarantee |

`Meta.write_only_fields` is **not implemented** in 0.7.0. Do not rely on it to
hide passwords or other secrets from output. Use an explicit output field list
or a dedicated response serializer and verify the actual response. Input-only
secret handling often belongs in an application service, such as the
[account creation helper](authentication.md), rather than a raw user serializer.

Read-only input fields are omitted from the serializer's input model; this does
not mean every extra client key is rejected. Generated HTTP/MCP execution adds
its own field-write enforcement. A direct serializer caller must not treat
successful validation as an authorization decision.

## Partial updates need special care

The constructor accepts `instance`, `data`, `many`, and `context`. It does not
accept a DRF-style `partial=True` argument. Input validation uses the serializer's
full field requirements and dumps defaults into validated data. The default
update method skips `None` values, so it is not a general “clear this nullable
field” implementation either.

For ordinary PATCH behavior, retain the generated update schema and validate
only explicitly supplied fields, as the
[ticket-desk update example](../tutorials/ticket-desk.md) does. If you introduce an
update serializer, define and test omitted-field, default, null, and relationship
replacement behavior explicitly. Do not reuse a create serializer and assume
partial-update semantics.

## Relationships and custom representation

Foreign keys use their stored identifier names in input, such as
`assigned_to_id`. `Meta.expand` can request related output; ensure the relation
is loaded through your query strategy. It does not promise automatic async
queries during synchronous representation.

DRF-style `SerializerMethodField`, `Field(source=...)`, and nested serializer
attributes are not the declaration API shown by this implementation. Use the
supported model fields/expansion or override `to_representation()` explicitly.
The generated ViewSet response schema must also agree with the output; adding
a dictionary key alone does not publish a new OpenAPI contract.

Saving multiple items or replacing relationships can perform several database
operations. Use an explicit transaction when they must be atomic, and validate
related-object tenant ownership before saving. Follow the
[tenant-isolation tutorial](../tutorials/ticket-desk-tenancy.md) rather than
assuming a foreign-key constraint proves authorization.
