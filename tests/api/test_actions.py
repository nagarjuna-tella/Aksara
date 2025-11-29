"""
Tests for Vidyut @action decorator (v0.3.1)

Tests cover:
- @action decorator metadata attachment
- Detail and collection actions
- OpenAPI/Swagger documentation
- Path parameters, query params, and body models
- Docstring fallback for summary/description
- Multiple actions coexisting
- Backward compatibility (no actions scenario)
"""

import pytest
from uuid import UUID
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from vidyut.api.actions import (
    action,
    get_action_metadata,
    is_action,
    extract_docstring_summary,
    extract_docstring_description,
)
from vidyut.api import ModelViewSet, include_viewset


# =============================================================================
# Test Fixtures
# =============================================================================

class MockModel:
    """Mock model for testing."""
    __name__ = "MockModel"
    __tablename__ = "mock_models"
    _fields = {
        "id": MagicMock(column_name="id"),
        "name": MagicMock(column_name="name"),
        "is_active": MagicMock(column_name="is_active"),
    }
    objects = MagicMock()


# =============================================================================
# Test @action Decorator
# =============================================================================

class TestActionDecorator:
    """Test the @action decorator itself."""
    
    def test_action_attaches_metadata(self):
        """Test that @action attaches _vidyut_action metadata."""
        @action(detail=True, methods=["post"])
        async def my_action(self, pk, request):
            pass
        
        assert hasattr(my_action, "_vidyut_action")
        meta = my_action._vidyut_action
        assert meta["detail"] is True
        assert meta["methods"] == ["POST"]
        assert meta["path"] == "my_action"
        assert meta["name"] == "my_action"
    
    def test_action_normalizes_methods_uppercase(self):
        """Test that HTTP methods are normalized to uppercase."""
        @action(detail=False, methods=["get", "Post", "DELETE"])
        async def multi_method(self, request):
            pass
        
        meta = multi_method._vidyut_action
        assert meta["methods"] == ["GET", "POST", "DELETE"]
    
    def test_action_with_custom_path(self):
        """Test custom path override."""
        @action(detail=True, methods=["get"], path="full-profile")
        async def get_full_profile(self, pk, request):
            pass
        
        meta = get_full_profile._vidyut_action
        assert meta["path"] == "full-profile"
        assert meta["name"] == "get_full_profile"
    
    def test_action_with_custom_name(self):
        """Test custom route name."""
        @action(detail=True, methods=["post"], name="user_deactivation")
        async def deactivate(self, pk, request):
            pass
        
        meta = deactivate._vidyut_action
        assert meta["name"] == "user_deactivation"
    
    def test_action_with_summary_and_description(self):
        """Test explicit summary and description."""
        @action(
            detail=True,
            methods=["post"],
            summary="Deactivate user",
            description="This will deactivate the user account permanently.",
        )
        async def deactivate(self, pk, request):
            pass
        
        meta = deactivate._vidyut_action
        assert meta["summary"] == "Deactivate user"
        assert meta["description"] == "This will deactivate the user account permanently."
    
    def test_action_detail_false(self):
        """Test collection action (detail=False)."""
        @action(detail=False, methods=["get"])
        async def active(self, request):
            pass
        
        meta = active._vidyut_action
        assert meta["detail"] is False
    
    def test_action_preserves_function(self):
        """Test that the decorator doesn't change function behavior."""
        @action(detail=True, methods=["post"])
        async def my_action(self, pk, request):
            return {"result": pk}
        
        # Function should still be callable
        import asyncio
        result = asyncio.run(my_action(None, "123", None))
        assert result == {"result": "123"}


