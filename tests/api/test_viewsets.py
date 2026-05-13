"""
Tests for ModelViewSet.

Tests:
    - ViewSet initialization
    - CRUD methods (list, retrieve, create, update, delete)
    - Pagination
    - Filtering
    - Schema generation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from aksara import Model, fields
from aksara.manager import DoesNotExist
from aksara.api.viewsets import ModelViewSet
from aksara.api.schemas import clear_schema_cache


# =============================================================================
# Test Models
# =============================================================================

class Product(Model):
    """Test model for ViewSet testing."""
    name = fields.String(max_length=100)
    price = fields.Integer(default=0)
    is_available = fields.Boolean(default=True)
    description = fields.String(max_length=1000, nullable=True)
    
    class Meta:
        table_name = "products"


class Order(Model):
    """Model with ForeignKey."""
    product = fields.ForeignKey(Product)
    quantity = fields.Integer(default=1)
    
    class Meta:
        table_name = "orders"


# =============================================================================
# Test ViewSets
# =============================================================================

class ProductViewSet(ModelViewSet):
    model = Product
    prefix = "/products"
    tags = ["Products"]


class OrderViewSet(ModelViewSet):
    model = Order
    prefix = "/orders"


class CustomViewSet(ModelViewSet):
    model = Product
    prefix = "/custom"
    default_limit = 50
    max_limit = 200


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
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.query_params = {}
    return request


@pytest.fixture
def sample_product_data():
    """Sample product data."""
    return {
        "id": uuid4(),
        "name": "Test Product",
        "price": 100,
        "is_available": True,
        "description": "A test product",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# =============================================================================
# ViewSet Initialization Tests
# =============================================================================

class TestViewSetInit:
    """Tests for ViewSet initialization."""
    
    def test_basic_init(self):
        """Test basic ViewSet initialization."""
        viewset = ProductViewSet()
        
        assert viewset.model == Product
        assert viewset.prefix == "/products"
        assert viewset.tags == ["Products"]
    
    def test_auto_prefix(self):
        """ViewSet should auto-generate prefix from model."""
        class AutoPrefixViewSet(ModelViewSet):
            model = Product
        
        viewset = AutoPrefixViewSet()
        assert viewset.prefix == "/products"
    
    def test_auto_tags(self):
        """ViewSet should auto-generate tags from model."""
        class AutoTagViewSet(ModelViewSet):
            model = Product
            prefix = "/products"
        
        viewset = AutoTagViewSet()
        assert viewset.tags == ["Product"]
    
    def test_custom_limits(self):
        """Test custom pagination limits."""
        viewset = CustomViewSet()
        
        assert viewset.default_limit == 50
        assert viewset.max_limit == 200
    
    def test_missing_model_raises(self):
        """ViewSet without model should raise."""
        class BadViewSet(ModelViewSet):
            prefix = "/bad"
        
        with pytest.raises(ValueError, match="must define 'model'"):
            BadViewSet()

    def test_is_ai_request_ignores_client_header(self, mock_request):
        """ViewSet should not trust client-controlled AI headers."""
        viewset = ProductViewSet()
        mock_request.headers = {"X-AI-Agent": "true"}
        mock_request.state.is_ai_agent = False

        assert viewset._is_ai_request(mock_request) is False

    def test_is_ai_request_uses_request_state(self, mock_request):
        """ViewSet should trust server-side AI state only."""
        viewset = ProductViewSet()
        mock_request.headers = {}
        mock_request.state.is_ai_agent = True

        assert viewset._is_ai_request(mock_request) is True


# =============================================================================
# Schema Generation Tests
# =============================================================================

class TestViewSetSchemas:
    """Tests for ViewSet schema generation."""
    
    def test_schemas_generated(self):
        """ViewSet should generate schemas on init."""
        viewset = ProductViewSet()
        
        assert viewset.create_schema is not None
        assert viewset.update_schema is not None
        assert viewset.read_schema is not None
    
    def test_create_schema_name(self):
        """Create schema should have correct name."""
        viewset = ProductViewSet()
        assert viewset.create_schema.__name__ == "ProductCreate"
    
    def test_update_schema_name(self):
        """Update schema should have correct name."""
        viewset = ProductViewSet()
        assert viewset.update_schema.__name__ == "ProductUpdate"
    
    def test_read_schema_name(self):
        """Read schema should have correct name."""
        viewset = ProductViewSet()
        assert viewset.read_schema.__name__ == "ProductRead"


# =============================================================================
# List Action Tests
# =============================================================================

class TestListAction:
    """Tests for list action."""
    
    @pytest.mark.asyncio
    async def test_list_returns_paginated(self, mock_request):
        """List should return paginated response."""
        viewset = ProductViewSet()

        # Mock the internal methods. The viewset now fetches the page and the
        # total in a single round-trip via queryset.limit().offset().fetch_with_count().
        with patch.object(viewset, 'get_queryset') as mock_get_qs:
            mock_qs = MagicMock()
            paginated_qs = MagicMock()
            paginated_qs.fetch_with_count = AsyncMock(return_value=([], 10))
            mock_qs.limit.return_value.offset.return_value = paginated_qs
            mock_get_qs.return_value = mock_qs

            result = await viewset.list(mock_request, limit=20, offset=0)

            assert "count" in result
            assert "results" in result
            assert "limit" in result
            assert "offset" in result
            assert result["count"] == 10
    
    @pytest.mark.asyncio
    async def test_list_respects_max_limit(self, mock_request):
        """List should enforce max_limit."""
        viewset = ProductViewSet()  # max_limit = 100
        
        with patch.object(viewset, '_paginate', new_callable=AsyncMock) as mock_paginate:
            mock_paginate.return_value = {"count": 0, "results": [], "limit": 100, "offset": 0}
            
            # Request more than max
            await viewset.list(mock_request, limit=1000, offset=0)
            
            # _paginate is called, limit is capped inside it
            mock_paginate.assert_called_once()


# =============================================================================
# Retrieve Action Tests
# =============================================================================

class TestRetrieveAction:
    """Tests for retrieve action."""
    
    @pytest.mark.asyncio
    async def test_retrieve_found(self, mock_request, sample_product_data):
        """Retrieve should return item when found."""
        viewset = ProductViewSet()
        pk = str(sample_product_data["id"])
        
        # Create a mock product instance
        mock_product = Product(**sample_product_data)
        mock_product._is_new = False
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_product
            
            result = await viewset.retrieve(pk=pk, request=mock_request)
            
            assert result["name"] == "Test Product"
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, mock_request):
        """Retrieve should raise 404 when not found."""
        viewset = ProductViewSet()
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = DoesNotExist("Not found")
            
            with pytest.raises(HTTPException) as exc_info:
                await viewset.retrieve(pk="nonexistent", request=mock_request)
            
            assert exc_info.value.status_code == 404


# =============================================================================
# Create Action Tests
# =============================================================================

class TestCreateAction:
    """Tests for create action."""
    
    @pytest.mark.asyncio
    async def test_create_success(self, mock_request, sample_product_data):
        """Create should return created item."""
        viewset = ProductViewSet()
        
        mock_product = Product(**sample_product_data)
        mock_product._is_new = False
        
        with patch.object(Product.objects, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_product
            
            result = await viewset.create(
                data={"name": "Test Product", "price": 100},
                request=mock_request,
            )
            
            assert result["name"] == "Test Product"
            mock_create.assert_called_once()


# =============================================================================
# Update Action Tests
# =============================================================================

class TestUpdateAction:
    """Tests for update action."""
    
    @pytest.mark.asyncio
    async def test_update_success(self, mock_request, sample_product_data):
        """Update should apply changes."""
        viewset = ProductViewSet()
        pk = str(sample_product_data["id"])
        
        mock_product = Product(**sample_product_data)
        mock_product._is_new = False
        mock_product.save = AsyncMock()
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_product
            
            result = await viewset.update(
                pk=pk,
                data={"name": "Updated Name"},
                request=mock_request,
            )
            
            # save should be called
            mock_product.save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_request):
        """Update should raise 404 when not found."""
        viewset = ProductViewSet()
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = DoesNotExist("Not found")
            
            with pytest.raises(HTTPException) as exc_info:
                await viewset.update(
                    pk="nonexistent",
                    data={"name": "New Name"},
                    request=mock_request,
                )
            
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_partial(self, mock_request, sample_product_data):
        """Update should only apply non-None values."""
        viewset = ProductViewSet()
        pk = str(sample_product_data["id"])
        
        mock_product = Product(**sample_product_data)
        mock_product._is_new = False
        mock_product.save = AsyncMock()
        original_price = mock_product.price
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_product
            
            # Only update name, not price (price=None in data)
            await viewset.update(
                pk=pk,
                data={"name": "New Name", "price": None},
                request=mock_request,
            )
            
            # price should remain unchanged
            assert mock_product.price == original_price


# =============================================================================
# Delete Action Tests
# =============================================================================

class TestDeleteAction:
    """Tests for delete action."""
    
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_request, sample_product_data):
        """Delete should remove item."""
        viewset = ProductViewSet()
        pk = str(sample_product_data["id"])
        
        mock_product = Product(**sample_product_data)
        mock_product._is_new = False
        mock_product.delete = AsyncMock()
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_product
            
            result = await viewset.delete(pk=pk, request=mock_request)
            
            assert result["deleted"] == True
            assert result["id"] == pk
            mock_product.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_request):
        """Delete should raise 404 when not found."""
        viewset = ProductViewSet()
        
        with patch.object(Product.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = DoesNotExist("Not found")
            
            with pytest.raises(HTTPException) as exc_info:
                await viewset.delete(pk="nonexistent", request=mock_request)
            
            assert exc_info.value.status_code == 404


# =============================================================================
# Get Queryset Tests
# =============================================================================

class TestGetQueryset:
    """Tests for get_queryset method."""
    
    def test_get_queryset_no_filters(self):
        """get_queryset without filters returns all."""
        viewset = ProductViewSet()
        
        queryset = viewset.get_queryset()
        
        assert queryset._model == Product
        assert queryset._filters == {}
    
    def test_get_queryset_with_filters(self):
        """get_queryset with filters applies them."""
        viewset = ProductViewSet()
        
        queryset = viewset.get_queryset(is_available=True)
        
        assert queryset._filters == {"is_available": True}
    
    def test_get_queryset_ignores_none(self):
        """get_queryset should ignore None values."""
        viewset = ProductViewSet()
        
        queryset = viewset.get_queryset(is_available=True, name=None)
        
        assert queryset._filters == {"is_available": True}
        assert "name" not in queryset._filters


# =============================================================================
# Filter Fields Tests
# =============================================================================

class TestFilterFields:
    """Tests for get_filter_fields method."""
    
    def test_filter_fields_returns_all(self):
        """get_filter_fields returns all model fields."""
        viewset = ProductViewSet()
        
        fields = viewset.get_filter_fields()
        
        assert "name" in fields
        assert "price" in fields
        assert "is_available" in fields
        assert "id" in fields


# =============================================================================
# Custom ViewSet Override Tests
# =============================================================================

class TestCustomViewSet:
    """Tests for custom ViewSet overrides."""
    
    @pytest.mark.asyncio
    async def test_custom_list(self, mock_request):
        """Custom list method should be called."""
        
        class CustomListViewSet(ModelViewSet):
            model = Product
            prefix = "/custom-list"
            
            async def list(self, request, limit, offset, **filters):
                return {"custom": True, "count": 0, "results": []}
        
        viewset = CustomListViewSet()
        result = await viewset.list(mock_request, 20, 0)
        
        assert result["custom"] == True
    
    @pytest.mark.asyncio
    async def test_custom_retrieve(self, mock_request):
        """Custom retrieve method should be called."""
        
        class CustomRetrieveViewSet(ModelViewSet):
            model = Product
            prefix = "/custom-retrieve"
            
            async def retrieve(self, pk, request):
                return {"custom": True, "pk": pk}
        
        viewset = CustomRetrieveViewSet()
        result = await viewset.retrieve("test-pk", mock_request)
        
        assert result["custom"] == True
        assert result["pk"] == "test-pk"
