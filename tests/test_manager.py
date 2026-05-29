"""
Tests for QuerySet and Manager

Unit tests for the query API.
"""

import os
from uuid import uuid4

import pytest
from aksara import Model, fields
from aksara.manager import QuerySet, Manager, DoesNotExist, MultipleObjectsReturned
from aksara.registry import ModelRegistry


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
