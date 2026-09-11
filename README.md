<p align="center">
  <img src="https://raw.githubusercontent.com/nagarjuna-tella/Aksara/main/aksara/studio/static/icons/aksara-logo.svg" width="64" alt="Aksara logo"/>
</p>

<h1 align="center">Aksara</h1>

<p align="center">
  An async PostgreSQL backend framework that generates REST APIs and authorized MCP tools from the same model and policy boundary.
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://github.com/nagarjuna-tella/Aksara/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/release-v0.7.0-22c55e?style=flat-square" alt="Release v0.7.0">
  <img src="https://img.shields.io/badge/PostgreSQL-required-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL required">
</p>

## What is Aksara?

Aksara is a Python 3.11+ framework for async PostgreSQL applications. Define an
ORM model and a `ModelViewSet`, then use the same schema and application policy
for generated REST routes and MCP tools.

The v0.6 stable contract covers the ORM, migrations, generated REST,
authentication and server-owned `Principal`, permissions and `PolicyEngine`,
tenant isolation, core CLI and Doctor, PostgreSQL background tasks, and MCP
Streamable HTTP execution at `/mcp/`.

The v0.7 release adds opt-in Durable Authorized Operations: one PostgreSQL
Operation, separate fenced Attempts, scoped idempotency, current
reauthorization, approval and cancellation intent, task-backed execution, and
honest external-effect recovery.

