"""
Regression tests for Phase 1 bug-hunt findings on the ORM core.

Each test exercises one of the six confirmed bugs from
`bug-hunt/phase-1-findings.md`. The tests inspect the generated SQL or
ensure that the previously-broken serialization / validation paths now
behave correctly. The database layer is mocked so these tests run
without a live PostgreSQL connection.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from aksara import Model, fields
from aksara.registry import ModelRegistry


# ─── Helpers ──────────────────────────────────────────────────────────────


class _FakeRecord(dict):
    """asyncpg.Record-like object backed by a dict."""

    def keys(self):  # type: ignore[override]
        return super().keys()


class _CapturingDB:
    """Stand-in for the Database singleton that records calls."""

    def __init__(self, fetchrow_return=None, fetch_return=None, execute_return="UPDATE 0"):
        self.fetchrow = AsyncMock(return_value=fetchrow_return)
        self.fetch = AsyncMock(return_value=fetch_return or [])
        self.execute = AsyncMock(return_value=execute_return)


@pytest.fixture(autouse=True)
def _clear_registry():
    ModelRegistry._models.clear()
    yield
    ModelRegistry._models.clear()


# ─── Fix #1 — String.to_db enforces max_length ─────────────────────────────


class TestStringMaxLengthEnforcement:
    def test_to_db_rejects_value_longer_than_max_length(self):
        field = fields.String(max_length=3)
        with pytest.raises(ValueError, match="too long"):
            field.to_db("abcd")

    def test_to_db_accepts_value_at_max_length(self):
        field = fields.String(max_length=3)
        assert field.to_db("abc") == "abc"

    def test_to_db_accepts_value_shorter_than_max_length(self):
        field = fields.String(max_length=5)
        assert field.to_db("hi") == "hi"


# ─── Fix #2 — bulk_update emits a boolean WHEN condition ───────────────────


class TestBulkUpdateCaseSyntax:
    @pytest.mark.asyncio
    async def test_bulk_update_emits_id_comparison_in_case(self):
        class Item(Model):
            title = fields.String(max_length=50)

        instance = Item(title="renamed")
        instance._is_new = False
        instance._data["id"] = uuid.uuid4()

        db = _CapturingDB(execute_return="UPDATE 1")
        with patch("aksara.db.Database.get_instance", return_value=db):
            await Item.objects.bulk_update([instance], ["title"])

        query = db.execute.await_args.args[0]
        # The bug emitted `WHEN $1 THEN $2` (a non-boolean parameter).
        # The fix must compare against the PK column.
        assert "WHEN id =" in query
        assert "WHEN $1 THEN" not in query


# ─── Fix #3 — bulk_create uses FK DB column names ──────────────────────────


class TestBulkCreateForeignKeyColumns:
    @pytest.mark.asyncio
    async def test_bulk_create_uses_db_column_for_foreign_key(self):
        class Owner(Model):
            name = fields.String(max_length=50)

        class Article(Model):
            owner = fields.ForeignKey(Owner)
            title = fields.String(max_length=50)

        owner_id = uuid.uuid4()
        article = Article(owner=owner_id, title="hi")

        returned_id = uuid.uuid4()
        returning_row = _FakeRecord({
            "id": returned_id,
            "owner_id": owner_id,
            "title": "hi",
            "created_at": None,
            "updated_at": None,
        })
        db = _CapturingDB(fetch_return=[returning_row])

        with patch("aksara.db.Database.get_instance", return_value=db):
            await Article.objects.bulk_create([article])

        query = db.fetch.await_args.args[0]
        # The bug wrote raw field names — here the Python field is `owner`
        # but the DB column is `owner_id`. The INSERT must target the
        # column, not the field name.
        assert '"owner_id"' in query
        assert '"owner"' not in query


# ─── Fixes #4, #5, #6 — upsert behaviour ───────────────────────────────────


class TestUpsertSerialization:
    @pytest.mark.asyncio
    async def test_upsert_passes_to_db_serialized_values(self):
        """Fix #4: JSON.to_db() must run before values reach asyncpg."""

        class Item(Model):
            email = fields.String(max_length=120, unique=True)
            metadata = fields.JSON(default=dict)

        returning_row = _FakeRecord({
            "id": uuid.uuid4(),
            "email": "a@example.com",
            "metadata": {"x": 1},
            "created_at": None,
            "updated_at": None,
            "_is_created": True,
        })
        db = _CapturingDB(fetchrow_return=returning_row)

        with patch("aksara.db.Database.get_instance", return_value=db):
            await Item.objects.upsert(
                email="a@example.com",
                defaults={"metadata": {"x": 1}},
            )

        params = db.fetchrow.await_args.args[1:]
        # The bug forwarded the raw dict. After the fix, JSON.to_db()
        # converts it to a JSON-encoded string before asyncpg sees it.
        def _is_serialized_metadata(p):
            if not isinstance(p, str):
                return False
            try:
                return json.loads(p) == {"x": 1}
            except (ValueError, TypeError):
                return False

        assert any(_is_serialized_metadata(p) for p in params)
        assert not any(isinstance(p, dict) for p in params)


class TestUpsertEmptyDefaults:
    @pytest.mark.asyncio
    async def test_upsert_with_no_defaults_emits_valid_sql(self):
        """Fix #5: empty SET clause is syntactically invalid."""

        class Item(Model):
            email = fields.String(max_length=120, unique=True)

        returning_row = _FakeRecord({
            "id": uuid.uuid4(),
            "email": "b@example.com",
            "created_at": None,
            "updated_at": None,
            "_is_created": True,
        })
        db = _CapturingDB(fetchrow_return=returning_row)

        with patch("aksara.db.Database.get_instance", return_value=db):
            await Item.objects.upsert(email="b@example.com")

        query = db.fetchrow.await_args.args[0]
        # The pre-fix SQL was `... DO UPDATE SET RETURNING ...`, which
        # PostgreSQL rejects. The fix must produce a valid assignment.
        assert "DO UPDATE SET" in query
        assert "DO UPDATE SET \n" not in query.replace(" ", "")  # not empty
        # Sanity: ensure the no-op assignment uses the conflict column.
        normalized = " ".join(query.split())
        assert 'DO UPDATE SET "email" = EXCLUDED."email"' in normalized


class TestUpsertForeignKeyColumns:
    @pytest.mark.asyncio
    async def test_upsert_uses_db_column_for_foreign_key(self):
        """Fix #6: INSERT columns and ON CONFLICT must use FK column names."""

        class Owner(Model):
            name = fields.String(max_length=50)

        class Article(Model):
            owner = fields.ForeignKey(Owner)
            title = fields.String(max_length=50)

        owner_id = uuid.uuid4()
        returning_row = _FakeRecord({
            "id": uuid.uuid4(),
            "owner_id": owner_id,
            "title": "x",
            "created_at": None,
            "updated_at": None,
            "_is_created": True,
        })
        db = _CapturingDB(fetchrow_return=returning_row)

        with patch("aksara.db.Database.get_instance", return_value=db):
            await Article.objects.upsert(owner=owner_id, defaults={"title": "x"})

        query = db.fetchrow.await_args.args[0]
        normalized = " ".join(query.split())
        # Both the INSERT column list and ON CONFLICT must reference the
        # real DB column (`owner_id`), never the Python field (`owner`).
        assert '"owner_id"' in normalized
        # Make sure the bare field name never appears as a quoted column.
        assert '"owner"' not in normalized
