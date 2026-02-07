"""
Tests for Aksara AI Route Hints

v0.5.13: Tests for the per-view/per-route AI metadata system.
"""

import pytest
from unittest.mock import MagicMock, patch

from aksara.ai.models import (
    AiRiskLevel,
    AiUsageKind,
    AiRouteHint,
    AiHintSet,
)
from aksara.ai.hints import (
    ai_route_hint,
    set_view_default_hint,
    get_ai_route_hint,
    extract_hints_from_viewset,
    extract_hints_from_app,
    build_ai_hint_set,
)


class TestAiRouteHintModel:
    """Tests for AiRouteHint model."""
    
    def test_create_minimal_hint(self):
        """Test creating a hint with minimal required fields."""
        hint = AiRouteHint(
            title="List Users",
            view_name="UserViewSet",
            route_name="list",
            path="/api/users/",
        )
        assert hint.title == "List Users"
        assert hint.view_name == "UserViewSet"
        assert hint.route_name == "list"
        assert hint.path == "/api/users/"
        assert hint.risk_level == "low"  # default
        assert hint.usage_kind == "read_only"  # default
        assert hint.description == ""
        assert hint.example_prompt is None
    
    def test_create_full_hint(self):
        """Test creating a hint with all fields."""
        hint = AiRouteHint(
            title="Delete User Account",
            description="Permanently removes a user and all associated data.",
            view_name="UserViewSet",
            route_name="destroy",
            path="/api/users/{id}/",
            methods=["DELETE"],
            usage_kind="admin",
            risk_level="high",
            example_prompt="Delete user with ID 123",
            example_input={"user_id": 123},
            example_output={"status": "deleted"},
            recommended_model="gpt-4o",
            recommended_provider="openai",
        )
        assert hint.title == "Delete User Account"
        assert hint.risk_level == "high"
        assert hint.usage_kind == "admin"
        assert hint.methods == ["DELETE"]
        assert hint.recommended_model == "gpt-4o"
        assert hint.recommended_provider == "openai"
    
    def test_risk_level_values(self):
        """Test that risk level accepts valid literals."""
        for level in ["low", "medium", "high"]:
            hint = AiRouteHint(
                title="Test",
                view_name="TestViewSet",
                route_name="action",
                path="/api/test/",
                risk_level=level,
            )
            assert hint.risk_level == level
    
    def test_usage_kind_values(self):
        """Test that usage kind accepts valid literals."""
        for kind in ["read_only", "write", "admin"]:
            hint = AiRouteHint(
                title="Test",
                view_name="TestViewSet",
                route_name="action",
                path="/api/test/",
                usage_kind=kind,
            )
            assert hint.usage_kind == kind


class TestAiHintSet:
    """Tests for AiHintSet model."""
    
    def test_create_empty_hint_set(self):
        """Test creating an empty hint set."""
        hint_set = AiHintSet(routes=[])
        assert hint_set.routes == []
        assert hint_set.total_count == 0
    
    def test_create_hint_set_with_routes(self):
        """Test creating a hint set with multiple hints."""
        routes = [
            AiRouteHint(title="List", view_name="UserViewSet", route_name="list", path="/api/users/", risk_level="low"),
            AiRouteHint(title="Create", view_name="UserViewSet", route_name="create", path="/api/users/", risk_level="medium"),
            AiRouteHint(title="Delete", view_name="UserViewSet", route_name="destroy", path="/api/users/{id}/", risk_level="high"),
        ]
        hint_set = AiHintSet(routes=routes, total_count=3, low_risk_count=1, medium_risk_count=1, high_risk_count=1)
        assert hint_set.total_count == 3
        assert hint_set.low_risk_count == 1
        assert hint_set.medium_risk_count == 1
        assert hint_set.high_risk_count == 1
    
    def test_hint_set_stats(self):
        """Test hint set stat fields."""
        hint_set = AiHintSet(
            routes=[],
            total_count=10,
            read_only_count=5,
            write_count=3,
            admin_count=2,
            low_risk_count=6,
            medium_risk_count=3,
            high_risk_count=1,
        )
        assert hint_set.read_only_count == 5
        assert hint_set.write_count == 3
        assert hint_set.admin_count == 2


