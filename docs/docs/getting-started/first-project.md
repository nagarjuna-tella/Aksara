# First Project

This is the shortest complete path from install to a running Aksara app.

## Install

```bash
pip install aksara-framework
aksara --version
```

## Create a Project

```bash
aksara startproject hello_aksara
cd hello_aksara
```

## Define a Model

Open `app/models.py` and add a model:

```python
from aksara import Model, fields

class Task(Model):
    title = fields.String(max_length=200, ai_description="Short task title")
    done = fields.Boolean(default=False, ai_description="Whether the task is complete")

    class Meta:
        table_name = "tasks"
        ai_agent_exposed = True
```

## Register an API

Open `app/views.py` and expose the model through a ViewSet:

```python
from aksara.api import ModelViewSet
from .models import Task

class TaskViewSet(ModelViewSet):
    model = Task
```

## Check Readiness

```bash
aksara doctor launch-check
```

If the database is not configured, run:

```bash
aksara dbsetup
```

## Migrate

```bash
aksara makemigrations
aksara migrate
```

## Run the Dev Server

```bash
aksara dev
```

## Open Docs and Studio

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* MCP tools: http://127.0.0.1:8000/ai/tools/mcp
