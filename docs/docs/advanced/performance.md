# Performance

Optimize your Vidyut application for speed.

---

## Overview

Key areas for performance optimization:

- **Database queries** — N+1 prevention, indexing
- **Serialization** — Efficient data transformation
- **Caching** — Reduce redundant operations
- **Async patterns** — Concurrent execution

---

## Database Optimization

### Select Related (Eager Loading)

Prevent N+1 queries by loading related objects:

```python
# ❌ Bad: N+1 queries
posts = await Post.objects.all()
for post in posts:
    author = await post.author  # Query per post!

# ✅ Good: Single query with JOIN
posts = await Post.objects.select_related("author").all()
for post in posts:
    author = post.author  # Already loaded
```

### Prefetch Related (Many Relations)

For many-to-many or reverse foreign keys:

```python
# ❌ Bad: N+1 queries
posts = await Post.objects.all()
for post in posts:
    comments = await post.comments.all()  # Query per post!

# ✅ Good: Batched queries
posts = await Post.objects.prefetch_related("comments").all()
for post in posts:
    comments = post.comments  # Already loaded
```

### Nested Prefetch

```python
# Load posts → comments → comment authors
posts = await Post.objects.prefetch_related(
    "comments",
    "comments__author"
).all()
```

### Only / Defer Fields

Load only needed fields:

```python
# Load only specific fields
posts = await Post.objects.only("id", "title", "slug").all()

# Exclude heavy fields
posts = await Post.objects.defer("content", "metadata").all()
```

### Pagination

Always paginate large queries:

```python
# Limit results
posts = await Post.objects.limit(20).offset(40).all()

# Or use built-in pagination
from vidyut.api.pagination import PageNumberPagination

class PostViewSet(ModelViewSet):
    pagination_class = PageNumberPagination
    page_size = 20
```

---

## Query Profiling

### Enable Query Logging

```python
# settings.py
VIDYUT = {
    "DEBUG": True,
    "LOG_QUERIES": True,
}
```

### Profile Decorator

```python
from vidyut.debug import profile_queries

@profile_queries
async def get_posts():
    posts = await Post.objects.select_related("author").all()
    return posts

# Output:
# Query Profile: get_posts
# Total queries: 1
# Total time: 0.023s
# Queries:
#   1. SELECT posts.*, users.* FROM posts JOIN users... (0.023s)
```

### Query Capture

```python
from vidyut.debug import capture_queries

async with capture_queries() as queries:
    posts = await Post.objects.all()
    for post in posts:
        author = await post.author

print(f"Executed {len(queries)} queries")
for q in queries:
    print(f"  {q.sql} ({q.duration}ms)")
```

### N+1 Detection

```python
from vidyut.debug import detect_n_plus_one

@detect_n_plus_one
async def list_posts(request):
    posts = await Post.objects.all()
    return [{"title": p.title, "author": p.author.name} for p in posts]

# Warning: N+1 detected!
# Similar query executed 10 times:
#   SELECT * FROM users WHERE id = ?
```

---

## Database Indexing

### Add Indexes

```python
class Post(Model):
    title = fields.StringField(max_length=200)
    slug = fields.StringField(max_length=200, db_index=True)  # Index
    author = fields.ForeignKey(User)  # FK auto-indexed
    created_at = fields.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        indexes = [
            # Composite index
            Index(fields=["author", "created_at"]),
            # Partial index
            Index(
                fields=["is_published"],
                condition="is_published = true"
            ),
        ]
```

### Check Explain Plans

```python
# Get query plan
plan = await Post.objects.filter(
    author=user,
    is_published=True
).explain()

print(plan)
# Bitmap Heap Scan on posts
#   -> Bitmap Index Scan on posts_author_id_idx
```

---

## Serialization Performance

### Efficient Serializers

```python
# ❌ Bad: Nested queries in serializer
class PostSerializer(ModelSerializer):
    author_name = SerializerMethodField()
    comment_count = SerializerMethodField()
    
    async def get_author_name(self, obj):
        author = await obj.author  # Query!
        return author.name
    
    async def get_comment_count(self, obj):
        return await obj.comments.count()  # Query!

# ✅ Good: Use select_related and annotations
class PostSerializer(ModelSerializer):
    author_name = StringField(source="author.name")
    comment_count = IntegerField()

# In viewset:
def get_queryset(self):
    return Post.objects.select_related("author").annotate(
        comment_count=Count("comments")
    )
```

### Read-Only Serializers

```python
# For list views, use lightweight serializers
class PostListSerializer(ModelSerializer):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "created_at"]
        read_only = True

# Detailed serializer for single items
class PostDetailSerializer(ModelSerializer):
    class Meta:
        model = Post
        fields = "__all__"
```

