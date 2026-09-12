# Historical multitenant example

**Application demonstration.** This example contains Tenant, User and Project. For a complete
protected application, use the [Ticket Desk tutorial](https://nagarjuna-tella.github.io/Aksara/getting-started/first-project/).

Do not use this historical example as a production isolation reference. EX-001: its slash-prefix exemption skips tenant resolution for all normal requests. MIGRATION-001: CLI discovery replaces the example User with the built-in auth User and omits tenant_users despite successful migration commands. The application can start without a complete schema. No safe tenant seed/write flow is claimed.

## Repository source or generated copy?

If you are reading the repository's example source, first
[install Aksara](https://nagarjuna-tella.github.io/Aksara/getting-started/installation/)
in an activated environment and generate a standalone copy in your working
directory:

```bash
aksara startproject tenant_demo --template multitenant
cd tenant_demo
```

If this README is already inside a project created by `startproject`, skip those
two commands and work in that project's directory. The generated copy has flat
`models.py`, `views.py`, `settings.py` and `main.py` modules. It does not contain
an `app/` package, `.env`, or a `pyproject.toml` for editable installation.
The repository source uses package-relative imports; it is not the same layout
as a generated standalone copy.

## Run the generated copy locally

Use an environment with Aksara installed. Export `DATABASE_URL` for a dedicated
local PostgreSQL database before running these commands. This example prefers
it over `AKSARA_DATABASE_URL`; keep both values consistent if both are set.
Do not use a production database for example migrations.

```bash
aksara makemigrations --app models --output migrations
aksara migrate --migrations-dir migrations
aksara run main:app --host 127.0.0.1 --port 8000
```

Review generated migrations before applying them. A successful command does not
prove every model is present; the historical multitenant example has the
explicit omission described above.

In another terminal:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/openapi.json
```

Use `/docs` for registered API routes. Health and OpenAPI success are startup
checks, not positive CRUD, custom-action authorization, tenant isolation, or
production readiness evidence. Do not disable permissions to make an old
unauthenticated seed command succeed.

## Adapt with the public guide

Read the [historical multitenant pattern guide](https://nagarjuna-tella.github.io/Aksara/patterns/multitenant/)
for purpose, limitations and next steps. For tenant isolation, use
[Ticket Desk tenancy](https://nagarjuna-tella.github.io/Aksara/tutorials/ticket-desk-tenancy/)
and the [production guide](https://nagarjuna-tella.github.io/Aksara/tutorials/deployment/).

Optional Studio and AI surfaces are experimental. The `/ai/tools/mcp` inspection
catalog is not the MCP protocol transport or an authorization test. Follow the
[official MCP client tutorial](https://nagarjuna-tella.github.io/Aksara/tutorials/ticket-desk-mcp/)
for server-owned identity and tool execution. No provider integration is proved
by the local startup checks.
