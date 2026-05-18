"""
Tests for router utilities.

Tests:
    - include_viewset function
    - Route generation
    - Exception handling
    - Filter extraction
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, Request
from fastapi.testclient import TestClient

from aksara import Model, fields
from aksara.api.viewsets import ModelViewSet
from aksara.api.router import include_viewset, _extract_filters, _handle_exception
from aksara.api.schemas import clear_schema_cache
from aksara.exceptions import UniqueConstraintError, ForeignKeyConstraintError, DatabaseError


# =============================================================================
# Test Models
# =============================================================================

class Item(Model):
    """Test model for router testing."""
    name = fields.String(max_length=100)
    quantity = fields.Integer(default=0)
    is_active = fields.Boolean(default=True)
    
    class Meta:
        table_name = "items"


class ItemViewSet(ModelViewSet):
    model = Item
    prefix = "/items"
    tags = ["Items"]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear schema cache before each test."""
    clear_schema_cache()
    yield
    clear_schema_cache()


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    return FastAPI()


@pytest.fixture
def router():
    """Create a test router."""
    return APIRouter()


@pytest.fixture
def sample_item():
    """Create a sample item."""
    item = Item(name="Test Item", quantity=10)
    item._data["id"] = uuid4()
    item._data["created_at"] = datetime.now(timezone.utc)
    item._data["updated_at"] = datetime.now(timezone.utc)
    item._is_new = False
    return item


# =============================================================================
# Route Generation Tests
# =============================================================================

class TestIncludeViewSet:
    """Tests for include_viewset function."""
    
    def test_routes_created(self, app):
        """include_viewset should create all CRUD routes."""
        include_viewset(app, ItemViewSet)
        
        routes = [route.path for route in app.routes]
        
        assert "/items/" in routes
        assert "/items/{pk}" in routes
    
    def test_route_methods(self, app):
        """Routes should have correct HTTP methods."""
        include_viewset(app, ItemViewSet)
        
        # Collect all methods per path
        route_methods = {}
        for route in app.routes:
            if hasattr(route, 'methods'):
                path = route.path
                if path not in route_methods:
                    route_methods[path] = set()
                route_methods[path].update(route.methods)
        
        # List and Create share /items/ path
        items_methods = route_methods.get("/items/", set())
        assert "GET" in items_methods
        assert "POST" in items_methods
        
        # Retrieve, Update, Delete share /items/{pk}
        pk_methods = route_methods.get("/items/{pk}", set())
        assert "GET" in pk_methods
        assert "PATCH" in pk_methods
        assert "DELETE" in pk_methods
    
    def test_works_with_router(self, router, app):
        """Should work with APIRouter, not just FastAPI app."""
        include_viewset(router, ItemViewSet)
        app.include_router(router)
        
        routes = [route.path for route in app.routes]
        assert "/items/" in routes


# =============================================================================
# Integration Tests with TestClient
# =============================================================================

