"""
Tests for the v0.5.55 Advanced Field Policy.

Covers JSON scalar support and allow_nan validation, Vector finite/bool/empty
validation plus high-precision serialization, and the FileField/ImageField
path-vs-wrapper contract (including update/bulk_update upload rejection).

DB-backed round-trip tests run only when DATABASE_URL is set.
"""

from __future__ import annotations

import math
import os
import uuid as uuid_lib

import pytest

from aksara import Model, fields
from aksara.db.engine import Database, _decode_vector, _encode_vector
from aksara.fields import (
    Array,
    FieldFile,
    FileField,
    JSON,
    Vector,
    serialize_vector_components,
    validate_vector_components,
)
from aksara.registry import ModelRegistry


pytestmark_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set"
)


# ---------------------------------------------------------------------------
# JSON policy (unit)
# ---------------------------------------------------------------------------


class TestJSONPolicy:
    def test_object_round_trips(self):
        field = JSON()
        stored = field.to_db({"a": None, "b": 1})
        assert field.to_python(stored) == {"a": None, "b": 1}

    def test_array_with_mixed_items(self):
        field = JSON()
        stored = field.to_db(["x", 1, True, None])
        assert field.to_python(stored) == ["x", 1, True, None]

    def test_top_level_string_scalar(self):
        field = JSON()
        stored = field.to_db("draft")
        assert stored == '"draft"'
        assert field.to_python(stored) == "draft"

    def test_top_level_number_scalar(self):
        field = JSON()
        stored = field.to_db(3.14)
        assert field.to_python(stored) == 3.14

    def test_top_level_bool_scalar(self):
        field = JSON()
        assert field.to_db(True) == "true"
        assert field.to_python(field.to_db(True)) is True

    def test_top_level_none_is_sql_null(self):
        field = JSON()
        assert field.to_db(None) is None

    def test_nan_rejected(self):
        field = JSON()
        with pytest.raises(ValueError, match="non-finite"):
            field.to_db(float("nan"))

    def test_infinity_rejected(self):
        field = JSON()
        with pytest.raises(ValueError, match="non-finite"):
            field.to_db(float("inf"))

    def test_nested_nan_rejected(self):
        field = JSON()
        with pytest.raises(ValueError, match="non-finite"):
            field.to_db({"score": float("nan")})

    def test_non_serializable_rejected(self):
        field = JSON()
        with pytest.raises(ValueError, match="not JSON-serializable"):
            field.to_db(object())


# ---------------------------------------------------------------------------
# Vector policy (unit)
# ---------------------------------------------------------------------------


class TestVectorPolicy:
    def test_high_precision_not_truncated(self):
        field = Vector()
        assert field.to_db([0.123456789]) == "[0.123456789]"

    def test_serialize_helper_matches_codec(self):
        values = [0.123456789, 1.5, 2.0]
        assert serialize_vector_components(values) == _encode_vector(values)

    def test_codec_round_trip_precision(self):
        values = [0.123456789, 0.987654321]
        encoded = _encode_vector(values)
        decoded = _decode_vector(encoded)
        for original, restored in zip(values, decoded):
            assert math.isclose(original, restored, rel_tol=1e-12)

    def test_nan_rejected(self):
        field = Vector()
        with pytest.raises(ValueError, match="finite"):
            field.to_db([float("nan")])

    def test_inf_rejected(self):
        field = Vector()
        with pytest.raises(ValueError, match="finite"):
            field.to_db([1.0, float("inf")])

    def test_negative_inf_rejected(self):
        field = Vector()
        with pytest.raises(ValueError, match="finite"):
            field.to_db([float("-inf")])

    def test_bool_item_rejected(self):
        field = Vector()
        with pytest.raises(ValueError, match="boolean"):
            field.to_db([True, False])

    def test_empty_vector_rejected(self):
        field = Vector()
        with pytest.raises(ValueError, match="at least one dimension"):
            field.to_db([])

    def test_dimension_mismatch_rejected(self):
        field = Vector(dimensions=3)
        field.name = "embedding"
        with pytest.raises(ValueError, match="requires 3 dimensions"):
            field.to_db([1.0, 2.0])

    def test_none_when_nullable(self):
        field = Vector(nullable=True)
        assert field.to_db(None) is None


