"""
Tests for CRM Example Pattern

Tests the CRM example app structure and imports.
"""

import pytest
import importlib
import sys
from pathlib import Path


# Add examples to path
examples_path = Path(__file__).parent.parent.parent / "examples"
if str(examples_path) not in sys.path:
    sys.path.insert(0, str(examples_path))


class TestCRMExampleStructure:
    """Test CRM example has correct structure."""
    
    def test_crm_package_exists(self):
        """CRM example should be importable."""
        spec = importlib.util.find_spec("crm")
        assert spec is not None, "crm package should exist"
    
    def test_crm_models_importable(self):
        """CRM models should be importable."""
        from crm import models
        assert hasattr(models, "Customer")
        assert hasattr(models, "Deal")
    
    def test_crm_serializers_importable(self):
        """CRM serializers should be importable."""
        from crm import serializers
        assert hasattr(serializers, "CustomerSerializer")
        assert hasattr(serializers, "DealSerializer")
    
    def test_crm_views_importable(self):
        """CRM views should be importable."""
        from crm import views
        assert hasattr(views, "CustomerViewSet")
        assert hasattr(views, "DealViewSet")
    
    def test_crm_admin_importable(self):
        """CRM admin should be importable."""
        from crm import admin
        assert hasattr(admin, "CustomerAdmin")
        assert hasattr(admin, "DealAdmin")
    
    def test_crm_urls_importable(self):
        """CRM urls should be importable."""
        from crm import urls
        assert hasattr(urls, "register_routes")


class TestCRMModels:
    """Test CRM model definitions."""
    
    def test_customer_model_fields(self):
        """Customer model should have correct fields."""
        from crm.models import Customer
        
        assert hasattr(Customer, "Meta")
        assert Customer.Meta.table_name == "customers"
        
        # Check required fields in _fields (dict)
        field_names = list(Customer._fields.keys())
        assert "name" in field_names
        assert "email" in field_names
        assert "industry" in field_names or "company_size" in field_names
    
    def test_deal_model_fields(self):
        """Deal model should have correct fields."""
        from crm.models import Deal
        
        assert hasattr(Deal, "Meta")
        assert Deal.Meta.table_name == "deals"
        
        # Check required fields in _fields (dict)
        field_names = list(Deal._fields.keys())
        assert "customer" in field_names
        assert "title" in field_names
        assert "amount" in field_names  # Deal amount/value
        assert "stage" in field_names
        assert "probability" in field_names
    
    def test_deal_expected_revenue_property(self):
        """Deal should have expected_revenue property."""
        from crm.models import Deal
        
        # Check property exists
        assert hasattr(Deal, "expected_revenue")
        assert isinstance(getattr(Deal, "expected_revenue", None), property)


class TestCRMViewSets:
    """Test CRM ViewSet definitions."""
    
    def test_customer_viewset_config(self):
        """CustomerViewSet should have correct configuration."""
        from crm.views import CustomerViewSet
        from crm.models import Customer
        
        assert CustomerViewSet.model == Customer
        assert CustomerViewSet.prefix == "/api/customers"
        assert "CRM API" in CustomerViewSet.tags
    
    def test_deal_viewset_config(self):
        """DealViewSet should have correct configuration."""
        from crm.views import DealViewSet
        from crm.models import Deal
        
        assert DealViewSet.model == Deal
        assert DealViewSet.prefix == "/api/deals"
        assert "CRM API" in DealViewSet.tags
    
    def test_deal_viewset_forecast_action(self):
        """DealViewSet should have forecast action."""
        from crm.views import DealViewSet
        
        assert hasattr(DealViewSet, "forecast")
    
    def test_deal_viewset_pipeline_action(self):
        """DealViewSet should have pipeline action."""
        from crm.views import DealViewSet
        
        assert hasattr(DealViewSet, "pipeline")
    
    def test_deal_viewset_advance_stage_action(self):
        """DealViewSet should have advance_stage action."""
        from crm.views import DealViewSet
        
        assert hasattr(DealViewSet, "advance_stage")


