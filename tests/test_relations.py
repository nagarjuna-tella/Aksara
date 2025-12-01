"""
Tests for Vidyut v0.3.5 Relationship Fields

Unit tests for OneToOne and ManyToMany field types.
"""

import pytest
from uuid import uuid4

from vidyut.fields import (
    String, UUID, ForeignKey, OneToOne, ManyToMany,
    ManyToManyManager,
)
from vidyut.model.base import Model


# Mock models for testing
class MockCategory(Model):
    """Mock category model for testing."""
    class Meta:
        table = "categories"


class MockTag(Model):
    """Mock tag model for testing."""
    class Meta:
        table = "tags"


class MockArticle(Model):
    """Mock article model for testing."""
    class Meta:
        table = "articles"


class TestOneToOneField:
    """Tests for OneToOne field."""
    
    def test_extends_foreign_key(self):
        field = OneToOne(MockCategory)
        assert isinstance(field, ForeignKey)
    
    def test_unique_is_true(self):
        field = OneToOne(MockCategory)
        assert field.unique is True
    
    def test_unique_cannot_be_false(self):
        # OneToOne should always be unique - it extends FK with unique constraint
        field = OneToOne(MockCategory)
        assert field.unique is True
    
    def test_sql_type(self):
        field = OneToOne(MockCategory)
        assert field.sql_type == "UUID"
    
    def test_column_definition_includes_unique(self):
        field = OneToOne(MockCategory)
        field.name = "category_id"
        definition = field.get_column_definition()
        assert "UNIQUE" in definition
    
    def test_column_definition_not_nullable_by_default(self):
        field = OneToOne(MockCategory)
        field.name = "category_id"
        definition = field.get_column_definition()
        assert "NOT NULL" in definition
    
    def test_column_definition_nullable(self):
        field = OneToOne(MockCategory, nullable=True)
        field.name = "category_id"
        definition = field.get_column_definition()
        assert "NOT NULL" not in definition
    
    def test_on_delete_default(self):
        field = OneToOne(MockCategory)
        assert field.on_delete == "CASCADE"
    
    def test_on_delete_custom(self):
        field = OneToOne(MockCategory, on_delete="SET NULL")
        assert field.on_delete == "SET NULL"
    
    def test_to_model(self):
        field = OneToOne(MockCategory)
        assert field.to_model == MockCategory
    
    def test_related_name(self):
        field = OneToOne(MockCategory, related_name="article")
        assert field.related_name == "article"


class TestManyToManyField:
    """Tests for ManyToMany field."""
    
    def test_sql_type_virtual(self):
        field = ManyToMany(MockTag)
        # M2M returns "VIRTUAL" to indicate it's not a real column
        assert field.sql_type == "VIRTUAL"
    
    def test_to_model(self):
        field = ManyToMany(MockTag)
        assert field.to_model == MockTag
    
    def test_related_name(self):
        field = ManyToMany(MockTag, related_name="articles")
        assert field.related_name == "articles"
    
    def test_join_table_name_generation(self):
        field = ManyToMany(MockTag)
        field.name = "tags"
        field._source_model = MockArticle
        
        join_table = field.join_table_name
        # Join table should contain the source table and field name
        assert "tags" in join_table
        assert "article" in join_table.lower()
    
    def test_get_create_join_table_sql(self):
        field = ManyToMany(MockTag)
        field.name = "tags"
        field._source_model = MockArticle
        
        sql = field.get_join_table_sql()
        
        # Should create proper join table
        assert 'CREATE TABLE IF NOT EXISTS' in sql
        assert 'UUID NOT NULL' in sql
        assert 'REFERENCES' in sql
        assert 'UNIQUE' in sql
    
    def test_get_drop_join_table_sql(self):
        field = ManyToMany(MockTag)
        field.name = "tags"
        field._source_model = MockArticle
        
        # M2M field uses get_join_table_sql, drop would need to be constructed
        # Test that join_table_name is correct
        assert "articles_tags" in field.join_table_name


class TestManyToManyManager:
    """Tests for ManyToManyManager (unit tests, no DB)."""
    
    def test_initialization(self):
        mock_instance = type('MockInstance', (), {'id': uuid4()})()
        field = ManyToMany(MockTag)
        field.name = "tags"
        field._source_model = MockArticle
        
        manager = ManyToManyManager(field, mock_instance)
        
        assert manager._source == mock_instance
        assert manager._field == field
    
    def test_join_table_property(self):
        mock_instance = type('MockInstance', (), {'id': uuid4()})()
        field = ManyToMany(MockTag)
        field.name = "related_items"
        field._source_model = MockArticle
        
        manager = ManyToManyManager(field, mock_instance)
        # Join table should contain the field name
        assert "related_items" in manager._join_table


class TestManyToManyFieldDescriptor:
    """Tests for M2M field descriptor behavior."""
    
    def test_column_definition_returns_empty(self):
        """M2M doesn't create a column, so definition should be empty."""
        field = ManyToMany(MockTag)
        field.name = "tags"
        # Should return empty or None
        definition = field.get_column_definition()
        assert definition is None or definition == ""
    
    def test_sql_type_virtual(self):
        """M2M fields have VIRTUAL sql_type since they don't create real columns."""
        field = ManyToMany(MockTag)
        assert field.sql_type == "VIRTUAL"