class TestVectorCodecValidation:
    """The asyncpg codec must validate, not only serialize (Issue 5)."""

    def test_codec_rejects_bool(self):
        with pytest.raises(ValueError, match="boolean"):
            _encode_vector([True])

    def test_codec_rejects_nan(self):
        with pytest.raises(ValueError, match="finite"):
            _encode_vector([float("nan")])

    def test_codec_rejects_inf(self):
        with pytest.raises(ValueError, match="finite"):
            _encode_vector([float("inf")])

    def test_codec_rejects_negative_inf(self):
        with pytest.raises(ValueError, match="finite"):
            _encode_vector([float("-inf")])

    def test_codec_rejects_empty(self):
        with pytest.raises(ValueError, match="at least one dimension"):
            _encode_vector([])

    def test_codec_high_precision(self):
        assert _encode_vector([0.123456789]) == "[0.123456789]"

    def test_codec_passes_through_serialized_string(self):
        # Already-serialized strings (from Vector.to_db) pass through unchanged.
        assert _encode_vector("[1.0,2.0]") == "[1.0,2.0]"

    def test_validate_helper_rejects_bool(self):
        with pytest.raises(ValueError, match="boolean"):
            validate_vector_components([True])

    def test_validate_helper_enforces_dimensions(self):
        with pytest.raises(ValueError, match="requires 2 dimensions"):
            validate_vector_components([1.0], dimensions=2)


class TestJSONDefaultPolicy:
    """Invalid JSON defaults must raise, not become DEFAULT NULL (Issue 2)."""

    def test_valid_object_default(self):
        field = JSON(default={"a": 1})
        field.name = "meta"
        sql = field._format_default()
        assert sql == '\'{"a": 1}\'::jsonb'

    def test_valid_array_with_nested_null_default(self):
        field = JSON(default=["a", None])
        field.name = "meta"
        sql = field._format_default()
        assert sql == '\'["a", null]\'::jsonb'

    def test_none_default_is_sql_null(self):
        field = JSON(default=None)
        assert field._format_default() == "NULL"

    def test_nan_default_raises(self):
        field = JSON(default=float("nan"))
        field.name = "meta"
        with pytest.raises(ValueError, match="non-finite"):
            field._format_default()

    def test_infinity_default_raises(self):
        field = JSON(default={"x": float("inf")})
        field.name = "meta"
        with pytest.raises(ValueError, match="non-finite"):
            field._format_default()

    def test_non_serializable_default_raises(self):
        field = JSON(default=object())
        field.name = "meta"
        with pytest.raises(ValueError, match="not JSON-serializable"):
            field._format_default()


# ---------------------------------------------------------------------------
# FileField / ImageField policy (unit)
# ---------------------------------------------------------------------------


class _DocModel(Model):
    file = FileField(upload_to="documents", nullable=True)

    class Meta:
        table_name = "advanced_policy_docs"


class TestFileFieldPolicy:
    def test_to_python_returns_normalized_string(self):
        field = FileField()
        assert field.to_python("docs/a.txt") == "docs/a.txt"
        assert field.to_python("\\docs\\a.txt") == "docs/a.txt"

    def test_to_python_returns_str_not_wrapper(self):
        field = FileField()
        result = field.to_python("docs/a.txt")
        assert isinstance(result, str)
        assert not isinstance(result, FieldFile)

    def test_model_attribute_returns_wrapper(self):
        doc = _DocModel(file="docs/a.txt")
        assert isinstance(doc.file, FieldFile)
        assert doc.file.name == "docs/a.txt"
        assert str(doc.file) == "docs/a.txt"

    def test_to_db_accepts_path_string(self):
        field = FileField()
        assert field.to_db("docs/a.txt") == "docs/a.txt"

    def test_to_db_accepts_field_file(self):
        field = FileField()
        wrapper = FieldFile(instance=None, field=field, name="docs/a.txt")
        assert field.to_db(wrapper) == "docs/a.txt"

    def test_to_db_accepts_none(self):
        field = FileField(nullable=True)
        assert field.to_db(None) is None

    def test_to_db_rejects_upload_tuple(self):
        field = FileField()
        field.name = "file"
        with pytest.raises(ValueError, match="unresolved upload-like"):
            field.to_db(("report.txt", b"data"))

    def test_to_db_rejects_bytes(self):
        field = FileField()
        field.name = "file"
        with pytest.raises(ValueError, match="unresolved upload-like"):
            field.to_db(b"raw-bytes")

    @pytest.mark.asyncio
    async def test_queryset_update_rejects_upload(self):
        # update() builds SET clauses (via to_db) before any DB call, so an
        # unresolved upload raises a clear error pre-execution.
        with pytest.raises(ValueError, match="unresolved upload-like"):
            await _DocModel.objects.filter(id=uuid_lib.uuid4()).update(
                file=("report.txt", b"data")
            )

    @pytestmark_db
    @pytest.mark.asyncio
    async def test_bulk_update_rejects_upload(self, db):
        # bulk_update acquires the DB instance up front, but still rejects the
        # unresolved upload via to_db before any statement executes.
        doc = _DocModel(file="docs/a.txt")
        doc._is_new = False
        doc._data["id"] = uuid_lib.uuid4()
        doc._data["file"] = ("report.txt", b"data")
        with pytest.raises(ValueError, match="unresolved upload-like"):
            await _DocModel.objects.bulk_update([doc], ["file"])