class TestActionHelpers:
    """Test helper functions for action metadata."""
    
    def test_get_action_metadata_exists(self):
        """Test getting metadata from action-decorated function."""
        @action(detail=True, methods=["get"])
        async def my_action(self, pk, request):
            pass
        
        meta = get_action_metadata(my_action)
        assert meta is not None
        assert meta["detail"] is True
    
    def test_get_action_metadata_not_exists(self):
        """Test getting metadata from non-action function."""
        async def regular_function():
            pass
        
        meta = get_action_metadata(regular_function)
        assert meta is None
    
    def test_is_action_true(self):
        """Test is_action returns True for action functions."""
        @action(detail=True, methods=["post"])
        async def my_action(self, pk, request):
            pass
        
        assert is_action(my_action) is True
    
    def test_is_action_false(self):
        """Test is_action returns False for regular functions."""
        async def regular_function():
            pass
        
        assert is_action(regular_function) is False
    
    def test_extract_docstring_summary(self):
        """Test extracting first line of docstring."""
        def func_with_doc():
            """This is the summary.
            
            This is more detail.
            """
            pass
        
        summary = extract_docstring_summary(func_with_doc)
        assert summary == "This is the summary."
    
    def test_extract_docstring_summary_single_line(self):
        """Test extracting single-line docstring."""
        def func_with_doc():
            """Short summary."""
            pass
        
        summary = extract_docstring_summary(func_with_doc)
        assert summary == "Short summary."
    
    def test_extract_docstring_summary_none(self):
        """Test no docstring returns None."""
        def func_without_doc():
            pass
        
        summary = extract_docstring_summary(func_without_doc)
        assert summary is None
    
    def test_extract_docstring_description(self):
        """Test extracting full docstring."""
        def func_with_doc():
            """This is the summary.
            
            This is more detail.
            And even more.
            """
            pass
        
        desc = extract_docstring_description(func_with_doc)
        assert "This is the summary." in desc
        assert "This is more detail." in desc
        assert "And even more." in desc
    
    def test_extract_docstring_description_none(self):
        """Test no docstring returns None."""
        def func_without_doc():
            pass
        
        desc = extract_docstring_description(func_without_doc)
        assert desc is None


# =============================================================================
# Test @action Integration with ViewSet and Router
# =============================================================================

class TestActionRouting:
    """Test that @action methods are registered as routes."""
    
    @pytest.fixture
    def app_with_actions(self):
        """Create a FastAPI app with a ViewSet containing actions."""
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/items"
            tags = ["Items"]
            
            @action(detail=True, methods=["post"], summary="Activate item")
            async def activate(self, pk: str, request: Request):
                """Activate a specific item."""
                return {"status": "activated", "pk": pk}
            
            @action(detail=True, methods=["post"])
            async def deactivate(self, pk: str, request: Request):
                """
                Deactivate a specific item.
                
                This will set is_active to False.
                """
                return {"status": "deactivated", "pk": pk}
            
            @action(detail=False, methods=["get"], summary="Get active items")
            async def active(self, request: Request):
                """Return all active items."""
                return [{"id": "1", "is_active": True}]
            
            @action(detail=False, methods=["get", "post"], path="bulk-update")
            async def bulk_update(self, request: Request):
                """Perform bulk update."""
                return {"updated": 0}
        
        # Mock the CRUD operations
        with patch.object(ModelViewSet, '__init__', lambda self: None):
            viewset = TestViewSet()
            viewset.model = MockModel
            viewset.prefix = "/items"
            viewset.tags = ["Items"]
            viewset.lookup_field = "id"
            viewset.default_limit = 20
            viewset.max_limit = 100
            viewset._create_schema = MagicMock()
            viewset._update_schema = MagicMock()
            viewset._read_schema = MagicMock()
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        return app
    
    def test_detail_action_route_exists(self, app_with_actions):
        """Test that detail action creates route with pk."""
        client = TestClient(app_with_actions)
        
        response = client.post("/items/123/activate")
        assert response.status_code == 200
        assert response.json() == {"status": "activated", "pk": "123"}
    
    def test_collection_action_route_exists(self, app_with_actions):
        """Test that collection action creates route without pk."""
        client = TestClient(app_with_actions)
        
        response = client.get("/items/active")
        assert response.status_code == 200
        assert response.json() == [{"id": "1", "is_active": True}]
    
    def test_custom_path_action(self, app_with_actions):
        """Test action with custom path."""
        client = TestClient(app_with_actions)
        
        response = client.get("/items/bulk-update")
        assert response.status_code == 200
        
        response = client.post("/items/bulk-update")
        assert response.status_code == 200
    
    def test_multiple_methods_action(self, app_with_actions):
        """Test action with multiple HTTP methods."""
        client = TestClient(app_with_actions)
        
        # Both GET and POST should work
        response = client.get("/items/bulk-update")
        assert response.status_code == 200
        
        response = client.post("/items/bulk-update")
        assert response.status_code == 200


