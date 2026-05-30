"""
Integration tests for JSONB path filtering and pgvector support.
"""

from __future__ import annotations

import os

import pytest

from aksara import Model, fields
from aksara.db.engine import Database
from aksara.registry import ModelRegistry


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
async def db():
    """Create a database connection for JSONB/vector integration tests."""
    ModelRegistry.clear()
    database = Database(os.environ["DATABASE_URL"])
    await database.connect()

    yield database

    try:
        await database.execute('DROP TABLE IF EXISTS "json_vector_records" CASCADE')
    except Exception:
        pass

    await database.disconnect()
    ModelRegistry.clear()


@pytest.fixture
def json_model():
    class JsonVectorRecord(Model):
        title = fields.String(max_length=200)
        metadata = fields.JSON(default=dict)

        class Meta:
            table_name = "json_vector_records"

    return JsonVectorRecord


class TestJsonbPathFiltering:
    """Integration tests for nested JSON path lookups."""

    @pytest.mark.asyncio
    async def test_filters_nested_json_path(self, db, json_model):
        await db.execute(json_model.get_create_table_sql())

        await json_model.objects.create(
            title="Ada",
            metadata={"preferences": {"theme": "dark", "language": "en"}},
        )
        await json_model.objects.create(
            title="Grace",
            metadata={"preferences": {"theme": "light", "language": "en"}},
        )

        records = await json_model.objects.filter(metadata__preferences__theme="dark").all()

        assert len(records) == 1
        assert records[0].title == "Ada"


class TestVectorFieldIntegration:
    """Integration tests for vector storage when pgvector is available."""

    @pytest.mark.asyncio
    async def test_stores_and_reads_vectors_when_extension_available(self, db):
        extension_available = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
        )
        if not extension_available:
            pytest.skip("pgvector extension is not available")

        await db.execute("CREATE EXTENSION IF NOT EXISTS vector")

        class EmbeddingRecord(Model):
            title = fields.String(max_length=200)
            embedding = fields.Vector(dimensions=3)

            class Meta:
                table_name = "json_vector_records"

        await db.execute(EmbeddingRecord.get_create_table_sql())

        created = await EmbeddingRecord.objects.create(
            title="Vector",
            embedding=[1, 2, 3],
        )

        fetched = await EmbeddingRecord.objects.get(id=created.id)

        assert fetched.embedding == [1.0, 2.0, 3.0]

    @pytest.mark.asyncio
    async def test_bulk_update_vectors_when_extension_available(self, db):
        extension_available = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
        )
        if not extension_available:
            pytest.skip("pgvector extension is not available")

        await db.execute("CREATE EXTENSION IF NOT EXISTS vector")

        class EmbeddingRecord(Model):
            title = fields.String(max_length=200)
            embedding = fields.Vector(dimensions=3)

            class Meta:
                table_name = "json_vector_records"

        await db.execute(EmbeddingRecord.get_create_table_sql())

        created = await EmbeddingRecord.objects.create(
            title="Vector",
            embedding=[1, 2, 3],
        )
        created.embedding = [4, 5, 6]

        updated = await EmbeddingRecord.objects.bulk_update([created], ["embedding"])
        fetched = await EmbeddingRecord.objects.get(id=created.id)

        assert updated == 1
        assert fetched.embedding == [4.0, 5.0, 6.0]
