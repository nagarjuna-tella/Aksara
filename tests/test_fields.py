"""
Tests for Aksara Fields

Unit tests for field types and their SQL generation.
"""

import pytest
import uuid
from datetime import datetime

from aksara.fields import (
    String, Integer, Boolean, DateTime, UUID, JSON,
    Field
)


class TestStringField:
    """Tests for String field."""
    
    def test_default_max_length(self):
        field = String()
        field.name = "test"
        assert field.sql_type == "VARCHAR(255)"
    
    def test_custom_max_length(self):
        field = String(max_length=100)
        field.name = "test"
        assert field.sql_type == "VARCHAR(100)"
    
    def test_column_definition_basic(self):
        field = String(max_length=50)
        field.name = "email"
        assert field.get_column_definition() == "email VARCHAR(50) NOT NULL"
    
    def test_column_definition_nullable(self):
        field = String(nullable=True)
        field.name = "name"
        definition = field.get_column_definition()
        assert "NOT NULL" not in definition
    
    def test_column_definition_unique(self):
        field = String(unique=True)
        field.name = "email"
        assert "UNIQUE" in field.get_column_definition()
    
    def test_column_definition_default(self):
        field = String(default="hello")
        field.name = "greeting"
        assert "DEFAULT 'hello'" in field.get_column_definition()
    
    def test_to_python(self):
        field = String()
        assert field.to_python("hello") == "hello"
        assert field.to_python(123) == "123"
        assert field.to_python(None) is None
    
    def test_to_db(self):
        field = String()
        assert field.to_db("hello") == "hello"
        assert field.to_db(123) == "123"
        assert field.to_db(None) is None


class TestIntegerField:
    """Tests for Integer field."""
    
    def test_sql_type(self):
        field = Integer()
        assert field.sql_type == "INTEGER"
    
    def test_column_definition(self):
        field = Integer()
        field.name = "count"
        assert field.get_column_definition() == "count INTEGER NOT NULL"
    
    def test_column_definition_with_default(self):
        field = Integer(default=0)
        field.name = "count"
        assert "DEFAULT 0" in field.get_column_definition()
    
    def test_to_python(self):
        field = Integer()
        assert field.to_python(42) == 42
        assert field.to_python("42") == 42
        assert field.to_python(None) is None
    
    def test_to_db(self):
        field = Integer()
        assert field.to_db(42) == 42
        assert field.to_db("42") == 42
        assert field.to_db(None) is None


class TestBooleanField:
    """Tests for Boolean field."""
    
    def test_sql_type(self):
        field = Boolean()
        assert field.sql_type == "BOOLEAN"
    
    def test_column_definition(self):
        field = Boolean()
        field.name = "is_active"
        assert field.get_column_definition() == "is_active BOOLEAN NOT NULL"
    
    def test_column_definition_with_default_true(self):
        field = Boolean(default=True)
        field.name = "is_active"
        assert "DEFAULT TRUE" in field.get_column_definition()
    
    def test_column_definition_with_default_false(self):
        field = Boolean(default=False)
        field.name = "is_active"
        assert "DEFAULT FALSE" in field.get_column_definition()
    
    def test_to_python(self):
        field = Boolean()
        assert field.to_python(True) is True
        assert field.to_python(False) is False
        assert field.to_python(1) is True
        assert field.to_python(0) is False
        assert field.to_python(None) is None


class TestDateTimeField:
    """Tests for DateTime field."""
    
    def test_sql_type(self):
        field = DateTime()
        assert field.sql_type == "TIMESTAMP WITH TIME ZONE"
    
    def test_column_definition_auto_now_add(self):
        field = DateTime(auto_now_add=True)
        field.name = "created_at"
        assert "DEFAULT CURRENT_TIMESTAMP" in field.get_column_definition()
    
    def test_to_python_datetime(self):
        field = DateTime()
        now = datetime.now()
        assert field.to_python(now) == now
    
    def test_to_python_none(self):
        field = DateTime()
        assert field.to_python(None) is None


class TestUUIDField:
    """Tests for UUID field."""
    
    def test_sql_type(self):
        field = UUID()
        assert field.sql_type == "UUID"
    
    def test_column_definition_primary_key(self):
        field = UUID(primary_key=True)
        field.name = "id"
        definition = field.get_column_definition()
        assert "PRIMARY KEY" in definition
        assert "gen_random_uuid()" in definition
    
    def test_to_python_uuid(self):
        field = UUID()
        test_uuid = uuid.uuid4()
        assert field.to_python(test_uuid) == test_uuid
    
    def test_to_python_string(self):
        field = UUID()
        test_uuid = uuid.uuid4()
        result = field.to_python(str(test_uuid))
        assert result == test_uuid
    
    def test_to_python_none(self):
        field = UUID()
        assert field.to_python(None) is None


class TestJSONField:
    """Tests for JSON field."""
    
    def test_sql_type(self):
        field = JSON()
        assert field.sql_type == "JSONB"
    
    def test_default_nullable(self):
        field = JSON()
        assert field.nullable is True
    
    def test_column_definition(self):
        field = JSON()
        field.name = "metadata"
        definition = field.get_column_definition()
        assert "JSONB" in definition
        assert "NOT NULL" not in definition
    
    def test_to_python(self):
        field = JSON()
        # Test dict passthrough
        data = {"key": "value", "number": 42}
        assert field.to_python(data) == data
        # Test string parsing
        json_str = '{"key": "value"}'
        assert field.to_python(json_str) == {"key": "value"}
    
    def test_to_db(self):
        field = JSON()
        data = {"key": "value", "list": [1, 2, 3]}
        # to_db should serialize dict to JSON string for asyncpg
        result = field.to_db(data)
        assert isinstance(result, str)
        assert '"key": "value"' in result


class TestFieldOrdering:
    """Tests for field creation ordering."""
    
    def test_creation_counter_increments(self):
        initial = Field._creation_counter
        field1 = String()
        field2 = Integer()
        field3 = Boolean()
        
        assert field1._creation_order < field2._creation_order
        assert field2._creation_order < field3._creation_order
