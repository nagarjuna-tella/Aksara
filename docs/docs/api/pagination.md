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

## Current custom-pagination integration limitation

**Known defect in 0.7.0 (PAGINATION-001):** setting `pagination_class` to
`PageNumberPagination` or `CursorPagination` changes row selection, but the
generated route's fixed response schema discards their additional metadata.
A page-number HTTP response loses `page`, `size` and `total_pages`; a cursor HTTP
response loses `next_cursor`. Both can include `limit: null` and `offset: null`.

Do not build a generated cursor client assuming it will receive a usable next
cursor. Use the default limit/offset path until a separate runtime patch fixes
the response integration, or own and test an application endpoint and response
schema explicitly. Calling a ViewSet or paginator directly is not proof of the
HTTP response contract.

`LimitOffsetPagination` uses the same envelope as the generated route. Setting
it explicitly is supported, but the class has its own `default_limit` and
`max_limit`. Those are separate from the ViewSet attributes used by the generated
route's request validation; keep them aligned if you customize either.

## Paginator class behavior

These classes are available from `aksara.api.pagination`. The metadata below is
what the paginator returns before the generated response schema is applied.

| Class | Parameters | Defaults / maximum | Metadata |
|---|---|---|---|
| `LimitOffsetPagination` | `limit`, `offset` | 20 / 100; offset 0 | `count`, `limit`, `offset`, `results` |
| `PageNumberPagination` | `page`, `size` | page 1; size 20 / 100 | `count`, `page`, `size`, `total_pages`, `results` |
| `CursorPagination` | `cursor`, `page_size` | size 20 / 100 | `count`, `results`, optional `next_cursor` |

Page-number parsing falls back to page 1/default size when integer parsing
fails, clamps a page below 1 to 1, restores the default for size below 1, and
caps size at the maximum. Cursor page-size parsing similarly falls back and
caps. These are paginator behaviors, not a promise of strict invalid-input
rejection. The generated route still validates its own `limit`/`offset` query
parameters even when another pagination class selects rows.

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
