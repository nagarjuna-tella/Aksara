# Throttling

Rate limiting for API endpoints.

---

## Overview

!!! warning "Not Yet Implemented"
    Throttling is planned for a future release. This page outlines the planned API.

Throttling prevents API abuse by limiting request rates:

```python
from aksara.api import ModelViewSet
from aksara.throttling import UserRateThrottle

class PostViewSet(ModelViewSet):
    model = Post
    throttle_classes = [UserRateThrottle]
```

---

## Planned Features

### Rate Limits

```python
class UserRateThrottle(BaseThrottle):
    """Limit requests per user."""
    rate = "100/hour"  # 100 requests per hour

class AnonRateThrottle(BaseThrottle):
    """Limit requests for anonymous users."""
    rate = "20/hour"

class BurstRateThrottle(BaseThrottle):
    """Limit burst requests."""
    rate = "10/minute"
```

### Configuration

```python
# settings.py
THROTTLE_RATES = {
    "anon": "100/day",
    "user": "1000/day",
    "premium": "10000/day",
}
```

### ViewSet Integration

```python
class PostViewSet(ModelViewSet):
    model = Post
    throttle_classes = [UserRateThrottle, BurstRateThrottle]
    
    # Per-action throttling
    def get_throttles(self):
        if self.action == "create":
            return [CreateRateThrottle()]
        return super().get_throttles()
```

### Custom Throttles

```python
class CustomThrottle(BaseThrottle):
    def allow_request(self, request, view):
        # Custom logic
        return True
    
    def wait(self):
        # Seconds until next allowed request
        return 60
```

---

## Current Workaround

Until built-in throttling is available, use middleware:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/posts/")
@limiter.limit("100/hour")
async def list_posts(request):
    ...
```

---

## Related Documentation

- [Permissions](permissions.md) — Access control
- [Middleware](../middleware/index.md) — Custom middleware
