# First app

The basic scaffold contains neutral model, serializer, ViewSet, route, and admin
stubs. The [First project](first-project.md) guide turns those stubs into a Task
API using exported v0.7.0 APIs.

A minimal resource has three parts:

```python
# app/models.py
from aksara import Model, fields


class Task(Model):
    title = fields.String(max_length=200)
    done = fields.Boolean(default=False)

    class Meta:
        table_name = "tasks"
        ai_agent_exposed = True
```

```python
# app/views.py
from aksara import ModelViewSet

from .models import Task


class TaskViewSet(ModelViewSet):
    model = Task
    prefix = "/api/tasks"
    ai_exposed = True
```

```python
# app/urls.py
from aksara import include_viewset

from .views import TaskViewSet


urlpatterns = [TaskViewSet]


def register_routes(app):
    for viewset in urlpatterns:
        include_viewset(app, viewset)
```

Apply the model to PostgreSQL and start the app:

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

`/api/tasks/` is the generated REST collection. Protected mutations require a
server-resolved Principal. Setting `ai_exposed=True` also makes generated tools
eligible for the inspection catalog and, after MCP and authentication are
configured, the protocol endpoint at `/mcp/`.

Use the [MCP quickstart](mcp.md) for the authenticated official-client journey.
Studio and provider-backed AI remain optional experimental surfaces.
