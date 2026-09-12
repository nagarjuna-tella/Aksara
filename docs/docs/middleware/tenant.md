# Tenant identifier middleware

`TenantMiddleware` extracts a tenant identifier from an HTTP header, with an
optional subdomain fallback. It stores the value in `request.state.tenant_id`
and `aksara.middleware.tenant_id_var`. **Extraction does not prove that the
caller belongs to the tenant.**

For an application handling tenant data, follow the
[ticket desk tenancy tutorial](../tutorials/ticket-desk-tenancy.md). It verifies
identity and membership, uses tenant-scoped application models, and tests
restricted-role PostgreSQL RLS. A client-supplied header alone is not that
security boundary.

## Inspect extraction without accessing tenant data

This standalone example only echoes extracted context. It does not query a
database or authorize a tenant operation.

```python title="tenant_context_app.py"
from starlette.requests import Request
from aksara import Aksara
from aksara.middleware import TenantMiddleware, tenant_id_var

app = Aksara(
    database_url=None,
    auto_discover_views=False,
    middlewares=[(TenantMiddleware, {"use_subdomain": True})],
)


@app.get("/context")
async def context(request: Request):
    return {
        "state": request.state.tenant_id,
        "context": tenant_id_var.get(),
    }
```

Run `uvicorn tenant_context_app:app` after installing Uvicorn. A request with
`X-Tenant-Id: example` returns `example` in both fields. Without that header,
`Host: example.test.local` selects `example`. A header value takes precedence
over the host. Neither input is inherently trusted.

## Exact extraction rules

| Constructor option | Default | Meaning |
| --- | --- | --- |
| `header_name` | `"X-Tenant-Id"` | Header to inspect. HTTP header names are case-insensitive. |
| `use_subdomain` | `False` | Try the host's first label if no tenant header is present. |

An explicitly empty or whitespace-only tenant header returns HTTP 400. Other
header values are stripped of surrounding whitespace. If no value is found,
handling continues with `None`; there is no built-in requirement to supply a
tenant.

With subdomain extraction enabled, the middleware removes a port and requires
at least three dot-separated host parts. It uses the first part unless it is
`www`, `api` or `app` (case-insensitive). This is a simple extraction rule, not
public-suffix parsing, host validation or tenant lookup. Validate allowed hosts
and tenant membership in the application or trusted deployment boundary.

There are no `resolver`, `path_prefix`, `default_tenant`, `required` or
`exclude_paths` constructor options. A custom authentication/membership resolver
belongs in application code; it is not passed to this middleware as a callback.
The middleware resets its context token in `finally` after downstream handling.

## From context to isolation

The extracted value does not automatically add an ORM filter, validate a tenant
record, choose a database or change a PostgreSQL schema. Supported Aksara
connection paths can apply tenant context to PostgreSQL, but isolation also
requires the correct models, deployed policies and restricted database role.
See [multi-tenancy](../security/multi-tenancy.md) for that contract.

Use trusted identity to determine which tenant the actor may access. Reject
missing or unauthorized tenant selection before serving protected data, and
prevent client payloads from choosing another tenant during writes. Establish
and reset trusted tenant context around the work that requires it. The tutorial
provides an executable membership and RLS example instead of relying on an
unauthenticated header-to-query shortcut.

Do not build schema selection by interpolating a header into `SET search_path`,
or assume a setting applied to one pool connection affects the next acquired
connection. Database-per-tenant and schema-per-tenant routing are separate
application architectures, not capabilities configured by this middleware.
