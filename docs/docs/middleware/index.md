# Middleware and request context

Middleware wraps request handling: it can inspect a request, reject it before an
endpoint runs, and modify a returned response. Use it for request-wide context
such as correlation identifiers. Endpoint permissions and database isolation
still need their own enforcement.

## Choose a component

| Component | What it supplies | What it does not establish |
| --- | --- | --- |
| [Request ID](request-id.md) | Header, request state and context variable for correlation | Identity, uniqueness of client-provided values or validation |
| [Logging](logging.md) | Method, path, status, elapsed time and available context | Body capture, redaction policy or durable audit storage |
| [Tenant](tenant.md) | A tenant identifier extracted from a header or optional host fallback | Membership, automatic authorization or complete database isolation |
| [Locale and timezone](../advanced/internationalization-and-timezones.md) | Request presentation preferences | Identity or tenant membership |
| [Query tracing](../debugging/query-profiling.md) | Optional in-process query observations | Durable telemetry or automatic parameter masking |

These components must be installed where needed. Do not assume every component
is enabled merely because it is available from `aksara.middleware`.

## Register middleware in the correct order

Pass `(class, options)` pairs through `Aksara(middlewares=[...])`. Within that
list, the first entry is outermost: it runs first on a request and finishes last
on a normal response. To include request and tenant context in logging, place
those context middleware entries before `LoggingMiddleware`.

Alternatively, call `app.add_middleware(...)` before the application starts.
With successive calls, the **last added** component is outermost. These two
registration styles therefore have different ordering syntax. Other framework
or application middleware can wrap this stack too.

The [logging example](logging.md) shows a complete configured application and
the resulting correlation fields. An `AKSARA` dictionary or a module-level
`MIDDLEWARE` string list is not the configuration mechanism for these classes.

## Custom application middleware

Use Starlette's middleware interfaces; Aksara does not export a `BaseMiddleware`
class. This complete example adds timing for a returned response:

```python title="timing_app.py"
from time import perf_counter
from starlette.middleware.base import BaseHTTPMiddleware
from aksara import Aksara


class ResponseTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Response-Time"] = f"{perf_counter() - started:.6f}"
        return response


app = Aksara(database_url=None, auto_discover_views=False)
app.add_middleware(ResponseTimeMiddleware)


@app.get("/ping")
async def ping():
    return {"status": "ok"}
```

Run `uvicorn timing_app:app` after installing Uvicorn. `GET /ping` returns the
status and an `X-Response-Time` header measured in seconds. This measures time
until `call_next` returns, not completion of a streamed body or delivery to the
client. An exception escaping `call_next` skips the header assignment.

## Context lifetime and authority

Built-in context values are available on documented `request.state` attributes
and through context variables. Request-ID and tenant middleware reset their
tokens in `finally`. A child task may inherit a copy of context; that is not a
contract for carrying identity or permissions into a separate worker process.
Pass and validate any context required by background work explicitly.

Use the [authentication guide](../api/authentication.md) to establish identity,
[permissions](../api/permissions.md) to authorize endpoints and the
[tenant tutorial](../tutorials/ticket-desk-tenancy.md) for verified membership
and PostgreSQL RLS. Merely attaching a header value to request state grants no
permission. Route-specific dependencies are useful when a check needs parsed
route arguments; middleware alone does not replace those checks.