Planner behavior, provider-specific quality, process-local investigation
sessions, autonomous workflows, memory, and Studio AI internals remain
experimental. Aksara is pre-1.0; read the
[exact v0.7 stability contract](https://nagarjuna-tella.github.io/Aksara/roadmap/v0-7-stability-contract/)
before production adoption.

## Why Aksara?

REST callers and AI agents often reach the same data through separate code and
security paths. Aksara generates both surfaces from one model/ViewSet definition
and rechecks identity, permissions, policy, tenant, and field-write rules when a
tool actually runs. The production tenant claim also depends on a restricted
PostgreSQL role and forced RLS.

## 10-Minute Quickstart

Aksara requires PostgreSQL.

```bash
python -m venv .venv
source .venv/bin/activate
pip install "aksara-framework==0.7.0"
aksara startproject opsdesk
cd opsdesk
aksara dbsetup
```

Open `app/models.py` and define a model:

```python
from aksara import Model, fields


class Incident(Model):
    title = fields.String(max_length=200, ai_description="Short summary")
    resolved = fields.Boolean(
        default=False,
        ai_description="Resolution state",
        ai_agent_writable=False,
    )
    notes = fields.Text(nullable=True, ai_sensitive=True)

    class Meta:
        table_name = "incidents"
        ai_agent_exposed = True
```

Open `app/views.py`:

```python
from aksara import ModelViewSet

from .models import Incident


class IncidentViewSet(ModelViewSet):
    model = Incident
    prefix = "/api/incidents"
    ai_exposed = True
```

Then import `IncidentViewSet` in `app/urls.py`, add it to `urlpatterns`, and run:

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for generated
REST OpenAPI. The scaffold keeps MCP, provider-backed AI, and Studio disabled
until you configure them.

## REST and MCP

The two MCP-related paths have different meanings:

| Path | Purpose |
| --- | --- |
| `/mcp/` | MCP Streamable HTTP protocol endpoint used by official clients |
| `/ai/tools/mcp` | Permission-filtered HTTP JSON inspection catalog of generated tool metadata |

MCP requires trusted server-side authentication that resolves the bearer
credential into a `Principal`; enabling the route does not verify credentials
for your application. Follow the
[complete MCP quickstart](https://nagarjuna-tella.github.io/Aksara/getting-started/mcp/)
for the copy-pasteable model → migration → REST → Principal → official client →
persisted invocation path.

## Core Features

| Classification | Surface |
| --- | --- |
| Stable v0.6 | Async PostgreSQL ORM, relations and migrations |
| Stable v0.6 | Generated REST CRUD, validation, filters and pagination |
| Stable v0.6 | Principal, permissions, PolicyEngine, tenant and field enforcement |
| Stable v0.6 | MCP Streamable HTTP, generated tools, approval boundary, audit events, structured failures and runtime limits |
| Stable v0.6 | Core CLI, Doctor production policy, and PostgreSQL task queue |
| Stable v0.7 | Opt-in durable Operations, Attempts, idempotency, fencing, current reauthorization, decisions, retention, and external-effect recovery |
| Functional but evolving | Admin details, storage backends, email, search, SDK generation and `DurableStep` |
| Experimental | Studio/Studio AI, planners, prompt providers, investigation sessions, code patches, memory and autonomous workflows |

Application approval workflow UX, durable compliance retention, and external
exactly-once effects remain application-owned. Protocol-level durable MCP Tasks
are deferred because the official SDK does not yet implement the current Tasks
extension; synchronous MCP tools remain unchanged.

## Security boundary

Applications verify credentials and resolve a server-owned `Principal`. Aksara
then applies covered permission, object, policy, field, tenant, ORM transaction,
and RLS checks to REST and MCP execution. Schemas and hidden UI controls are
helpful descriptions; they are not authorization controls.

For production:

```bash
aksara doctor security-check
aksara doctor production-check --release
```

Read the
[Security Overview](https://nagarjuna-tella.github.io/Aksara/security/overview/)
and
[Production Hardening guide](https://nagarjuna-tella.github.io/Aksara/security/production-hardening/).
Release gates and security tests provide repository evidence; they are not an
external audit or certification.

## Configuration

The global `aksara.conf.settings` object is the runtime source of truth. Use
environment variables for deploy-time values and `configure(...)` for explicit
Python overrides. Precedence is explicit configuration, `AKSARA_*` environment
variables, supported aliases such as `DATABASE_URL`, then defaults.

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/opsdesk
AKSARA_DEBUG=true
AKSARA_MCP_ENABLED=false
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
```

An `AKSARA = {...}` dictionary does not configure the runtime. See the
[Settings Reference](https://nagarjuna-tella.github.io/Aksara/reference/settings-reference/).

## Open Studio

Studio is an experimental inspection and AI surface at `/studio/ui`. It is
disabled in new projects. Enabling it requires its secret/authentication and
production exposure settings; see the
[Studio guide](https://nagarjuna-tella.github.io/Aksara/studio/).

## Use AI

Provider-backed prompt execution is optional and experimental. Configure the
current AI Hub path when you need it:

```bash
aksara ai-hub configure
aksara ai-hub status
aksara ai-hub doctor
```

There is no public `AgentRuntime` or `Planner` class in v0.7.0. The documented
real primitives remain experimental and are described in the
[AI Mode guide](https://nagarjuna-tella.github.io/Aksara/ai-mode/).

## Use MCP

Set `AKSARA_MCP_ENABLED=true` only after adding server-side Principal
resolution, then connect an official MCP client to
`http://127.0.0.1:8000/mcp/`. MCP does not require an AI model provider.

## Examples

- [Basic app](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/basic_app)
- [Blog](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/blog)
- [CRM](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/crm)
- [Multi-tenant app](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/multitenant)
- [Support Desk production reference](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/support_desk)

From a source checkout, validate bundled examples with:

```bash
aksara examples validate --format json
```

## Documentation

- [Installation](https://nagarjuna-tella.github.io/Aksara/getting-started/installation/)
- [First Project](https://nagarjuna-tella.github.io/Aksara/getting-started/first-project/)
- [MCP Quickstart](https://nagarjuna-tella.github.io/Aksara/getting-started/mcp/)
- [Durable Authorized Operations](https://nagarjuna-tella.github.io/Aksara/advanced/durable-operations/)
- [v0.7 Stability Contract](https://nagarjuna-tella.github.io/Aksara/roadmap/v0-7-stability-contract/)
- [ORM](https://nagarjuna-tella.github.io/Aksara/orm/)
- [API](https://nagarjuna-tella.github.io/Aksara/api/)
- [Security](https://nagarjuna-tella.github.io/Aksara/security/overview/)
- [CLI](https://nagarjuna-tella.github.io/Aksara/cli/)
- [Runtime compatibility](https://nagarjuna-tella.github.io/Aksara/reference/runtime-compatibility/)

## Roadmap

v0.7.0 implements the accepted Durable Authorized Operations architecture
while preserving the v0.6 synchronous surfaces and PostgreSQL-first deployment
profile. See the
[Roadmap](https://nagarjuna-tella.github.io/Aksara/roadmap/).

## Contributing

Read the
[Contributing Guide](https://github.com/nagarjuna-tella/Aksara/blob/main/CONTRIBUTING.md)
and [Code of Conduct](https://github.com/nagarjuna-tella/Aksara/blob/main/CODE_OF_CONDUCT.md).
Run the relevant tests and strict documentation build before opening a pull
request.

## License

[MIT](https://github.com/nagarjuna-tella/Aksara/blob/main/LICENSE)
