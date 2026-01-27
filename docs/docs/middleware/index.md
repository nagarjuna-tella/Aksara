# Middleware

Add request processing logic with Aksara middleware.

---

## Overview

Middleware processes requests before they reach your views and responses before they're sent:

```
Request → Middleware → View → Middleware → Response
```

```python
from aksara import Aksara
from aksara.middleware import RequestIDMiddleware

app = Aksara()
app.add_middleware(RequestIDMiddleware)
```

---

## Built-in Middleware

Aksara provides several production-ready middleware:

| Middleware | Purpose |
|------------|---------|
| `RequestIDMiddleware` | Add unique ID to each request |
| `TenantMiddleware` | Multi-tenant support |
| `LoggingMiddleware` | Structured request logging |
| `AuthenticationMiddleware` | User authentication |
| `CORSMiddleware` | Cross-origin requests |

---

## Adding Middleware

### Basic Usage

```python
from aksara import Aksara
from aksara.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
)

app = Aksara()

# Add middleware (order matters!)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
```

### With Configuration

```python
app.add_middleware(
    LoggingMiddleware,
    log_request_body=True,
    log_response_body=False,
    exclude_paths=["/health", "/metrics"],
)
```

### Middleware Order

Middleware executes in reverse order on the way in, and forward order on the way out:

```python
app.add_middleware(A)  # 3rd in, 1st out
app.add_middleware(B)  # 2nd in, 2nd out
app.add_middleware(C)  # 1st in, 3rd out

# Request flow:  C → B → A → View → A → B → C
```

---

## Section Contents

<div class="grid cards" markdown>

-   :material-identifier: **[Request ID](request-id.md)**
    
    Unique identifiers for request tracing

-   :material-account-group: **[Tenant Middleware](tenant.md)**
    
    Multi-tenant application support

-   :material-text-box: **[Logging](logging.md)**
    
    Structured request/response logging

</div>

---

## Custom Middleware

### Class-Based

```python
from starlette.middleware.base import BaseHTTPMiddleware

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        import time
        
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response

app.add_middleware(TimingMiddleware)
```

### Pure ASGI

```python
class TimingMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import time
        start = time.time()
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start
                headers = list(message.get("headers", []))
                headers.append((b"x-response-time", f"{duration:.3f}s".encode()))
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_wrapper)

app.add_middleware(TimingMiddleware)
```

---

## Context Variables

Aksara middleware uses context variables to share data:

```python
from aksara.middleware import (
    request_id_var,  # Current request ID
    tenant_id_var,   # Current tenant ID
    user_id_var,     # Current user ID
)

# In any async code
current_request_id = request_id_var.get()
current_tenant = tenant_id_var.get()
```

### Using in Views

```python
from aksara.middleware import request_id_var

@app.get("/api/data")
async def get_data(request):
    request_id = request_id_var.get()
    logger.info(f"Processing request {request_id}")
    ...
```

### Using in Services

```python
from aksara.middleware import request_id_var, tenant_id_var

class DataService:
    async def fetch_data(self):
        request_id = request_id_var.get()
        tenant_id = tenant_id_var.get()
        
        logger.info(
            "Fetching data",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
            }
        )
        
        # Query with tenant filter
        return await Data.objects.filter(tenant_id=tenant_id).all()
```

---

## Complete Example

```python
from aksara import Aksara
from aksara.middleware import (
    RequestIDMiddleware,
    TenantMiddleware,
    LoggingMiddleware,
)
from starlette.middleware.cors import CORSMiddleware

app = Aksara()

# CORS (first, so it handles preflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID (adds X-Request-ID header)
app.add_middleware(RequestIDMiddleware)

# Tenant resolution
app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",
    default_tenant="default",
)

# Logging (logs with request ID and tenant)
app.add_middleware(
    LoggingMiddleware,
    log_level="INFO",
    exclude_paths=["/health"],
)
```

---

## Related Documentation

- [Request ID](request-id.md) — Request tracing
- [Tenant Middleware](tenant.md) — Multi-tenancy
- [Logging](logging.md) — Request logging
