# Caching

Speed up your application with caching.

---

## Overview

Vidyut provides a flexible caching system:

- **Query caching** — Cache database query results
- **Response caching** — Cache API responses
- **Object caching** — Cache individual objects
- **Function caching** — Cache function return values

---

## Configuration

### Basic Setup

```python
# settings.py
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "memory",
            "ttl": 300,  # 5 minutes
        }
    }
}
```

### Redis Backend

```python
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "redis",
            "url": "redis://localhost:6379/0",
            "ttl": 300,
        }
    }
}
```

### Multiple Caches

```python
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "redis",
            "url": "redis://localhost:6379/0",
            "ttl": 300,
        },
        "sessions": {
            "backend": "redis",
            "url": "redis://localhost:6379/1",
            "ttl": 86400,  # 24 hours
        },
        "queries": {
            "backend": "memory",
            "max_size": 1000,
            "ttl": 60,
        }
    }
}
```

---

## Function Caching

### Basic Usage

```python
from vidyut.cache import cached

@cached(ttl=300)
async def get_popular_posts():
    return await Post.objects.filter(
        is_published=True
    ).order_by("-view_count").limit(10).all()

# First call: hits database
posts = await get_popular_posts()

# Second call: returns cached result
posts = await get_popular_posts()
```

### Cache Keys

```python
@cached(ttl=300)
async def get_user_posts(user_id: str):
    # Automatic key: "get_user_posts:user_id=abc123"
    return await Post.objects.filter(author_id=user_id).all()

# Custom key
@cached(ttl=300, key="posts:{user_id}")
async def get_user_posts(user_id: str):
    return await Post.objects.filter(author_id=user_id).all()

# Custom key function
def make_key(user_id, status=None):
    return f"user_posts:{user_id}:{status or 'all'}"

@cached(ttl=300, key_func=make_key)
async def get_user_posts(user_id: str, status: str = None):
    qs = Post.objects.filter(author_id=user_id)
    if status:
        qs = qs.filter(status=status)
    return await qs.all()
```

### Conditional Caching

```python
@cached(ttl=300, condition=lambda result: len(result) > 0)
async def search_posts(query: str):
    """Only cache non-empty results."""
    return await Post.objects.filter(title__contains=query).all()
```

---

## Query Caching

### Cache QuerySet Results

```python
from vidyut.cache import cache

# Manual caching
cache_key = "active_users"
users = await cache.get(cache_key)

if users is None:
    users = await User.objects.filter(is_active=True).all()
    await cache.set(cache_key, users, ttl=300)

# Or use get_or_set
users = await cache.get_or_set(
    "active_users",
    lambda: User.objects.filter(is_active=True).all(),
    ttl=300
)
```

### QuerySet Cache Method

```python
# Cache enabled queryset (if supported)
posts = await Post.objects.filter(
    is_published=True
).cache(ttl=300).all()
```

---

## Object Caching

### Cache Single Objects

```python
from vidyut.cache import cache

async def get_user(user_id: str) -> User:
    cache_key = f"user:{user_id}"
    
    user = await cache.get(cache_key)
    if user is None:
        user = await User.objects.get(id=user_id)
        await cache.set(cache_key, user, ttl=600)
    
    return user
```

### Cache Mixin

```python
from vidyut.cache import CacheMixin

class User(CacheMixin, Model):
    email = fields.EmailField(unique=True)
    name = fields.StringField()
    
    class Meta:
        cache_ttl = 600

# Automatic caching
user = await User.objects.cached_get(id=user_id)

# Invalidate on save
await user.save()  # Auto-invalidates cache
```

---

## Response Caching

### Cache API Responses

```python
from vidyut.api import ViewSet, action
from vidyut.cache import cache_response

class PostViewSet(ViewSet):
    @cache_response(ttl=60)
    async def list(self, request):
        posts = await Post.objects.filter(is_published=True).all()
        return PostSerializer(posts, many=True).data
    
    @cache_response(ttl=300, key="post:{pk}")
    async def retrieve(self, request, pk=None):
        post = await Post.objects.get(id=pk)
        return PostDetailSerializer(post).data
```

### Vary Cache by User

```python
@cache_response(ttl=60, vary_on=["user_id"])
async def list(self, request):
    user_id = request.user.id if request.user else "anonymous"
    posts = await get_posts_for_user(user_id)
    return PostSerializer(posts, many=True).data
```

### Vary by Headers

```python
@cache_response(ttl=300, vary_headers=["Accept-Language"])
async def list(self, request):
    # Different cache for each language
    return posts
```

---

## Cache Invalidation

### Manual Invalidation

```python
from vidyut.cache import cache

# Delete specific key
await cache.delete("user:abc123")

# Delete multiple keys
await cache.delete_many(["user:abc123", "user:def456"])

# Delete by pattern (Redis)
await cache.delete_pattern("user:*")

# Clear all
await cache.clear()
```

### Signal-Based Invalidation

