# Application patterns

Use a pattern to study how models and API actions fit together. For your first
working application, follow the [Ticket Desk tutorial](../getting-started/first-project.md):
it supplies the identity adapter, migrations, and positive/negative tests that
these older domain examples do not.

| What you want to learn | Example | Boundary |
|---|---|---|
| Related content and explicit state changes | [Blog](blog.md) | Post and Comment; local domain demonstration, not a complete protected publishing application. |
| Customer relationships and sales actions | [CRM](crm.md) | Customer, Deal and Activity; illustrative pipeline logic, not a production CRM or accounting system. |
| Authenticated tenant isolation | [Ticket Desk tenancy](../tutorials/ticket-desk-tenancy.md) | The recommended path, with server-owned tenant identity and restricted-role PostgreSQL RLS. |
| Historical tenant middleware design | [Multitenant example](multitenant.md) | Known resolver defect; retained for inspection, not an isolation reference. |

## Templates and examples are different starting points

`aksara templates list` lists `basic`, `blog`, `crm`, and `multitenant`.
The default `basic` template generates a project shell with commented model/API
examples, a project configuration, and setup guidance. The three domain templates
copy their bundled example files into a flat directory. They do not have the
same layout or defaults as `basic`.

Use [Choosing a starting point](../getting-started/patterns.md) before generating
a project. Follow the specific pattern page's commands for domain templates:
the CLI's generic post-generation file tree and next steps do not describe their
actual copied layout. In particular, do not assume an `app/` package,
`pyproject.toml`, or `.env` exists.

## Adapt a pattern deliberately

Start with the domain model, then decide which operations each actor may perform.
A publish flag or deal stage is application state, not a Durable Operation.
An API-key helper does not by itself establish the Principal used by generated
write permissions. Custom HTTP actions also need explicit authorization checks;
see the [action contract](../api/actions.md) before exposing one.

Use the checked references when adapting an example:

- [Relations](../orm/relations.md) for foreign-key storage and eager loading.
- [Serializers](../api/serializers.md) for input validation and output shaping.
- [Authentication](../api/authentication.md) and [permissions](../api/permissions.md)
  for identity and allowed operations.
- [Durable actions](../tutorials/ticket-desk-durable.md) when a delayed or retried
  mutation needs current authorization and recovery.
- [MCP client tutorial](../tutorials/ticket-desk-mcp.md) for an authenticated tool
  consumer. Model metadata alone does not mount a safe protocol endpoint.

Optional Studio and AI settings in historical examples are experimental. Their
presence is not a requirement for an ordinary backend, nor evidence of a tested
provider integration.
