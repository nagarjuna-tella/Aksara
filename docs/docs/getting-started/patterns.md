# Choose a starting point

For a first application, use [Ticket Desk](first-project.md). It starts from the
basic scaffold and grows one tested application through relations, permissions,
tenancy, background reports, durable actions, and an optional MCP client.

| Your goal | Start here |
|---|---|
| Learn the basic application lifecycle | [First project](first-project.md) and [project layout](project-layout.md). |
| Study posts, comments, and state-changing actions | [Blog example](../patterns/blog.md), with its documented authentication limitations. |
| Study customer/deal relationships and pipeline actions | [CRM example](../patterns/crm.md), an application demonstration. |
| Build tenant-isolated data access | [Ticket Desk tenancy](../tutorials/ticket-desk-tenancy.md), not the historical multitenant template. |
| Run a production-oriented reference | [Example tiers](examples.md) and [production deployment](../tutorials/deployment.md). |
| Explore optional model providers | [Bring your own LLM](../ai-mode/bring-your-own-llm.md), explicitly experimental. |

## Generate a basic shell

```bash
aksara startproject myapp
```

The default template provides the application layout and commented model/API
examples. It does not create a finished domain application or automatically
start a durable worker. Studio and MCP are optional and disabled by default.
Follow the generated README and the first-project tutorial for dependency,
database, migration, and test instructions.

## Inspect a domain template

```bash
aksara templates list
```

The available names are `basic`, `blog`, `crm`, and `multitenant`. The three domain
templates copy bundled example modules into a flat directory, rather than
producing the basic template's `app/` package and `pyproject.toml`. Their settings
also differ. Follow each pattern page's checked commands instead of assuming
that all templates share one install/startup flow.

The blog copy contains `Post` and `Comment`. CRM contains `Customer`, `Deal`,
and `Activity`; it does not contain separate `Pipeline` and `Stage` models.
The historical multitenant copy contains `Tenant`, `User`, and `Project` and has
a [known resolver defect](../patterns/multitenant.md). It is retained for study,
not recommended as a SaaS security foundation.

The provider-adapter example is a separate experimental example, not another
`--template` choice. Consult the [example catalog](examples.md) for the purpose,
execution coverage, and limitations of every repository example.
