# CRM example

**Application demonstration.** This example illustrates related customer data
and sales-stage actions. It is not a complete CRM, financial ledger, or
production authorization design. Start with the protected
[Ticket Desk application](../getting-started/first-project.md) if you need a
complete onboarding and testing path.

## What is in the example

| Model | What it illustrates |
|---|---|
| `Customer` | Contact information and application metadata. |
| `Deal` | A customer relationship, decimal `amount`, a string `stage`, and a probability value. |
| `Activity` | Follow-up information related to the customer/deal domain. |

There are no separate `Pipeline` or `Stage` models in this template. Stage labels
and transition logic are defined in the example code. The older guide's `value`
field and model declarations did not match the actual example; inspect the
copied `models.py` before designing a migration or request.

The ViewSets include pipeline, forecast, and stage-transition actions. These are
illustrative application calculations. An action named `forecast` is not proof
of statistical prediction or accounting correctness, and an AI-related name
does not establish that a provider is involved.

## Generate a local copy

Use an activated environment with [Aksara installed](../getting-started/installation.md).
Export `DATABASE_URL` for a dedicated local PostgreSQL database. This example
prefers `DATABASE_URL` over `AKSARA_DATABASE_URL`; keep them consistent.

```bash
aksara startproject crm_demo --template crm
cd crm_demo
aksara makemigrations --app models --output migrations
aksara migrate --migrations-dir migrations
aksara run main:app --host 127.0.0.1 --port 8000
```

The copied modules are flat files, so use `models`, not `app.models`. No
`pyproject.toml` or `.env` is generated for this domain template. If an older CLI
suggests an editable install, use the framework already installed in your
environment instead.

In another terminal:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/openapi.json
```

Use `/docs` to inspect registered endpoints. Generated updates use `PATCH`.
Health and OpenAPI success prove startup, not a complete customer/deal workflow.

## Adapt the boundaries before using real customer data

A valid unauthenticated POST to `/api/customers/` returns **403** in released v0.7.0.
The example API-key helper does not supply the Principal expected by generated
write permissions. Copy the [authentication](../api/authentication.md) and
[permission](../api/permissions.md) approach from a tested application rather
than removing that protection.

Custom HTTP actions need explicit authorization checks. Decide who may read
contact data, change amounts, transition stages, and inspect aggregate reports.
Field metadata such as `ai_sensitive` or `ai_agent_writable` does not replace
those application policies or make the example a tenant-isolated backend.
See [field-level permissions](../security/field-level-permissions.md) and the
[action contract](../api/actions.md).

Use [Decimal fields](../orm/fields.md) and an explicit application rounding and
currency policy for monetary values. A weighted pipeline total is a sales
estimate; it does not record recognized revenue or a payment. Add database and
HTTP tests for the business rules you actually need.

For tenant-owned customers and deals, follow the
[tenant-isolation chapter](../tutorials/ticket-desk-tenancy.md). For a delayed,
authorized state change, follow [durable actions](../tutorials/ticket-desk-durable.md).
These paths preserve the same identity and transaction reasoning as the
canonical application without treating this historical example as complete.
