"""Regression tests for ORM primitive field correctness."""

import os
from decimal import Decimal as D

import pytest

from aksara.fields import (
    BigInteger,
    Boolean,
    Decimal,
    Email,
    Float,
    Integer,
    PositiveBigInteger,
    PositiveInteger,
    PositiveSmallInteger,
    SmallInteger,
)


class TestIntegerStrictCoercion:
    def test_rejects_non_integral_float(self):
        with pytest.raises(ValueError):
            Integer().to_db(1.9)

    def test_rejects_non_integral_decimal(self):
        with pytest.raises(ValueError):
            Integer().to_db(D("1.2"))

    def test_rejects_bool(self):
        with pytest.raises(ValueError):
            Integer().to_db(True)

    def test_accepts_integral_float(self):
        assert Integer().to_db(1.0) == 1

    def test_accepts_integral_decimal(self):
        assert Integer().to_db(D("1.0")) == 1

    def test_accepts_integer_string(self):
        assert Integer().to_db("10") == 10

    def test_rejects_decimal_string(self):
        with pytest.raises(ValueError):
            Integer().to_db("10.5")

    def test_integer_rejects_postgresql_integer_overflow(self):
        with pytest.raises(ValueError, match="INTEGER range"):
            Integer().to_db(2147483648)

    def test_positive_integer_rejects_postgresql_integer_overflow(self):
        with pytest.raises(ValueError, match="INTEGER range"):
            PositiveInteger().to_db(2147483648)

    def test_positive_big_integer_rejects_postgresql_bigint_overflow(self):
        with pytest.raises(ValueError, match="BIGINT range"):
            PositiveBigInteger().to_db(2**63)

    def test_positive_integer_rejects_negative_after_coercion(self):
        with pytest.raises(ValueError, match="non-negative"):
            PositiveInteger().to_db("-1")

    @pytest.mark.parametrize(
        "field",
        [
            SmallInteger(),
            BigInteger(),
            PositiveSmallInteger(),
            PositiveBigInteger(),
        ],
    )
    def test_extended_integer_fields_reject_bool(self, field):
        with pytest.raises(ValueError):
            field.to_db(False)

    @pytest.mark.parametrize(
        "field",
        [
            SmallInteger(),
            BigInteger(),
            PositiveSmallInteger(),
            PositiveBigInteger(),
        ],
    )
    def test_extended_integer_fields_reject_non_integral_values(self, field):
        with pytest.raises(ValueError):
            field.to_db(D("2.5"))


class TestBooleanStrictCoercion:
    @pytest.mark.parametrize("value", ["False", "0", "no", "off", "N"])
    def test_false_strings(self, value):
        assert Boolean().to_db(value) is False

    @pytest.mark.parametrize("value", ["true", "1", "yes", "y", "on"])
    def test_true_strings(self, value):
        assert Boolean().to_db(value) is True

    @pytest.mark.parametrize("value", [True, False])
    def test_accepts_bool_directly(self, value):
        assert Boolean().to_db(value) is value

    @pytest.mark.parametrize("value, expected", [(1, True), (0, False), (1.0, True), (D("0"), False)])
    def test_accepts_numeric_one_zero_only(self, value, expected):
        assert Boolean().to_db(value) is expected

    @pytest.mark.parametrize("value", ["maybe", "truthy", "", "none", 2, -1])
    def test_rejects_ambiguous_values(self, value):
        with pytest.raises(ValueError):
            Boolean().to_db(value)


class TestDecimalPrecisionScale:
    def test_accepts_value_that_fits(self):
        value = Decimal(max_digits=5, decimal_places=2).to_db("1.23")
        assert isinstance(value, D)
        assert value == D("1.23")

    def test_rejects_too_many_fractional_digits(self):
        with pytest.raises(ValueError, match="decimal places"):
            Decimal(max_digits=5, decimal_places=2).to_db("1.234")

    def test_rejects_too_many_total_digits(self):
        with pytest.raises(ValueError):
            Decimal(max_digits=5, decimal_places=2).to_db("1234.56")

    def test_accepts_maximum_value(self):
        assert Decimal(max_digits=5, decimal_places=2).to_db("999.99") == D("999.99")

    def test_rejects_integer_digits_beyond_precision(self):
        with pytest.raises(ValueError):
            Decimal(max_digits=5, decimal_places=2).to_db("1000.00")


