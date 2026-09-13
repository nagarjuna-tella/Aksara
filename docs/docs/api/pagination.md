# Pagination

Generated list routes use limit/offset pagination by default. Keep ordering
explicit and include a unique tie-breaker so unchanged data has predictable
page boundaries. Pagination does not provide a snapshot across requests.

## Default generated list

For the [Ticket model](../getting-started/first-project.md), replace its ViewSet
with this configuration and retain the application's authentication adapter and
`include_viewset` registration:

```python title="app/pagination_views.py"
from aksara import ModelViewSet
from aksara.api import OrderingFilter
from aksara.permissions import IsAuthenticated
from .models import Ticket


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated]
    ai_exposed = False
    stream_enabled = False
    pagination_class = None
    default_limit = 20
    max_limit = 100
    filter_backends = [OrderingFilter]
    ordering_fields = ["id"]
    ordering = ["id"]

    def get_filter_fields(self):
        return []
```

```text
GET /api/tickets/?limit=20&offset=0
GET /api/tickets/?limit=20&offset=20
```

The response has `count`, `limit`, `offset`, and `results`. Generated route
validation rejects `limit < 1`, a limit above `max_limit`, and negative offsets
with HTTP 422. `count` describes the filtered query, not just the returned page.
Concurrent inserts/deletes can shift offsets; do not promise repeatable traversal
of a changing dataset without an application-specific consistency contract.

## Custom pagination classes

Setting `pagination_class` changes both the generated route parameters and its
response schema. `PageNumberPagination` exposes `page` and `size` and retains
`page`, `size`, and `total_pages` in HTTP responses. `CursorPagination` exposes
`cursor` and `page_size` and returns `next_cursor` as a string or `null`.
`LimitOffsetPagination` exposes `limit` and `offset` and uses its own default and
maximum limit. These contracts also appear in OpenAPI and generated TypeScript
client types.

An application-defined paginator can declare `response_schema_fields` for a
concrete generated response schema. Without that declaration, Aksara uses an
unstructured mapping so FastAPI response serialization preserves custom
metadata rather than discarding unknown keys.

## Paginator class behavior

These classes are available from `aksara.api.pagination`. The metadata below is
what the paginator returns before the generated response schema is applied.

| Class | Parameters | Defaults / maximum | Metadata |
|---|---|---|---|
| `LimitOffsetPagination` | `limit`, `offset` | 20 / 100; offset 0 | `count`, `limit`, `offset`, `results` |
| `PageNumberPagination` | `page`, `size` | page 1; size 20 / 100 | `count`, `page`, `size`, `total_pages`, `results` |
| `CursorPagination` | `cursor`, `page_size` | size 20 / 100 | `count`, `results`, `next_cursor` (string or null) |

Direct paginator use normalizes malformed or out-of-range numeric values. The
generated HTTP route gives each built-in paginator typed, bounded parameters and
returns HTTP 422 for invalid numeric bounds.

## Cursor limits

The current cursor contains base64-encoded JSON with an `id`, and continuation
adds `id__gt` to the query. It does not encode arbitrary ordering fields or
support descending continuation. If using the paginator in an application-owned
endpoint, require ascending ID ordering and preserve IDs in the serialized rows.
An ordering such as `-created_at` is incompatible with its continuation rule.

`count` is computed after applying the cursor filter, so it counts remaining
matching rows, not the original total. A full page emits a cursor even if there
are no more rows; the following request can return an empty page. Invalid
base64/JSON is ignored and may restart traversal. Cursor contents are not signed
or an authorization credential; apply the caller's current policy to every page.

Avoid unconditional performance claims. The implementation still issues a count
query; cost depends on indexes, predicates and data volume. A keyset predicate
can avoid scanning through a large offset, but this does not establish O(1)
request cost or snapshot stability under data changes.

See [filtering and ordering](filtering.md) for query allowlists and
[ViewSets](viewsets.md) for generated route configuration.
