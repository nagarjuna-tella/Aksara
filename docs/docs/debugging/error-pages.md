# Debug error pages

Aksara can render rich HTML tracebacks for local development. Enable them with
its explicit `debug=True` constructor argument. This is diagnostic output, not
an authenticated administration surface.

!!! danger "Keep debug disabled in production"
    Debug HTML can expose exception messages, source context, request data and
    internal paths. It is not restricted to staff or loopback clients by Aksara.
    `debug_allowed_ips`, `debug_hide_vars` and `debug_error_template` are not
    implemented Aksara controls; passing those extra keywords does not install
    access restrictions, configurable masking or a custom template.

## A reproducible example

This application deliberately raises an error and needs no database. Use the
factory's `debug` argument to compare modes; do not deploy the probe route.

```python title="debug_example.py"
from aksara import Aksara


def create_debug_example(*, debug=False):
    app = Aksara(
        database_url=None,
        auto_discover_views=False,
        enable_admin=False,
        debug=debug,
    )

    @app.get("/probe-error")
    async def probe_error():
        raise ValueError("deliberate diagnostic example")

    return app
```

For this unhandled `ValueError`, the response is status 500:

| Mode and request | Result |
| --- | --- |
| `debug=False`, `Accept: application/json` | Generic JSON `error` with `message="Internal Server Error"`; no exception detail |
| `debug=False`, `Accept: text/html` | Minimal HTML error page |
| `debug=True`, `Accept: text/html` | Rich HTML debug page, including for non-loopback clients |
| `debug=True`, JSON, direct client `127.0.0.1` or `::1` | Generic JSON plus `error.debug_detail` containing the exception message |
| `debug=True`, JSON, other direct client address | Generic JSON without `debug_detail` |

Browser-like Accept headers, including `*/*`, can select HTML. The JSON
loopback check is not an access restriction on HTML and is not authentication.
Do not infer a trusted user from a proxy connection's address. Keep development
servers private and apply any network access control outside this feature.

Known HTTP and ORM exceptions have their own handlers; not every missing record
or validation error becomes this generic 500 page. The
[exception reference](../reference/exceptions.md) documents their statuses and
different response shapes, with an executable custom handler example.

## What the rich page contains

The implementation collects traceback frames and available source lines,
exception information, request method/URL/query data, selected request context,
headers and a small request body when available. It also provides system and
application context. Which data is present depends on the failure path and what
can still be read from the request.

Header collection masks the fixed names `authorization`, `cookie`, `x-api-key`
and `api-key`. This is not comprehensive secret redaction: another header,
query string, body or exception message can contain sensitive values. The
collector does not promise a complete session dump, frame-local variable
inspection, expression evaluation or a configurable variable-mask list.

Use the traceback and source context to locate the first relevant application
frame. Reproduce the input in a test before changing behavior. Copy only reviewed,
redacted diagnostics into bug reports or external tools. Do not treat a debug
page as a durable audit record or an operational monitoring service.

## Custom behavior and AI assistance

Use explicit application exception handlers that return an application-owned
response. Do not raise the same exception from a handler expecting another
handler to reprocess it. Test custom handling with the actual middleware and
Accept headers used by your clients.

AI debug assistance is experimental and separately configured; `debug=True`
alone is not a guarantee that an AI panel or provider-backed analysis runs.
Any suggested fix still needs review and tests. See [AI debug](ai-debug.md) and
the [stability boundary](../concepts/stability.md).

For production configuration, roles and diagnostics, follow the
[deployment guide](../tutorials/deployment.md). Error-page presentation does not
replace authentication, permission checks or incident monitoring.
