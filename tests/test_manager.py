"""
Tests for QuerySet and Manager

Unit tests for the query API.
"""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from aksara import Model, fields
from aksara.db.expressions import F
from aksara.manager import QuerySet, Manager, DoesNotExist, MultipleObjectsReturned
from aksara.registry import ModelRegistry


class _CapturingDB:
    """Stand-in for the Database singleton that records write calls."""

    def __init__(self, fetch_return=None, execute_return="UPDATE 0"):
        self.fetch = AsyncMock(return_value=fetch_return or [])
        self.execute = AsyncMock(return_value=execute_return)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the model registry before each test."""
    ModelRegistry.clear()
    yield
    ModelRegistry.clear()


class TestQuerySet:
    """Tests for QuerySet class."""
    
    def test_queryset_creation(self):
        class User(Model):
            email = fields.String()
        
        qs = QuerySet(User)
        assert qs._model == User
        assert qs._filters == {}
    
    def test_queryset_filter(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        qs = QuerySet(User).filter(is_active=True)
        assert qs._filters == {"is_active": True}
    
    def test_queryset_filter_chaining(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        qs = QuerySet(User).filter(is_active=True).filter(email="test@example.com")
        assert qs._filters == {"is_active": True, "email": "test@example.com"}
    
    def test_queryset_filter_creates_new_instance(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        qs1 = QuerySet(User)
        qs2 = qs1.filter(is_active=True)
        
        assert qs1 is not qs2
        assert qs1._filters == {}
        assert qs2._filters == {"is_active": True}
    
    def test_queryset_build_where_clause_empty(self):
        class User(Model):
            email = fields.String()
        
        qs = QuerySet(User)
        where, values = qs._build_where_clause()
        
        assert where == ""
        assert values == []
    
    def test_queryset_build_where_clause_single_filter(self):
        class User(Model):
            is_active = fields.Boolean(default=True)
        
        qs = QuerySet(User).filter(is_active=True)
        where, values = qs._build_where_clause()
        
        assert '"is_active" = $1' in where
        assert values == [True]
    
    def test_queryset_build_where_clause_multiple_filters(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        qs = QuerySet(User).filter(email="test@example.com", is_active=True)
        where, values = qs._build_where_clause()
        
        assert "WHERE" in where
        assert "AND" in where
        assert len(values) == 2
    
    def test_queryset_invalid_field_raises(self):
        class User(Model):
            email = fields.String()
        
        qs = QuerySet(User).filter(invalid_field="value")
        
        with pytest.raises(ValueError, match="Unknown field"):
            qs._build_where_clause()

    def test_queryset_filter_none_uses_is_null(self):
        class User(Model):
            email = fields.String(nullable=True)

        query, values = QuerySet(User).filter(email=None)._build_select_query()

        assert '"email" IS NULL' in query
        assert "= NULL" not in query
        assert '"email" = $1' not in query
        assert values == []

    def test_queryset_filter_exact_none_uses_is_null(self):
        class User(Model):
            email = fields.String(nullable=True)

        query, values = QuerySet(User).filter(email__exact=None)._build_select_query()

        assert '"email" IS NULL' in query
        assert "= NULL" not in query
        assert '"email" = $1' not in query
        assert values == []

    def test_queryset_filter_non_nullable_none_uses_is_null(self):
        class User(Model):
            email = fields.String()

        query, values = QuerySet(User).filter(email=None)._build_select_query()

        assert '"email" IS NULL' in query
        assert values == []

    @pytest.mark.parametrize(
        ("value", "expected_sql"),
        [
            (True, '"email" IS NULL'),
            (False, '"email" IS NOT NULL'),
            ("true", '"email" IS NULL'),
            ("false", '"email" IS NOT NULL'),
            ("False", '"email" IS NOT NULL'),
            ("0", '"email" IS NOT NULL'),
        ],
    )
    def test_queryset_isnull_uses_strict_boolean_parsing(
        self,
        value,
        expected_sql,
    ):
        class User(Model):
            email = fields.String(nullable=True)

        query, values = QuerySet(User).filter(email__isnull=value)._build_select_query()

        assert expected_sql in query
        assert values == []

    @pytest.mark.parametrize("value", ["maybe", "", None, [], {}, 2, -1])
    def test_queryset_isnull_rejects_invalid_values(self, value):
        class User(Model):
            email = fields.String(nullable=True)

        qs = QuerySet(User).filter(email__isnull=value)

        with pytest.raises((TypeError, ValueError), match="__isnull"):
            qs._build_select_query()

    def test_queryset_filter_accepts_foreign_key_column_alias(self):
        class Author(Model):
            name = fields.String()

        class Post(Model):
            title = fields.String()
            author = fields.ForeignKey(Author)

        author_id = uuid4()

        query, values = QuerySet(Post).filter(author_id=author_id)._build_select_query()

        assert '"author_id" = $1' in query
        assert values == [author_id]

    def test_queryset_filter_foreign_key_field_still_uses_column_name(self):
        class Author(Model):
            name = fields.String()

        class Post(Model):
            title = fields.String()
            author = fields.ForeignKey(Author)

        author_id = uuid4()

        query, values = QuerySet(Post).filter(author=author_id)._build_select_query()

        assert '"author_id" = $1' in query
        assert values == [author_id]

    def test_queryset_filter_unknown_id_alias_still_raises(self):
        class Post(Model):
            title = fields.String()

        qs = QuerySet(Post).filter(nonexistent_id=uuid4())

        with pytest.raises(ValueError, match="Unknown field"):
            qs._build_select_query()


class TestManager:
    """Tests for Manager class."""
    
    def test_manager_attached_to_model(self):
        class User(Model):
            email = fields.String()
        
        assert hasattr(User, "objects")
        assert isinstance(User.objects, Manager)
    
    def test_manager_filter_returns_queryset(self):
        class User(Model):
            email = fields.String()
        
        qs = User.objects.filter(email="test@example.com")
        assert isinstance(qs, QuerySet)
        assert qs._filters == {"email": "test@example.com"}


class TestWritePathSQL:
    """SQL-level regressions for write-path consistency fixes."""

    @pytest.mark.asyncio
    async def test_bulk_create_prepares_slug_and_keeps_later_explicit_created_at(self):
        class Article(Model):
            title = fields.String(max_length=200)
            slug = fields.Slug(max_length=200, auto_from="title")

        explicit_created = datetime(2000, 1, 1, tzinfo=timezone.utc)
        first = Article(title="Hello World")
        second = Article(title="Second Post", created_at=explicit_created)

        db = _CapturingDB()
        with patch("aksara.db.Database.get_instance", return_value=db):
            await Article.objects.bulk_create([first, second])

        query = db.fetch.await_args.args[0]
        params = db.fetch.await_args.args[1:]

        assert first.slug == "hello-world"
        assert second.slug == "second-post"
        assert first.updated_at is not None
        assert second.updated_at is not None
        assert '"created_at"' in query
        assert "DEFAULT" in query
        assert explicit_created in params

    @pytest.mark.asyncio
    async def test_bulk_create_auto_now_overwrites_explicit_updated_at_like_save(self):
        class Article(Model):
            title = fields.String(max_length=200)

        explicit_updated = datetime(1999, 1, 1, tzinfo=timezone.utc)
        article = Article(title="Old timestamp", updated_at=explicit_updated)

        db = _CapturingDB()
        with patch("aksara.db.Database.get_instance", return_value=db):
            await Article.objects.bulk_create([article])

        params = db.fetch.await_args.args[1:]
        assert article.updated_at is not None
        assert article.updated_at != explicit_updated
        assert explicit_updated not in params

    @pytest.mark.asyncio
    async def test_queryset_update_adds_auto_now_for_regular_updates(self):
        class User(Model):
            age = fields.Integer(default=0)

        db = _CapturingDB(execute_return="UPDATE 1")
        with patch("aksara.db.Database.get_instance", return_value=db):
            updated = await QuerySet(User).filter(age__gte=0).update(age=F("age") + 1)

        query = db.execute.await_args.args[0]
        params = db.execute.await_args.args[1:]

        assert updated == 1
        assert '"age" = ("age" + $1)' in query
        assert '"updated_at" = $2' in query
        assert 'WHERE "age" >= $3' in query
        assert params[0] == 1
        assert isinstance(params[1], datetime)
        assert params[2] == 0

    @pytest.mark.asyncio
    async def test_queryset_update_respects_explicit_updated_at_only_update(self):
        class User(Model):
            age = fields.Integer(default=0)

        explicit_updated = datetime(2001, 1, 1, tzinfo=timezone.utc)
        db = _CapturingDB(execute_return="UPDATE 1")
        with patch("aksara.db.Database.get_instance", return_value=db):
            await QuerySet(User).update(updated_at=explicit_updated)

        query = db.execute.await_args.args[0]
        params = db.execute.await_args.args[1:]

        assert query.count('"updated_at"') == 1
        assert params == (explicit_updated,)

    @pytest.mark.asyncio
    async def test_queryset_update_vector_subclass_uses_vector_cast(self):
        class CustomVector(fields.Vector):
            pass

        class Embedding(Model):
            embedding = CustomVector(dimensions=3)

        db = _CapturingDB(execute_return="UPDATE 1")
        with patch("aksara.db.Database.get_instance", return_value=db):
            await QuerySet(Embedding).update(embedding=[1, 2, 3])

        query = db.execute.await_args.args[0]
        assert '"embedding" = CAST($1 AS vector)' in query

    @pytest.mark.asyncio
    async def test_bulk_update_vector_casts_case_values(self):
        class CustomVector(fields.Vector):
            pass

        class Embedding(Model):
            embedding = CustomVector(dimensions=3)

        instance = Embedding(embedding=[1, 2, 3])
        instance._is_new = False
        instance._data["id"] = uuid4()
        instance.embedding = [4, 5, 6]

        db = _CapturingDB(execute_return="UPDATE 1")
        with patch("aksara.db.Database.get_instance", return_value=db):
            await Embedding.objects.bulk_update([instance], ["embedding"])

        query = db.execute.await_args.args[0]
        normalized = " ".join(query.split())
        assert 'WHEN "id" = $1 THEN CAST($2 AS vector)' in normalized
        assert '"embedding" = CASE' in normalized

    @pytest.mark.asyncio
    async def test_bulk_create_vector_subclass_uses_vector_cast(self):
        class CustomVector(fields.Vector):
            pass

        class Embedding(Model):
            embedding = CustomVector(dimensions=3)

        instance = Embedding(embedding=[1, 2, 3])

        db = _CapturingDB()
        with patch("aksara.db.Database.get_instance", return_value=db):
            await Embedding.objects.bulk_create([instance])

        query = db.fetch.await_args.args[0]
        assert "CAST($1 AS vector)" in query


class TestExceptions:
    """Tests for ORM exceptions."""
    
    def test_does_not_exist_message(self):
        error = DoesNotExist("User matching query does not exist")
        assert "User matching query does not exist" in str(error)
    
    def test_multiple_objects_returned_message(self):
        error = MultipleObjectsReturned("get() returned 2 objects")
        assert "get() returned 2 objects" in str(error)


@pytest.fixture
async def db():
    """Create database connection and clean up query semantics tables."""
    from aksara.db import Database

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    database = Database(database_url)
    await database.connect()

    yield database

    try:
        await database.execute("DROP TABLE IF EXISTS qs_null_users CASCADE")
    finally:
        await database.disconnect()


@pytest.fixture
async def null_user_model(db):
    class QuerySemanticsUser(Model):
        __tablename__ = "qs_null_users"
        email = fields.String(max_length=255, nullable=True)

    await db.execute("DROP TABLE IF EXISTS qs_null_users CASCADE")
    await db.execute(QuerySemanticsUser.get_create_table_sql())
    return QuerySemanticsUser


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestQuerySetNullDatabase:
    """DB-backed coverage for NULL filter semantics."""

    @pytest.mark.asyncio
    async def test_filter_none_returns_only_null_rows(self, db, null_user_model):
        null_user = null_user_model(email=None)
        present_user = null_user_model(email="present@example.com")
        await null_user.save()
        await present_user.save()

        users = await null_user_model.objects.filter(email=None).all()

        assert [user.id for user in users] == [null_user.id]

    @pytest.mark.asyncio
    async def test_isnull_false_string_returns_non_null_rows(
        self,
        db,
        null_user_model,
    ):
        null_user = null_user_model(email=None)
        present_user = null_user_model(email="present@example.com")
        await null_user.save()
        await present_user.save()

        users = await null_user_model.objects.filter(email__isnull="False").all()

        assert [user.id for user in users] == [present_user.id]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestWritePathDatabase:
    """DB-backed regressions for ORM write-path consistency."""

    @pytest.mark.asyncio
    async def test_bulk_create_sets_updated_at_for_single_and_multiple_rows(self, db):
        class BulkTimestampUser(Model):
            __tablename__ = "bulk_timestamp_users_v054"
            email = fields.String(max_length=255)

        await db.execute('DROP TABLE IF EXISTS "bulk_timestamp_users_v054" CASCADE')
        await db.execute(BulkTimestampUser.get_create_table_sql())

        try:
            created = await BulkTimestampUser.objects.create(email="create@example.com")
            single = await BulkTimestampUser.objects.bulk_create([
                BulkTimestampUser(email="bulk-one@example.com")
            ])
            many = await BulkTimestampUser.objects.bulk_create([
                BulkTimestampUser(email="bulk-two@example.com"),
                BulkTimestampUser(email="bulk-three@example.com"),
            ])

            assert created.updated_at is not None
            assert single[0].updated_at is not None
            assert all(user.updated_at is not None for user in many)
        finally:
            await db.execute('DROP TABLE IF EXISTS "bulk_timestamp_users_v054" CASCADE')

    @pytest.mark.asyncio
    async def test_bulk_create_preserves_later_explicit_created_at(self, db):
        class BulkCreatedAtUser(Model):
            __tablename__ = "bulk_created_at_users_v054"
            email = fields.String(max_length=255)

        explicit_created = datetime(2000, 1, 1, tzinfo=timezone.utc)

        await db.execute('DROP TABLE IF EXISTS "bulk_created_at_users_v054" CASCADE')
        await db.execute(BulkCreatedAtUser.get_create_table_sql())

        try:
            first_obj = BulkCreatedAtUser(email="first@example.com")
            second_obj = BulkCreatedAtUser(
                email="second@example.com",
                created_at=explicit_created,
            )
            returned = await BulkCreatedAtUser.objects.bulk_create([first_obj, second_obj])

            first = await BulkCreatedAtUser.objects.get(email="first@example.com")
            second = await BulkCreatedAtUser.objects.get(email="second@example.com")

            assert returned == [first_obj, second_obj]
            assert first_obj.created_at is not None
            assert first_obj.created_at == first.created_at
            assert second_obj.created_at == explicit_created
            assert second_obj.created_at == second.created_at
            assert first_obj._is_new is False
            assert second_obj._is_new is False
            assert first.created_at is not None
            assert second.created_at == explicit_created
        finally:
            await db.execute('DROP TABLE IF EXISTS "bulk_created_at_users_v054" CASCADE')

    @pytest.mark.asyncio
    async def test_bulk_create_runs_async_prepare_for_slug(self, db):
        class BulkSlugArticle(Model):
            __tablename__ = "bulk_slug_articles_v054"
            title = fields.String(max_length=200)
            slug = fields.Slug(max_length=200, auto_from="title")

        await db.execute('DROP TABLE IF EXISTS "bulk_slug_articles_v054" CASCADE')
        await db.execute(BulkSlugArticle.get_create_table_sql())

        try:
            bulk = await BulkSlugArticle.objects.bulk_create([
                BulkSlugArticle(title="Hello World")
            ])
            created = await BulkSlugArticle.objects.create(title="Hello World")

            assert bulk[0].slug == "hello-world"
            assert created.slug == "hello-world"
        finally:
            await db.execute('DROP TABLE IF EXISTS "bulk_slug_articles_v054" CASCADE')

    @pytest.mark.asyncio
    async def test_queryset_update_updated_at_policy(self, db):
        class UpdatePolicyUser(Model):
            __tablename__ = "update_policy_users_v054"
            email = fields.String(max_length=255)
            age = fields.Integer(default=0)

        await db.execute('DROP TABLE IF EXISTS "update_policy_users_v054" CASCADE')
        await db.execute(UpdatePolicyUser.get_create_table_sql())

        try:
            user = await UpdatePolicyUser.objects.create(
                email="update-policy@example.com",
                age=0,
            )
            initial_updated_at = user.updated_at

            await asyncio.sleep(0.01)
            await UpdatePolicyUser.objects.filter(id=user.id).update(age=1)
            after_age_update = await UpdatePolicyUser.objects.get(id=user.id)

            assert after_age_update.age == 1
            assert after_age_update.updated_at > initial_updated_at

            explicit_updated = datetime(2001, 1, 1, tzinfo=timezone.utc)
            await UpdatePolicyUser.objects.filter(id=user.id).update(
                updated_at=explicit_updated
            )
            after_explicit_update = await UpdatePolicyUser.objects.get(id=user.id)

            assert after_explicit_update.updated_at == explicit_updated

            await asyncio.sleep(0.01)
            await UpdatePolicyUser.objects.filter(id=user.id).update(
                age=F("age") + 1
            )
            after_f_update = await UpdatePolicyUser.objects.get(id=user.id)

            assert after_f_update.age == 2
            assert after_f_update.updated_at > explicit_updated
        finally:
            await db.execute('DROP TABLE IF EXISTS "update_policy_users_v054" CASCADE')