---

## Async Optimization

### Concurrent Queries

```python
import asyncio

# ❌ Bad: Sequential queries
async def get_dashboard():
    users = await User.objects.count()
    posts = await Post.objects.count()
    comments = await Comment.objects.count()
    return {"users": users, "posts": posts, "comments": comments}

# ✅ Good: Concurrent queries
async def get_dashboard():
    users, posts, comments = await asyncio.gather(
        User.objects.count(),
        Post.objects.count(),
        Comment.objects.count()
    )
    return {"users": users, "posts": posts, "comments": comments}
```

### Batch Operations

```python
# ❌ Bad: Individual inserts
for item in items:
    await Item.objects.create(**item)

# ✅ Good: Bulk insert
await Item.objects.bulk_create([
    Item(**item) for item in items
])

# ❌ Bad: Individual updates
for user in users:
    user.last_login = now
    await user.save()

# ✅ Good: Bulk update
await User.objects.filter(
    id__in=[u.id for u in users]
).update(last_login=now)
```

---

## Caching Strategies

### Cache Expensive Queries

```python
from vidyut.cache import cached

@cached(ttl=300)
async def get_popular_posts():
    return await Post.objects.filter(
        is_published=True
    ).order_by("-view_count").limit(10).all()
```

### Cache Computed Values

```python
class Post(Model):
    @property
    async def comment_count(self):
        cache_key = f"post:{self.id}:comment_count"
        count = await cache.get(cache_key)
        
        if count is None:
            count = await self.comments.count()
            await cache.set(cache_key, count, ttl=60)
        
        return count
```

### Response Caching

```python
from vidyut.cache import cache_response

class PostViewSet(ModelViewSet):
    @cache_response(ttl=60)
    async def list(self, request):
        return await super().list(request)
```

See [Caching Guide](caching.md) for more.

---

## Connection Pooling

### Database Pool

```python
# settings.py
VIDYUT = {
    "DATABASE_URL": "postgresql://localhost/myapp",
    "DATABASE_POOL": {
        "min_size": 5,
        "max_size": 20,
        "max_queries": 50000,
        "max_inactive_connection_lifetime": 300,
    }
}
```

### Redis Pool

```python
VIDYUT = {
    "CACHE": {
        "default": {
            "backend": "redis",
            "url": "redis://localhost:6379/0",
            "pool_size": 10,
        }
    }
}
```

---

## Response Optimization

### Compression

```python
from vidyut.middleware import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=500)
```

### Pagination

```python
class PostViewSet(ModelViewSet):
    pagination_class = PageNumberPagination
    page_size = 20
    max_page_size = 100
```

### Field Selection

```python
# Allow clients to select fields
# GET /api/posts/?fields=id,title,slug

class PostViewSet(ModelViewSet):
    def get_serializer_fields(self):
        fields = self.request.query_params.get("fields")
        if fields:
            return fields.split(",")
        return None
```

---

## Benchmarking

### Simple Benchmark

```python
import time

async def benchmark_query():
    start = time.perf_counter()
    
    for _ in range(100):
        await Post.objects.filter(is_published=True).all()
    
    elapsed = time.perf_counter() - start
    print(f"100 queries in {elapsed:.2f}s ({elapsed/100*1000:.1f}ms avg)")
```

### Load Testing

```bash
# Using locust
pip install locust

# locustfile.py
from locust import HttpUser, task

class APIUser(HttpUser):
    @task
    def list_posts(self):
        self.client.get("/api/posts/")
    
    @task
    def get_post(self):
        self.client.get("/api/posts/abc-123/")

# Run
locust -f locustfile.py --host=http://localhost:8000
```

---

## Checklist

### Before Production

- [ ] Enable query logging in development
- [ ] Check for N+1 queries
- [ ] Add database indexes
- [ ] Enable caching
- [ ] Configure connection pooling
- [ ] Set up pagination
- [ ] Enable response compression

### Monitoring

- [ ] Track query counts per request
- [ ] Monitor cache hit rates
- [ ] Set up slow query alerts
- [ ] Profile periodically

---

## Common Issues

### N+1 Queries

**Symptom:** High query count, slow responses

**Solution:** Use `select_related()` and `prefetch_related()`

### Missing Indexes

**Symptom:** Slow filtered queries

**Solution:** Add `db_index=True` or composite indexes

### Large Payloads

**Symptom:** Slow serialization, high memory

**Solution:** Paginate, use lightweight serializers, enable compression

### Connection Exhaustion

**Symptom:** Database connection errors under load

**Solution:** Configure connection pooling

---

## Related Documentation

- [Caching](caching.md)
- [Query Profiling](../debugging/query-profiling.md)
- [Querying](../orm/querying.md)