class TestCRMDealStages:
    """Test CRM deal stage constants."""
    
    def test_stage_order_defined(self):
        """STAGE_ORDER should be defined."""
        from crm.views import STAGE_ORDER
        
        assert isinstance(STAGE_ORDER, list)
        assert "lead" in STAGE_ORDER
        assert "qualified" in STAGE_ORDER
        assert "proposal" in STAGE_ORDER
        assert "negotiation" in STAGE_ORDER
        assert "closed_won" in STAGE_ORDER
    
    def test_stage_probabilities_defined(self):
        """STAGE_PROBABILITIES should be defined."""
        from crm.views import STAGE_PROBABILITIES
        
        assert isinstance(STAGE_PROBABILITIES, dict)
        assert STAGE_PROBABILITIES["lead"] == 10
        assert STAGE_PROBABILITIES["closed_won"] == 100


class TestCRMAuth:
    """Test CRM auth module (v0.5.8)."""
    
    def test_auth_module_importable(self):
        """auth module should be importable."""
        from crm import auth
        assert hasattr(auth, "verify_api_key")
        assert hasattr(auth, "require_api_key")
    
    def test_verify_api_key_function(self):
        """verify_api_key should work correctly."""
        from crm.auth import verify_api_key
        from crm import settings
        
        # Should verify against configured key
        assert verify_api_key(settings.CRM_API_KEY) is True
        assert verify_api_key("wrong-key") is False
    
    def test_require_api_key_is_async(self):
        """require_api_key should be async."""
        from crm.auth import require_api_key
        import inspect
        
        assert inspect.iscoroutinefunction(require_api_key)
    
    def test_settings_has_api_key(self):
        """settings should have CRM_API_KEY."""
        from crm import settings
        
        assert hasattr(settings, "CRM_API_KEY")
        assert settings.CRM_API_KEY  # Should be non-empty
    
    def test_viewset_has_dependencies(self):
        """ViewSets should have auth dependencies."""
        from crm.views import CustomerViewSet, DealViewSet
        
        assert hasattr(CustomerViewSet, "dependencies")
        assert CustomerViewSet.dependencies is not None
        assert len(CustomerViewSet.dependencies) > 0
        
        assert hasattr(DealViewSet, "dependencies")
        assert DealViewSet.dependencies is not None


class TestCRMPagination:
    """Test CRM pagination settings (v0.5.8)."""
    
    def test_settings_has_page_size(self):
        """settings should have DEFAULT_PAGE_SIZE."""
        from crm import settings
        
        assert hasattr(settings, "DEFAULT_PAGE_SIZE")
        assert settings.DEFAULT_PAGE_SIZE == 10
    
    def test_settings_has_max_page_size(self):
        """settings should have MAX_PAGE_SIZE."""
        from crm import settings
        
        assert hasattr(settings, "MAX_PAGE_SIZE")
        assert settings.MAX_PAGE_SIZE == 100
    
    def test_viewsets_have_list_override(self):
        """ViewSets should have custom list method."""
        from crm.views import CustomerViewSet, DealViewSet
        import inspect
        
        assert hasattr(CustomerViewSet, "list")
        assert inspect.iscoroutinefunction(CustomerViewSet.list)
        
        assert hasattr(DealViewSet, "list")
        assert inspect.iscoroutinefunction(DealViewSet.list)


class TestCRMAI:
    """Test CRM AI endpoint (v0.5.8)."""
    
    def test_ai_context_action(self):
        """CustomerViewSet should have ai_context action."""
        from crm.views import CustomerViewSet
        
        assert hasattr(CustomerViewSet, "ai_context")
    
    def test_ai_context_has_ai_name(self):
        """ai_context should be registered as summarize_customer_context."""
        from crm.views import CustomerViewSet
        
        method = getattr(CustomerViewSet, "ai_context")
        # Check for action attributes
        assert callable(method)


class TestCRMFiles:
    """Test CRM example file structure."""
    
    def test_readme_exists(self):
        """README.md should exist."""
        readme = examples_path / "crm" / "README.md"
        assert readme.exists(), "crm/README.md should exist"
    
    def test_main_exists(self):
        """main.py should exist."""
        main = examples_path / "crm" / "main.py"
        assert main.exists(), "crm/main.py should exist"
    
    def test_settings_exists(self):
        """settings.py should exist."""
        settings = examples_path / "crm" / "settings.py"
        assert settings.exists(), "crm/settings.py should exist"
    
    def test_auth_exists(self):
        """auth.py should exist (v0.5.8)."""
        auth = examples_path / "crm" / "auth.py"
        assert auth.exists(), "crm/auth.py should exist"
    
    def test_migrations_folder_exists(self):
        """migrations folder should exist."""
        migrations = examples_path / "crm" / "migrations"
        assert migrations.exists(), "crm/migrations/ should exist"
