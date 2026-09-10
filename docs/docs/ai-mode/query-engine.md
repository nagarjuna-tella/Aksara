# AI query plans

!!! warning "Experimental"
    Aksara does not expose a `QueryEngine` class that turns natural language
    into database queries. The real API executes a structured `AiQueryPlan`.

An external model or application may construct a validated plan:

```python
from aksara.ai.query import (
    AiFilterCondition,
    AiQueryPagination,
    AiQueryPlan,
    AiSortField,
    execute_ai_query_plan,
)

plan = AiQueryPlan(
    model="Task",
    filters=[AiFilterCondition(field="done", lookup="exact", value=False)],
    sorting=[AiSortField(field="created_at", direction="desc")],
    pagination=AiQueryPagination(limit=20, offset=0),
    select_fields=["id", "title", "done"],
)
result = await execute_ai_query_plan(plan)
print(result.rows)
```

The executor resolves a registered model, validates field names and supported
lookups, applies ORM filters and ordering, and returns serialized rows. It does
not parse natural language or call an LLM.

This low-level helper does not receive a request `Principal`; do not expose it
directly to untrusted callers. Application code must establish authorization,
field visibility, and tenant context first. Generated REST and MCP routes are
the stable policy-enforced public execution paths.
