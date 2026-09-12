# Choose an example

Use the [ticket desk](first-project.md) for the complete beginner-to-durable
application path. Repository examples are supplementary demonstrations with
different boundaries; a template is not a production security profile.

| Example | Purpose | Current scope |
| --- | --- | --- |
| `basic_app` | Models, serializers and legacy/manual versus generated APIs | Starts locally; its old unauthenticated seed request is denied. Replaced by the ticket desk as the minimal starter |
| `blog` | Post/Comment relationship and custom publishing actions | Starts after generating migrations; requires an application identity adapter for generated writes |
| `crm` | Customer/Deal/Activity model and action patterns | Starts after generating migrations; API-key examples do not supply a Principal |
| `support_desk` | Production-oriented reference with restricted-role RLS, tasks and synchronous MCP | Has a packaged execution gate; application identities remain an example adapter |
| `multitenant` | Historical tenant-routing code | Known middleware exemption defect; use Support Desk or the ticket-desk tenancy chapter for isolation |
| `ai_providers` | Application-owned provider adapters | Experimental configuration/status demo; no live provider quality or availability guarantee |

Read the [repository example catalog](https://github.com/nagarjuna-tella/Aksara/tree/main/examples)
for exact setup and limitations. Source-checkout examples use explicit package
entry points such as `examples.blog.main:app`; installed framework code and
copied application examples are different things.

## What the structural validator proves

```bash
aksara examples validate
aksara examples validate --format json
```

This checks bundled structure, selected imports and README conventions. It does
not execute migrations and authenticated requests or validate tenant isolation.
A successful report does not override an example's documented limitations.

## Three learning tiers

1. **Minimal:** the [first project](first-project.md) supplies a model, migration,
   protected REST API and positive/negative tests.
2. **Production-oriented:** the [deployment guide](../tutorials/deployment.md)
   connects the Support Desk reference to restricted roles, RLS and diagnostics.
3. **Durable:** the [ticket-desk durable chapter](../tutorials/ticket-desk-durable.md)
   supplies registration, admission, worker, idempotency, status, retry,
   cancellation and current-authorization tests.

Optional [MCP access](../tutorials/ticket-desk-mcp.md) uses the official protocol
client. `/mcp/` is its Streamable HTTP endpoint; `/ai/tools/mcp` is an inspection
catalog. Studio, AI Console and provider-backed experiments are separate from
these backend guarantees.
