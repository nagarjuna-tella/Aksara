# Request logging

`LoggingMiddleware` emits a Python logging record for a handled HTTP request.
It records method, URL path, status, elapsed milliseconds and the request,
tenant and user context values visible to it. The logger name is
`aksara.request`.

## A complete example

Save this as `logging_app.py`. It uses Python's standard logging module and
requires no database. The `/ping` endpoint only demonstrates request context;
it serves no tenant data and does not authenticate callers.

```python title="logging_app.py"
import json
import logging
from aksara import Aksara
from aksara.conf import configure
from aksara.middleware import (
    LoggingMiddleware,
    RequestIDMiddleware,
    TenantMiddleware,
)


class RequestJSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            return json.dumps(record.msg)
        return super().format(record)


handler = logging.StreamHandler()
handler.setFormatter(RequestJSONFormatter())
request_logger = logging.getLogger("aksara.request")
request_logger.addHandler(handler)
request_logger.setLevel(logging.INFO)
configure(log_requests=True, log_json=True)

app = Aksara(
    database_url=None,
    auto_discover_views=False,
    middlewares=[
        (RequestIDMiddleware, {}),
        (TenantMiddleware, {}),
        (LoggingMiddleware, {}),
    ],
)


@app.get("/ping")
async def ping():
    return {"status": "ok"}
```

Run `uvicorn logging_app:app` after installing Uvicorn. `GET /ping` with
`X-Request-ID: local-demo` and `X-Tenant-Id: example` produces a record with
`event="http_request"`, `status_code=200`, `request_id="local-demo"` and
`tenant_id="example"`. `user_id` is `None` unless an outer application component
has established that context. Tenant extraction is not membership verification.

## Options and output

| Setting or option | Default | Effect |
| --- | --- | --- |
| `settings.log_requests` | `True` | Emit request records; `False` skips this middleware's logging. |
| `settings.log_json` | `False` | `False` emits a formatted text message; `True` passes a dictionary as the logging message. |
| Constructor `log_body` | `False` | Reserved; currently does not capture request or response bodies. |

With `log_json=True`, a normal text formatter prints a Python dictionary,
**not necessarily valid JSON**. The example formatter explicitly serializes it.
Configure handlers once in application startup; avoid repeatedly adding them
when constructing apps in tests. The settings are process-wide; consult
[configuration precedence](../reference/settings-reference.md).

The dictionary has `event`, `method`, `path`, `status_code`, `duration_ms`,
`request_id`, `tenant_id` and `user_id`. The text form uses:

```text
HTTP GET /ping -> 200 in 1.23ms [request_id=local-demo tenant=example user=None]
```

Status 400–499 logs at WARNING; 500 or above, or an unavailable status, at ERROR;
other statuses at INFO. An ordinary exception escaping downstream is logged as
500 and re-raised. This is fixed behavior, not a `status_levels` option.
Timing ends when `call_next` returns or raises; it is not full streamed-response
transmission time.

## Scope and sensitive information

There are no constructor options for `log_level`, `logger_name`, custom `logger`,
`structured`, `log_response_body`, excluded paths/methods/patterns, masking
fields, maximum body length or included headers/users. Configure the
`aksara.request` logger and application-owned handlers/filters for routing and
formatting, rather than passing unsupported options to middleware.

The middleware does not collect request/response bodies, headers or query-string
values. It also does not redact sensitive path segments or context identifiers.
Avoid secrets in URLs and define an application logging policy. `log_body=True`
does not enable a masking system. Identity is not inferred from request headers
or `request.state.user` by this logger.

Order matters: context-producing components must wrap the logger if their
values must remain available while it emits its record. Changes to context
inside a downstream endpoint or child task need not propagate back to outer
middleware. See [middleware ordering](index.md).

Request logs are not durable audit events and do not prove a database commit.
Operators own collection, access, retention and monitoring; see the
[production guide](../tutorials/deployment.md).
