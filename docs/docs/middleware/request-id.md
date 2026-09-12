# Request identifiers

`RequestIDMiddleware` makes a correlation value available during an HTTP
request. It reads the configured header; if the value is missing or empty, it
generates a UUID4 string. A nonempty client value is used unchanged, including a
value that is not a UUID. Treat it as untrusted correlation data, never as an
identity, authorization credential or unique idempotency key.

## A complete example

```python title="request_id_app.py"
from starlette.requests import Request
from aksara import Aksara
from aksara.middleware import RequestIDMiddleware, request_id_var

app = Aksara(
    database_url=None,
    auto_discover_views=False,
    middlewares=[(RequestIDMiddleware, {"header_name": "X-Correlation-ID"})],
)


@app.get("/context")
async def context(request: Request):
    return {
        "state": request.state.request_id,
        "context": request_id_var.get(),
    }
```

Run `uvicorn request_id_app:app` after installing Uvicorn. A request carrying
`X-Correlation-ID: local-demo` returns that value in both JSON fields and in the
response's `X-Correlation-ID` header. Without it, the middleware generates a
UUID. No database is used by this example.

## Constructor and response behavior

The only middleware-specific constructor option is `header_name`, defaulting
to `"X-Request-ID"`. `RequestIdMiddleware` is a compatibility alias for the same
class. There are no `generator`, `validate` or `validator` options.

The middleware sets `request.state.request_id` and
`aksara.middleware.request_id_var`, then resets its context token when downstream
handling finishes or raises. It adds the response header after `call_next`
returns. Do not assume an unhandled error rendered by an outer error handler
will carry that header.

Client-provided IDs can repeat. If your deployment requires validated,
length-bounded or server-generated identifiers, enforce that policy at a trusted
boundary and test it. Do not describe the built-in behavior as validating or
replacing malformed IDs.

## Logging and other processes

Place RequestIDMiddleware outside LoggingMiddleware so the latter can read the
context; see the [complete logging example](logging.md). Application log records
do not automatically gain a request-ID field. An application-owned logging
filter or formatter can read `request_id_var.get()` while context is available.

Context variables normally return `None` outside their context. They do not
transport themselves to a queued task, external service or another process.
If a consumer needs a correlation value, include it deliberately in its message
or request, subject to the consumer's validation and privacy policy. Correlation
continues to be separate from [current authorization](../concepts/application-boundaries.md).
