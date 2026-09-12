# Debugging

Start with the failure you need to understand. Use [exception handling](../reference/exceptions.md)
for application error responses, [error pages](error-pages.md) for a development
traceback, and [query profiling](query-profiling.md) for database tracing.

## Inspect a development error

Pass `debug=True` explicitly when creating a local development application:

```python
from aksara import Aksara

app = Aksara(debug=True)
```

The [error-page example](error-pages.md) shows a complete application and the
JSON versus HTML response behavior. Debug HTML includes traceback source context
and selected request and system details. It is not a frame-local inspector or an
interactive Python debugger. Do not assume that a `/__debug__/` request inspector
is mounted by this constructor option.

!!! warning "Keep debug mode out of production"
    Debug HTML can expose sensitive data to remote clients. The loopback check
    for JSON `debug_detail` does not restrict HTML access. Header redaction is
    limited; it does not make request bodies, query strings, or exception text
    safe to disclose. See the precise [access and masking boundaries](error-pages.md).

## Choose the next diagnostic step

- **Unexpected HTTP status or response body:** compare the exception with the
  [exception reference](../reference/exceptions.md). Different exception families
  have different response shapes.
- **Slow database work:** inspect query tracing separately. `debug=True` does not
  by itself configure per-request query collection; tracing has its own
  `db_trace_enabled` setting and `QueryTraceMiddleware` integration.
- **A suspected application bug:** reproduce it in a focused test, then use normal
  Python logging or a debugger in a local process. A breakpoint blocks the
  executing worker and is unsuitable for a shared production service.
- **AI-assisted diagnosis:** treat [AI debugging](ai-debug.md) as experimental
  assistance. Review suggested changes and validate them against a reproduction
  before applying them. Provider output is not a correctness guarantee.

For a reproducible starting point, follow the
[testing guide](../advanced/testing.md) and preserve the failing request or operation
inputs with credentials and private payloads removed.