```python
from vidyut.signals import post_save, post_delete
from vidyut.cache import cache

@post_save(Post)
async def invalidate_post_cache(sender, instance, **kwargs):
    await cache.delete(f"post:{instance.id}")
    await cache.delete("posts:all")
    await cache.delete(f"posts:author:{instance.author_id}")

@post_delete(Post)
async def invalidate_on_delete(sender, instance, **kwargs):
    await cache.delete(f"post:{instance.id}")
    await cache.delete("posts:all")
```

### Decorator-Based Invalidation

```python
from vidyut.cache import invalidates

@invalidates("posts:all", "post:{post_id}")
async def update_post(post_id: str, data: dict):
    post = await Post.objects.get(id=post_id)
    for key, value in data.items():
        setattr(post, key, value)
    await post.save()
    return post
```

---

## Cache Backends

### Memory Backend

```python
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "memory",
            "max_size": 1000,  # Max entries
            "ttl": 300,
        }
    }
}
```

!!! warning "Memory Cache Limitations"
    Memory cache is not shared between processes. Use Redis in production.

### Redis Backend

```python
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "redis",
            "url": "redis://localhost:6379/0",
            "ttl": 300,
            "key_prefix": "myapp:",
        }
    }
}
```

### Custom Backend

```python
from vidyut.cache import CacheBackend

class MyBackend(CacheBackend):
    async def get(self, key: str):
        # Implementation
        pass
    
    async def set(self, key: str, value, ttl: int = None):
        # Implementation
        pass
    
    async def delete(self, key: str):
        # Implementation
        pass
    
    async def clear(self):
        # Implementation
        pass

# Register
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "myapp.cache.MyBackend",
            "custom_option": "value",
        }
    }
}
```

---

## Cache Utilities

### Cache Object

```python
from vidyut.cache import cache, get_cache

# Default cache
await cache.set("key", "value")
value = await cache.get("key")

# Named cache
query_cache = get_cache("queries")
await query_cache.set("key", "value")
```

### Cache Methods

```python
# Get with default
value = await cache.get("key", default="not_found")

# Check existence
exists = await cache.exists("key")

# Get remaining TTL
ttl = await cache.ttl("key")

# Increment/decrement (Redis)
await cache.incr("counter")
await cache.decr("counter")

# Set if not exists
was_set = await cache.set_nx("lock:task", "1", ttl=60)
```

### Lock

```python
from vidyut.cache import cache

# Distributed lock
async with cache.lock("process:task", timeout=30):
    # Only one process can execute this
    await expensive_operation()
```

---

## Caching Patterns

### Cache-Aside

```python
async def get_user(user_id: str) -> User:
    # 1. Try cache
    user = await cache.get(f"user:{user_id}")
    
    if user is None:
        # 2. Load from database
        user = await User.objects.get(id=user_id)
        
        # 3. Store in cache
        await cache.set(f"user:{user_id}", user, ttl=600)
    
    return user
```

### Write-Through

```python
async def update_user(user_id: str, data: dict) -> User:
    # Update database
    user = await User.objects.get(id=user_id)
    for key, value in data.items():
        setattr(user, key, value)
    await user.save()
    
    # Update cache
    await cache.set(f"user:{user_id}", user, ttl=600)
    
    return user
```

### Cache Stampede Prevention

```python
from vidyut.cache import cache

async def get_expensive_data():
    cache_key = "expensive_data"
    
    # Use lock to prevent multiple simultaneous cache rebuilds
    async with cache.lock(f"lock:{cache_key}", timeout=30):
        data = await cache.get(cache_key)
        
        if data is None:
            data = await compute_expensive_data()
            await cache.set(cache_key, data, ttl=300)
    
    return data
```

---

## Best Practices

### Do

- Use meaningful cache keys
- Set appropriate TTLs
- Invalidate on data changes
- Monitor cache hit rates
- Use Redis in production

### Don't

- Don't cache user-specific data without variation
- Don't cache sensitive data without encryption
- Don't cache with infinite TTL
- Don't ignore cache invalidation

### Key Naming

```python
# Good: hierarchical, descriptive
"user:abc123:profile"
"posts:published:page:1"
"org:xyz:members:count"

# Bad: flat, unclear
"data1"
"cache_key"
```

---

## Monitoring

### Cache Statistics

```python
from vidyut.cache import cache

stats = await cache.stats()
print(f"Hits: {stats['hits']}")
print(f"Misses: {stats['misses']}")
print(f"Hit ratio: {stats['hit_ratio']:.2%}")
```

### Debug Caching

```python
import logging

logging.getLogger("vidyut.cache").setLevel(logging.DEBUG)

# Logs:
# DEBUG - Cache HIT: user:abc123
# DEBUG - Cache MISS: posts:all
# DEBUG - Cache SET: posts:all (ttl=300)
```

---

## Related Documentation

- [Performance](performance.md)
- [Signals](signals.md)
- [Settings Reference](../reference/settings-reference.md)
