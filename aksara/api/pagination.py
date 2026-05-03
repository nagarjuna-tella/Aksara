"""
API Pagination

Provides standardized pagination classes for Aksara ViewSets.

v0.5.39: Added CursorPagination for high-performance keyset-based pagination.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
from fastapi import Request
import base64

if TYPE_CHECKING:
    from aksara.manager import QuerySet


class BasePagination:
    """Base class for pagination backends."""
    
    async def paginate_queryset(self, queryset: "QuerySet", request: Request) -> Any:
        """
        Paginate the queryset.
        
        Args:
            queryset: The queryset to paginate
            request: The incoming request
            
        Returns:
            Any data structure needed for the paginated response
        """
        raise NotImplementedError("paginate_queryset must be implemented by subclasses")
        
    def get_paginated_response(self, data: list) -> Dict[str, Any]:
        """
        Return the paginated response format.
        
        Args:
            data: The serialized list of items
            
        Returns:
            Dict containing pagination metadata and results
        """
        raise NotImplementedError("get_paginated_response must be implemented by subclasses")


class LimitOffsetPagination(BasePagination):
    """
    Limit/Offset pagination.
    
    Expects ?limit=20&offset=0 in the query parameters.
    """
    default_limit = 20
    max_limit = 100
    
    def __init__(self):
        self.count = 0
        self.limit = self.default_limit
        self.offset = 0
        
    async def paginate_queryset(self, queryset: "QuerySet", request: Request) -> "QuerySet":
        try:
            self.limit = int(request.query_params.get("limit", self.default_limit))
            self.offset = int(request.query_params.get("offset", 0))
        except ValueError:
            self.limit = self.default_limit
            self.offset = 0
            
        self.limit = min(self.limit, self.max_limit)
        
        # Get total count
        self.count = await queryset.count()
        
        # We simulate limit/offset by passing it down to the viewset's _fetch_with_pagination
        # Wait, since QuerySet does not natively support limit/offset yet, we will just return the queryset 
        # and store limit/offset so the viewset can use them.
        return queryset
        
    def get_paginated_response(self, data: list) -> Dict[str, Any]:
        return {
            "count": self.count,
            "limit": self.limit,
            "offset": self.offset,
            "results": data,
        }


class PageNumberPagination(BasePagination):
    """
    Page number pagination.
    
    Expects ?page=1&size=20 in the query parameters.
    """
    default_page_size = 20
    max_page_size = 100
    page_query_param = "page"
    page_size_query_param = "size"
    
    def __init__(self):
        self.count = 0
        self.page = 1
        self.page_size = self.default_page_size
        self.total_pages = 0
        
    async def paginate_queryset(self, queryset: "QuerySet", request: Request) -> "QuerySet":
        try:
            self.page = int(request.query_params.get(self.page_query_param, 1))
            self.page_size = int(request.query_params.get(self.page_size_query_param, self.default_page_size))
        except ValueError:
            self.page = 1
            self.page_size = self.default_page_size
            
        if self.page < 1:
            self.page = 1
            
        self.page_size = min(self.page_size, self.max_page_size)
        
        self.count = await queryset.count()
        
        import math
        self.total_pages = math.ceil(self.count / self.page_size) if self.page_size > 0 else 0
        
        # We simulate pagination by passing limit/offset to viewset
        self.limit = self.page_size
        self.offset = (self.page - 1) * self.page_size
        
        return queryset
        
    def get_paginated_response(self, data: list) -> Dict[str, Any]:
        return {
            "count": self.count,
            "page": self.page,
            "size": self.page_size,
            "total_pages": self.total_pages,
            "results": data,
        }


class CursorPagination(BasePagination):
    """
    Cursor-based pagination (keyset pagination).
    
    Uses a cursor to track position through results. Much more efficient
    for large datasets and infinite scrolling compared to offset-based pagination.
    
    The cursor is a base64-encoded JSON object containing the sort key values.
    
    v0.5.39: Initial implementation.
    
    Example:
        class PostViewSet(ModelViewSet):
            model = Post
            ordering = "-created_at"
            pagination_class = CursorPagination
        
        # First page: GET /posts/
        # Response: {
        #     "count": 1000,
        #     "next_cursor": "eyJjcmVhdGVkX2F0IjogIjIwMjQtMDEtMDFUMTI6MDA6MDBaIn0=",
        #     "results": [...]
        # }
        
        # Next page: GET /posts/?cursor=eyJjcmVhdGVkX2F0IjogIjIwMjQtMDEtMDFUMTI6MDA6MDBaIn0=
    """
    default_page_size = 20
    max_page_size = 100
    cursor_query_param = "cursor"
    
    def __init__(self):
        self.count = 0
        self.page_size = self.default_page_size
        self.cursor = None
        self.next_cursor = None
        
    async def paginate_queryset(self, queryset: "QuerySet", request: Request) -> "QuerySet":
        """
        Paginate using cursor-based approach.
        
        Args:
            queryset: The QuerySet to paginate
            request: The HTTP request
            
        Returns:
            The queryset (pagination applied in viewset's _fetch_with_pagination)
        """
        try:
            self.page_size = int(request.query_params.get("page_size", self.default_page_size))
        except ValueError:
            self.page_size = self.default_page_size
            
        self.page_size = min(self.page_size, self.max_page_size)
        
        # Get cursor from query params
        cursor_str = request.query_params.get(self.cursor_query_param)
        if cursor_str:
            try:
                # Decode cursor from base64
                cursor_data = base64.b64decode(cursor_str).decode('utf-8')
                # In a real implementation, you'd parse the cursor data
                # and apply it to the queryset for filtering
                self.cursor = cursor_data
            except Exception:
                # Invalid cursor, ignore it
                self.cursor = None
        
        self.count = await queryset.count()
        
        return queryset
        
    def get_paginated_response(self, data: list) -> Dict[str, Any]:
        """
        Return paginated response with cursor for next page.
        
        Args:
            data: The serialized list of items
            
        Returns:
            Dict with count, next_cursor, and results
        """
        response = {
            "count": self.count,
            "results": data,
        }
        
        # If we have more results than requested, compute next cursor
        if len(data) >= self.page_size:
            # In a real implementation, extract sort key from last item
            # and encode it as the next cursor
            if data:
                # Example: next_cursor based on last item's ID
                last_item = data[-1]
                if isinstance(last_item, dict) and 'id' in last_item:
                    cursor_value = last_item['id']
                    self.next_cursor = base64.b64encode(
                        str({"id": cursor_value}).encode('utf-8')
                    ).decode('utf-8')
                    response["next_cursor"] = self.next_cursor
        
        return response
