# Quickstart

Build a PostgreSQL-backed Task API from the installed package, then choose
whether to add MCP. Provider-backed AI and Studio are not prerequisites.

## Install and scaffold

```bash
python -m venv .venv
source .venv/bin/activate
pip install "aksara-framework==0.6.1"
aksara startproject task_api
cd task_api
aksara dbsetup
```

The scaffold loads environment variables into the global
`aksara.conf.settings` object. It keeps MCP, provider-backed AI, and Studio
disabled until explicitly configured.

## Define the model

Replace `app/models.py` with:

```python
from aksara import Model, fields


class Task(Model):
    title = fields.String(max_length=200, ai_description="Short task title")
    done = fields.Boolean(default=False, ai_description="Completion state")

    class Meta:
        table_name = "tasks"
        ai_agent_exposed = True
```

## Generate REST routes

Replace `app/views.py` with:

```python
from aksara import ModelViewSet

from .models import Task


class TaskViewSet(ModelViewSet):
    model = Task
    prefix = "/api/tasks"
    ai_exposed = True
```

Replace `app/urls.py` with:

```python
from aksara import include_viewset

from .views import TaskViewSet


urlpatterns = [TaskViewSet]


def register_routes(app):
    for viewset in urlpatterns:
        include_viewset(app, viewset)
```

## Migrate and run

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

Open `http://127.0.0.1:8000/docs` and inspect `/api/tasks/` in generated
OpenAPI. Aksara requires a server-resolved authenticated `Principal` for
protected writes, so anonymous POST requests are denied.

## Add the stable MCP path

The two tool-related routes are different:

| Path | Purpose |
| --- | --- |
| `/mcp/` | Streamable HTTP protocol endpoint for official MCP clients |
| `/ai/tools/mcp` | HTTP JSON inspection catalog for generated tool metadata |

Continue with the [MCP quickstart](getting-started/mcp.md). It adds a small
server-side bearer verifier, resolves an MCP `Principal`, connects an official
client to `/mcp/`, calls `task_create`, and confirms the database row over
REST.

## What is stable

The v0.6 contract covers the ORM, migrations, generated REST, authentication and
Principal boundaries, permissions and `PolicyEngine`, tenant isolation, core
CLI and Doctor, PostgreSQL tasks, and generated MCP execution. Planner quality,
provider-backed AI, investigations, memory, autonomous workflows, and Studio AI
internals remain experimental.

Read the [full stability contract](roadmap/v0-6-stability-contract.md) and
[production security guidance](security/production-hardening.md) before
deployment.
