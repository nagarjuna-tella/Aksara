"""Independent advanced-field release review: defaults and API boundaries."""

import os
from uuid import UUID

import asyncpg
import pytest
from pydantic import ValidationError

from aksara import Model, fields
from aksara.api.serializers import ModelSerializer


class PolicyBoundaryModel(Model):
    numbers = fields.Array(item_type=int, default=list)
    vector = fields.Vector(dimensions=2, nullable=True)
    payload = fields.JSON()
    document = fields.FileField(nullable=True)

    class Meta:
        table_name = "policy_boundary_probe"
        app_label = "policy_boundary_probe"


class PolicyBoundarySerializer(ModelSerializer):
    class Meta:
        model = PolicyBoundaryModel
        fields = ("numbers", "vector", "payload", "document")


@pytest.mark.parametrize("value", [object, dict, bytes])
def test_unsupported_array_item_types_fail_explicitly(value):
    with pytest.raises(ValueError, match="item_type"):
        fields.Array(item_type=value)


@pytest.mark.parametrize("default", [[None], [[1]], [True], [1.5], "1,2"])
def test_array_default_uses_write_validation(default):
    with pytest.raises(ValueError):
        fields.Array(item_type=int, default=default)._format_default()


@pytest.mark.parametrize("dimensions", [True, False, 0, -1, 1.5, "2"])
def test_vector_dimensions_are_positive_integers(dimensions):
    with pytest.raises(ValueError, match="dimensions"):
        fields.Vector(dimensions=dimensions)


@pytest.mark.parametrize(
    "data",
    [
        {"numbers": [True]},
        {"numbers": ["1"]},
        {"numbers": [[1]]},
        {"numbers": [None]},
        {"vector": [True, 2]},
        {"vector": [1]},
        {"vector": [float("inf"), 2]},
        {"payload": {"bad": float("nan")}},
    ],
)
def test_api_input_rejects_values_before_lossy_coercion(data):
    serializer = PolicyBoundarySerializer()
    with pytest.raises((ValidationError, ValueError)):
        serializer._input_model(**data)


@pytest.mark.parametrize(
    "payload", [{"a": None}, [1, None], "draft", 2, 2.5, True, None]
)
def test_api_json_scalar_and_nested_null_preserved(payload):
    serializer = PolicyBoundarySerializer(data={"payload": payload})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["payload"] == payload


@pytest.mark.parametrize(
    "item_type,values",
    [
        (str, ["", "O'Reilly", "NULL", "a,b", "back\\slash"]),
        (int, [0, -1, 2]),
        (float, [0.0, 1.25]),
        (bool, [True, False]),
        (UUID, [UUID("01234567-89ab-cdef-0123-456789abcdef")]),
    ],
)
async def test_array_ddl_defaults_roundtrip_in_postgres(item_type, values):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL required")
    connection = await asyncpg.connect(url)
    try:
        field = fields.Array(item_type=item_type, default=values)
        result = await connection.fetchval(
            f"SELECT {field._format_default()}::{field.sql_type}"
        )
        assert result == values
    finally:
        await connection.close()


@pytest.mark.parametrize(
    "data",
    [
        {"numbers": [True]},
        {"vector": [True, 2]},
        {"vector": [1]},
        {"payload": {"bad": float("inf")}},
    ],
)
def test_generated_create_and_update_share_advanced_policy(data):
    from aksara.api.schemas import generate_create_schema, generate_update_schema

    for schema in (
        generate_create_schema(PolicyBoundaryModel),
        generate_update_schema(PolicyBoundaryModel),
    ):
        with pytest.raises(ValidationError):
            schema(**data)


@pytest.mark.parametrize(
    "payload", ["draft", 4, 4.5, True, {"nested": None}, [None], None]
)
def test_generated_crud_json_scalars(payload):
    from aksara.api.schemas import (
        generate_create_schema,
        generate_read_schema,
        generate_update_schema,
    )

    for factory in (generate_create_schema, generate_update_schema):
        assert factory(PolicyBoundaryModel)(payload=payload).payload == payload
    assert "string" in str(
        generate_read_schema(PolicyBoundaryModel).model_json_schema()
    )


@pytest.mark.parametrize(
    "value", [object(), {}, "../outside.txt", "docs/../outside.txt", "bad\x00.txt"]
)
@pytest.mark.parametrize("field_type", [fields.FileField, fields.ImageField])
def test_file_database_values_reject_malformed_paths(field_type, value):
    with pytest.raises(ValueError):
        field_type().to_python(value)
    with pytest.raises(ValueError):
        field_type().to_db(value)


@pytest.mark.parametrize(
    "default", ["[true,2]", "[NaN,2]", "[1,2]' invalid", [], [True, 2]]
)
def test_migration_vectors_reject_invalid_defaults(default):
    from aksara.migrations.operations import VectorField

    with pytest.raises(ValueError):
        VectorField(dimensions=2, default=default).to_sql()


@pytest.mark.parametrize("value", [[None], [[1]], [True], [1.5], "1,2"])
def test_migration_integer_arrays_use_runtime_validation(value):
    from aksara.migrations.operations import ArrayField

    with pytest.raises(ValueError):
        ArrayField(sql_type="INTEGER[]", default=value).to_sql()


@pytest.mark.parametrize("value", [float("nan"), {"bad": float("inf")}, object()])
def test_migration_json_rejects_non_json_defaults(value):
    from aksara.migrations.operations import JSONField

    with pytest.raises((ValueError, TypeError)):
        JSONField(default=value).to_sql()


@pytest.mark.parametrize(
    "raw,item_type", [("[1.5]", int), ("[[1,2]]", str), ('[{"a":1}]', str)]
)
def test_admin_array_coercion_does_not_hide_invalid_values(raw, item_type):
    from aksara.contrib.admin.views import _coerce_array_form_value

    with pytest.raises(ValueError):
        field = fields.Array(item_type=item_type)
        field.to_db(_coerce_array_form_value(raw, field))


def test_mutable_advanced_defaults_are_isolated_per_model_instance():
    class Defaults(Model):
        numbers = fields.Array(item_type=int, default=[1])
        payload = fields.JSON(default={"items": []})

        class Meta:
            app_label = "policy_default_probe"

    one, two = Defaults(), Defaults()
    one.numbers.append(2)
    one.payload["items"].append("changed")
    assert two.numbers == [1]
    assert two.payload == {"items": []}
    assert Defaults._fields["payload"].default == {"items": []}
