# Throttling

Rate limiting is on the roadmap. Until built-in throttling ships, use middleware-based rate limiting:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/posts/")
@limiter.limit("100/hour")
async def list_posts(request):
    ...
```

See [slowapi documentation](https://github.com/laurentS/slowapi) for configuration options.

---

## Related Documentation

- [Permissions](permissions.md) — Access control
- [Running Your App](../getting-started/running-your-app.md) — Server configuration and middleware