class TestAiRouteHintDecorator:
    """Tests for the @ai_route_hint decorator."""
    
    def test_basic_decorator(self):
        """Test applying the decorator with basic arguments."""
        @ai_route_hint(
            title="List Items",
            description="Returns a paginated list of items.",
        )
        def list_action(self):
            pass
        
        hint = get_ai_route_hint(list_action)
        assert hint is not None
        assert hint["title"] == "List Items"
        assert hint["description"] == "Returns a paginated list of items."
        assert hint["risk_level"] == "low"  # default
        assert hint["usage_kind"] == "read_only"  # default
    
    def test_decorator_with_risk_level(self):
        """Test decorator with explicit risk level."""
        @ai_route_hint(
            title="Delete Item",
            risk_level="high",
            usage_kind="admin",
        )
        def destroy_action(self):
            pass
        
        hint = get_ai_route_hint(destroy_action)
        assert hint["risk_level"] == "high"
        assert hint["usage_kind"] == "admin"
    
    def test_decorator_with_examples(self):
        """Test decorator with example data."""
        @ai_route_hint(
            title="Create Item",
            example_prompt="Create a new item named 'Widget'",
            example_input='{"name": "Widget"}',
            example_output='{"id": 1, "name": "Widget"}',
        )
        def create_action(self):
            pass
        
        hint = get_ai_route_hint(create_action)
        assert hint["example_prompt"] == "Create a new item named 'Widget'"
        assert hint["example_input"] == '{"name": "Widget"}'
        assert hint["example_output"] == '{"id": 1, "name": "Widget"}'
    
    def test_decorator_preserves_function(self):
        """Test that decorator preserves function behavior."""
        @ai_route_hint(title="Test")
        def test_func():
            return 42
        
        assert test_func() == 42
    
    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function metadata."""
        @ai_route_hint(title="Test")
        def my_special_action():
            """My docstring."""
            pass
        
        assert my_special_action.__name__ == "my_special_action"
        assert "My docstring" in (my_special_action.__doc__ or "")


class TestViewSetHintExtraction:
    """Tests for extracting hints from viewsets."""
    
    def test_extract_hints_from_viewset_class(self):
        """Test extracting hints from a viewset class."""
        class ItemViewSet:
            @ai_route_hint(title="List Items", risk_level="low")
            def list(self):
                pass
            
            @ai_route_hint(title="Create Item", risk_level="medium", usage_kind="write")
            def create(self):
                pass
            
            def retrieve(self):
                """No hint on this action."""
                pass
        
        hints = extract_hints_from_viewset(ItemViewSet)
        assert len(hints) == 2
        
        titles = [h.title for h in hints]
        assert "List Items" in titles
        assert "Create Item" in titles
    
    def test_extract_hints_fills_view_name(self):
        """Test that extraction fills in view_name from class."""
        class ProductViewSet:
            @ai_route_hint(title="List Products")
            def list(self):
                pass
        
        hints = extract_hints_from_viewset(ProductViewSet)
        assert len(hints) == 1
        assert hints[0].view_name == "ProductViewSet"
        # route_name is derived from the viewset prefix
        assert "product" in hints[0].route_name.lower()


class TestSetViewDefaultHint:
    """Tests for set_view_default_hint helper."""
    
    def test_set_default_hint_on_class(self):
        """Test setting default hint values on a viewset class."""
        class AdminViewSet:
            def list(self):
                pass
        
        set_view_default_hint(
            AdminViewSet, 
            title="Admin API",
            risk_level="high", 
            usage_kind="admin",
        )
        
        default = getattr(AdminViewSet, "_aksara_ai_default_hint", None)
        assert default is not None
        assert default["title"] == "Admin API"
        assert default["risk_level"] == "high"
        assert default["usage_kind"] == "admin"


class TestBuildAiHintSet:
    """Tests for building complete hint sets."""
    
    def test_build_empty_hint_set(self):
        """Test building hint set with no viewsets."""
        settings = MagicMock()
        settings.app_module = None
        
        with patch('aksara.ai.hints.extract_hints_from_app', return_value=[]):
            hint_set = build_ai_hint_set(settings)
        
        assert isinstance(hint_set, AiHintSet)
        assert hint_set.total_count == 0
    
    def test_hint_set_has_stat_fields(self):
        """Test that hint set has all stat fields."""
        hint_set = AiHintSet(routes=[])
        
        # Verify all stat fields exist
        assert hasattr(hint_set, "total_count")
        assert hasattr(hint_set, "read_only_count")
        assert hasattr(hint_set, "write_count")
        assert hasattr(hint_set, "admin_count")
        assert hasattr(hint_set, "low_risk_count")
        assert hasattr(hint_set, "medium_risk_count")
        assert hasattr(hint_set, "high_risk_count")


class TestRiskLevelAndUsageKindTypes:
    """Tests for type literals."""
    
    def test_risk_level_literal_values(self):
        """Test AiRiskLevel type accepts correct values."""
        # These should work (type checking at runtime via Pydantic)
        hint = AiRouteHint(title="T", view_name="V", route_name="r", path="/", risk_level="low")
        assert hint.risk_level == "low"
        
        hint = AiRouteHint(title="T", view_name="V", route_name="r", path="/", risk_level="medium")
        assert hint.risk_level == "medium"
        
        hint = AiRouteHint(title="T", view_name="V", route_name="r", path="/", risk_level="high")
        assert hint.risk_level == "high"
    
    def test_usage_kind_literal_values(self):
        """Test AiUsageKind type accepts correct values."""
        hint = AiRouteHint(title="T", view_name="V", route_name="r", path="/", usage_kind="read_only")
        assert hint.usage_kind == "read_only"
        
        hint = AiRouteHint(title="T", view_name="V", route_name="r", path="/", usage_kind="write")
        assert hint.usage_kind == "write"
        
        hint = AiRouteHint(title="T", view_name="V", route_name="r", path="/", usage_kind="admin")
        assert hint.usage_kind == "admin"


class TestContextIntegration:
    """Tests for hints integration with AI context."""
    
    def test_ai_full_context_has_hints_fields(self):
        """Test that AiFullContext has ai_hints and ai_hint_count fields."""
        from aksara.ai.context import AiFullContext, AiRouteHintInfo
        
        # Check field exists
        assert "ai_hints" in AiFullContext.model_fields
        assert "ai_hint_count" in AiFullContext.model_fields
    
    def test_ai_route_hint_info_model(self):
        """Test AiRouteHintInfo model for context export."""
        from aksara.ai.context import AiRouteHintInfo
        
        info = AiRouteHintInfo(
            title="Test Action",
            view_name="TestViewSet",
            route_name="test",
            path="/api/test",
            methods=["GET"],
            risk_level="low",
            usage_kind="read_only",
            description="A test endpoint",
        )
        assert info.title == "Test Action"
        assert info.risk_level == "low"
        assert info.methods == ["GET"]
