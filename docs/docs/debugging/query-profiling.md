# Query Profiling

Analyze and optimize database queries.

---

## Overview

Aksara's Query Profiler helps you:

- **Identify slow queries** — Find queries that take too long
- **Detect N+1 problems** — Catch relationship loading issues
- **Analyze query plans** — Understand how queries execute
- **Track query counts** — Monitor per-request query volume

---

## Enabling Query Profiling

### Debug Mode

Query profiling is automatic in debug mode:

```python
app = Aksara(debug=True)
```

### Production Profiling

For selective profiling in production:

```python
from aksara.debug import QueryProfiler

@app.get("/api/posts")
async def list_posts(request):
    async with QueryProfiler() as profiler:
        posts = await Post.objects.all()
    
    print(f"Queries: {profiler.count}")
    print(f"Time: {profiler.total_time_ms}ms")
    return posts
```

---

## Debug Error Page Integration

When an error occurs, the **Queries** tab shows:

| # | Query | Time | Rows |
|---|-------|------|------|
| 1 | SELECT * FROM posts | 12ms | 50 |
| 2 | SELECT * FROM users WHERE id = ? | 3ms | 1 |
| 3 | SELECT * FROM users WHERE id = ? | 2ms | 1 |
| ... | | | |

Click any query to see:

- **Full SQL** with parameters
- **Query plan** (EXPLAIN output)
- **Stack trace** showing where it was issued
- **Duplicate detection** alerts

---

## Query Analysis

### Query Count

Track total queries per request:

```python
from aksara.debug import get_query_log

@app.middleware("http")
async def log_queries(request, call_next):
    response = await call_next(request)
    
    query_log = get_query_log()
    if query_log.count > 20:
        logger.warning(
            f"High query count: {query_log.count} queries "
            f"for {request.url.path}"
        )
    
    return response
```

### Slow Query Detection

Identify queries over a threshold:

```python
from aksara.debug import get_query_log

query_log = get_query_log()
slow_queries = [q for q in query_log.queries if q.time_ms > 100]

for query in slow_queries:
    logger.warning(f"Slow query ({query.time_ms}ms): {query.sql}")
```

### N+1 Detection

Automatic detection of N+1 patterns:

```python
from aksara.debug import get_query_log

query_log = get_query_log()
for pattern in query_log.n_plus_one_patterns:
    logger.warning(
        f"N+1 detected: {pattern.count} queries to {pattern.table}\n"
        f"Fix with: .select_related('{pattern.relation}')"
    )
```

---

## N+1 Query Problems

### The Problem

```python
# BAD: N+1 queries
@app.get("/api/posts")
async def list_posts(request):
    posts = await Post.objects.all()  # 1 query
    results = []
    for post in posts:
        author = await post.author  # N queries!
        results.append({
            "title": post.title,
            "author": author.name,
        })
    return results
```

With 100 posts, this runs **101 queries**.

### The Solution

```python
# GOOD: 1 query with select_related
@app.get("/api/posts")
async def list_posts(request):
    posts = await Post.objects.select_related("author").all()  # 1 query
    return [{
        "title": post.title,
        "author": post.author.name,  # Already loaded!
    } for post in posts]
```

### Detection in Profiler

The profiler shows:

```
⚠️ N+1 Pattern Detected

50 similar queries to 'users' table:
  SELECT * FROM users WHERE id = ?

Triggered from: api/views.py:25
  author = await post.author

Suggestion: Use .select_related('author') on the Post query
```

---

## Query Plan Analysis

### View Query Plans

```python
from aksara.debug import explain_query

# Get EXPLAIN output
plan = await explain_query(
    User.objects.filter(email__contains="@example.com")
)
print(plan)
```

Output:
```
EXPLAIN ANALYZE:
Seq Scan on users (cost=0.00..15.00 rows=5 width=200)
  Filter: (email ~~ '%@example.com%')
Planning Time: 0.1 ms
Execution Time: 2.5 ms

⚠️ Warning: Sequential scan on large table
Suggestion: Add index on 'email' column
```

### Automatic Suggestions

The profiler suggests indexes:

```
Missing Index Detected

Query: SELECT * FROM posts WHERE created_at > ?
Scan: Sequential (slow on 100K+ rows)

Suggested: CREATE INDEX idx_posts_created_at ON posts(created_at);
```

---

## QueryProfiler API

### Basic Usage

```python
from aksara.debug import QueryProfiler

async with QueryProfiler() as profiler:
    users = await User.objects.filter(is_active=True).all()
    posts = await Post.objects.filter(author__in=users).all()

print(f"Total queries: {profiler.count}")
print(f"Total time: {profiler.total_time_ms}ms")
print(f"Slowest: {profiler.slowest.sql} ({profiler.slowest.time_ms}ms)")
```

