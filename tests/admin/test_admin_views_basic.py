"""
Tests for admin views basic functionality (v0.3.15).

Tests that:
- Admin index shows registered apps and models
- App index shows models for an app
- Model list shows objects
- Model forms render correctly
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from starlette.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from aksara import Model, fields, Aksara
from aksara.registry import ModelRegistry


def create_staff_middleware():
    """Create middleware that injects a staff user."""
    class StaffUserMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            user = MagicMock()
            user.is_staff = True
            user.email = "admin@test.com"
            user.id = "test-user-id"
            request.state.user = user
            return await call_next(request)
    return StaffUserMiddleware


class TestAdminIndexView:
    """Tests for admin index view."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()
    
    def test_admin_index_shows_registered_models(self):
        """Test that admin index shows registered models."""
        from aksara.contrib.admin import site
        
        class Author(Model):
            name = fields.String()
            
            class Meta:
                app_label = "blog"
        
        class Post(Model):
            title = fields.String()
            
            class Meta:
                app_label = "blog"
        
        site.register(Author)
        site.register(Post)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        client = TestClient(app)
        response = client.get("/admin/")
        
        assert response.status_code == 200
        assert "blog" in response.text
        assert "Author" in response.text
        assert "Post" in response.text
    
    def test_admin_index_empty_when_no_models(self):
        """Test admin index shows empty state when no models registered."""
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        client = TestClient(app)
        response = client.get("/admin/")
        
        assert response.status_code == 200
        assert "No models registered" in response.text


class TestAdminAppIndexView:
    """Tests for admin app index view."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()
    
    def test_app_index_shows_app_models(self):
        """Test that app index shows all models for an app."""
        from aksara.contrib.admin import site
        
        class Product(Model):
            name = fields.String()
            
            class Meta:
                app_label = "shop"
        
        class Order(Model):
            total = fields.Integer()
            
            class Meta:
                app_label = "shop"
        
        site.register(Product)
        site.register(Order)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        client = TestClient(app)
        response = client.get("/admin/shop/")
        
        assert response.status_code == 200
        assert "Product" in response.text
        assert "Order" in response.text
    
    def test_app_index_404_for_unknown_app(self):
        """Test that app index returns 404 for unknown app."""
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/admin/nonexistent/")
        
        assert response.status_code == 404


class TestAdminModelListView:
    """Tests for admin model list view."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()
    
    def test_model_list_view_renders(self):
        """Test that model list view renders correctly."""
        from aksara.contrib.admin import site, ModelAdmin
        
        class Item(Model):
            name = fields.String()
            price = fields.Integer()
            
            class Meta:
                app_label = "inventory"
        
        class ItemAdmin(ModelAdmin):
            list_display = ["name", "price"]
        
        site.register(Item, ItemAdmin)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        # Mock the queryset to return empty list
        with patch.object(ItemAdmin, 'get_queryset', new_callable=AsyncMock) as mock_qs:
            mock_queryset = MagicMock()
            mock_queryset.all = AsyncMock(return_value=[])
            mock_qs.return_value = mock_queryset
            
            client = TestClient(app)
            response = client.get("/admin/inventory/item/")
            
            assert response.status_code == 200
            assert "Item" in response.text
            assert "Add Item" in response.text
    
    def test_model_list_404_for_unknown_model(self):
        """Test that model list returns 404 for unknown model."""
        from aksara.contrib.admin import site
        
        class KnownModel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "myapp"
        
        site.register(KnownModel)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/admin/myapp/unknownmodel/")
        
        assert response.status_code == 404


class TestAdminModelFormView:
    """Tests for admin model add/change forms."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()
    
    def test_model_add_form_renders(self):
        """Test that model add form renders correctly."""
        from aksara.contrib.admin import site
        
        class Article(Model):
            title = fields.String()
            body = fields.Text()
            
            class Meta:
                app_label = "content"
        
        site.register(Article)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        app.add_middleware(create_staff_middleware())
        
        client = TestClient(app)
        response = client.get("/admin/content/article/add/")
        
        assert response.status_code == 200
        assert "Add Article" in response.text
        assert 'name="title"' in response.text
        assert 'name="body"' in response.text


class TestModelAdminConfiguration:
    """Tests for ModelAdmin field configuration."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
    
    def test_get_list_display_default(self):
        """Test default list_display auto-picks fields."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            name = fields.String()
            email = fields.Email()
            age = fields.Integer()
        
        admin = ModelAdmin(TestModel, None)
        request = MagicMock()
        
        display = admin.get_list_display(request)
        
        # Should have id first, then up to 3 other fields
        assert display[0] == "id"
        assert len(display) <= 4
    
    def test_get_list_display_custom(self):
        """Test custom list_display is used."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            name = fields.String()
            email = fields.Email()
        
        class CustomAdmin(ModelAdmin):
            list_display = ["name", "email"]
        
        admin = CustomAdmin(TestModel, None)
        request = MagicMock()
        
        display = admin.get_list_display(request)
        
        assert display == ["name", "email"]
    
    def test_get_form_fields_excludes_pk(self):
        """Test form_fields excludes primary key."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            name = fields.String()
        
        admin = ModelAdmin(TestModel, None)
        request = MagicMock()
        
        form_fields = admin.get_form_fields(request)
        
        assert "id" not in form_fields
        assert "name" in form_fields
    
    def test_get_form_fields_excludes_readonly(self):
        """Test form_fields excludes readonly fields."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            name = fields.String()
            secret = fields.String()
        
        class CustomAdmin(ModelAdmin):
            readonly_fields = ["secret"]
        
        admin = CustomAdmin(TestModel, None)
        request = MagicMock()
        
        form_fields = admin.get_form_fields(request)
        
        assert "name" in form_fields
        assert "secret" not in form_fields
    
    def test_get_field_type_mapping(self):
        """Test field type to HTML input type mapping."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            email_field = fields.Email()
            int_field = fields.Integer()
            bool_field = fields.Boolean()
            text_field = fields.Text()
        
        admin = ModelAdmin(TestModel, None)
        
        assert admin.get_field_type("email_field") == "email"
        assert admin.get_field_type("int_field") == "number"
        assert admin.get_field_type("bool_field") == "checkbox"
        assert admin.get_field_type("text_field") == "textarea"
        assert admin.get_field_type("unknown") == "text"