class TestActionOpenAPI:
    """Test OpenAPI/Swagger documentation for actions."""
    
    @pytest.fixture
    def app_with_openapi(self):
        """Create app for OpenAPI testing."""
        
        class DeactivateBody(BaseModel):
            reason: str | None = None
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/users"
            tags = ["Users"]
            
            @action(detail=True, methods=["post"], summary="Deactivate user")
            async def deactivate(self, pk: str, request: Request):
                """
                Deactivate a user account.
                
                This will set is_active to False and log the reason.
                """
                return {"status": "deactivated"}
            
            @action(detail=False, methods=["get"])
            async def active(self, request: Request):
                """Return all active users in the system."""
                return []
            
            @action(detail=True, methods=["get"], path="profile")
            async def get_profile(self, pk: str, request: Request):
                """Get user profile."""
                return {"pk": pk}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        return app
    
    def test_action_appears_in_openapi(self, app_with_openapi):
        """Test that actions appear in OpenAPI schema."""
        client = TestClient(app_with_openapi)
        
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi = response.json()
        paths = openapi["paths"]
        
        # Check detail action path exists
        assert "/users/{pk}/deactivate" in paths
        
        # Check collection action path exists
        assert "/users/active" in paths
        
        # Check custom path action exists
        assert "/users/{pk}/profile" in paths
    
    def test_action_has_correct_method(self, app_with_openapi):
        """Test that actions have correct HTTP method in OpenAPI."""
        client = TestClient(app_with_openapi)
        
        openapi = client.get("/openapi.json").json()
        paths = openapi["paths"]
        
        # Deactivate should be POST
        assert "post" in paths["/users/{pk}/deactivate"]
        
        # Active should be GET
        assert "get" in paths["/users/active"]
    
    def test_action_has_summary(self, app_with_openapi):
        """Test that action summary appears in OpenAPI."""
        client = TestClient(app_with_openapi)
        
        openapi = client.get("/openapi.json").json()
        
        deactivate_spec = openapi["paths"]["/users/{pk}/deactivate"]["post"]
        assert deactivate_spec["summary"] == "Deactivate user"
    
    def test_action_has_docstring_fallback(self, app_with_openapi):
        """Test that docstring is used as fallback for summary."""
        client = TestClient(app_with_openapi)
        
        openapi = client.get("/openapi.json").json()
        
        # Active action has no explicit summary, should use docstring
        active_spec = openapi["paths"]["/users/active"]["get"]
        assert "Return all active users" in active_spec["summary"]
    
    def test_action_has_description(self, app_with_openapi):
        """Test that action description appears in OpenAPI."""
        client = TestClient(app_with_openapi)
        
        openapi = client.get("/openapi.json").json()
        
        deactivate_spec = openapi["paths"]["/users/{pk}/deactivate"]["post"]
        # Description should contain the full docstring
        assert "Deactivate a user account" in deactivate_spec["description"]
    
    def test_action_has_tags(self, app_with_openapi):
        """Test that action inherits viewset tags."""
        client = TestClient(app_with_openapi)
        
        openapi = client.get("/openapi.json").json()
        
        deactivate_spec = openapi["paths"]["/users/{pk}/deactivate"]["post"]
        assert "Users" in deactivate_spec["tags"]
    
    def test_action_path_params_in_openapi(self, app_with_openapi):
        """Test that path parameters appear in OpenAPI."""
        client = TestClient(app_with_openapi)
        
        openapi = client.get("/openapi.json").json()
        
        deactivate_spec = openapi["paths"]["/users/{pk}/deactivate"]["post"]
        params = deactivate_spec.get("parameters", [])
        
        # Should have pk path parameter
        pk_params = [p for p in params if p["name"] == "pk"]
        assert len(pk_params) == 1
        assert pk_params[0]["in"] == "path"


class TestActionWithBody:
    """Test actions with request body."""
    
    def test_action_with_body_model(self):
        """Test action that accepts a Pydantic body."""
        
        class ApprovalBody(BaseModel):
            approved: bool
            notes: str | None = None
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/invoices"
            tags = ["Invoices"]
            
            @action(detail=True, methods=["post"], summary="Approve invoice")
            async def approve(self, pk: str, body: ApprovalBody, request: Request):
                """Approve or reject an invoice."""
                return {"pk": pk, "approved": body.approved, "notes": body.notes}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        response = client.post(
            "/invoices/123/approve",
            json={"approved": True, "notes": "Looks good"}
        )
        assert response.status_code == 200
        assert response.json() == {
            "pk": "123",
            "approved": True,
            "notes": "Looks good"
        }
    
    def test_action_body_in_openapi(self):
        """Test that body model appears in OpenAPI."""
        
        class ApprovalBody(BaseModel):
            approved: bool
            notes: str | None = None
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/invoices"
            tags = ["Invoices"]
            
            @action(detail=True, methods=["post"])
            async def approve(self, pk: str, body: ApprovalBody, request: Request):
                """Approve invoice."""
                return {}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        openapi = client.get("/openapi.json").json()
        
        approve_spec = openapi["paths"]["/invoices/{pk}/approve"]["post"]
        
        # Should have a requestBody
        assert "requestBody" in approve_spec


