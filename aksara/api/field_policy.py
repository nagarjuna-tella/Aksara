"""Advanced ORM field validation shared by generated API input schemas."""

from typing import Annotated, Any

from pydantic import BeforeValidator

from aksara import fields


def advanced_input_type(field: fields.Field, python_type: Any) -> Any:
    """Validate raw input before Pydantic can lose bool/numeric distinctions."""
    if not isinstance(
        field, (fields.Array, fields.Vector, fields.JSON, fields.FileField)
    ):
        return python_type

    def validate(value: Any) -> Any:
        if value is None:
            if not field.nullable:
                raise ValueError(f"Field '{field.name}' cannot be null")
            return None
        if isinstance(field, fields.Vector):
            return field.validate(value)
        if isinstance(field, fields.JSON):
            field.to_db(value)  # Validate serializability without encoding API data.
            return value
        return field.to_db(value)

    return Annotated[python_type, BeforeValidator(validate)]
