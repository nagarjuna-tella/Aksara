"""
Tests for Multitenant Example Pattern

Tests the multitenant example app structure and imports.
"""

import pytest
import importlib
import sys
from pathlib import Path


# Add examples to path
examples_path = Path(__file__).parent.parent.parent / "examples"
if str(examples_path) not in sys.path:
    sys.path.insert(0, str(examples_path))


class TestMultitenantExampleStructure:
    """Test multitenant example has correct structure."""
    
    def test_multitenant_package_exists(self):
        """Multitenant example should be importable."""
        spec = importlib.util.find_spec("multitenant")
        assert spec is not None, "multitenant package should exist"
    
    def test_multitenant_models_importable(self):
        """Multitenant models should be importable."""
        from multitenant import models
        assert hasattr(models, "Tenant")
        assert hasattr(models, "User")
        assert hasattr(models, "Project")
    
    def test_multitenant_middleware_importable(self):
        """Multitenant middleware should be importable."""
        from multitenant import middleware
        assert hasattr(middleware, "TenantMiddleware")
        assert hasattr(middleware, "get_current_tenant")
        assert hasattr(middleware, "current_tenant")
    
    def test_multitenant_serializers_importable(self):
        """Multitenant serializers should be importable."""
        from multitenant import serializers
        assert hasattr(serializers, "TenantSerializer")
        assert hasattr(serializers, "UserSerializer")
        assert hasattr(serializers, "ProjectSerializer")
    
    def test_multitenant_views_importable(self):
        """Multitenant views should be importable."""
        from multitenant import views
        assert hasattr(views, "TenantViewSet")
        assert hasattr(views, "UserViewSet")
        assert hasattr(views, "ProjectViewSet")
    
    def test_multitenant_admin_importable(self):
        """Multitenant admin should be importable."""
        from multitenant import admin
        assert hasattr(admin, "TenantAdmin")
        assert hasattr(admin, "UserAdmin")
        assert hasattr(admin, "ProjectAdmin")


class TestMultitenantModels:
    """Test multitenant model definitions."""
    
    def test_tenant_model_fields(self):
        """Tenant model should have correct fields."""
        from multitenant.models import Tenant
        
        assert hasattr(Tenant, "Meta")
        assert Tenant.Meta.table_name == "tenants"
        
        # Check required fields
        assert hasattr(Tenant, "name")
        assert hasattr(Tenant, "slug")
        assert hasattr(Tenant, "domain")
        assert hasattr(Tenant, "plan")
        assert hasattr(Tenant, "is_active")
    
    def test_user_model_fields(self):
        """User model should have correct fields."""
        from multitenant.models import User
        
        assert hasattr(User, "Meta")
        assert User.Meta.table_name == "tenant_users"
        
        # Check required fields
        assert hasattr(User, "tenant")  # FK to Tenant
        assert hasattr(User, "email")
        assert hasattr(User, "name")
        assert hasattr(User, "role")
    
    def test_project_model_fields(self):
        """Project model should have correct fields."""
        from multitenant.models import Project
        
        assert hasattr(Project, "Meta")
        assert Project.Meta.table_name == "projects"
        
        # Check required fields
        assert hasattr(Project, "tenant")  # FK to Tenant
        assert hasattr(Project, "name")
        assert hasattr(Project, "description")
        assert hasattr(Project, "is_public")


class TestMultitenantMiddleware:
    """Test multitenant middleware definitions."""
    
    def test_current_tenant_context_var(self):
        """current_tenant should be a ContextVar."""
        from multitenant.middleware import current_tenant
        from contextvars import ContextVar
        
        assert isinstance(current_tenant, ContextVar)
    
    def test_get_current_tenant_function(self):
        """get_current_tenant should be a callable."""
        from multitenant.middleware import get_current_tenant
        
        assert callable(get_current_tenant)
        # Should return None when no tenant is set
        assert get_current_tenant() is None
    
    def test_tenant_middleware_class(self):
        """TenantMiddleware should exist and be a class."""
        from multitenant.middleware import TenantMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware
        
        assert issubclass(TenantMiddleware, BaseHTTPMiddleware)
        assert hasattr(TenantMiddleware, "dispatch")


class TestMultitenantViewSets:
    """Test multitenant ViewSet definitions."""
    
    def test_tenant_viewset_config(self):
        """TenantViewSet should have correct configuration."""
        from multitenant.views import TenantViewSet
        from multitenant.models import Tenant
        
        assert TenantViewSet.model == Tenant
        assert TenantViewSet.prefix == "/api/tenants"
    
    def test_user_viewset_config(self):
        """UserViewSet should have correct configuration."""
        from multitenant.views import UserViewSet
        from multitenant.models import User
        
        assert UserViewSet.model == User
        assert UserViewSet.prefix == "/api/users"
    
    def test_user_viewset_has_scoped_queryset(self):
        """UserViewSet should have get_queryset method."""
        from multitenant.views import UserViewSet
        
        assert hasattr(UserViewSet, "get_queryset")
    
    def test_project_viewset_config(self):
        """ProjectViewSet should have correct configuration."""
        from multitenant.views import ProjectViewSet
        from multitenant.models import Project
        
        assert ProjectViewSet.model == Project
        assert ProjectViewSet.prefix == "/api/projects"
    
    def test_project_viewset_has_scoped_queryset(self):
        """ProjectViewSet should have get_queryset method."""
        from multitenant.views import ProjectViewSet
        
        assert hasattr(ProjectViewSet, "get_queryset")


class TestMultitenantFiles:
    """Test multitenant example file structure."""
    
    def test_readme_exists(self):
        """README.md should exist."""
        readme = examples_path / "multitenant" / "README.md"
        assert readme.exists(), "multitenant/README.md should exist"
    
    def test_main_exists(self):
        """main.py should exist."""
        main = examples_path / "multitenant" / "main.py"
        assert main.exists(), "multitenant/main.py should exist"
    
    def test_middleware_exists(self):
        """middleware.py should exist."""
        middleware = examples_path / "multitenant" / "middleware.py"
        assert middleware.exists(), "multitenant/middleware.py should exist"
    
    def test_settings_exists(self):
        """settings.py should exist."""
        settings = examples_path / "multitenant" / "settings.py"
        assert settings.exists(), "multitenant/settings.py should exist"
    
    def test_migrations_folder_exists(self):
        """migrations folder should exist."""
        migrations = examples_path / "multitenant" / "migrations"
        assert migrations.exists(), "multitenant/migrations/ should exist"
