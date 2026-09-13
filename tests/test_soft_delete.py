"""Regression tests for soft-delete model behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from aksara import Model, fields
from aksara.contrib.soft_delete import SoftDeleteModel, only_deleted, with_deleted
from aksara.db import Database
from aksara.db.expressions import Count, Q
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


class TestSoftDeleteQueryTransforms:
    """SOFTDELETE001 visibility changes preserve the complete query shape."""

    def test_visibility_helpers_clone_all_existing_query_state(self):
        class Owner(Model):
            name = fields.String()

        class Document(SoftDeleteModel, Model):
            title = fields.String()
            tenant_id = fields.String()
            owner = fields.ForeignKey(Owner)

        restricted = (
            Document.objects.filter(
                Q(title="Draft") | Q(title="Review"),
                tenant_id="tenant-a",
            )
            .order_by("-title")
            .select_related("owner")
            .prefetch_related("labels")
            .annotate(row_count=Count("*"))
            .limit(5)
            .offset(2)
        )

        including = with_deleted(restricted)
        deleted = only_deleted(restricted)

        for transformed in (including, deleted):
            assert transformed is not restricted
            assert transformed._filters == restricted._filters
            assert transformed._q_objects == restricted._q_objects
            assert transformed._order_by == restricted._order_by
            assert transformed._select_related == restricted._select_related
            assert transformed._prefetch_related == restricted._prefetch_related
            assert transformed._annotations == restricted._annotations
            assert transformed._limit_value == restricted._limit_value
            assert transformed._offset_value == restricted._offset_value

        including_sql, including_values = including._build_where_clause()
        deleted_sql, deleted_values = deleted._build_where_clause()
        assert including_values == deleted_values == ["Draft", "Review", "tenant-a"]
        assert "tenant_id" in including_sql
        assert "deleted_at" not in including_sql
        assert "tenant_id" in deleted_sql
        assert '"deleted_at" IS NOT NULL' in deleted_sql
