# MCP quickstart

Aksara turns an AI-exposed `ModelViewSet` into generated MCP tools and executes
them through the same application path as REST. This journey uses PostgreSQL,
a server-resolved `Principal`, and the official MCP Python SDK.

## 1. Scaffold and configure PostgreSQL

```bash
pip install "aksara-framework==0.7.0"
aksara startproject task_api
cd task_api
```

Edit `.env` with your PostgreSQL URL and MCP settings:

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/task_api
AKSARA_MCP_ENABLED=true
AKSARA_MCP_TOKEN_AUDIENCE=task-api
APP_MCP_TOKEN=replace-with-a-random-local-token
```

`DATABASE_URL` is the scaffold default. `AKSARA_DATABASE_URL` is an accepted
higher-priority alias for deployments that namespace every setting.

## 2. Define the model

Replace `app/models.py` with:

```python
from aksara import Model, fields


class Task(Model):
    title = fields.String(max_length=200, ai_description="Short task title")
    done = fields.Boolean(default=False, ai_description="Completion state")

    class Meta:
        table_name = "quickstart_tasks"
        ai_agent_exposed = True
```

## 3. Register REST and tool generation

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

## 4. Resolve credentials on the server

Create `app/auth.py`. This compact local example maps one bearer secret to a
server-owned MCP principal. Production applications should verify their real
JWT, API key, or session and derive tenant membership, owner, audience, expiry,
roles, and scopes on the server.

```python
import hmac
import os
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware

from aksara.context_state import tenant_id_var, user_id_var
from aksara.security.principal import Principal


class QuickstartAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        expected = os.environ.get("APP_MCP_TOKEN", "")
        valid = (
            scheme.lower() == "bearer"
            and bool(expected)
            and hmac.compare_digest(token, expected)
        )
        if valid:
            principal = Principal.for_mcp_agent(
                token_id="quickstart-token",
                human_owner_id="quickstart-owner",
                agent_id="quickstart-agent",
                scopes=("mcp:read:task", "mcp:write:task"),
                metadata={
                    "audience": os.getenv(
                        "AKSARA_MCP_TOKEN_AUDIENCE", "task-api"
                    )
                },
            )
        else:
            principal = Principal.anonymous()

        user = SimpleNamespace(
            id=principal.human_owner_id,
            is_authenticated=principal.is_authenticated,
            is_staff=False,
            is_superuser=False,
        )
        request.state.user = user
        request.state.principal = principal
        request.state.tenant_id = principal.tenant_id
        request.state.auth_method = principal.auth_method
        request.state.is_ai_agent = principal.is_ai_agent
        tenant_token = tenant_id_var.set(principal.tenant_id)
        user_token = user_id_var.set(principal.human_owner_id)
        try:
            return await call_next(request)
        finally:
            user_id_var.reset(user_token)
            tenant_id_var.reset(tenant_token)
```

Add this import near the other imports in `main.py`:

```python
from app.auth import QuickstartAuthMiddleware
```

Then add the middleware immediately after the `Aksara(...)` construction and
before the server starts:

```python
app.add_middleware(QuickstartAuthMiddleware)
```

The bearer value is only an authentication input. The client cannot choose its
`Principal`, tenant, scopes, or audience.

## 5. Migrate and run

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

The generated REST API is at `/api/tasks/`. The two MCP-related surfaces have
different jobs:

| Path | Meaning |
| --- | --- |
| `/mcp/` | Streamable HTTP protocol endpoint used by MCP clients |
| `/ai/tools/mcp` | Permission-filtered HTTP JSON inspection catalog of generated tool metadata |

## 6. Use the official MCP client

Install Aksara's supported SDK line in the client environment, then run:

```python
import asyncio
import os

import httpx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def main():
    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {os.environ['APP_MCP_TOKEN']}"}
    )
    async with http_client, Client(
        streamable_http_client(
            "http://127.0.0.1:8000/mcp/",
            http_client=http_client,
        )
    ) as client:
        tools = await client.list_tools()
        assert "task_create" in {tool.name for tool in tools.tools}

        result = await client.call_tool(
            "task_create",
            {"title": "created through MCP", "done": False},
        )
        assert not result.is_error


asyncio.run(main())
```

Confirm persistence through the authenticated REST path:

```bash
curl -H "Authorization: Bearer $APP_MCP_TOKEN" \
  http://127.0.0.1:8000/api/tasks/
```

The result should include `created through MCP`. Before production use, replace
the local token mapping with real credential verification, define application
permissions and policy, review `ai_sensitive` and `ai_agent_writable` for every
field, configure tenant/RLS policy where applicable, and run
`aksara doctor production-check --release`.

See [MCP protocol server](../ai-mode/mcp.md) for approvals, audit events,
structured errors, transport settings, runtime limits, and v0.6 durability
limits.
