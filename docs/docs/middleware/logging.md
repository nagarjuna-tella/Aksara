# Logging Middleware

Structured request and response logging.

---

## Overview

`LoggingMiddleware` provides automatic logging for all HTTP requests:

```python
from vidyut import Vidyut
from vidyut.middleware import LoggingMiddleware

app = Vidyut()
app.add_middleware(LoggingMiddleware)
```

**Output:**
```
INFO  | POST /api/users 201 | 45ms | request_id=abc-123
```

---

## Configuration

### Basic Options

```python
app.add_middleware(
    LoggingMiddleware,
    log_level="INFO",          # Log level
    logger_name="vidyut.http", # Logger name
)
```

### All Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_level` | `str` | `"INFO"` | Logging level |
| `logger_name` | `str` | `"vidyut.http"` | Logger name |
| `log_request_body` | `bool` | `False` | Log request bodies |
| `log_response_body` | `bool` | `False` | Log response bodies |
| `exclude_paths` | `list` | `[]` | Paths to skip |
| `exclude_methods` | `list` | `["OPTIONS"]` | Methods to skip |
| `max_body_length` | `int` | `1000` | Max body chars to log |
| `mask_fields` | `list` | `["password", "token"]` | Fields to mask |

---

## Log Format

### Default Format

```
{level} | {method} {path} {status} | {duration}ms | request_id={request_id}
```

### With Request Body

```python
app.add_middleware(
    LoggingMiddleware,
    log_request_body=True,
)
```

```
INFO  | POST /api/users 201 | 45ms | request_id=abc-123
      | body: {"email": "jane@example.com", "password": "***"}
```

### With Response Body

```python
app.add_middleware(
    LoggingMiddleware,
    log_response_body=True,
)
```

```
INFO  | POST /api/users 201 | 45ms | request_id=abc-123
      | response: {"id": "user-123", "email": "jane@example.com"}
```

---

## Excluding Paths

Skip logging for certain endpoints:

```python
app.add_middleware(
    LoggingMiddleware,
    exclude_paths=[
        "/health",
        "/metrics",
        "/favicon.ico",
        "/static/",
    ],
)
```

### Pattern Matching

```python
app.add_middleware(
    LoggingMiddleware,
    exclude_patterns=[
        r"^/static/.*",
        r"^/assets/.*",
        r".*\.(css|js|png|jpg)$",
    ],
)
```

---

## Masking Sensitive Data

Automatically mask sensitive fields in logs:

```python
app.add_middleware(
    LoggingMiddleware,
    log_request_body=True,
    mask_fields=[
        "password",
        "token",
        "api_key",
        "secret",
        "credit_card",
    ],
)
```

**Input:**
```json
{"email": "jane@example.com", "password": "secret123"}
```

**Logged as:**
```json
{"email": "jane@example.com", "password": "***"}
```

---

## Custom Logging

### Custom Logger

```python
import logging

# Configure custom logger
logger = logging.getLogger("myapp.requests")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s"
))
logger.addHandler(handler)

# Use with middleware
app.add_middleware(
    LoggingMiddleware,
    logger_name="myapp.requests",
)
```

### Structured Logging

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger("http")

app.add_middleware(
    LoggingMiddleware,
    logger=logger,
    structured=True,
)
```

**Output:**
```json
{
    "timestamp": "2024-01-15T10:30:00.000Z",
    "level": "info",
    "method": "POST",
    "path": "/api/users",
    "status": 201,
    "duration_ms": 45,
    "request_id": "abc-123"
}
```

---

## Log Levels by Status

```python
app.add_middleware(
    LoggingMiddleware,
    status_levels={
        "2xx": "INFO",
        "3xx": "INFO",
        "4xx": "WARNING",
        "5xx": "ERROR",
    },
)
```

**Result:**
```
INFO    | GET /api/users 200 | 12ms
WARNING | POST /api/users 400 | 5ms
ERROR   | GET /api/data 500 | 120ms
```

---

## Additional Context

### Include Headers

```python
app.add_middleware(
    LoggingMiddleware,
    include_headers=["User-Agent", "Accept-Language"],
)
```

### Include User Info

```python
app.add_middleware(
    LoggingMiddleware,
    include_user=True,
)
```

```
INFO | POST /api/posts 201 | 45ms | request_id=abc-123 user=jane@example.com
```

---

## Integration with Request ID

Automatically includes request ID when used with `RequestIDMiddleware`:

```python
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)

# Logs include request_id from context
```

---

## Complete Example

```python
import logging
import structlog
from vidyut import Vidyut
from vidyut.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    request_id_var,
)

# Configure structlog
def add_request_id(logger, method_name, event_dict):
    event_dict["request_id"] = request_id_var.get()
    return event_dict

structlog.configure(
    processors=[
        add_request_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

# Create app
app = Vidyut()

# Add middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    LoggingMiddleware,
    log_level="INFO",
    log_request_body=True,
    log_response_body=False,
    exclude_paths=[
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
    ],
    mask_fields=[
        "password",
        "token",
        "api_key",
        "authorization",
    ],
    status_levels={
        "2xx": "INFO",
        "3xx": "INFO",
        "4xx": "WARNING",
        "5xx": "ERROR",
    },
)


@app.post("/api/users")
async def create_user(request):
    data = await request.json()
    user = await User.objects.create(**data)
    return {"id": str(user.id), "email": user.email}


@app.get("/api/users/{user_id}")
async def get_user(request, user_id: str):
    user = await User.objects.get(id=user_id)
    return {"id": str(user.id), "email": user.email}


@app.get("/health")
async def health():
    # Not logged (excluded path)
    return {"status": "healthy"}
```

**Sample Output:**
```json
{"timestamp": "2024-01-15T10:30:00.000Z", "level": "info", "request_id": "abc-123", "method": "POST", "path": "/api/users", "status": 201, "duration_ms": 45, "body": {"email": "jane@example.com", "password": "***"}}
{"timestamp": "2024-01-15T10:30:01.000Z", "level": "info", "request_id": "def-456", "method": "GET", "path": "/api/users/123", "status": 200, "duration_ms": 12}
{"timestamp": "2024-01-15T10:30:02.000Z", "level": "warning", "request_id": "ghi-789", "method": "GET", "path": "/api/users/999", "status": 404, "duration_ms": 8}
```

---

## Related Documentation

- [Middleware Overview](index.md) — All middleware
- [Request ID](request-id.md) — Request tracing
- [Debugging](../debugging/index.md) — Debug tools
