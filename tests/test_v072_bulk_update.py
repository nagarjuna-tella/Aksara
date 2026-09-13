"""PostgreSQL regression coverage for field-aware ``bulk_update`` typing."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

import pytest

from aksara import Model, fields
from aksara.registry import ModelRegistry
from aksara.signals import post_save, pre_save

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


class BulkState(Enum):
    READY = "ready"
    DONE = "done"


@pytest.fixture
async def bulk_database():
    from aksara.db import Database

    ModelRegistry.clear()

    class TypedBulkRecord(Model):
        __tablename__ = "v072_typed_bulk_records"

        short_text = fields.String(max_length=80)
        long_text = fields.Text()
        quantity = fields.Integer()
        ratio = fields.Float()
        amount = fields.Decimal(max_digits=10, decimal_places=2)
        enabled = fields.Boolean()
        external_id = fields.UUID()
        event_date = fields.Date()
        event_time = fields.Time()
        happened_at = fields.DateTime()
        duration = fields.Duration()
        state = fields.Enum(BulkState)
        optional_text = fields.String(nullable=True)
        payload = fields.JSON(nullable=True)
        tags = fields.Array(item_type=str, nullable=True)
        uuid_tags = fields.Array(item_type=UUID, nullable=True)

    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=2)
    await database.connect()
    await database.execute('DROP TABLE IF EXISTS "v072_typed_bulk_records" CASCADE')
    await database.execute(TypedBulkRecord.get_create_table_sql())
    try:
        yield database, TypedBulkRecord
    finally:
        await database.execute('DROP TABLE IF EXISTS "v072_typed_bulk_records" CASCADE')
        await database.disconnect()
        ModelRegistry.clear()


def _values(index: int) -> dict:
    return {
        "short_text": f"short-{index}",
        "long_text": f"long-{index}",
        "quantity": index,
        "ratio": index + 0.25,
        "amount": Decimal(f"{index}.50"),
        "enabled": bool(index % 2),
        "external_id": uuid4(),
        "event_date": date(2026, 9, index),
        "event_time": time(8 + index, 15, 30),
        "happened_at": datetime(2026, 9, index, 12, 0, tzinfo=UTC),
        "duration": timedelta(days=index, seconds=30),
        "state": BulkState.READY,
        "optional_text": f"optional-{index}",
        "payload": {"index": index, "nested": [True, None, {"ok": index}]},
        "tags": [f"tag-{index}", "shared"],
        "uuid_tags": [uuid4(), uuid4()],
    }


@pytest.mark.asyncio
async def test_bulk_update_casts_all_supported_scalar_and_advanced_fields(bulk_database):
    _database, record_model = bulk_database
    original = [await record_model.objects.create(**_values(index)) for index in (1, 2, 3)]
    targets = original[:2]

    expected = []
    for index, record in enumerate(targets, start=11):
        values = _values(index)
        if index == 12:
            values["optional_text"] = None
            values["payload"] = None
            values["tags"] = None
            values["uuid_tags"] = None
        values["state"] = BulkState.DONE
        for field_name, value in values.items():
            setattr(record, field_name, value)
        expected.append(values)

    events = []

    async def receiver(sender, **kwargs):
        events.append((sender, kwargs))

    pre_save.connect(receiver, sender=record_model)
    post_save.connect(receiver, sender=record_model)
    try:
        field_names = list(expected[0])
        updated = await record_model.objects.bulk_update(
            targets,
            fields=field_names,
            batch_size=1,
        )
    finally:
        pre_save.disconnect(receiver, sender=record_model)
        post_save.disconnect(receiver, sender=record_model)

    assert updated == 2
    assert events == []
    for record, values in zip(targets, expected):
        reloaded = await record_model.objects.get(id=record.id)
        for field_name, expected_value in values.items():
            assert getattr(reloaded, field_name) == expected_value

    untouched = await record_model.objects.get(id=original[2].id)
    assert untouched.short_text == "short-3"
    assert untouched.state is BulkState.READY


@pytest.mark.asyncio
async def test_bulk_update_preserves_validation_and_empty_input_contract(bulk_database):
    _database, record_model = bulk_database
    record = await record_model.objects.create(**_values(1))

    with pytest.raises(ValueError, match="non-empty"):
        await record_model.objects.bulk_update([], ["enabled"])
    with pytest.raises(ValueError, match="non-empty"):
        await record_model.objects.bulk_update([record], [])

    record.amount = Decimal("123456789.12")
    with pytest.raises(ValueError, match="maximum integer digits"):
        await record_model.objects.bulk_update([record], ["amount"])

    reloaded = await record_model.objects.get(id=record.id)
    assert reloaded.amount == Decimal("1.50")
