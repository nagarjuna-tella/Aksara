# Middleware

Learn how middleware works in Aksara and how to use the built-in middleware.

---

## What is Middleware?

**Middleware** is code that runs **before** and **after** every request to your application.

Think of it like security checkpoints at an airport:

```
Request → [Middleware 1] → [Middleware 2] → [Your Code] → [Middleware 2] → [Middleware 1] → Response
```

Each middleware can:
- **Inspect** the request before it reaches your code
- **Modify** the request or response
- **Block** requests that shouldn't proceed
- **Add** information to the request (like user identity)

---

## Why Use Middleware?

Common use cases:

| Use Case | What It Does |
|----------|--------------|
| **Authentication** | Check if user is logged in |
| **Request ID** | Add unique ID to track requests |
| **Logging** | Record all requests and responses |
| **CORS** | Allow cross-origin requests |
| **Multi-tenancy** | Identify which tenant made the request |
| **Rate Limiting** | Prevent too many requests |

---

## Built-in Middleware

Aksara includes these middleware out of the box:

| Middleware | Purpose |
|------------|---------|
| [Request ID](request-id.md) | Adds a unique ID to every request |
| [Logging](logging.md) | Logs request/response information |
| [Tenant](tenant.md) | Multi-tenant support |

---

## Using Middleware

### Enabling Middleware

Add middleware to your app configuration:

```python
# settings.py
AKSARA = {
    "MIDDLEWARE": [
        "aksara.middleware.RequestIDMiddleware",
        "aksara.middleware.LoggingMiddleware",
        "aksara.middleware.TenantMiddleware",
    ]
}
```

**Order matters!** Middleware runs in the order listed for requests, and reverse order for responses.

---

### Request ID Middleware

Adds a unique identifier to every request for tracking and debugging.

```python
"aksara.middleware.RequestIDMiddleware"
```

**What it does:**
- Generates a UUID for each request
- Adds it to `request.state.request_id`
- Includes it in response headers as `X-Request-ID`

**Use it for:**
- Tracking requests across services
- Finding related log entries
- Debugging production issues

```python
# Access in your code
@router.get("/test")
async def test(request: Request):
    request_id = request.state.request_id
    return {"request_id": request_id}
```

👉 [Full Request ID Documentation](request-id.md)

---

### Logging Middleware

Automatically logs information about every request and response.

```python
"aksara.middleware.LoggingMiddleware"
```

**What it logs:**
- Request method and path
- Response status code
- Request duration
- Request ID (if enabled)

**Example log output:**
```
INFO: GET /api/users - 200 OK - 45ms - request_id=abc-123
```

👉 [Full Logging Documentation](logging.md)

---

### Tenant Middleware

Enables multi-tenant applications where one codebase serves multiple customers.

```python
"aksara.middleware.TenantMiddleware"
```

**What it does:**
- Identifies the tenant from the request (subdomain, header, or path)
- Sets `request.state.tenant`
- Scopes database queries to that tenant

**Tenant identification methods:**
- **Subdomain**: `acme.yourapp.com` → tenant is "acme"
- **Header**: `X-Tenant-ID: acme`
- **Path**: `/acme/api/users` → tenant is "acme"

👉 [Full Tenant Documentation](tenant.md)

---

## Writing Custom Middleware

Create your own middleware for custom logic:

```python
from aksara.middleware import BaseMiddleware
from starlette.requests import Request
from starlette.responses import Response

class MyMiddleware(BaseMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Code that runs BEFORE your view
        print(f"Request starting: {request.url}")
        
        # Call the next middleware or your view
        response = await call_next(request)
        
        # Code that runs AFTER your view
        print(f"Request finished: {response.status_code}")
        
        return response
```

### Middleware Structure

```python
class MyMiddleware(BaseMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Pre-processing (runs before your view)
        #    - Validate request
        #    - Add data to request.state
        #    - Reject request early if needed
        
        # 2. Call next middleware or view
        response = await call_next(request)
        
        # 3. Post-processing (runs after your view)
        #    - Modify response
        #    - Add headers
        #    - Log information
        
        return response
```

### Example: API Key Authentication

```python
from aksara.middleware import BaseMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class APIKeyMiddleware(BaseMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for certain paths
        if request.url.path in ["/health", "/docs"]:
            return await call_next(request)
        
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            return JSONResponse(
                {"error": "API key required"},
                status_code=401
            )
        
        # Validate API key (you'd check against database)
        if not await self.validate_api_key(api_key):
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=403
            )
        
        # Store user info on request for later use
        request.state.api_key = api_key
        
        return await call_next(request)
    
    async def validate_api_key(self, key: str) -> bool:
        # Check if key exists in database
        from myapp.models import APIKey
        return await APIKey.objects.filter(key=key, is_active=True).exists()
```

### Example: Response Time Header

```python
import time
from aksara.middleware import BaseMiddleware

class ResponseTimeMiddleware(BaseMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response
```

---

## Middleware Order

Middleware runs in **order** for requests and **reverse order** for responses:

```python
MIDDLEWARE = [
    "RequestIDMiddleware",    # 1st for request, last for response
    "LoggingMiddleware",      # 2nd for request, 2nd-to-last for response
    "AuthMiddleware",         # 3rd for request, 3rd-to-last for response
]
```

**Typical ordering:**

```python
MIDDLEWARE = [
    # First: Request tracking
    "aksara.middleware.RequestIDMiddleware",
    
    # Second: Logging (to capture everything)
    "aksara.middleware.LoggingMiddleware",
    
    # Third: Authentication
    "myapp.middleware.AuthMiddleware",
    
    # Last: Business logic middleware
    "myapp.middleware.TenantMiddleware",
]
```

---

## Accessing Middleware Data

Data added by middleware is available on `request.state`:

```python
# In your view
@router.get("/dashboard")
async def dashboard(request: Request):
    # From RequestIDMiddleware
    request_id = request.state.request_id
    
    # From custom AuthMiddleware
    user = request.state.user
    
    # From TenantMiddleware
    tenant = request.state.tenant
    
    return {"user": user.id, "tenant": tenant.name}
```

---

## Middleware vs Dependencies

| Middleware | Dependencies |
|------------|--------------|
| Runs on **every** request | Runs only when declared |
| Global scope | Route-specific scope |
| Good for cross-cutting concerns | Good for route-specific logic |
| Cannot access route parameters | Can access route parameters |

**Use middleware for:**
- Request ID, logging, authentication
- Anything that should run on every request

**Use dependencies for:**
- Getting current user for a specific route
- Validating permissions on specific endpoints
- Parsing route-specific data

---

## Configuration Options

Some middleware accepts configuration:

```python
# settings.py
AKSARA = {
    "MIDDLEWARE": [
        "aksara.middleware.RequestIDMiddleware",
    ],
    
    # Middleware-specific settings
    "REQUEST_ID_HEADER": "X-Request-ID",    # Custom header name
    "REQUEST_ID_GENERATOR": "uuid4",         # ID generation method
    
    "LOGGING_LEVEL": "INFO",                 # Logging verbosity
    "LOGGING_INCLUDE_BODY": False,           # Log request bodies?
    
    "TENANT_HEADER": "X-Tenant-ID",          # Tenant identification
    "TENANT_STRATEGY": "header",             # header, subdomain, or path
}
```

---

## Middleware Documentation

| Guide | What You'll Learn |
|-------|-------------------|
| [Request ID](request-id.md) | Request tracking and debugging |
| [Logging](logging.md) | Request/response logging |
| [Tenant](tenant.md) | Multi-tenant applications |

---

## Reference

For complete API documentation:

👉 [API Reference](../reference/api-reference.md)