class TestNoActionsScenario:
    """Test that ViewSets without actions work normally."""
    
    def test_viewset_without_actions(self):
        """Test that ViewSet without @action works as before."""
        
        class PlainViewSet(ModelViewSet):
            model = MockModel
            prefix = "/plain"
            tags = ["Plain"]
            # No @action methods
        
        app = FastAPI()
        include_viewset(app, PlainViewSet)
        client = TestClient(app)
        
        openapi = client.get("/openapi.json").json()
        paths = openapi["paths"]
        
        # Should have standard CRUD routes
        assert "/plain/" in paths
        assert "/plain/{pk}" in paths
        
        # Should NOT have any unexpected routes
        plain_routes = [p for p in paths if p.startswith("/plain")]
        assert len(plain_routes) == 2  # list/create and retrieve/update/delete


class TestMultipleActionsCoexist:
    """Test multiple @action methods on same ViewSet."""
    
    def test_multiple_detail_actions(self):
        """Test multiple detail actions coexist."""
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/items"
            tags = ["Items"]
            
            @action(detail=True, methods=["post"])
            async def action_one(self, pk: str, request: Request):
                return {"action": "one", "pk": pk}
            
            @action(detail=True, methods=["post"])
            async def action_two(self, pk: str, request: Request):
                return {"action": "two", "pk": pk}
            
            @action(detail=True, methods=["get"])
            async def action_three(self, pk: str, request: Request):
                return {"action": "three", "pk": pk}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        # All actions should work
        r1 = client.post("/items/123/action_one")
        assert r1.status_code == 200
        assert r1.json()["action"] == "one"
        
        r2 = client.post("/items/123/action_two")
        assert r2.status_code == 200
        assert r2.json()["action"] == "two"
        
        r3 = client.get("/items/123/action_three")
        assert r3.status_code == 200
        assert r3.json()["action"] == "three"
    
    def test_mix_detail_and_collection_actions(self):
        """Test mix of detail and collection actions."""
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/items"
            tags = ["Items"]
            
            @action(detail=True, methods=["post"])
            async def detail_action(self, pk: str, request: Request):
                return {"type": "detail", "pk": pk}
            
            @action(detail=False, methods=["get"])
            async def collection_action(self, request: Request):
                return {"type": "collection"}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        openapi = client.get("/openapi.json").json()
        paths = openapi["paths"]
        
        # Both should exist
        assert "/items/{pk}/detail_action" in paths
        assert "/items/collection_action" in paths
        
        # Both should work
        r1 = client.post("/items/123/detail_action")
        assert r1.json()["type"] == "detail"
        
        r2 = client.get("/items/collection_action")
        assert r2.json()["type"] == "collection"


class TestActionEdgeCases:
    """Test edge cases for @action."""
    
    def test_action_with_query_params(self):
        """Test action with query parameters."""
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/items"
            tags = ["Items"]
            
            @action(detail=False, methods=["get"])
            async def search(self, request: Request, q: str = "", limit: int = 10):
                """Search items."""
                return {"query": q, "limit": limit}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        response = client.get("/items/search?q=test&limit=5")
        assert response.status_code == 200
        assert response.json() == {"query": "test", "limit": 5}
    
    def test_action_with_uuid_pk(self):
        """Test action with UUID path parameter."""
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/items"
            tags = ["Items"]
            
            @action(detail=True, methods=["get"])
            async def details(self, pk: UUID, request: Request):
                """Get item details."""
                return {"pk": str(pk)}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/items/{uuid_str}/details")
        assert response.status_code == 200
        assert response.json()["pk"] == uuid_str
    
    def test_action_with_hyphenated_path(self):
        """Test action with hyphenated custom path."""
        
        class TestViewSet(ModelViewSet):
            model = MockModel
            prefix = "/items"
            tags = ["Items"]
            
            @action(detail=True, methods=["post"], path="mark-as-complete")
            async def mark_complete(self, pk: str, request: Request):
                """Mark item as complete."""
                return {"marked": True}
        
        app = FastAPI()
        include_viewset(app, TestViewSet)
        client = TestClient(app)
        
        response = client.post("/items/123/mark-as-complete")
        assert response.status_code == 200
        assert response.json()["marked"] is True
