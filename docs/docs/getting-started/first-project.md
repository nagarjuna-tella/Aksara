# First project

This is the shortest path from the installed wheel to a generated REST API.
PostgreSQL is required.

## Install and scaffold

```bash
python -m venv .venv
source .venv/bin/activate
pip install "aksara-framework==0.7.0"
aksara --version
aksara startproject hello_aksara
cd hello_aksara
aksara dbsetup
```

`dbsetup` writes `DATABASE_URL` to `.env`. You can edit it directly instead.
`AKSARA_DATABASE_URL` is the higher-priority namespaced alias.

## Define a model

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

## Register a REST API

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

## Migrate and check readiness

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

Open:

- REST OpenAPI: http://127.0.0.1:8000/docs
- generated Task API: http://127.0.0.1:8000/api/tasks/
- tool inspection catalog: http://127.0.0.1:8000/ai/tools/mcp

The inspection catalog is ordinary HTTP JSON. MCP clients use Streamable HTTP
at `/mcp/`, which is disabled in the scaffold until you add server-side
authentication and set `AKSARA_MCP_ENABLED=true`.

Continue with the [MCP quickstart](mcp.md) to resolve a server-owned `Principal`,
connect the official client to `http://127.0.0.1:8000/mcp/`, create a Task
through the generated tool, and verify the persisted row through REST.

Provider-backed AI and Studio are experimental and disabled in a fresh project.
They are not prerequisites for generated REST or MCP.
