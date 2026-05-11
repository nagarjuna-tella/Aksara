"""
Tests for Aksara Models

Unit tests for model definition, registry, and SQL generation.
"""

import pytest
from aksara import Model, fields
from aksara.registry import ModelRegistry
from aksara.relations import RelationRegistry


# Clear registry before tests
@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the model registry before each test."""
    ModelRegistry.clear()
    RelationRegistry.clear()
    yield
    ModelRegistry.clear()
    RelationRegistry.clear()


class TestModelDefinition:
    """Tests for model class definition."""
    
    def test_model_gets_table_name(self):
        class User(Model):
            email = fields.String()
        
        assert User.__tablename__ == "users"
    
    def test_model_snake_case_pluralization(self):
        class BlogPost(Model):
            title = fields.String()
        
        assert BlogPost.__tablename__ == "blog_posts"
    
    def test_model_ends_with_y_pluralization(self):
        class Category(Model):
            name = fields.String()
        
        assert Category.__tablename__ == "categories"
    
    def test_model_ends_with_s_pluralization(self):
        class Address(Model):
            street = fields.String()
        
        assert Address.__tablename__ == "addresses"
    
    def test_custom_table_name(self):
        class CustomModel(Model):
            __tablename__ = "my_custom_table"
            name = fields.String()
        
        assert CustomModel.__tablename__ == "my_custom_table"
    
    def test_model_has_default_id_field(self):
        class User(Model):
            email = fields.String()
        
        assert "id" in User._fields
        assert User._fields["id"].primary_key is True
    
    def test_model_has_default_timestamps(self):
        class User(Model):
            email = fields.String()
        
        assert "created_at" in User._fields
        assert "updated_at" in User._fields
    
    def test_model_field_name_assignment(self):
        class User(Model):
            email = fields.String()
            name = fields.String()
        
        assert User._fields["email"].name == "email"
        assert User._fields["name"].name == "name"
    
    def test_model_registered(self):
        class TestRegisteredModel(Model):
            name = fields.String()
        
        assert "TestRegisteredModel" in ModelRegistry.all()

    def test_generic_foreign_key_adds_support_fields(self):
        class Activity(Model):
            label = fields.String()
            subject = fields.GenericForeignKey()

        assert "content_type_id" in Activity._fields
        assert "object_id" in Activity._fields
        assert "subject" in Activity._generic_fk_fields


class TestModelInstance:
    """Tests for model instance creation and attributes."""
    
    def test_model_instance_creation(self):
        class User(Model):
            email = fields.String()
            name = fields.String(nullable=True)
        
        user = User(email="test@example.com", name="Test")
        assert user.email == "test@example.com"
        assert user.name == "Test"
    
    def test_model_instance_with_defaults(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        user = User(email="test@example.com")
        assert user.is_active is True
    
    def test_model_instance_override_default(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        user = User(email="test@example.com", is_active=False)
        assert user.is_active is False
    
    def test_model_instance_attribute_setting(self):
        class User(Model):
            email = fields.String()
            name = fields.String(nullable=True)
        
        user = User(email="test@example.com")
        user.name = "Updated Name"
        assert user.name == "Updated Name"
    
    def test_model_instance_is_new(self):
        class User(Model):
            email = fields.String()
        
        user = User(email="test@example.com")
        assert user._is_new is True
    
    def test_model_to_dict(self):
        class User(Model):
            email = fields.String()
            is_active = fields.Boolean(default=True)
        
        user = User(email="test@example.com")
        data = user.to_dict()
        
        assert data["email"] == "test@example.com"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_model_repr(self):
        class User(Model):
            email = fields.String()
        
        user = User(email="test@example.com")
        repr_str = repr(user)
        assert "User" in repr_str


class TestModelSQLGeneration:
    """Tests for CREATE TABLE SQL generation."""
    
    def test_simple_model_sql(self):
        class SimpleModel(Model):
            name = fields.String(max_length=100)
        
        sql = SimpleModel.get_create_table_sql()
        
        # Table names are quoted to handle SQL reserved words
        assert 'CREATE TABLE IF NOT EXISTS "simple_models"' in sql
        assert "id UUID PRIMARY KEY" in sql
        assert "name VARCHAR(100) NOT NULL" in sql
        assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
        assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    
    def test_model_with_all_field_types(self):
        class CompleteModel(Model):
            text = fields.String(max_length=200)
            number = fields.Integer()
            flag = fields.Boolean(default=True)
            data = fields.JSON(nullable=True)
        
        sql = CompleteModel.get_create_table_sql()
        
        assert "VARCHAR(200)" in sql
        assert "INTEGER" in sql
        assert "BOOLEAN" in sql
        assert "JSONB" in sql
    
    def test_model_with_unique_field(self):
        class UniqueModel(Model):
            email = fields.String(unique=True)
        
        sql = UniqueModel.get_create_table_sql()
        assert "UNIQUE" in sql
    
    def test_model_with_nullable_field(self):
        class NullableModel(Model):
            optional = fields.String(nullable=True)
        
        sql = NullableModel.get_create_table_sql()
        # The optional field should not have NOT NULL
        assert "optional VARCHAR(255)" in sql


class TestModelRegistry:
    """Tests for the model registry."""
    
    def test_registry_stores_models(self):
        class RegisteredModel(Model):
            name = fields.String()
        
        assert ModelRegistry.get("RegisteredModel") == RegisteredModel
    
    def test_registry_all_returns_read_only_view(self):
        class Model1(Model):
            name = fields.String()

        all_models = ModelRegistry.all()
        # all() returns a read-only mapping view of the live registry.
        with pytest.raises(TypeError):
            all_models["fake"] = None

        # snapshot() returns a mutable copy for callers that need stability.
        snapshot = ModelRegistry.snapshot()
        snapshot["fake"] = None
        assert "fake" not in ModelRegistry.all()
    
    def test_registry_clear(self):
        class ModelToClear(Model):
            name = fields.String()
        
        ModelRegistry.clear()
        assert len(ModelRegistry.all()) == 0
    
    def test_registry_get_raises_on_missing(self):
        with pytest.raises(KeyError):
            ModelRegistry.get("NonExistentModel")
