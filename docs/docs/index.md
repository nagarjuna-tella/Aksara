# Aksara Framework

## Async PostgreSQL, generated REST, and authorized MCP tools

Aksara is a Python 3.11+ backend framework for PostgreSQL applications. Define
an ORM model and a `ModelViewSet`, then expose the same application behavior
through generated REST routes and MCP tools.

[Build your first project →](getting-started/first-project.md){ .md-button .md-button--primary }
[Follow the MCP journey](getting-started/mcp.md){ .md-button }

!!! info "v0.7.0 durable authorized operations"
    The candidate adds opt-in PostgreSQL Operations and fenced Attempts,
    scoped idempotency, current reauthorization, durable approval and
    cancellation intent, task-backed execution, and honest external-effect
    recovery while preserving the v0.6 synchronous surfaces.

## The core idea

REST callers and AI agents often reach the same data through different code and
security paths. Aksara generates both surfaces from one model and ViewSet, then
rechecks identity, permissions, policy, tenant, and field-write rules when an
operation runs.

```text
Model + ViewSet
      |
      +--> PostgreSQL migration
      +--> generated REST API
      +--> generated MCP tool
                 |
                 +--> the same Principal, policy, tenant, field, ORM,
                      transaction, and PostgreSQL RLS boundaries
```

## Start with the stable backend

Aksara requires PostgreSQL.

```bash
python -m venv .venv
source .venv/bin/activate
pip install "aksara-framework==0.7.0"
aksara startproject opsdesk
cd opsdesk
aksara dbsetup
```

Define a model in `app/models.py`:

```python
from aksara import Model, fields


class Incident(Model):
    title = fields.String(max_length=200)
    resolved = fields.Boolean(default=False, ai_agent_writable=False)

    class Meta:
        table_name = "incidents"
        ai_agent_exposed = True
```

Define a ViewSet in `app/views.py`:

```python
from aksara import ModelViewSet

from .models import Incident


class IncidentViewSet(ModelViewSet):
    model = Incident
    prefix = "/api/incidents"
    ai_exposed = True
```

Register it in `app/urls.py`, then run:

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

Open `http://127.0.0.1:8000/docs` for generated REST OpenAPI. The generated
project keeps MCP, provider-backed AI, and Studio disabled until explicitly
configured.

## REST and MCP share an execution boundary

The MCP paths serve different purposes:

| Path | Meaning |
| --- | --- |
| `/mcp/` | Streamable HTTP protocol endpoint used by official MCP clients |
| `/ai/tools/mcp` | Permission-filtered HTTP JSON inspection catalog for generated tool metadata |

An application must verify credentials and resolve a server-owned `Principal`.
Aksara then applies covered permission, object, `PolicyEngine`, field, tenant,
transaction, and PostgreSQL RLS checks to REST and MCP execution. Enabling MCP
does not implement an application's credential verifier.

The [MCP quickstart](getting-started/mcp.md) is the canonical model → migration
→ REST → Principal → official MCP client → persisted result journey.

## Stability map

| Classification | Surface |
| --- | --- |
| Stable v0.6 | Async PostgreSQL ORM, relations, migrations, and transaction/session handling |
| Stable v0.6 | Generated REST CRUD, validation, filters, pagination, and OpenAPI |
| Stable v0.6 | Authentication boundary, Principal, permissions, `PolicyEngine`, tenant and field enforcement |
| Stable v0.6 | MCP Streamable HTTP, generated tools, execution-time authorization, exact approval grants, audit events, structured failures, cancellation, and bounded limits |
| Stable v0.6 | Core CLI, Doctor production policy, and PostgreSQL task queue |
| Functional but evolving | Admin details, storage backends, email, search, SDK generation, and `DurableStep` |
| Experimental | Studio/Studio AI, planners, provider-backed prompts, investigations, code patches, memory, and autonomous workflows |

Aksara is pre-1.0. Read the
[v0.6 stability and production contract](roadmap/v0-6-stability-contract.md)
before production adoption.

## Configuration

The global `aksara.conf.settings` object is the runtime source of truth. Use
environment variables for deploy-time values and `configure(...)` for explicit
Python overrides. Precedence is explicit configuration, `AKSARA_*` environment
variables, supported compatibility aliases such as `DATABASE_URL`, then
defaults.

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/opsdesk
AKSARA_DEBUG=true
AKSARA_MCP_ENABLED=false
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
```

An `AKSARA = {...}` dictionary does not configure the runtime. See the
[settings reference](reference/settings-reference.md) for current, compatible,
deprecated, and experimental paths.

## Production boundary

Run the production diagnostics with deployment configuration and a migration
role:

```bash
aksara doctor security-check
aksara doctor production-check --release
```

Production tenant isolation requires a restricted PostgreSQL role and forced
RLS. Signed MCP approval grants are bounded authorization inputs; they do not
provide a durable human-review workflow. Replay state is process-local, and
applications own durable audit retention and external side-effect idempotency.

## Experimental AI surfaces

Provider-backed prompt execution and planner, investigation, patch, and Studio
AI surfaces are available for experimentation. They are not part of the stable
v0.6 guarantee. The installed package does not export a public `AgentRuntime`
or `Planner` class; the [AI Mode guide](ai-mode/index.md) documents the narrower
real primitives and labels conceptual material explicitly.

## Continue

- [Installation](getting-started/installation.md)
- [First project](getting-started/first-project.md)
- [MCP quickstart](getting-started/mcp.md)
- [ORM](orm/index.md)
- [Generated API](api/index.md)
- [Security](security/overview.md)
- [CLI](cli/index.md)
- [Runtime compatibility](reference/runtime-compatibility.md)
- [Roadmap](roadmap.md)
