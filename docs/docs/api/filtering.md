# Filtering & Search

Aksara provides powerful, out-of-the-box filtering and search capabilities for your APIs, inspired by Django REST Framework.

---

## Automatic URL Filtering

Manually parsing query parameters is tedious and error-prone. Aksara provides `AksaraFilterBackend` to automatically parse Django-style query parameters.

`DjangoFilterBackend` remains available as a backward-compatible alias, but `AksaraFilterBackend` is the preferred name for new code.

### Setup

Add the backend to your `ModelViewSet` and specify which fields are filterable:

```python
from aksara import Model, fields
from aksara.api import ModelViewSet, AksaraFilterBackend

class Product(Model):
    name = fields.String()
    price = fields.Decimal(max_digits=10, decimal_places=2)
    category = fields.String()
    in_stock = fields.Boolean()

class ProductViewSet(ModelViewSet):
    model = Product
    filter_backends = [AksaraFilterBackend]
    filterable_fields = ['price', 'category', 'in_stock']

# ✅ Now all these queries work automatically:
# GET /products/?price__gte=50
# GET /products/?category=electronics
# GET /products/?category__in=tech,news
# GET /products/?in_stock=true
# GET /products/?price__gte=50&price__lte=100&in_stock=true
```

### Supported Lookups

| Lookup | Syntax | Example | Notes |
|--------|--------|---------|-------|
| Exact | `field=value` | `?status=active` | Default when no __ operator |
| Greater than | `field__gt=value` | `?price__gt=50` | Numeric only |
| Greater/equal | `field__gte=value` | `?price__gte=50` | Numeric only |
| Less than | `field__lt=value` | `?age__lt=18` | Numeric only |
| Less/equal | `field__lte=value` | `?age__lte=65` | Numeric only |
| In list | `field__in=v1,v2,v3` | `?status__in=active,pending` | Comma-separated |
| Is null | `field__isnull=true\|false` | `?deleted_at__isnull=true` | Boolean value |
| Case-insensitive | `field__icontains=value` | `?name__icontains=john` | String only |
| Case-sensitive | `field__contains=value` | `?email__contains=@gmail` | String only |

### Type Coercion

Values are automatically converted to the correct type based on your model field definitions:

```
?active=true          → True (boolean)
?active=1             → True
?age=30               → 30 (integer)
?price=19.99          → 19.99 (float)
?deleted_at=null      → None
?tags__in=a,b,c       → ['a', 'b', 'c'] (list)
```

---

## Search

The `SearchFilter` backend provides a simple `?search=` query parameter that searches across multiple fields.

### Setup

Add `SearchFilter` to your backends and specify the fields to search:

```python
from aksara.api import SearchFilter

class PostViewSet(ModelViewSet):
    model = Post
    filter_backends = [SearchFilter]
    search_fields = ['title', 'content', 'author__name']

# ✅ Searches title OR content OR author.name for "django"
# GET /posts/?search=django
```

---

## Ordering

The `OrderingFilter` backend allows clients to specify how results should be sorted.

### Setup

```python
from aksara.api import OrderingFilter

class PostViewSet(ModelViewSet):
    model = Post
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'title', 'views']
    ordering = '-created_at'  # Default: newest first

# ✅ Single field ascending
# GET /posts/?ordering=title

# ✅ Single field descending  
# GET /posts/?ordering=-created_at

# ✅ Multiple fields (comma-separated)
# GET /posts/?ordering=-created_at,title
```

---

## Combining Backends

You can combine multiple backends to provide comprehensive list endpoints:

```python
class PostViewSet(ModelViewSet):
    model = Post
    filter_backends = [AksaraFilterBackend, SearchFilter, OrderingFilter]
    filterable_fields = ['status', 'author_id']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'views']
    ordering = '-created_at'

# Complex query:
# GET /posts/?status=published&search=tutorial&ordering=-views
```
