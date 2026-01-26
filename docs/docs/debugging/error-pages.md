# Debug Error Pages

Rich error pages with context for faster debugging.

---

## Overview

When `debug=True`, Vidyut displays detailed error pages instead of generic 500 errors:

```python
app = Vidyut(debug=True)
```

![Debug Error Page](../assets/images/debug-error-page.png)

---

## Error Page Features

### Exception Details

- **Exception type** — `ValueError`, `DoesNotExist`, etc.
- **Error message** — The full exception message
- **Exception chain** — For chained exceptions (`raise ... from ...`)

### Stack Trace

- **Full traceback** — All frames from error to root
- **Code context** — Source code around each frame
- **Syntax highlighting** — Colored code for readability
- **Frame expansion** — Click to expand any frame

### Local Variables

Each stack frame shows local variables:

```python
# At the error point:
user_id = "abc-123"
post = <Post: My Post>
data = {"title": "...", "content": "..."}
```

### Request Information

Complete request details:

- **Method & URL** — `POST /api/posts/`
- **Headers** — All request headers
- **Query params** — URL parameters
- **Body** — Request body (JSON formatted)
- **Cookies** — Request cookies
- **Session** — Session data (if available)

---

## Configuration

### Enable/Disable

```python
# Development
app = Vidyut(debug=True)

# Production (default)
app = Vidyut(debug=False)
```

### Custom Error Template

```python
app = Vidyut(
    debug=True,
    debug_error_template="myapp/custom_error.html",
)
```

### Hide Sensitive Data

```python
app = Vidyut(
    debug=True,
    debug_hide_vars=["password", "secret", "token", "api_key"],
)
```

Variables matching these names are masked in error pages.

---

## Error Types

### Application Errors

Standard Python exceptions from your code:

```python
@app.get("/api/users/{user_id}")
async def get_user(request, user_id: str):
    user = await User.objects.get(id=user_id)  # DoesNotExist
    return user
```

### ORM Errors

Database-related exceptions:

- `DoesNotExist` — Record not found
- `MultipleObjectsReturned` — Expected one, got many
- `IntegrityError` — Constraint violation
- `OperationalError` — Database connection issues

### Validation Errors

Request validation failures:

```python
@app.post("/api/users")
async def create_user(request):
    data = await request.json()
    # ValidationError if data is invalid
```

---

## Interactive Features

### Frame Expansion

Click any stack frame to expand:

- Full source code
- Local variables at that point
- Expression evaluation

### Copy Stack Trace

Button to copy the full traceback as text for bug reports.

### Search

Search through the stack trace and variables.

---

## Security Considerations

!!! danger "Never use debug=True in production"
    Debug error pages expose:
    
    - Source code
    - Environment variables
    - Database credentials
    - Session secrets
    - Internal paths

### Environment-Based Configuration

```python
import os

DEBUG = os.getenv("ENVIRONMENT") == "development"
app = Vidyut(debug=DEBUG)
```

### Conditional Debug

```python
# Even in debug mode, hide from non-staff
app = Vidyut(
    debug=True,
    debug_allowed_ips=["127.0.0.1", "::1"],  # Localhost only
)
```

---

## Custom Error Handlers

Override default error handling:

```python
from vidyut.exceptions import HTTPException

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    if app.debug:
        # Show debug page for HTTP errors too
        raise exc
    
    return JSONResponse(
        {"error": exc.detail},
        status_code=exc.status_code,
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    if app.debug:
        raise exc  # Let debug handler catch it
    
    # Log error
    logger.exception("Unhandled exception")
    
    return JSONResponse(
        {"error": "Internal server error"},
        status_code=500,
    )
```

---

## Debugging Tips

### 1. Check Local Variables

Look at variable values at the error point:

```python
# Error: NoneType has no attribute 'id'
# Check locals: user = None
# Fix: Check if user exists before accessing
```

### 2. Trace the Flow

Follow the stack trace from bottom to top:

```
get_data() called
  fetch_user() called
    User.objects.get() → DoesNotExist
```

### 3. Check Request Data

Verify the request contains expected data:

```python
# Expected: {"user_id": "123"}
# Actual: {"userId": "123"}  # Wrong key!
```

### 4. Use the AI Debug Tab

Click "AI Debug" for automated analysis and fix suggestions.

---

## Complete Example

```python
from vidyut import Vidyut
import os

# Environment-based debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

app = Vidyut(
    debug=DEBUG,
    debug_hide_vars=[
        "password",
        "secret",
        "token",
        "api_key",
        "DATABASE_URL",
    ],
)


@app.get("/api/posts/{post_id}")
async def get_post(request, post_id: str):
    # If post doesn't exist, debug page shows:
    # - DoesNotExist exception
    # - post_id value in locals
    # - Full request details
    post = await Post.objects.get(id=post_id)
    return {"id": str(post.id), "title": post.title}


@app.post("/api/posts")
async def create_post(request):
    data = await request.json()
    
    # Debug page will show 'data' contents
    # if validation fails
    post = await Post.objects.create(
        title=data["title"],
        content=data["content"],
        author_id=str(request.user.id),
    )
    
    return {"id": str(post.id)}
```

---

## Related Documentation

- [AI Debug](ai-debug.md) — AI-powered suggestions
- [Query Profiling](query-profiling.md) — Query analysis
- [Debugging Overview](index.md) — All debug tools
