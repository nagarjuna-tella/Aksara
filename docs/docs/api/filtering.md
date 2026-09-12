# Filtering, search and ordering

Generated list routes support query parameters, and optional filter backends add
coercion, search and ordering. These control query shape; they do not replace
authentication, object/tenant policy or PostgreSQL RLS.

## Configure the Ticket list

Use the Ticket model from the [first-project tutorial](../getting-started/first-project.md).
This ViewSet replaces that tutorial's ViewSet rather than registering a second
route at the same prefix. Keep the application's authentication adapter and
register this class with `include_viewset` as shown in the
[ViewSet guide](viewsets.md).

```python title="app/search_views.py"
from aksara import ModelViewSet
from aksara.api import AksaraFilterBackend, SearchFilter, OrderingFilter
from aksara.permissions import IsAuthenticated
from .models import Ticket


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated]
    ai_exposed = False
    stream_enabled = False

    filter_backends = [AksaraFilterBackend, SearchFilter, OrderingFilter]
    filterable_fields = ["resolved"]
    search_fields = ["subject", "description"]
    ordering_fields = ["subject", "created_at", "id"]
    ordering = ["subject", "id"]

    def get_filter_fields(self):
        return list(self.filterable_fields)
```

After authentication, clients can request:

```text
GET /api/tickets/?resolved=false
GET /api/tickets/?search=login
GET /api/tickets/?resolved=false&search=login&ordering=-subject
GET /api/tickets/?ordering=-created_at,id&limit=20&offset=0
```

There are two filter entry points to configure:

- The generated router calls `get_filter_fields()`. Its default returns all
  model field names; override it to restrict router-provided filters.
- `AksaraFilterBackend` uses `filterable_fields`. That attribute does not by
  itself change the router's default allowlist.

The example shares one allowlist between the two. An unrelated query parameter
is ignored rather than rejected. An accepted field prefix may still carry an
unsupported lookup suffix; this backend is not a comprehensive query-language
validator. Validate client-facing query contracts explicitly if your application
requires a uniform 400/422 response for invalid filter syntax.

The backend runs synchronously to build a QuerySet. Database execution happens
later. `DjangoFilterBackend` is a compatibility alias for `AksaraFilterBackend`;
use the latter name in new applications.

## Lookups and coercion

Common ORM lookup forms include exact equality, `__gt`, `__gte`, `__lt`, `__lte`,
`__in`, `__isnull`, `__contains` and `__icontains`. The field type, ORM compiler
and PostgreSQL still determine which combinations are valid. The list above is
not an exhaustive validation allowlist implemented by the backend.

The backend's coercion is heuristic, not derived from model-field definitions:

| Input form | Value supplied by the backend |
|---|---|
| Exact `true`, `yes`, `1` (case-insensitive words) | `True` |
| Exact `false`, `no`, `0` | `False` |
| Exact `null`, `none`, or empty string | `None` |
| Other exact values such as `30` or `19.99` | String, before subsequent ORM conversion |
| `__in=a,b,c` | List of nonempty trimmed strings |
| `__gt`, `__gte`, `__lt`, `__lte` | Tries float when the value contains a dot, otherwise integer; retains a string if parsing fails |
| `__isnull` | Uses the general coercion above; arbitrary strings are not strictly rejected here |

These rules can surprise applications with string identifiers such as `"1"`,
`"true"` or `"none"`. Do not promise that every field receives the same typed
value a request-body serializer would produce. Use an application-specific
backend or explicit parameter validation when the heuristic is unsuitable.

## Search

`SearchFilter` uses the entire `search` value as a substring and combines the
configured fields with OR. Use direct text field names. Relation paths such as
`author__name` are not supported by this search implementation and fail when the
query is compiled. This is SQL `ILIKE` search, not tokenization, full-text search,
ranking, or semantic/vector search. `%` and `_` can act as pattern wildcards.

Choose searchable fields deliberately; being able to search a field can reveal
information even when it is omitted from a response. Keep tenant and object
policy independent of client search terms.

## Ordering

`OrderingFilter` reads comma-separated terms from `ordering`; `-` requests
descending order. Terms must be in `ordering_fields` and, when a principal is
resolved, pass the backend's field-visibility and tenant-field restrictions.
Prefer an explicit allowlist over `"__all__"`.

`ordering` on the class supplies the default when there is no requested ordering
(or no ordering allowlist). A string is one term; use a list/tuple for several
default terms. If a client supplies only invalid terms, the backend returns the
query unchanged rather than applying the configured default. Do not assume such
a response has deterministic ordering. For normal paginated requests, include a
unique tie-breaker such as `id`.

## Pagination and authorization

The generated default list envelope contains `count`, `results`, `limit` and
`offset`. `count` describes the filtered result set. Default limit is 20, maximum
100; the generated route rejects limits below 1 or above the configured maximum,
and negative offsets, with HTTP 422. Custom pagination classes select rows differently, but the generated response
schema currently drops page/cursor metadata; see the
[pagination limitation](pagination.md#current-custom-pagination-integration-limitation).

Permissions are checked before the list query. PolicyEngine's required query
filters are reapplied after filter backends so client parameters cannot replace
them. This does not turn custom backends into trusted authorization code or
prove that every application object policy is a SQL filter. Test cross-tenant
and unauthorized requests with your real identity adapter and restricted role.
