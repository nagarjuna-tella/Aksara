# AI Debug Tab

AI-powered debugging suggestions on error pages.

---

## Overview

When an error occurs in debug mode, Aksara's AI Debug tab provides:

- **Root cause analysis** — What went wrong
- **Fix suggestions** — How to fix it
- **Code examples** — Working solutions
- **Documentation links** — Relevant docs

```python
app = Aksara(debug=True)  # AI Debug tab enabled automatically
```

---

## How It Works

1. Exception occurs in your application
2. Aksara collects error context:
   - Exception type and message
   - Stack trace
   - Local variables
   - Related code
3. AI analyzes the context
4. Suggestions appear in the "AI Debug" tab

---

## Features

### Root Cause Analysis

The AI explains what went wrong:

```
Root Cause: The User.objects.get() call raised DoesNotExist 
because no user exists with id="invalid-uuid".

The 'user_id' parameter came from the URL path and was passed 
directly to the database query without validation.
```

### Fix Suggestions

Actionable fixes ranked by likelihood:

```
1. Add existence check before accessing
   ↳ Use get_or_404() or filter().first() with None check

2. Validate UUID format
   ↳ The ID "invalid-uuid" is not a valid UUID format

3. Handle DoesNotExist explicitly
   ↳ Wrap in try/except to return proper 404 response
```

### Code Examples

Each suggestion includes working code:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
# Suggestion 1: Use get_or_404
from aksara.shortcuts import get_object_or_404

@app.get("/api/users/{user_id}")
async def get_user(request, user_id: str):
    user = await get_object_or_404(User, id=user_id)
    return {"id": str(user.id), "email": user.email}
```

```python
# Suggestion 2: Handle explicitly
@app.get("/api/users/{user_id}")
async def get_user(request, user_id: str):
    try:
        user = await User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": str(user.id), "email": user.email}
```

### Documentation Links

Links to relevant documentation:

- [Querying Data](../orm/querying.md)
- [Exceptions Reference](../reference/exceptions.md)
- [Validation](../advanced/validation.md)

---

## Common Error Patterns

### DoesNotExist

```
Error: Post.DoesNotExist: Post matching query does not exist.

AI Analysis:
The query returned no results. This typically happens when:
- The ID doesn't exist in the database
- The ID format is invalid (e.g., not a valid UUID)
- Filters exclude all records

Suggestions:
1. Use get_or_404() for automatic 404 handling
2. Use filter().first() and check for None
3. Validate input format before querying
```

### ValidationError

```
Error: ValidationError: {'email': ['Enter a valid email address.']}

AI Analysis:
The input data failed validation. The 'email' field contains 
an invalid value.

Suggestions:
1. Check the request payload format
2. Add client-side validation
3. Return clear error messages to the client
```

### IntegrityError

```
Error: IntegrityError: duplicate key value violates unique 
constraint "users_email_key"

AI Analysis:
A record with this email already exists. The database rejected
the insert due to a unique constraint.

Suggestions:
1. Check for existing record before creating
2. Use get_or_create() to handle duplicates
3. Return appropriate error to client
```

### AttributeError on None

```
Error: AttributeError: 'NoneType' object has no attribute 'id'

AI Analysis:
A variable expected to hold an object was None. The query 
User.objects.filter(...).first() returned None.

Suggestions:
1. Check if result is None before accessing attributes
2. Use get() which raises DoesNotExist instead of returning None
3. Add null check with early return
```

---

## Configuration

### Enable/Disable AI Debug

```python
app = Aksara(
    debug=True,
    debug_ai_enabled=True,  # Default: True when debug=True
)
```

### Custom AI Provider

```python
app = Aksara(
    debug=True,
    debug_ai_provider="openai",  # or "anthropic", "local"
    debug_ai_model="gpt-4",
)
```

### Privacy Mode

Limit data sent to AI:

```python
app = Aksara(
    debug=True,
    debug_ai_privacy=True,  # Don't send variable values
)
```

---

## Using AI Debug Effectively

### 1. Read the Root Cause First

Before looking at suggestions, understand what happened.

### 2. Check All Suggestions

The first suggestion isn't always the best for your case.

### 3. Adapt Code Examples

Examples are templates—adapt to your specific code style.

### 4. Use Documentation Links

For complex issues, the linked docs provide deeper understanding.

---

## Example Scenarios

### Scenario 1: N+1 Query

```python
@app.get("/api/posts")
async def list_posts(request):
    posts = await Post.objects.all()
    return [{
        "id": str(p.id),
        "author": (await p.author).name,  # N+1 query!
    } for p in posts]
```

**AI Analysis:**
```
Performance Issue Detected: N+1 Query Pattern

The code makes a separate database query for each post's author.
With 100 posts, this results in 101 queries (1 for posts + 100 for authors).

Fix: Use select_related to load authors in the initial query.
```

**Suggested Fix:**
```python
@app.get("/api/posts")
async def list_posts(request):
    posts = await Post.objects.select_related("author").all()
    return [{
        "id": str(p.id),
        "author": p.author.name,  # Already loaded!
    } for p in posts]
```

### Scenario 2: Missing Await

```python
@app.get("/api/users/{user_id}")
async def get_user(request, user_id: str):
    user = User.objects.get(id=user_id)  # Missing await!
    return {"email": user.email}
```

**AI Analysis:**
```
Error: 'coroutine' object has no attribute 'email'

The async query was not awaited. In async code, database 
operations return coroutines that must be awaited.

Fix: Add 'await' before the query.
```

### Scenario 3: Circular Import

```python
# models.py
from myapp.services import UserService  # Imports models.py!

# AI detects circular import from traceback
```

**AI Analysis:**
```
Import Error: Circular import detected

models.py imports services.py which imports models.py.

Suggestions:
1. Move import inside function
2. Use lazy imports
3. Restructure modules to avoid circular dependency
```

---

## Privacy & Security

### What's Sent to AI

- Exception type and message
- Stack trace (file paths, line numbers)
- Code context (source lines)
- Variable names (not values in privacy mode)

### What's NOT Sent

- Database credentials
- Environment variables
- Full request bodies (unless explicitly enabled)
- Session data

### Local AI Option

For sensitive projects, use local AI:

```python
app = Aksara(
    debug=True,
    debug_ai_provider="local",
    debug_ai_endpoint="http://localhost:11434",  # Ollama
)
```

---

## Related Documentation

- [Error Pages](error-pages.md) — Debug error pages
- [Query Profiling](query-profiling.md) — Query analysis
- [AI Mode](../ai-mode/index.md) — Full AI integration
