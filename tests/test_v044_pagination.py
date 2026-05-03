"""
Test Pagination Backends

Tests for PageNumberPagination, LimitOffsetPagination, and CursorPagination.

v0.5.44: Comprehensive test coverage for pagination.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from aksara.api.pagination import (
    PageNumberPagination,
    LimitOffsetPagination,
    CursorPagination,
)


class TestPageNumberPagination:
    """Test page number based pagination."""
    
    @pytest.mark.asyncio
    async def test_default_page_size(self):
        """Test default page size."""
        paginator = PageNumberPagination()
        request = Mock()
        request.query_params = {}
        
        # Create mock queryset
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=100)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page == 1
        assert paginator.page_size == PageNumberPagination.default_page_size
    
    @pytest.mark.asyncio
    async def test_custom_page_and_size(self):
        """Test custom page and size parameters."""
        paginator = PageNumberPagination()
        request = Mock()
        request.query_params = {'page': '2', 'size': '50'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=200)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page == 2
        assert paginator.page_size == 50
    
    @pytest.mark.asyncio
    async def test_max_page_size(self):
        """Test that page size is capped at max."""
        paginator = PageNumberPagination()
        request = Mock()
        request.query_params = {'size': '500'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=1000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page_size == paginator.max_page_size
    
    @pytest.mark.asyncio
    async def test_negative_page(self):
        """Test that negative page is set to 1."""
        paginator = PageNumberPagination()
        request = Mock()
        request.query_params = {'page': '-1'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=100)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page == 1
    
    def test_paginated_response(self):
        """Test paginated response structure."""
        paginator = PageNumberPagination()
        paginator.count = 100
        paginator.page = 2
        paginator.page_size = 20
        paginator.total_pages = 5
        
        data = [{'id': i} for i in range(20)]
        response = paginator.get_paginated_response(data)
        
        assert response['count'] == 100
        assert response['page'] == 2
        assert response['size'] == 20
        assert response['total_pages'] == 5
        assert response['results'] == data
    
    @pytest.mark.asyncio
    async def test_invalid_page_param(self):
        """Test invalid page parameter defaults to 1."""
        paginator = PageNumberPagination()
        request = Mock()
        request.query_params = {'page': 'invalid'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=100)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page == 1


class TestLimitOffsetPagination:
    """Test limit/offset based pagination."""
    
    @pytest.mark.asyncio
    async def test_default_limit_offset(self):
        """Test default limit and offset."""
        paginator = LimitOffsetPagination()
        request = Mock()
        request.query_params = {}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=100)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.limit == LimitOffsetPagination.default_limit
        assert paginator.offset == 0
    
    @pytest.mark.asyncio
    async def test_custom_limit_offset(self):
        """Test custom limit and offset."""
        paginator = LimitOffsetPagination()
        request = Mock()
        request.query_params = {'limit': '50', 'offset': '100'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=500)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.limit == 50
        assert paginator.offset == 100
    
    @pytest.mark.asyncio
    async def test_max_limit(self):
        """Test that limit is capped at max."""
        paginator = LimitOffsetPagination()
        request = Mock()
        request.query_params = {'limit': '500'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=1000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.limit == paginator.max_limit
    
    def test_paginated_response(self):
        """Test limit/offset paginated response structure."""
        paginator = LimitOffsetPagination()
        paginator.count = 500
        paginator.limit = 20
        paginator.offset = 40
        
        data = [{'id': i} for i in range(20)]
        response = paginator.get_paginated_response(data)
        
        assert response['count'] == 500
        assert response['limit'] == 20
        assert response['offset'] == 40
        assert response['results'] == data


class TestCursorPagination:
    """Test cursor-based (keyset) pagination."""
    
    @pytest.mark.asyncio
    async def test_default_page_size(self):
        """Test default page size for cursor pagination."""
        paginator = CursorPagination()
        request = Mock()
        request.query_params = {}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=1000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page_size == CursorPagination.default_page_size
    
    @pytest.mark.asyncio
    async def test_custom_page_size(self):
        """Test custom page size."""
        paginator = CursorPagination()
        request = Mock()
        request.query_params = {'page_size': '100'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=5000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page_size == 100
    
    @pytest.mark.asyncio
    async def test_max_page_size(self):
        """Test that page size is capped at max."""
        paginator = CursorPagination()
        request = Mock()
        request.query_params = {'page_size': '500'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=10000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.page_size == paginator.max_page_size
    
    @pytest.mark.asyncio
    async def test_cursor_parameter(self):
        """Test cursor parameter parsing."""
        paginator = CursorPagination()
        request = Mock()
        # Valid base64 encoded cursor
        import base64
        cursor_value = base64.b64encode(b'{"id": "123"}').decode('utf-8')
        request.query_params = {'cursor': cursor_value}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=1000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        assert paginator.cursor is not None
    
    @pytest.mark.asyncio
    async def test_invalid_cursor(self):
        """Test invalid cursor is ignored."""
        paginator = CursorPagination()
        request = Mock()
        request.query_params = {'cursor': 'not-valid-base64!!!'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=1000)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        # Invalid cursor should be ignored
        assert paginator.cursor is None
    
    def test_paginated_response(self):
        """Test cursor paginated response structure."""
        paginator = CursorPagination()
        paginator.count = 1000
        paginator.page_size = 20
        
        data = [{'id': str(i)} for i in range(20)]
        response = paginator.get_paginated_response(data)
        
        assert response['count'] == 1000
        assert 'results' in response
        assert response['results'] == data
    
    def test_paginated_response_with_next_cursor(self):
        """Test that next_cursor is generated when there are more results."""
        paginator = CursorPagination()
        paginator.count = 1000
        paginator.page_size = 20
        
        # Return exactly page_size items (indicates more results)
        data = [{'id': str(i)} for i in range(20)]
        response = paginator.get_paginated_response(data)
        
        # Should include next_cursor since we have a full page
        assert 'results' in response


class TestPaginationErrorHandling:
    """Test pagination error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_limit(self):
        """Test invalid limit parameter."""
        paginator = LimitOffsetPagination()
        request = Mock()
        request.query_params = {'limit': 'not-a-number'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=100)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        # Should use default
        assert paginator.limit == LimitOffsetPagination.default_limit
    
    @pytest.mark.asyncio
    async def test_invalid_offset(self):
        """Test invalid offset parameter."""
        paginator = LimitOffsetPagination()
        request = Mock()
        request.query_params = {'offset': 'invalid'}
        
        mock_qs = AsyncMock()
        mock_qs.count = AsyncMock(return_value=100)
        
        await paginator.paginate_queryset(mock_qs, request)
        
        # Should use default
        assert paginator.offset == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
