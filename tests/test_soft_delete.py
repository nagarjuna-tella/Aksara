"""Regression tests for soft-delete model behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from aksara import Model, fields
from aksara.contrib.soft_delete import SoftDeleteModel
from aksara.db import Database
from aksara.registry import ModelRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the model registry around each test."""
    ModelRegistry.clear()
    yield
    ModelRegistry.clear()


class TestSoftDeleteHydration:
    """Regression coverage for record hydration after soft delete updates."""

    def test_soft_delete_registers_deleted_at_field(self):
        class Document(SoftDeleteModel, Model):
            title = fields.String()

        assert Document._soft_delete_enabled is True
        assert "deleted_at" in Document._fields
        assert Document.objects._soft_delete_active() is True

    @pytest.mark.asyncio
    async def test_delete_hydrates_foreign_key_columns(self, monkeypatch):
        owner_id = uuid4()
        deleted_at = datetime.now(timezone.utc)
        fake_db = Mock()
        fake_db.fetchrow = AsyncMock(
            return_value={
                "id": uuid4(),
                "title": "Draft",
                "owner_fk": owner_id,
                "deleted_at": deleted_at,
            }
        )
        pre_delete = Mock(send=AsyncMock())
        post_delete = Mock(send=AsyncMock())

        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: fake_db))
        monkeypatch.setattr("aksara.signals.pre_delete", pre_delete)
        monkeypatch.setattr("aksara.signals.post_delete", post_delete)

        class Owner(Model):
            name = fields.String()

        class Document(SoftDeleteModel, Model):
            title = fields.String()
            owner = fields.ForeignKey(Owner, column_name="owner_fk")

        document = Document(title="Draft")
        document._is_new = False
        document._data["id"] = uuid4()
        document._data["owner"] = None

        await document.delete()

        assert document._data["owner"] == owner_id
        assert document._data["deleted_at"] == deleted_at

    @pytest.mark.asyncio
    async def test_undelete_hydrates_foreign_key_columns(self, monkeypatch):
        owner_id = uuid4()
        fake_db = Mock()
        fake_db.fetchrow = AsyncMock(
            return_value={
                "id": uuid4(),
                "title": "Draft",
                "owner_fk": owner_id,
                "deleted_at": None,
            }
        )

        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: fake_db))

        class Owner(Model):
            name = fields.String()

        class Document(SoftDeleteModel, Model):
            title = fields.String()
            owner = fields.ForeignKey(Owner, column_name="owner_fk")

        document = Document(title="Draft")
        document._is_new = False
        document._data["id"] = uuid4()
        document._data["owner"] = None
        document._data["deleted_at"] = datetime.now(timezone.utc)

        await document.undelete()

        assert document._data["owner"] == owner_id
        assert document._data["deleted_at"] is None