### Profiler Properties

| Property | Type | Description |
|----------|------|-------------|
| `count` | `int` | Total number of queries |
| `total_time_ms` | `float` | Total query time |
| `queries` | `list[Query]` | All captured queries |
| `slowest` | `Query` | Slowest query |
| `n_plus_one_patterns` | `list[N1Pattern]` | Detected N+1 patterns |
| `duplicate_queries` | `list[Query]` | Exact duplicate queries |

### Query Object

```python
for query in profiler.queries:
    print(query.sql)           # SQL statement
    print(query.params)        # Bound parameters
    print(query.time_ms)       # Execution time
    print(query.rows)          # Rows returned/affected
    print(query.stack_trace)   # Where it was issued
```

---

## Middleware Integration

### Query Logging Middleware

```python
from aksara.middleware import QueryLoggingMiddleware

app.add_middleware(
    QueryLoggingMiddleware,
    log_slow_queries=True,
    slow_threshold_ms=100,
    log_query_count=True,
    max_queries_warning=20,
)
```

### Automatic Logging

```
INFO: GET /api/posts - 5 queries, 45ms total
WARNING: GET /api/users - 52 queries, 230ms total (threshold: 20)
WARNING: Slow query (150ms): SELECT * FROM posts WHERE ...
```

---

## Testing Query Counts

### Assert Query Count

```python
from aksara.testing import QueryCounter

async def test_list_posts_efficient():
    async with QueryCounter() as counter:
        response = await client.get("/api/posts")
    
    assert counter.count <= 3, f"Too many queries: {counter.count}"
```

### Capture Queries in Tests

```python
from aksara.testing import capture_queries

async def test_select_related_works():
    async with capture_queries() as queries:
        posts = await Post.objects.select_related("author").all()
        # Access authors (should not trigger queries)
        for post in posts:
            _ = post.author.name
    
    # Should be exactly 1 query (the initial select_related)
    assert len(queries) == 1
```

---

## Configuration

### Settings

```python
# settings.py
AKSARA = {
    "DEBUG": True,
    
    # Query profiling settings
    "QUERY_PROFILING": True,
    "SLOW_QUERY_THRESHOLD_MS": 100,
    "MAX_QUERY_COUNT_WARNING": 20,
    "LOG_ALL_QUERIES": False,  # Only slow queries by default
    "DETECT_N_PLUS_ONE": True,
    "DETECT_MISSING_INDEXES": True,
}
```

### Per-Request Control

```python
from aksara.debug import enable_profiling, disable_profiling

@app.get("/api/debug/posts")
async def debug_posts(request):
    enable_profiling()  # Force profiling for this request
    posts = await Post.objects.all()
    return posts

@app.get("/api/health")
async def health(request):
    disable_profiling()  # Skip profiling for health checks
    return {"status": "ok"}
```

---

## Best Practices

### 1. Set Query Budgets

```python
# Establish expected query counts
async def test_endpoints_have_reasonable_queries():
    budgets = {
        "/api/posts": 5,
        "/api/users": 3,
        "/api/dashboard": 10,
    }
    
    for endpoint, max_queries in budgets.items():
        async with QueryCounter() as counter:
            await client.get(endpoint)
        assert counter.count <= max_queries
```

### 2. Profile in CI

```python
# pytest plugin for query budgets
@pytest.fixture(autouse=True)
async def enforce_query_limits(request):
    async with QueryCounter() as counter:
        yield
    
    # Fail if too many queries
    if counter.count > 50:
        pytest.fail(f"Too many queries: {counter.count}")
```

### 3. Monitor in Production

```python
# Metrics integration
from aksara.debug import get_query_log

@app.middleware("http")
async def report_query_metrics(request, call_next):
    response = await call_next(request)
    
    query_log = get_query_log()
    metrics.histogram(
        "request_query_count",
        query_log.count,
        tags={"path": request.url.path}
    )
    
    return response
```

---

## Troubleshooting

### Profiler Shows No Queries

```python
# Ensure profiling is enabled
app = Aksara(debug=True)  # or
enable_profiling()
```

### Missing Stack Traces

```python
# Enable detailed stack traces
AKSARA = {
    "QUERY_PROFILING": True,
    "QUERY_STACK_TRACES": True,  # May impact performance
}
```

### High Memory Usage

```python
# Limit query log size
AKSARA = {
    "MAX_LOGGED_QUERIES": 100,  # Keep last 100 queries
}
```

---

## Related Documentation

- [Error Pages](error-pages.md) — Debug error pages
- [AI Debug](ai-debug.md) — AI-powered debugging
- [Querying](../orm/querying.md) — QuerySet optimization
- [Testing](../advanced/testing.md) — Test utilities
