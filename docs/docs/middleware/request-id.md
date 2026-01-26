# Request ID Middleware

Add unique identifiers to each request for tracing.

---

## Overview

`RequestIDMiddleware` assigns a unique ID to every request, enabling:

- **Request tracing** — Follow a request through your system
- **Log correlation** — Connect logs from the same request
- **Debugging** — Identify specific requests in error reports

```python
from vidyut import Vidyut
from vidyut.middleware import RequestIDMiddleware

app = Vidyut()
app.add_middleware(RequestIDMiddleware)
```

---

## How It Works

1. Middleware checks for incoming `X-Request-ID` header
2. If not present, generates a new UUID
3. Stores ID in context variable
4. Adds `X-Request-ID` to response headers

---

## Configuration

### Basic Usage

```python
app.add_middleware(RequestIDMiddleware)
```

### With Options

```python
app.add_middleware(
    RequestIDMiddleware,
    header_name="X-Request-ID",      # Header to use
    generator=lambda: str(uuid.uuid4()),  # ID generator
    validate=True,                    # Validate incoming IDs
)
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `header_name` | `str` | `"X-Request-ID"` | Header name for request ID |
| `generator` | `callable` | `uuid.uuid4` | Function to generate IDs |
| `validate` | `bool` | `True` | Validate incoming IDs |

---

## Accessing Request ID

### In Views

```python
from vidyut.middleware import request_id_var

@app.get("/api/data")
async def get_data(request):
    request_id = request_id_var.get()
    print(f"Request ID: {request_id}")
    ...
```

### From Request Object

```python
@app.get("/api/data")
async def get_data(request):
    request_id = request.state.request_id
    ...
```

### In Services/Background Tasks

```python
from vidyut.middleware import request_id_var

async def background_task():
    # Context variable is automatically propagated
    request_id = request_id_var.get()
    logger.info(f"Background task for request {request_id}")
```

---

## Using with Logging

### Automatic Log Enrichment

```python
import logging
from vidyut.middleware import request_id_var

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or "no-request"
        return True

# Configure logging
handler = logging.StreamHandler()
handler.addFilter(RequestIDFilter())
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(request_id)s] %(levelname)s %(message)s"
))

logger = logging.getLogger("myapp")
logger.addHandler(handler)
```

### Structured Logging

```python
import structlog
from vidyut.middleware import request_id_var

def add_request_id(logger, method_name, event_dict):
    event_dict["request_id"] = request_id_var.get()
    return event_dict

structlog.configure(
    processors=[
        add_request_id,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()
logger.info("Processing data", user_id="123")
# {"event": "Processing data", "user_id": "123", "request_id": "abc-123-..."}
```

---

## Propagating to External Services

### HTTP Clients

```python
import httpx
from vidyut.middleware import request_id_var

async def call_external_service():
    request_id = request_id_var.get()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.example.com/data",
            headers={"X-Request-ID": request_id},
        )
    return response.json()
```

### Message Queues

```python
from vidyut.middleware import request_id_var

async def publish_message(queue, message):
    request_id = request_id_var.get()
    
    await queue.publish({
        "data": message,
        "metadata": {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        },
    })
```

---

## Custom ID Generator

### Short IDs

```python
import nanoid

app.add_middleware(
    RequestIDMiddleware,
    generator=lambda: nanoid.generate(size=12),
)
# Results in: "V1StGXR8_Z5j"
```

### Prefixed IDs

```python
import uuid

def generate_prefixed_id():
    return f"req_{uuid.uuid4().hex[:12]}"

app.add_middleware(
    RequestIDMiddleware,
    generator=generate_prefixed_id,
)
# Results in: "req_a1b2c3d4e5f6"
```

### Time-Based IDs

```python
import time
import uuid

def generate_time_based_id():
    timestamp = int(time.time() * 1000)
    random_part = uuid.uuid4().hex[:8]
    return f"{timestamp}-{random_part}"

app.add_middleware(
    RequestIDMiddleware,
    generator=generate_time_based_id,
)
# Results in: "1704067200000-a1b2c3d4"
```

---

## Validation

When `validate=True`, incoming request IDs are validated:

```python
app.add_middleware(
    RequestIDMiddleware,
    validate=True,  # Reject invalid IDs
)
```

Invalid IDs are replaced with new generated IDs.

### Custom Validation

```python
import re

def is_valid_request_id(value: str) -> bool:
    # Must be UUID format
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    return bool(re.match(pattern, value, re.IGNORECASE))

app.add_middleware(
    RequestIDMiddleware,
    validator=is_valid_request_id,
)
```

---

## Complete Example

```python
import logging
import uuid
from vidyut import Vidyut
from vidyut.middleware import RequestIDMiddleware, request_id_var

# Configure logging with request ID
class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or "-"
        return True

logging.basicConfig(
    format="%(asctime)s [%(request_id)s] %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
for handler in logging.root.handlers:
    handler.addFilter(RequestIDFilter())

logger = logging.getLogger(__name__)

# Create app
app = Vidyut()

# Add middleware
app.add_middleware(
    RequestIDMiddleware,
    header_name="X-Request-ID",
    generator=lambda: str(uuid.uuid4()),
)


@app.get("/api/users/{user_id}")
async def get_user(request, user_id: str):
    logger.info(f"Fetching user {user_id}")
    
    # Simulate database call
    user = await User.objects.get(id=user_id)
    
    logger.info(f"Found user: {user.email}")
    return {"id": str(user.id), "email": user.email}


@app.post("/api/users")
async def create_user(request):
    data = await request.json()
    logger.info(f"Creating user with email: {data['email']}")
    
    user = await User.objects.create(**data)
    
    # Call external service with same request ID
    await notify_external_service(user)
    
    logger.info(f"User created: {user.id}")
    return {"id": str(user.id)}


async def notify_external_service(user):
    """External call with request ID propagation."""
    import httpx
    
    request_id = request_id_var.get()
    logger.info(f"Notifying external service")
    
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://hooks.example.com/user-created",
            json={"user_id": str(user.id)},
            headers={"X-Request-ID": request_id},
        )
```

**Log Output:**
```
2024-01-15 10:30:00 [abc-123-def-456] INFO __main__: Fetching user 789
2024-01-15 10:30:01 [abc-123-def-456] INFO __main__: Found user: jane@example.com
```

---

## Related Documentation

- [Middleware Overview](index.md) — All middleware
- [Logging Middleware](logging.md) — Request logging
- [Debugging](../debugging/index.md) — Debug tools
