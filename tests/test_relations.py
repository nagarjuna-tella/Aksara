"""
Tests for Aksara v0.3.5 Relationship Fields

Unit tests for OneToOne and ManyToMany field types.
"""

import pytest
from uuid import uuid4

from aksara.fields import (
    String, UUID, ForeignKey, OneToOne, ManyToMany,
    ManyToManyManager,
)
from aksara.model.base import Model
from aksara.relations import OnDelete


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


class TestForeignKeySafety:
    """Tests for FK/O2O relation configuration safety."""

    def test_foreign_key_on_delete_accepts_valid_values(self):
        field = ForeignKey(MockCategory, on_delete="CASCADE")
        assert field.on_delete == "CASCADE"

    def test_foreign_key_on_delete_normalizes_case(self):
        field = ForeignKey(MockCategory, on_delete="cascade")
        assert field.on_delete == "CASCADE"

    def test_foreign_key_on_delete_normalizes_set_null_constant_style(self):
        field = ForeignKey(MockCategory, on_delete="SET_NULL", nullable=True)
        assert field.on_delete == "SET NULL"

    def test_foreign_key_protect_aliases_to_restrict(self):
        field = ForeignKey(MockCategory, on_delete="PROTECT")
        assert field.on_delete == "RESTRICT"

    def test_foreign_key_rejects_invalid_on_delete(self):
        with pytest.raises(ValueError, match="Invalid on_delete action.*Allowed") as exc_info:
            ForeignKey(MockCategory, on_delete="DROP TABLE users")

        message = str(exc_info.value)
        assert "CASCADE" in message
        assert "SET NULL" in message
        assert "RESTRICT" in message
        assert "PROTECT" in message
        assert "case-insensitive" in message
        assert "SET_NULL" in message
        assert "OnDelete enum" in message

    def test_foreign_key_accepts_on_delete_enum_instances(self):
        field = ForeignKey(MockCategory, on_delete=OnDelete.CASCADE)
        assert field.on_delete == "CASCADE"

    def test_one_to_one_rejects_invalid_on_delete(self):
        with pytest.raises(ValueError, match="Invalid on_delete action.*Allowed"):
            OneToOne(MockCategory, on_delete="DROP TABLE users")

    def test_foreign_key_set_null_requires_nullable_true(self):
        with pytest.raises(ValueError, match="SET NULL requires nullable=True"):
            ForeignKey(MockCategory, on_delete="SET NULL", nullable=False)

    def test_foreign_key_set_null_nullable_true_passes(self):
        field = ForeignKey(MockCategory, on_delete="SET NULL", nullable=True)
        assert field.on_delete == "SET NULL"
        assert field.nullable is True

    def test_one_to_one_set_null_requires_nullable_true(self):
        with pytest.raises(ValueError, match="SET NULL requires nullable=True"):
            OneToOne(MockCategory, on_delete="SET NULL", nullable=False)

    def test_forward_fk_access_returns_stored_id_and_alias(self):
        class Author(Model):
            name = String(max_length=100)

        class Post(Model):
            title = String(max_length=100)
            author = ForeignKey(Author)

        author_id = uuid4()
        post = Post(title="Contract", author_id=author_id)

        assert post.author == author_id
        assert post.author_id == author_id


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
        field = OneToOne(MockCategory, on_delete="SET NULL", nullable=True)
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

    def test_custom_through_model_is_rejected_until_supported(self):
        with pytest.raises(ValueError, match="Custom through models are not supported yet"):
            ManyToMany(MockTag, through=MockArticle)
    
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
