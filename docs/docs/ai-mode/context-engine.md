# Context export

!!! warning "Experimental"
    Context export feeds evolving Studio and external-agent workflows. Its
    detailed schema is not part of the stable v0.7 contract.

Aksara exports registered model, ViewSet, route, migration, admin, settings,
middleware, and generated-tool metadata through `build_full_ai_context()`.
There is no public `ContextEngine` class.

```python
from aksara.ai.context import build_full_ai_context

context = await build_full_ai_context(
    app,
    include_routes=True,
    include_migrations=True,
    include_admin=False,
    include_ai_tools=True,
)

print(context.model_count)
print(context.route_count)
print(context.checksum)
```

Use `build_full_ai_context_sync()` only from synchronous code when no event loop
is already running.

Sensitive fields marked `ai_sensitive=True` are omitted. This filtering helps
shape AI context; it is not an authorization control. Server-side permissions,
policy, tenant checks, field enforcement, and PostgreSQL RLS remain the security
boundary for executable REST and MCP operations.
