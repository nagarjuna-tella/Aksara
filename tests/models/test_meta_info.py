"""
Tests for Model.meta introspection (v0.3.14).

Tests that:
- Model.meta.name returns the model class name
- Model.meta.table_name returns the correct table name
- Model.meta.fields returns all field objects
- Model.meta.pk returns the primary key field
- Model.meta.relations contains FK/M2M fields
- Model.meta.to_dict() returns a complete dict
"""

import pytest
from typing import Dict, Any

from aksara import Model, fields
from aksara.fields import ForeignKey, ManyToMany
from aksara.registry import ModelRegistry


class TestModelMetaInfo:
    """Tests for ModelMetaInfo introspection."""
    
    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()
    
    def test_meta_name(self):
        """Test that meta.name returns the model class name."""
        class User(Model):
            email = fields.String(max_length=255)
        
        assert User.meta.name == "User"
    
    def test_meta_table_name(self):
        """Test that meta.table_name returns the correct table name."""
        class User(Model):
            email = fields.String(max_length=255)
        
        # Default pluralization
        assert User.meta.table_name == "users"
        
        # Custom table name
        class CustomModel(Model):
            __tablename__ = "my_custom_table"
            name = fields.String()
        
        assert CustomModel.meta.table_name == "my_custom_table"
    
    def test_meta_app_label(self):
        """Test that meta.app_label returns the value from Meta class or auto-detects."""
        class NoAppLabel(Model):
            name = fields.String()
        
        # Auto-detects from module path (test_meta_info module)
        assert NoAppLabel.meta.app_label == "test_meta_info"
        
        class WithAppLabel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "myapp"
        
        # Explicit app_label takes precedence
        assert WithAppLabel.meta.app_label == "myapp"
    
    def test_meta_fields(self):
        """Test that meta.fields returns all field objects."""
        class User(Model):
            email = fields.String(max_length=255)
            name = fields.String(max_length=100, nullable=True)
            is_active = fields.Boolean(default=True)
        
        field_list = User.meta.fields
        field_names = [f.name for f in field_list]
        
        # Should include custom fields + auto-generated id, created_at, updated_at
        assert "id" in field_names
        assert "email" in field_names
        assert "name" in field_names
        assert "is_active" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names
    
    def test_meta_field_names(self):
        """Test that meta.field_names returns all field names."""
        class User(Model):
            email = fields.String(max_length=255)
            name = fields.String(max_length=100)
        
        names = User.meta.field_names
        
        assert "id" in names
        assert "email" in names
        assert "name" in names
    
    def test_meta_pk(self):
        """Test that meta.pk returns the primary key field."""
        class User(Model):
            email = fields.String(max_length=255)
        
        pk = User.meta.pk
        assert pk is not None
        assert pk.name == "id"
        assert pk.primary_key is True
    
    def test_meta_pk_name(self):
        """Test that meta.pk_name returns the primary key field name."""
        class User(Model):
            email = fields.String(max_length=255)
        
        assert User.meta.pk_name == "id"
    
    def test_meta_relations_with_fk(self):
        """Test that meta.relations contains ForeignKey fields."""
        class Author(Model):
            name = fields.String()
        
        class Post(Model):
            title = fields.String()
            author = ForeignKey(Author)
        
        relations = Post.meta.relations
        
        assert "author" in relations
        assert isinstance(relations["author"], ForeignKey)
    
    def test_meta_relations_with_m2m(self):
        """Test that meta.relations contains ManyToMany fields."""
        class Tag(Model):
            name = fields.String()
        
        class Article(Model):
            title = fields.String()
            tags = ManyToMany(Tag)
        
        relations = Article.meta.relations
        
        assert "tags" in relations
        assert isinstance(relations["tags"], ManyToMany)
    
    def test_meta_foreign_keys(self):
        """Test that meta.foreign_keys returns only FK fields."""
        class Category(Model):
            name = fields.String()
        
        class Product(Model):
            name = fields.String()
            category = ForeignKey(Category)
        
        fks = Product.meta.foreign_keys
        
        assert "category" in fks
        assert len(fks) == 1
    
    def test_meta_many_to_many(self):
        """Test that meta.many_to_many returns only M2M fields."""
        class Tag(Model):
            name = fields.String()
        
        class Post(Model):
            title = fields.String()
            tags = ManyToMany(Tag)
        
        m2m = Post.meta.many_to_many
        
        assert "tags" in m2m
        assert len(m2m) == 1
    
    def test_meta_get_field(self):
        """Test that meta.get_field returns a specific field."""
        class User(Model):
            email = fields.String(max_length=255)
            name = fields.String(max_length=100)
        
        email_field = User.meta.get_field("email")
        assert email_field is not None
        assert email_field.name == "email"
        
        # Non-existent field
        assert User.meta.get_field("nonexistent") is None
    
    def test_meta_has_field(self):
        """Test that meta.has_field checks field existence."""
        class User(Model):
            email = fields.String(max_length=255)
        
        assert User.meta.has_field("email") is True
        assert User.meta.has_field("id") is True
        assert User.meta.has_field("nonexistent") is False
    
    def test_meta_to_dict_basic(self):
        """Test that meta.to_dict returns a complete dict."""
        class User(Model):
            email = fields.String(max_length=255, unique=True)
            name = fields.String(max_length=100, nullable=True)
        
        d = User.meta.to_dict()
        
        assert d["name"] == "User"
        assert d["table_name"] == "users"
        assert d["pk"] == "id"
        assert isinstance(d["fields"], list)
        assert isinstance(d["relations"], dict)
        
        # Check field representation
        field_names = [f["name"] for f in d["fields"]]
        assert "id" in field_names
        assert "email" in field_names
        assert "name" in field_names
    
    def test_meta_to_dict_with_relations(self):
        """Test that meta.to_dict includes relation metadata."""
        class Author(Model):
            name = fields.String()
        
        class Tag(Model):
            name = fields.String()
        
        class Post(Model):
            title = fields.String()
            author = ForeignKey(Author, related_name="posts")
            tags = ManyToMany(Tag, related_name="posts")
        
        d = Post.meta.to_dict()
        
        assert "author" in d["relations"]
        assert "tags" in d["relations"]
        
        # FK should have related_model
        author_rel = d["relations"]["author"]
        assert author_rel["type"] == "ForeignKey"
        assert author_rel["related_model"] == "Author"
        
        # M2M should have related_model
        tags_rel = d["relations"]["tags"]
        assert tags_rel["type"] == "ManyToMany"
        assert tags_rel["related_model"] == "Tag"
    
    def test_meta_to_dict_field_details(self):
        """Test that field dicts have all expected keys."""
        class User(Model):
            email = fields.String(max_length=255, unique=True)
            age = fields.Integer(nullable=True, default=0)
        
        d = User.meta.to_dict()
        
        # Find the email field
        email_field = next(f for f in d["fields"] if f["name"] == "email")
        
        assert "column_name" in email_field
        assert "type" in email_field
        assert "null" in email_field
        assert "unique" in email_field
        assert "primary_key" in email_field
        
        assert email_field["unique"] is True
        assert email_field["null"] is False
    
    def test_meta_repr(self):
        """Test that ModelMetaInfo has a useful repr."""
        class User(Model):
            email = fields.String()
        
        repr_str = repr(User.meta)
        assert "ModelMetaInfo" in repr_str
        assert "User" in repr_str


class TestModelMetaInfoInheritance:
    """Tests for Model.meta with inheritance."""
    
    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()
    
    def test_meta_on_inherited_model(self):
        """Test that inherited models have their own meta."""
        class BaseModel(Model):
            __abstract__ = True
            name = fields.String()
        
        class User(BaseModel):
            email = fields.String()
        
        assert User.meta.name == "User"
        assert User.meta.has_field("name")  # Inherited
        assert User.meta.has_field("email")  # Own field
