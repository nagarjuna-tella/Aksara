"""
Tests for QuerySet and Manager

Unit tests for the query API.
"""

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
        
        assert "is_active = $1" in where
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
