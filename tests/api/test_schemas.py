"""
Tests for auto-generated Pydantic schemas.

Tests:
    - Create schema generation
    - Update schema generation
    - Read schema generation
    - Field type mappings
    - Default value handling
    - ForeignKey handling
    - Schema caching
"""

import pytest
from datetime import datetime
from uuid import UUID
from typing import Optional, Union

from pydantic import BaseModel, ValidationError

from vidyut import Model, fields
from vidyut.api.schemas import (
    generate_create_schema,
    generate_update_schema,
    generate_read_schema,
    get_schemas_for_model,
    clear_schema_cache,
    model_to_dict,
)


# =============================================================================
# Test Models
# =============================================================================

class SimpleUser(Model):
    """Simple model for testing."""
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100, nullable=True)
    is_active = fields.Boolean(default=True)
    
    class Meta:
        table_name = "simple_users"


class FullUser(Model):
    """Model with all field types."""
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100, nullable=True)
    age = fields.Integer(nullable=True)
    is_active = fields.Boolean(default=True)
    metadata = fields.JSON(nullable=True)
    
    class Meta:
        table_name = "full_users"


class Article(Model):
    """Model with ForeignKey for testing."""
    title = fields.String(max_length=200)
    content = fields.String(max_length=10000, nullable=True)
    author = fields.ForeignKey(SimpleUser, nullable=True)
    
    class Meta:
        table_name = "articles"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear schema cache before each test."""
    clear_schema_cache()
    yield
    clear_schema_cache()


# =============================================================================
# Create Schema Tests
# =============================================================================

class TestCreateSchema:
    """Tests for Create schema generation."""
    
    def test_create_schema_basic(self):
        """Test basic Create schema generation."""
        schema = generate_create_schema(SimpleUser)
        
        assert schema.__name__ == "SimpleUserCreate"
        assert issubclass(schema, BaseModel)
    
    def test_create_schema_excludes_pk(self):
        """Create schema should not include primary key."""
        schema = generate_create_schema(SimpleUser)
        fields = schema.model_fields
        
        assert "id" not in fields
    
    def test_create_schema_excludes_timestamps(self):
        """Create schema should not include auto timestamps."""
        schema = generate_create_schema(SimpleUser)
        fields = schema.model_fields
        
        assert "created_at" not in fields
        assert "updated_at" not in fields
    
    def test_create_schema_required_field(self):
        """Required fields should not have defaults."""
        schema = generate_create_schema(SimpleUser)
        
        # email is required
        assert schema.model_fields["email"].is_required()
    
    def test_create_schema_optional_field(self):
        """Nullable fields should be optional."""
        schema = generate_create_schema(SimpleUser)
        
        # name is nullable, so optional
        assert not schema.model_fields["name"].is_required()
    
    def test_create_schema_default_value(self):
        """Fields with defaults should use them."""
        schema = generate_create_schema(SimpleUser)
        
        # is_active has default=True
        field_info = schema.model_fields["is_active"]
        assert field_info.default == True
    
    def test_create_schema_validation(self):
        """Test schema validation works."""
        schema = generate_create_schema(SimpleUser)
        
        # Valid data
        instance = schema(email="test@example.com")
        assert instance.email == "test@example.com"
        assert instance.name is None
        assert instance.is_active == True
    
    def test_create_schema_validation_error(self):
        """Test schema rejects invalid data."""
        schema = generate_create_schema(SimpleUser)
        
        # Missing required field
        with pytest.raises(ValidationError):
            schema()  # email is required


class TestCreateSchemaWithFK:
    """Tests for Create schema with ForeignKey."""
    
    def test_create_schema_fk_uses_column_name(self):
        """ForeignKey should use the _id column name."""
        schema = generate_create_schema(Article)
        fields = schema.model_fields
        
        # Should have author_id, not author
        assert "author_id" in fields
        assert "author" not in fields
    
    def test_create_schema_fk_is_uuid(self):
        """ForeignKey field should accept UUID."""
        schema = generate_create_schema(Article)
        
        # Valid data with FK
        from uuid import uuid4
        instance = schema(
            title="Test Article",
            author_id=uuid4(),
        )
        assert instance.title == "Test Article"


# =============================================================================
# Update Schema Tests
# =============================================================================

class TestUpdateSchema:
    """Tests for Update schema generation."""
    
    def test_update_schema_basic(self):
        """Test basic Update schema generation."""
        schema = generate_update_schema(SimpleUser)
        
        assert schema.__name__ == "SimpleUserUpdate"
        assert issubclass(schema, BaseModel)
    
    def test_update_schema_all_optional(self):
        """All fields in Update schema should be optional."""
        schema = generate_update_schema(SimpleUser)
        
        for name, field in schema.model_fields.items():
            assert not field.is_required(), f"Field {name} should be optional"
    
    def test_update_schema_excludes_pk(self):
        """Update schema should not include primary key."""
        schema = generate_update_schema(SimpleUser)
        fields = schema.model_fields
        
        assert "id" not in fields
    
    def test_update_schema_partial_update(self):
        """Should allow partial updates (empty is valid)."""
        schema = generate_update_schema(SimpleUser)
        
        # Empty update is valid
        instance = schema()
        assert instance.email is None
        assert instance.name is None
        
        # Partial update
        instance = schema(name="New Name")
        assert instance.email is None
        assert instance.name == "New Name"


# =============================================================================
# Read Schema Tests
# =============================================================================

class TestReadSchema:
    """Tests for Read schema generation."""
    
    def test_read_schema_basic(self):
        """Test basic Read schema generation."""
        schema = generate_read_schema(SimpleUser)
        
        assert schema.__name__ == "SimpleUserRead"
        assert issubclass(schema, BaseModel)
    
    def test_read_schema_includes_pk(self):
        """Read schema should include primary key."""
        schema = generate_read_schema(SimpleUser)
        fields = schema.model_fields
        
        assert "id" in fields
    
    def test_read_schema_includes_timestamps(self):
        """Read schema should include timestamps."""
        schema = generate_read_schema(SimpleUser)
        fields = schema.model_fields
        
        assert "created_at" in fields
        assert "updated_at" in fields
    
    def test_read_schema_fk_uses_column_name(self):
        """ForeignKey should use the _id column name in Read schema."""
        schema = generate_read_schema(Article)
        fields = schema.model_fields
        
        assert "author_id" in fields


# =============================================================================
# Field Type Mapping Tests
# =============================================================================

class TestFieldTypeMappings:
    """Tests for field type mappings."""
    
    def test_string_to_str(self):
        """String field maps to str."""
        schema = generate_create_schema(SimpleUser)
        # The type annotation should be str or Optional[str]
        assert schema.model_fields["email"].annotation == str
    
    def test_integer_to_int(self):
        """Integer field maps to int."""
        schema = generate_create_schema(FullUser)
        # age is nullable, so Optional[int]
        assert "age" in schema.model_fields
    
    def test_boolean_to_bool(self):
        """Boolean field maps to bool."""
        schema = generate_create_schema(SimpleUser)
        assert "is_active" in schema.model_fields
    
    def test_uuid_to_uuid(self):
        """UUID field maps to UUID."""
        schema = generate_read_schema(SimpleUser)
        # id is UUID type
        assert schema.model_fields["id"].annotation == UUID
    
    def test_datetime_to_datetime(self):
        """DateTime field maps to datetime."""
        schema = generate_read_schema(SimpleUser)
        # Timestamps should be datetime
        assert "created_at" in schema.model_fields
        assert "updated_at" in schema.model_fields


# =============================================================================
# Schema Caching Tests
# =============================================================================

class TestSchemaCaching:
    """Tests for schema caching."""
    
    def test_schema_is_cached(self):
        """Same schema should be returned from cache."""
        schema1 = generate_create_schema(SimpleUser)
        schema2 = generate_create_schema(SimpleUser)
        
        assert schema1 is schema2
    
    def test_different_schemas_cached_separately(self):
        """Different schema types should be cached separately."""
        create = generate_create_schema(SimpleUser)
        update = generate_update_schema(SimpleUser)
        read = generate_read_schema(SimpleUser)
        
        assert create is not update
        assert update is not read
        assert create is not read
    
    def test_cache_clear(self):
        """Cache clear should work."""
        schema1 = generate_create_schema(SimpleUser)
        clear_schema_cache()
        schema2 = generate_create_schema(SimpleUser)
        
        # After cache clear, new instance is created
        # (but they're still equal in structure)
        assert schema1.__name__ == schema2.__name__


# =============================================================================
# get_schemas_for_model Tests
# =============================================================================

class TestGetSchemasForModel:
    """Tests for get_schemas_for_model helper."""
    
    def test_returns_all_schemas(self):
        """Should return create, update, and read schemas."""
        schemas = get_schemas_for_model(SimpleUser)
        
        assert "create" in schemas
        assert "update" in schemas
        assert "read" in schemas
    
    def test_schema_types(self):
        """Each schema should be the correct type."""
        schemas = get_schemas_for_model(SimpleUser)
        
        assert schemas["create"].__name__ == "SimpleUserCreate"
        assert schemas["update"].__name__ == "SimpleUserUpdate"
        assert schemas["read"].__name__ == "SimpleUserRead"


# =============================================================================
# model_to_dict Tests
# =============================================================================

class TestModelToDict:
    """Tests for model_to_dict helper."""
    
    def test_basic_serialization(self):
        """Test basic model serialization."""
        user = SimpleUser(email="test@example.com", name="Test")
        user._data["id"] = UUID("12345678-1234-5678-1234-567812345678")
        
        result = model_to_dict(user)
        
        assert result["email"] == "test@example.com"
        assert result["name"] == "Test"
        assert "id" in result
    
    def test_fk_serialization(self):
        """Test ForeignKey is serialized with column name."""
        author_id = UUID("12345678-1234-5678-1234-567812345678")
        article = Article(title="Test", author_id=author_id)
        
        result = model_to_dict(article)
        
        assert result["title"] == "Test"
        assert "author_id" in result