class TestRouterIntegration:
    """Integration tests using TestClient."""
    
    def test_list_endpoint(self, app, sample_item):
        """Test list endpoint integration."""
        # Patch at module level before include_viewset runs.
        # Results must satisfy the published Read schema now that the
        # list endpoint declares response_model=Paginated{Model}Read.
        with patch('aksara.api.viewsets.ModelViewSet.list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {
                "count": 1,
                "limit": 20,
                "offset": 0,
                "results": [
                    {
                        "id": str(uuid4()),
                        "name": "Test",
                        "quantity": 10,
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                ],
            }

            include_viewset(app, ItemViewSet)
            client = TestClient(app)
            response = client.get("/items/")

            assert response.status_code == 200
            data = response.json()
            assert "count" in data
            assert "results" in data
    
    def test_retrieve_endpoint(self, app, sample_item):
        """Test retrieve endpoint integration."""
        pk = str(uuid4())
        
        with patch('aksara.api.viewsets.ModelViewSet.retrieve', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = {
                "id": pk,
                "name": "Test",
                "quantity": 10,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            
            include_viewset(app, ItemViewSet)
            client = TestClient(app)
            response = client.get(f"/items/{pk}")
            
            assert response.status_code == 200
    
    def test_create_endpoint(self, app, sample_item):
        """Test create endpoint integration."""
        with patch('aksara.api.viewsets.ModelViewSet.create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "id": str(uuid4()),
                "name": "New Item",
                "quantity": 5,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            
            include_viewset(app, ItemViewSet)
            client = TestClient(app)
            response = client.post("/items/", json={"name": "New Item"})
            
            assert response.status_code == 201
    
    def test_update_endpoint(self, app, sample_item):
        """Test update endpoint integration."""
        pk = str(uuid4())
        
        with patch('aksara.api.viewsets.ModelViewSet.update', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {
                "id": pk,
                "name": "Updated",
                "quantity": 10,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            
            include_viewset(app, ItemViewSet)
            client = TestClient(app)
            response = client.patch(f"/items/{pk}", json={"name": "Updated"})
            
            assert response.status_code == 200
    
    def test_delete_endpoint(self, app, sample_item):
        """Test delete endpoint integration."""
        pk = str(uuid4())
        
        with patch('aksara.api.viewsets.ModelViewSet.delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"deleted": True, "id": pk}
            
            include_viewset(app, ItemViewSet)
            client = TestClient(app)
            response = client.delete(f"/items/{pk}")
            
            assert response.status_code == 200
            assert response.json()["deleted"] == True


# =============================================================================
# Filter Extraction Tests
# =============================================================================

class TestFilterExtraction:
    """Tests for _extract_filters function."""
    
    def test_extract_basic_filter(self):
        """Extract basic filter from query params."""
        request = MagicMock(spec=Request)
        request.query_params = {"name": "Test", "is_active": "true"}
        
        filters = _extract_filters(request, ["name", "is_active", "quantity"])
        
        assert "name" in filters
        assert filters["name"] == "Test"
    
    def test_extract_lookup_filter(self):
        """Extract lookup filter from query params."""
        request = MagicMock(spec=Request)
        request.query_params = {"name__icontains": "test", "quantity__gte": "5"}
        
        filters = _extract_filters(request, ["name", "quantity"])
        
        assert "name__icontains" in filters
        assert "quantity__gte" in filters
    
    def test_ignore_pagination_params(self):
        """Should ignore limit and offset."""
        request = MagicMock(spec=Request)
        request.query_params = {"limit": "10", "offset": "0", "name": "Test"}
        
        filters = _extract_filters(request, ["name", "limit", "offset"])
        
        assert "limit" not in filters
        assert "offset" not in filters
        assert "name" in filters
    
    def test_ignore_unknown_fields(self):
        """Should ignore fields not in allowed list."""
        request = MagicMock(spec=Request)
        request.query_params = {"name": "Test", "unknown_field": "value"}
        
        filters = _extract_filters(request, ["name", "quantity"])
        
        assert "name" in filters
        assert "unknown_field" not in filters


# =============================================================================
# Exception Handling Tests
# =============================================================================

class TestExceptionHandling:
    """Tests for exception handling."""
    
    def test_unique_constraint_returns_409(self):
        """UniqueConstraintError should return 409."""
        exc = UniqueConstraintError(field_name="email")
        
        with pytest.raises(Exception) as exc_info:
            _handle_exception(exc)
        
        assert exc_info.value.status_code == 409
    
    def test_foreign_key_returns_400(self):
        """ForeignKeyConstraintError should return 400."""
        exc = ForeignKeyConstraintError(message="FK violated")
        
        with pytest.raises(Exception) as exc_info:
            _handle_exception(exc)
        
        assert exc_info.value.status_code == 400
    
    def test_database_error_returns_500(self):
        """DatabaseError should return 500."""
        exc = DatabaseError(message="DB error")
        
        with pytest.raises(Exception) as exc_info:
            _handle_exception(exc)
        
        assert exc_info.value.status_code == 500
    
    def test_unknown_exception_reraises(self):
        """Unknown exceptions should be re-raised."""
        exc = ValueError("Unknown error")
        
        with pytest.raises(ValueError):
            _handle_exception(exc)


# =============================================================================
# Pagination Tests via Integration
# =============================================================================

class TestPaginationIntegration:
    """Tests for pagination via integration."""
    
    def test_pagination_params(self, app):
        """Test pagination query params."""
        include_viewset(app, ItemViewSet)
        
        with patch.object(ItemViewSet, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {"count": 0, "limit": 10, "offset": 5, "results": []}
            
            client = TestClient(app)
            response = client.get("/items/?limit=10&offset=5")
            
            # Verify list was called with correct params
            call_args = mock_list.call_args
            assert call_args.kwargs["limit"] == 10
            assert call_args.kwargs["offset"] == 5
    
    def test_default_pagination(self, app):
        """Test default pagination values."""
        include_viewset(app, ItemViewSet)
        
        with patch.object(ItemViewSet, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {"count": 0, "limit": 20, "offset": 0, "results": []}
            
            client = TestClient(app)
            response = client.get("/items/")
            
            call_args = mock_list.call_args
            assert call_args.kwargs["limit"] == 20  # default_limit
            assert call_args.kwargs["offset"] == 0


# =============================================================================
# Tags and Documentation Tests
# =============================================================================

class TestTagsAndDocs:
    """Tests for tags and documentation."""
    
    def test_routes_have_tags(self, app):
        """Routes should have correct tags."""
        include_viewset(app, ItemViewSet)
        
        for route in app.routes:
            if hasattr(route, 'tags') and route.path.startswith("/items"):
                assert "Items" in route.tags
    
    def test_routes_have_summary(self, app):
        """Routes should have summaries."""
        include_viewset(app, ItemViewSet)
        
        for route in app.routes:
            if hasattr(route, 'summary') and route.path.startswith("/items"):
                assert route.summary is not None
