# Debugging

Developer tools for debugging Aksara applications.

---

## Overview

Aksara provides powerful debugging tools for development:

- **Debug Error Pages** — Rich error pages with context
- **AI Debug Tab** — AI-powered fix suggestions
- **Query Profiler** — Database query analysis
- **Request Inspector** — Request/response details

```python
from aksara import Aksara

app = Aksara(debug=True)  # Enable debug mode
```

!!! warning "Production Warning"
    Never enable debug mode in production. It exposes sensitive information.

---

## Enabling Debug Mode

### Via Constructor

```python
app = Aksara(debug=True)
```

### Via Settings

```python
# settings.py
DEBUG = True

# main.py
from aksara import Aksara
from myapp.settings import DEBUG

app = Aksara(debug=DEBUG)
```

### Via Environment

```python
import os

app = Aksara(debug=os.getenv("DEBUG", "false").lower() == "true")
```

---

## Debug Features

### Rich Error Pages

When an exception occurs in debug mode, you get a detailed error page:

- **Exception type and message**
- **Full stack trace with code context**
- **Local variables at each frame**
- **Request details (headers, body, params)**
- **AI-powered fix suggestions**

### Request/Response Inspector

View complete request and response data:

```python
# In debug mode, access via /__debug__/
# Or from error pages
```

### Query Profiler

Track database queries:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.debug import query_profiler

@app.get("/api/posts")
async def list_posts(request):
    with query_profiler() as profiler:
        posts = await Post.objects.select_related("author").all()
    
    print(f"Queries: {profiler.query_count}")
    print(f"Time: {profiler.total_time}ms")
    for query in profiler.queries:
        print(f"  {query.sql} ({query.time}ms)")
    
    return posts
```

---

## Section Contents

<div class="grid cards" markdown>

-   :material-alert-circle: **[Error Pages](error-pages.md)**
    
    Rich debugging error pages

-   :material-robot: **[AI Debug](ai-debug.md)**
    
    AI-powered debugging suggestions

-   :material-database-search: **[Query Profiling](query-profiling.md)**
    
    Database query analysis

</div>

---

## Quick Debug Tips

### Print Debugging

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.debug import debug_print

@app.get("/api/data")
async def get_data(request):
    data = await fetch_data()
    debug_print(data)  # Pretty prints with context
    return data
```

### Breakpoints

```python
@app.get("/api/data")
async def get_data(request):
    data = await fetch_data()
    breakpoint()  # Python debugger
    return data
```

### Query Logging

```python
# In settings
DATABASE_ECHO = True  # Log all SQL queries
```

---

## Related Documentation

- [Error Pages](error-pages.md) — Debug error pages
- [AI Debug](ai-debug.md) — AI suggestions
- [Query Profiling](query-profiling.md) — Query analysis