# ---------------------------------------------------------------------------
# DB-backed round trips
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    ModelRegistry.clear()
    database = Database(os.environ["DATABASE_URL"])
    await database.connect()
    yield database
    for table in ("afp_json_records", "afp_array_records", "afp_vector_records"):
        try:
            await database.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        except Exception:
            pass
    await database.disconnect()
    ModelRegistry.clear()


@pytestmark_db
class TestJSONDatabaseRoundTrip:
    @pytest.mark.asyncio
    async def test_scalar_and_container_round_trips(self, db):
        class JsonRecord(Model):
            title = fields.String(max_length=100)
            payload = fields.JSON(nullable=True)

            class Meta:
                table_name = "afp_json_records"

        await db.execute(JsonRecord.get_create_table_sql())

        cases = [
            {"a": 1, "b": None},
            ["x", 1, True, None],
            "draft",
            3.14,
            True,
        ]
        for index, value in enumerate(cases):
            created = await JsonRecord.objects.create(title=f"row-{index}", payload=value)
            fetched = await JsonRecord.objects.get(id=created.id)
            assert fetched.payload == value

        # Top-level None stores SQL NULL.
        created = await JsonRecord.objects.create(title="null-row", payload=None)
        fetched = await JsonRecord.objects.get(id=created.id)
        assert fetched.payload is None


@pytestmark_db
class TestArrayDatabaseRoundTrip:
    @pytest.mark.asyncio
    async def test_typed_arrays_round_trip(self, db):
        class ArrayRecord(Model):
            tags = fields.Array(item_type=str, default=list)
            scores = fields.Array(item_type=int, default=list)
            flags = fields.Array(item_type=bool, default=list)
            ids = fields.Array(item_type=uuid_lib.UUID, default=list)

            class Meta:
                table_name = "afp_array_records"

        await db.execute(ArrayRecord.get_create_table_sql())

        identifier = uuid_lib.uuid4()
        created = await ArrayRecord.objects.create(
            tags=["a", "b"],
            scores=[1, 2, 3],
            flags=[True, False],
            ids=[identifier],
        )
        fetched = await ArrayRecord.objects.get(id=created.id)
        assert fetched.tags == ["a", "b"]
        assert fetched.scores == [1, 2, 3]
        assert fetched.flags == [True, False]
        assert fetched.ids == [identifier]


@pytestmark_db
class TestVectorDatabaseRoundTrip:
    @pytest.mark.asyncio
    async def test_precision_better_than_six_significant_digits(self, db):
        extension_available = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
        )
        if not extension_available:
            pytest.skip("pgvector extension is not available")
        await db.execute("CREATE EXTENSION IF NOT EXISTS vector")

        class VectorRecord(Model):
            embedding = fields.Vector(dimensions=2)

            class Meta:
                table_name = "afp_vector_records"

        await db.execute(VectorRecord.get_create_table_sql())

        original = [0.123456789, 0.987654321]
        created = await VectorRecord.objects.create(embedding=original)
        fetched = await VectorRecord.objects.get(id=created.id)

        # Old six-significant-digit formatting would have truncated to
        # 0.123457 / 0.987654; pgvector stores float4 precision (~1e-7).
        for original_value, restored in zip(original, fetched.embedding):
            assert abs(original_value - restored) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
