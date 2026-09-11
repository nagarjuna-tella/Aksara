# AI route hints

!!! warning "Experimental metadata surface"
    Route hints describe application behavior for development tools. They do
    not enforce permission, tenancy, approval or transaction rules and are not
    the stable MCP execution contract.

`ai_route_hint` attaches metadata to a callable without invoking a provider or
changing what the callable does. This complete example demonstrates that boundary:

```python
from aksara.ai import ai_route_hint, get_hint_from_callable


@ai_route_hint(
    title="Describe a ticket",
    description="Return a short ticket description",
    usage_kind="read_only",
    risk_level="low",
)
def describe_ticket(subject: str) -> str:
    return f"Ticket: {subject}"


assert describe_ticket("Printer offline") == "Ticket: Printer offline"
assert get_hint_from_callable(describe_ticket)["usage_kind"] == "read_only"
```

For a real route or ViewSet action, attach the decorator to the actual handler.
This example does not register an HTTP route. `usage_kind` values are
`read_only`, `write` and `admin`; `risk_level` values are `low`, `medium` and
`high`. A handler labeled `read_only` can still mutate data if its implementation
does so. Keep metadata accurate and enforce the real boundary in application code.

Other supported fields include `example_prompt`, `example_input`,
`example_output`, `recommended_model` and `recommended_provider`.
`set_view_default_hint()` attaches class-level defaults; handler metadata takes
precedence for that handler. Do not depend on these hints to implement approvals.

Inspect registered application hints through:

```bash
aksara ai hints --format json
aksara ai hints --risk high
```

The CLI also supports `--view` and `--route` filters. Its application must be
importable and configured; hints are not discovered from arbitrary source files.
For executable tools and denied-call tests, use the
[MCP tutorial](../tutorials/ticket-desk-mcp.md).
