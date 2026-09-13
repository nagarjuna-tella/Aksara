"""Regression tests for the v0.7.2 fixture identity and round-trip contract."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from aksara import Model, fields
from aksara.fixtures import dump_database, load_data
from aksara.registry import AmbiguousModelError, ModelRegistry


@pytest.fixture(autouse=True)
def isolated_registry():
    ModelRegistry.clear()
    yield
    ModelRegistry.clear()


def _model(module: str, name: str, table: str):
    return type(
        name,
        (Model,),
        {
            "__module__": module,
            "__tablename__": table,
            "label": fields.String(),
        },
    )


@pytest.mark.asyncio
async def test_dump_database_uses_canonical_registry_values(monkeypatch):
    async def fake_dump(model, **kwargs):
        return json.dumps([{"model": ModelRegistry.reference(model), "fields": {}}])

    monkeypatch.setattr("aksara.fixtures.dump_data", fake_dump)

    assert json.loads(await dump_database()) == []

    account = _model("shop.models", "Account", "shop_accounts")
    assert json.loads(await dump_database()) == [
        {"model": "Account", "fields": {}},
    ]

    auth_user = _model("aksara.auth.models", "User", "aksara_users")
    tenant_user = _model("tenant.models", "User", "tenant_users")
    dumped = json.loads(await dump_database())
    assert {record["model"] for record in dumped} == {
        "Account",
        "aksara.auth.models.User",
        "tenant.models.User",
    }

    selected = json.loads(
        await dump_database(models=["tenant.models.User", "Account"])
    )
    assert [record["model"] for record in selected] == [
        "tenant.models.User",
        "Account",
    ]
    with pytest.raises(AmbiguousModelError):
        await dump_database(models=["User"])

    assert set(ModelRegistry.all().values()) == {account, auth_user, tenant_user}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
@pytest.mark.asyncio
async def test_json_and_safe_yaml_restore_round_trip():
    yaml = pytest.importorskip("yaml")
    from aksara.db import Database

    class FixtureParent(Model):
        __tablename__ = "v072_fixture_parents"

        name = fields.String()
        external_id = fields.UUID()
        active = fields.Boolean(default=True)
        published_at = fields.DateTime()
        due_on = fields.Date()
        optional_note = fields.String(nullable=True)
        payload = fields.JSON(nullable=True)
        tags = fields.Array(item_type=str)

    class FixtureChild(Model):
        __tablename__ = "v072_fixture_children"

        title = fields.String()
        parent = fields.ForeignKey(FixtureParent, on_delete="CASCADE")

    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=2)
    await database.connect()
    try:
        await database.execute("DROP TABLE IF EXISTS v072_fixture_children CASCADE")
        await database.execute("DROP TABLE IF EXISTS v072_fixture_parents CASCADE")
        await database.execute(FixtureParent.get_create_table_sql())
        await database.execute(FixtureChild.get_create_table_sql())

        parent_id = uuid4()
        external_id = uuid4()
        published_at = datetime(2026, 9, 12, 15, 30, tzinfo=UTC)
        parent = await FixtureParent.objects.create(
            id=parent_id,
            name="Primary",
            external_id=external_id,
            active=True,
            published_at=published_at,
            due_on=date(2026, 9, 30),
            optional_note=None,
            payload={"nested": {"items": [1, "two", None]}, "enabled": True},
            tags=["release", "fixture"],
        )
        child = await FixtureChild.objects.create(title="Dependent", parent=parent)

        json_dump = await dump_database(format="json")
        yaml_dump = await dump_database(format="yaml")
        json_records = json.loads(json_dump)
        yaml_records = yaml.safe_load(yaml_dump)

        assert yaml_records == json_records
        assert "!!python" not in yaml_dump
        assert [record["model"] for record in json_records] == [
            "FixtureParent",
            "FixtureChild",
        ]
        parent_record = json_records[0]
        assert parent_record["pk"] == str(parent_id)
        assert parent_record["fields"]["external_id"] == str(external_id)
        assert parent_record["fields"]["published_at"] == published_at.isoformat()
        assert parent_record["fields"]["due_on"] == "2026-09-30"
        assert parent_record["fields"]["optional_note"] is None
        assert parent_record["fields"]["payload"] == {
            "nested": {"items": [1, "two", None]},
            "enabled": True,
        }
        assert parent_record["fields"]["tags"] == ["release", "fixture"]

        expected = {
            "parent": {
                "id": parent.id,
                "name": parent.name,
                "external_id": parent.external_id,
                "active": parent.active,
                "published_at": parent.published_at,
                "due_on": parent.due_on,
                "optional_note": parent.optional_note,
                "payload": parent.payload,
                "tags": parent.tags,
            },
            "child": {"id": child.id, "title": child.title, "parent_id": child.parent_id},
        }

        for fixture_dump, format_name in ((json_dump, "json"), (yaml_dump, "yaml")):
            await database.execute("TRUNCATE v072_fixture_children, v072_fixture_parents")
            result = await load_data(fixture_dump, format=format_name, strict=True)
            assert result == {"loaded": 2, "errors": 0, "skipped": 0}

            restored_parent = await FixtureParent.objects.get(id=parent_id)
            restored_child = await FixtureChild.objects.get(id=child.id)
            assert {
                "id": restored_parent.id,
                "name": restored_parent.name,
                "external_id": restored_parent.external_id,
                "active": restored_parent.active,
                "published_at": restored_parent.published_at,
                "due_on": restored_parent.due_on,
                "optional_note": restored_parent.optional_note,
                "payload": restored_parent.payload,
                "tags": restored_parent.tags,
            } == expected["parent"]
            assert {
                "id": restored_child.id,
                "title": restored_child.title,
                "parent_id": restored_child.parent_id,
            } == expected["child"]

        json_records[0]["fields"]["name"] = "Updated"
        result = await load_data(json.dumps(json_records), strict=True)
        assert result["loaded"] == 2
        assert (await FixtureParent.objects.get(id=parent_id)).name == "Updated"

        seed = json.dumps([{"model": "FixtureParent", "fields": {
            "name": "Seed",
            "external_id": str(uuid4()),
            "active": False,
            "published_at": published_at.isoformat(),
            "due_on": "2026-10-01",
            "optional_note": None,
            "payload": {},
            "tags": [],
        }}])
        seed_result = await load_data(seed, strict=True)
        assert seed_result == {"loaded": 1, "errors": 0, "skipped": 0}
        seeded = await FixtureParent.objects.get(name="Seed")
        assert isinstance(seeded.id, UUID)

        bad = json.dumps([{"model": "MissingModel", "fields": {}}])
        assert await load_data(bad) == {"loaded": 0, "errors": 1, "skipped": 0}
        with pytest.raises(KeyError):
            await load_data(bad, strict=True)
    finally:
        await database.execute("DROP TABLE IF EXISTS v072_fixture_children CASCADE")
        await database.execute("DROP TABLE IF EXISTS v072_fixture_parents CASCADE")
        await database.disconnect()
