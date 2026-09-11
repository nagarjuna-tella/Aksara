# Choose an Aksara example

Start with the [first-project tutorial](../docs/docs/getting-started/first-project.md)
for a small model → migration → REST journey. The repository examples have
different purposes and are not interchangeable production templates.

| Example | Purpose | Status and limits |
| --- | --- | --- |
| [Basic app](basic_app/README.md) | Explore models, serializers, relations, and generated REST | Historical local demonstration; replaced by the ticket desk as the minimal starter |
| [Blog](blog/README.md) | Post and Comment relationships, publishing action, Admin | Application pattern; generated writes require a Principal adapter not supplied here |
| [CRM](crm/README.md) | Customer, Deal, and Activity models and custom actions | Application pattern; API-key headers alone do not authenticate generated writes |
| [Support Desk](support_desk/README.md) | Server-owned identities, permissions, restricted database role, forced RLS, tasks, diagnostics, synchronous MCP | Production-oriented reference with a packaged execution gate; replace example identities with your actual identity provider |
| [Multitenant](multitenant/README.md) | Historical tenant-routing and model pattern | Known middleware defect; do not use as a production isolation reference. Use Support Desk for the supported tenant boundary |
| [AI providers](ai_providers/README.md) | Application-owned provider adapters and prompting | Experimental; provider quality is outside the backend stability contract |

## Run or copy an example

Follow the individual README and configure a dedicated PostgreSQL database.
Repository-relative commands assume a source checkout. An installed framework
bundles template material under `aksara._examples`; a source import such as
`examples.support_desk` is not an installed-package import.

Inspect available templates with `aksara startproject --help`. For example:

```bash
aksara startproject myblog --template blog
aksara startproject mycrm --template crm
```

Copying a template does not establish a production security profile. Add trusted
authentication, review object and field policy, apply migrations separately,
and run through the [production guide](../docs/docs/tutorials/deployment.md).
Do not use the multitenant template to infer that tenant isolation is configured
correctly; its README records the known limitation.

## Tasks and Durable Operations

The Support Desk delivery task demonstrates ordinary persisted task execution.
Do not equate a durable task row with the v0.7 Durable Operation contract.
Operations add explicit admission, current reauthorization, idempotency,
Attempt ownership, fencing, decisions, and recovery semantics.

Use the [Durable Operations guide](../docs/docs/advanced/durable-operations.md)
for those APIs. The repository's installed-wheel and Support Desk validation
scripts exercise durability as release gates; they are not standalone user
application templates. The [durable ticket-desk chapter](../docs/docs/tutorials/ticket-desk-durable.md)
provides its action registry, identity resolver, worker process and database
lifecycle, with tests of retries, idempotency, revocation and cancellation.

## Validation scope

`aksara examples validate --format json` checks bundled example structure and
selected contracts. It does not certify every external provider, security
integration, or production deployment. Real PostgreSQL and installed-wheel
journeys remain necessary for the capabilities an application adopts.

Before contributing an example, give it a clear purpose, executable setup
instructions, a dedicated test database, and tests of both permitted and denied
behavior. Label experimental features and application-owned responsibilities.