class TestFloatFiniteValues:
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nan_and_infinity(self, value):
        with pytest.raises(ValueError, match="finite"):
            Float().to_db(value)

    def test_rejects_nan_before_min_value_check(self):
        with pytest.raises(ValueError, match="finite"):
            Float(min_value=0).to_db(float("nan"))

    def test_preserves_min_value_validation(self):
        with pytest.raises(ValueError, match="below the minimum"):
            Float(min_value=0).to_db(-1.0)

    def test_preserves_max_value_validation(self):
        with pytest.raises(ValueError, match="exceeds the maximum"):
            Float(max_value=10).to_db(11.0)

    def test_accepts_finite_values(self):
        assert Float().to_db(1.25) == 1.25


class TestEmailLocalPartDots:
    @pytest.mark.parametrize(
        "value",
        ["a..b@example.com", ".abc@example.com", "abc.@example.com"],
    )
    def test_rejects_invalid_local_part_dots(self, value):
        with pytest.raises(ValueError, match="Invalid email format"):
            Email().to_db(value)

    @pytest.mark.parametrize("value", ["abc@example.com", "first.last@example.co"])
    def test_accepts_valid_local_part_dots(self, value):
        assert Email().to_db(value) == value


@pytest.fixture
async def primitive_db():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    from aksara.db import Database
    from aksara.registry import ModelRegistry

    ModelRegistry.clear()
    database = Database(database_url)
    await database.connect()
    for table_name in [
        "primitive_boolean_records",
        "primitive_decimal_records",
        "primitive_float_records",
    ]:
        await database.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')

    try:
        yield database
    finally:
        for table_name in [
            "primitive_boolean_records",
            "primitive_decimal_records",
            "primitive_float_records",
        ]:
            await database.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        await database.disconnect()
        ModelRegistry.clear()


class TestPrimitiveDbRoundTrip:
    @pytest.mark.asyncio
    async def test_boolean_create_save_round_trips_false_strings(self, primitive_db):
        from aksara import Model, fields

        class PrimitiveBooleanRecord(Model):
            __tablename__ = "primitive_boolean_records"

            flag = fields.Boolean()

        await primitive_db.execute(PrimitiveBooleanRecord.get_create_table_sql())

        created = await PrimitiveBooleanRecord.objects.create(flag="False")
        fetched = await PrimitiveBooleanRecord.objects.get(id=created.id)
        assert fetched.flag is False

        fetched.flag = "0"
        await fetched.save()

        refetched = await PrimitiveBooleanRecord.objects.get(id=fetched.id)
        assert refetched.flag is False

    @pytest.mark.asyncio
    async def test_decimal_invalid_scale_rejected_before_db_rounding(self, primitive_db):
        from aksara import Model, fields
        from aksara.exceptions import ValidationError

        class PrimitiveDecimalRecord(Model):
            __tablename__ = "primitive_decimal_records"

            amount = fields.Decimal(max_digits=5, decimal_places=2)

        await primitive_db.execute(PrimitiveDecimalRecord.get_create_table_sql())

        with pytest.raises(ValidationError, match="decimal places"):
            await PrimitiveDecimalRecord.objects.create(amount="1.234")

        created = await PrimitiveDecimalRecord.objects.create(amount="999.99")
        fetched = await PrimitiveDecimalRecord.objects.get(id=created.id)
        assert fetched.amount == D("999.99")

        fetched.amount = "1.234"
        with pytest.raises(ValidationError, match="decimal places"):
            await fetched.save()

        refetched = await PrimitiveDecimalRecord.objects.get(id=created.id)
        assert refetched.amount == D("999.99")

    @pytest.mark.asyncio
    async def test_finite_float_round_trips(self, primitive_db):
        from aksara import Model, fields

        class PrimitiveFloatRecord(Model):
            __tablename__ = "primitive_float_records"

            reading = fields.Float()

        await primitive_db.execute(PrimitiveFloatRecord.get_create_table_sql())

        created = await PrimitiveFloatRecord.objects.create(reading=1.25)
        fetched = await PrimitiveFloatRecord.objects.get(id=created.id)
        assert fetched.reading == 1.25
