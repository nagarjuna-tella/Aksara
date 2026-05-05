"""
Tests for GenericForeignKey and content type support.
"""

from __future__ import annotations

import os

import pytest

from aksara import Model, fields
from aksara.contenttypes import clear_content_type_cache, sync_content_types
from aksara.registry import ModelRegistry


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
async def db():
    """Create a database connection for generic relation integration tests."""
    from aksara.db import Database

    ModelRegistry.clear()
    clear_content_type_cache()

    database = Database(os.environ["DATABASE_URL"])
    await database.connect()

    yield database

    try:
        await database.execute('DROP TABLE IF EXISTS "gfk_comments" CASCADE')
        await database.execute('DROP TABLE IF EXISTS "gfk_posts" CASCADE')
        await database.execute('DROP TABLE IF EXISTS "gfk_products" CASCADE')
        await database.execute('DROP TABLE IF EXISTS "aksara_content_types" CASCADE')
    except Exception:
        pass

    await database.disconnect()
    ModelRegistry.clear()
    clear_content_type_cache()


@pytest.fixture
def generic_models():
    """Create test models using a GenericForeignKey."""

    class GFKPost(Model):
        __tablename__ = "gfk_posts"
        title = fields.String(max_length=200)

    class GFKProduct(Model):
        __tablename__ = "gfk_products"
        name = fields.String(max_length=200)

    class GFKComment(Model):
        __tablename__ = "gfk_comments"
        body = fields.String(max_length=200)
        content_object = fields.GenericForeignKey()

    return {
        "Post": GFKPost,
        "Product": GFKProduct,
        "Comment": GFKComment,
    }


@pytest.fixture
async def setup_tables(db, generic_models):
    """Create the tables required for the generic relation tests."""
    await db.execute(generic_models["Post"].get_create_table_sql())
    await db.execute(generic_models["Product"].get_create_table_sql())
    await db.execute(generic_models["Comment"].get_create_table_sql())
    await sync_content_types(db, prune_stale=True)
    return generic_models


class TestGenericForeignKey:
    """Integration tests for generic relations."""

    @pytest.mark.asyncio
    async def test_resolves_related_object(self, setup_tables):
        post = await setup_tables["Post"].objects.create(title="Hello")

        comment = setup_tables["Comment"](body="First", content_object=post)
        await comment.save()

        assert comment.content_type_id is not None
        assert comment.object_id == str(post.id)

        fetched = await setup_tables["Comment"].objects.get(id=comment.id)
        related = await fetched.content_object()

        assert related is not None
        assert related.id == post.id
        assert related.title == "Hello"

    @pytest.mark.asyncio
    async def test_supports_multiple_target_models(self, setup_tables):
        product = await setup_tables["Product"].objects.create(name="Keyboard")

        comment = setup_tables["Comment"](body="Second")
        comment.content_object = product
        await comment.save()

        fetched = await setup_tables["Comment"].objects.get(id=comment.id)
        related = await fetched.content_object()

        assert related is not None
        assert related.id == product.id
        assert related.name == "Keyboard"