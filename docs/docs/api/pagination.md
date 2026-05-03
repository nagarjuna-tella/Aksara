# Pagination

Aksara provides flexible pagination strategies for your API endpoints. Choose the pagination style that best fits your application's needs.

---

## Usage

Set the `pagination_class` on your `ModelViewSet`:

```python
from aksara.api.pagination import PageNumberPagination

class ProductViewSet(ModelViewSet):
    model = Product
    pagination_class = PageNumberPagination
```

## Pagination Styles

### PageNumberPagination

Perfect for web browsers and traditional pagination UI.

```python
from aksara.api.pagination import PageNumberPagination

class ProductViewSet(ModelViewSet):
    model = Product
    pagination_class = PageNumberPagination

# API Request:
# GET /products/?page=2&size=50

# Response:
# {
#     "count": 1000,
#     "page": 2,
#     "size": 50,
#     "total_pages": 20,
#     "results": [...]
# }
```

### LimitOffsetPagination

Good for APIs with custom offset-based pagination. Common in programmatic API consumption.

```python
from aksara.api.pagination import LimitOffsetPagination

class ProductViewSet(ModelViewSet):
    model = Product
    pagination_class = LimitOffsetPagination

# API Request:
# GET /products/?limit=50&offset=100

# Response:
# {
#     "count": 1000,
#     "limit": 50,
#     "offset": 100,
#     "results": [...]
# }
```

### CursorPagination (Best for Performance)

Keyset-based pagination with O(1) performance, even for the last page of massive datasets.

```python
from aksara.api.pagination import CursorPagination

class ProductViewSet(ModelViewSet):
    model = Product
    pagination_class = CursorPagination

# Initial Request:
# GET /products/

# Response:
# {
#     "count": 10000,
#     "next_cursor": "eyJpZCI6IjEyMyJ9",
#     "results": [...]
# }

# Next Page Request:
# GET /products/?cursor=eyJpZCI6IjEyMyJ9
```

**Why CursorPagination?**

*   **O(1) performance** regardless of page number (no expensive `OFFSET` queries)
*   **Stable** when data changes between requests (offset pagination breaks if items are inserted/deleted)
*   **Perfect for mobile** and infinite-scroll UIs
*   **Works better with large datasets** than offset pagination
