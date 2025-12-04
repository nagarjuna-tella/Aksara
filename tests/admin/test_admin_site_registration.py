"""
Tests for AdminSite model registration (v0.3.15).

Tests that:
- Models can be registered with the admin site
- Double registration raises ValueError
- Models can be unregistered
- Registry can be queried by model class or name
"""

import pytest

from vidyut import Model, fields
from vidyut.registry import ModelRegistry


class TestAdminSiteRegistration:
    """Tests for AdminSite.register() and related methods."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        # Clear admin site
        from vidyut.contrib.admin import site
        site.clear()
    
    def test_register_model_simple(self):
        """Test simple model registration."""
        from vidyut.contrib.admin import site
        
        class Book(Model):
            title = fields.String()
            
            class Meta:
                app_label = "library"
        
        site.register(Book)
        
        assert site.is_registered(Book)
        assert Book in site.registry
    
    def test_register_model_with_custom_admin(self):
        """Test model registration with custom ModelAdmin."""
        from vidyut.contrib.admin import site, ModelAdmin
        
        class Article(Model):
            title = fields.String()
            body = fields.Text()
            
            class Meta:
                app_label = "blog"
        
        class ArticleAdmin(ModelAdmin):
            list_display = ["title", "created_at"]
            search_fields = ["title", "body"]
        
        site.register(Article, ArticleAdmin)
        
        assert site.is_registered(Article)
        
        model_admin = site.get_model_admin(Article)
        assert model_admin is not None
        assert isinstance(model_admin, ArticleAdmin)
        assert model_admin.list_display == ["title", "created_at"]
    
    def test_double_registration_raises_error(self):
        """Test that registering same model twice raises ValueError."""
        from vidyut.contrib.admin import site
        
        class Widget(Model):
            name = fields.String()
            
            class Meta:
                app_label = "widgets"
        
        site.register(Widget)
        
        with pytest.raises(ValueError, match="already registered"):
            site.register(Widget)
    
    def test_unregister_model(self):
        """Test model unregistration."""
        from vidyut.contrib.admin import site
        
        class Gadget(Model):
            name = fields.String()
            
            class Meta:
                app_label = "gadgets"
        
        site.register(Gadget)
        assert site.is_registered(Gadget)
        
        site.unregister(Gadget)
        assert not site.is_registered(Gadget)
    
    def test_unregister_nonexistent_model(self):
        """Test that unregistering non-registered model doesn't raise."""
        from vidyut.contrib.admin import site
        
        class Foo(Model):
            name = fields.String()
            
            class Meta:
                app_label = "foo"
        
        # Should not raise
        site.unregister(Foo)
    
    def test_get_model_admin_returns_none_for_unregistered(self):
        """Test get_model_admin returns None for unregistered model."""
        from vidyut.contrib.admin import site
        
        class Bar(Model):
            name = fields.String()
            
            class Meta:
                app_label = "bar"
        
        assert site.get_model_admin(Bar) is None
    
    def test_get_model_by_name(self):
        """Test looking up model by app_label and name."""
        from vidyut.contrib.admin import site
        
        class Post(Model):
            title = fields.String()
            
            class Meta:
                app_label = "blog"
        
        site.register(Post)
        
        # Exact match
        found = site.get_model_by_name("blog", "Post")
        assert found is Post
        
        # Case-insensitive
        found = site.get_model_by_name("blog", "post")
        assert found is Post
        
        # Not found
        found = site.get_model_by_name("blog", "NotExist")
        assert found is None
        
        # Wrong app
        found = site.get_model_by_name("other", "Post")
        assert found is None
    
    def test_get_app_list(self):
        """Test getting models grouped by app_label."""
        from vidyut.contrib.admin import site
        
        class Author(Model):
            name = fields.String()
            
            class Meta:
                app_label = "authors"
        
        class Post(Model):
            title = fields.String()
            
            class Meta:
                app_label = "blog"
        
        class Comment(Model):
            body = fields.Text()
            
            class Meta:
                app_label = "blog"
        
        site.register(Author)
        site.register(Post)
        site.register(Comment)
        
        app_list = site.get_app_list()
        
        assert "authors" in app_list
        assert "blog" in app_list
        assert len(app_list["authors"]) == 1
        assert len(app_list["blog"]) == 2
        assert Author in app_list["authors"]
        assert Post in app_list["blog"]
        assert Comment in app_list["blog"]
    
    def test_model_without_app_label_uses_default(self):
        """Test that models without app_label use 'default'."""
        from vidyut.contrib.admin import site
        
        class NoLabel(Model):
            name = fields.String()
        
        site.register(NoLabel)
        
        app_list = site.get_app_list()
        assert "default" in app_list
        assert NoLabel in app_list["default"]
        
        # Also test lookup
        found = site.get_model_by_name("default", "NoLabel")
        assert found is NoLabel
    
    def test_clear_site(self):
        """Test clearing all registrations."""
        from vidyut.contrib.admin import site
        
        class Model1(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        class Model2(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        site.register(Model1)
        site.register(Model2)
        
        assert len(site.registry) == 2
        
        site.clear()
        
        assert len(site.registry) == 0
