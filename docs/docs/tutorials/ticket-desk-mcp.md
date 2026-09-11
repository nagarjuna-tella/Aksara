# Let an MCP client use the ticket API

**Stable synchronous MCP execution.** This optional chapter continues the
[same ticket desk](ticket-desk-durable.md). It adds a machine credential and
uses the official MCP Python client to create and update tickets through the
same generated application path as REST. No model provider, planner or Studio
is needed. Keep the existing restricted role, forced RLS and membership file.

MCP is a transport for these synchronous tools. It does not automatically make
a tool a Durable Operation, and the server does not advertise protocol-level
MCP Tasks. The human durable-action path from the previous chapter stays separate.

## 1. Enable MCP explicitly

Stop the server. Append to the generated `settings.py`:

```python title="settings.py (append)"
from aksara.conf import configure

configure(
    mcp_enabled=True,
    mcp_token_audience="ticket-desk",
    mcp_require_scoped_tokens=True,
    ai_enabled=False,
    enable_studio=False,
)

```

The existing installed-app registration remains in that file. These keyword
settings are explicit application choices; package and scaffold defaults are
unchanged. Loopback host/origin defaults support this local client. For a remote
service, configure reviewed host/origin lists through explicit `configure(...)`
values as described in the [settings reference](../reference/settings-reference.md).

Generate three distinct local secrets in the server terminal, then supply the
same values to the client/test terminal:

```bash
export APP_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_MCP_READ_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_MCP_EXPIRED_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_MCP_EXPIRES_AT="$(python -c 'import time; print(int(time.time()) + 900)')"
```

The third secret is an intentionally expired negative-test credential. Valid
credentials expire at the fixed timestamp, not 15 minutes after each request.
After expiry, generate new local secrets and restart with a new timestamp; do
not disable expiry checks. Never commit these values or include them in examples.

## 2. Resolve credentials on the server

Replace `app/auth.py`:

```python title="app/auth.py"
import hmac
import os
from datetime import datetime, timezone
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware

from aksara.middleware.context import tenant_id_var, user_id_var
from aksara.security.principal import Principal
from starlette.responses import JSONResponse

from .identities import current_principal



class LocalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        principal = Principal.anonymous()
        identities = [
            ("APP_API_TOKEN", "editor-a"),
            ("APP_TENANT_B_TOKEN", "editor-b"),
            ("APP_READER_TOKEN", "reader-a"),
            ("APP_UNSCOPED_TOKEN", "unscoped-user"),
        ]
        if scheme.lower() == "bearer":
            for variable, user in identities:
                expected = os.environ.get(variable, "")
                if expected and hmac.compare_digest(token, expected):
                    try:
                        principal = current_principal(user) or Principal.anonymous()
                    except (OSError, ValueError, KeyError, TypeError):
                        return JSONResponse({"detail": "Identity store unavailable"}, status_code=503)
                    break
        if principal.is_anonymous and scheme.lower() == "bearer":
            agents = [
                ("APP_MCP_TOKEN", "editor-a", "ticket-writer", ("mcp:read:ticket", "mcp:write:ticket"), False),
                ("APP_MCP_READ_TOKEN", "reader-a", "ticket-reader", ("mcp:read:ticket",), False),
                ("APP_MCP_EXPIRED_TOKEN", "editor-a", "expired-test", ("mcp:read:ticket",), True),
            ]
            for variable, owner_id, token_id, scopes, expired in agents:
                expected = os.environ.get(variable, "")
                if not expected or not hmac.compare_digest(token, expected):
                    continue
                try:
                    owner = current_principal(owner_id)
                    expires = datetime.fromtimestamp(
                        1 if expired else float(os.environ["APP_MCP_EXPIRES_AT"]), tz=timezone.utc,
                    )
                except (OSError, ValueError, KeyError, TypeError):
                    return JSONResponse({"detail": "Identity store unavailable"}, status_code=503)
                if owner is not None:
                    principal = Principal.for_mcp_agent(
                        token_id=token_id, human_owner_id=owner_id,
                        agent_id="ticket-desk-client", tenant_id=owner.tenant_id,
                        roles=owner.roles, scopes=scopes, expires_at=expires,
                        metadata={"audience": "ticket-desk"},
                    )
                break
        request.state.principal = principal
        request.state.tenant_id = principal.tenant_id
        request.state.user = SimpleNamespace(
            id=principal.user_id or principal.human_owner_id,
            is_authenticated=principal.is_authenticated,
            is_active=principal.is_authenticated,
            is_staff=False,
            is_superuser=False,
        )
        tenant_token = tenant_id_var.set(principal.tenant_id)
        user_token = user_id_var.set(principal.user_id or principal.human_owner_id)
        try:
            return await call_next(request)
        finally:
            user_id_var.reset(user_token)
            tenant_id_var.reset(tenant_token)



```

A token selects a server-owned identity mapping. It does not let the client
supply owner, role, tenant, audience, scopes or expiry. Each request reloads the
owner's current membership. A production adapter must validate real credentials
and current membership; this is still the local learning adapter.

An ordinary user Principal can use REST but is not automatically an MCP-agent
Principal. The MCP credential has an agent ID, human owner, token ID, expiry,
scopes and audience. Credential expiry, permission and tenant checks apply at
actual tool invocation, even after a client has discovered the tool.

## 3. Reuse application permissions and expose only tickets

Replace `app/permissions.py`:

```python title="app/permissions.py"
from aksara.permissions import BasePermission
from aksara.security.principal import Principal
from aksara.security.mcp import require_mcp_audience


class TicketDeskPermission(BasePermission):
    message = "Ticket desk access requires a tenant and a permitted role"

    def has_permission(self, request, view=None):
        principal = getattr(request.state, "principal", None)
        if not isinstance(principal, Principal):
            return False
        if not principal.is_authenticated or not principal.tenant_id:
            return False
        if principal.is_ai_agent:
            if principal.is_expired or not require_mcp_audience(principal, "ticket-desk").allowed:
                return False
            scope = "mcp:read:ticket" if self.is_safe_method(request) else "mcp:write:ticket"
            if not principal.has_scope(scope):
                return False
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return principal.has_any_role(("reader", "editor"))
        return principal.has_role("editor")

    def has_object_permission(self, request, view, obj):
        return str(obj.tenant_id) == str(request.state.principal.tenant_id)


```

The additional machine checks apply to REST calls made with the same machine
credential too. They do not replace the existing role and object rules.

Replace `app/views.py`. Only `TicketViewSet` changes its `ai_exposed` flag;
agent administration remains outside tool discovery:

```python title="app/views.py"
from aksara import ModelViewSet
from aksara.permissions import IsAuthenticated
from aksara.exceptions import ValidationError
from aksara.manager import DoesNotExist

from .models import Agent, Ticket
from .permissions import TicketDeskPermission
from .serializers import TicketCreateSerializer, normalize_subject


class AgentViewSet(ModelViewSet):
    model = Agent
    prefix = "/api/agents"
    permission_classes = [IsAuthenticated, TicketDeskPermission]
    ai_exposed = False
    stream_enabled = False


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated, TicketDeskPermission]
    create_serializer_class = TicketCreateSerializer
    ai_exposed = True
    stream_enabled = False

    async def validate_assignee(self, data):
        assignee = data.get("assigned_to_id")
        if assignee is not None:
            try:
                await Agent.objects.get(id=assignee)
            except DoesNotExist as exc:
                raise ValidationError(
                    "Invalid assignee",
                    errors={"assigned_to_id": "Choose an agent in your tenant"},
                ) from exc

    async def create(self, data, request):
        self.check_permissions(request)
        await self.validate_assignee(data)
        return await super().create(data, request)

    async def update(self, pk, data, request):
        self.check_permissions(request)
        await self.validate_assignee(data)
        if "subject" in data:
            data = {**data, "subject": normalize_subject(data["subject"])}
        return await super().update(pk, data, request)


```

Before exposing a real model, review `ai_sensitive`, `ai_agent_writable`,
read-only fields and custom actions. This tutorial's tickets contain no fields
that require a separate agent redaction policy; tenant IDs remain server-owned.
The existing assignee and subject validators still run through generated REST.

Replace `main.py` with the previous application entry point plus an explicit
human-only durable dispatch guard:

```python title="main.py"
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, Request

import settings as project_settings  # Registers the generated INSTALLED_APPS.
from aksara import Aksara
from aksara.conf import settings
from aksara.durable import create_durable_operations_router
from aksara.middleware.request_id import RequestIDMiddleware
from aksara.middleware.logging import LoggingMiddleware
from aksara.permissions import IsAuthenticated, check_permissions

from app.auth import LocalAuthMiddleware
from app.operations import build_operations, principal_reference
from app.permissions import TicketDeskPermission
from app.reports import register_report_routes
from app.urls import register_routes


def require_durable_access(request: Request):
    if getattr(request.state, "principal", None) is not None and request.state.principal.is_ai_agent:
        raise HTTPException(status_code=403, detail="This tutorial's durable resolver supports human identities only")
    allowed, message = check_permissions([IsAuthenticated, TicketDeskPermission], request)
    if not allowed:
        raise HTTPException(status_code=403, detail=message)


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        # Aksara's wrapper has already connected app.db before this callback.
        operations = build_operations(app.db)
        app.include_router(
            create_durable_operations_router(
                operations, principal_reference_factory=principal_reference,
            ),
            dependencies=[Depends(require_durable_access)],
        )
        yield

    app = Aksara(
        database_url=settings.database_url, title="Ticket desk",
        debug=settings.debug, lifespan=lifespan,
        middlewares=[(RequestIDMiddleware, {}), (LoggingMiddleware, {})],
    )
    app.add_middleware(LocalAuthMiddleware)
    register_routes(app)
    register_report_routes(app)
    return app


app = create_app()


```

The tutorial's durable resolver reconstructs human identities only. A machine
credential therefore cannot enqueue an Operation that the resolver would later
reconstruct as a different identity. Supporting durable agent provenance is a
separate application integration, not a side effect of enabling MCP.

Start the server normally:

```bash
aksara run main:app --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000/mcp/` is the Streamable HTTP endpoint.
`/ai/tools/mcp` is a separate inspection catalog, not a protocol transport.

## 4. Run the official client and authorization tests

The installed Aksara package supplies its supported MCP SDK 2.0 line. Its
Streamable HTTP client accepts `httpx2.AsyncClient`; that is the SDK transport
client, distinct from Aksara's provider-side `httpx` dependency. There is no
additional model-provider setup.

Keep all previous tests. Add `tests/test_mcp.py`. Its `connect()` helper is the
minimal official-client connection pattern; entering `Client` negotiates the
protocol before listing or calling tools.

```python title="tests/test_mcp.py"
import json
import os
import unittest
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from test_api import BASE, call
from test_durable import MEMBERSHIPS, write_memberships


@asynccontextmanager
async def connect(variable=None):
    headers = {"Authorization": "Bearer " + os.environ[variable]} if variable else {}
    async with httpx2.AsyncClient(headers=headers) as transport:
        async with Client(
            streamable_http_client(BASE + "/mcp/", http_client=transport),
            read_timeout_seconds=10,
        ) as client:
            yield client


class TicketMCP(unittest.IsolatedAsyncioTestCase):
    async def test_generated_roundtrip_matches_rest_validation(self):
        async with connect("APP_MCP_TOKEN") as client:
            self.assertTrue(client.protocol_version)
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertTrue({"ticket_list", "ticket_retrieve", "ticket_create", "ticket_update", "ticket_delete"}.issubset(tools))
            self.assertFalse(any(name.startswith("agent_") for name in tools))
            self.assertNotIn("tenant_id", tools["ticket_create"].input_schema.get("properties", {}))
            created = await client.call_tool("ticket_create", {"subject": "  MCP ticket  "})
            self.assertFalse(created.is_error, created.structured_content)
            ticket = created.structured_content
            self.assertEqual(ticket["subject"], "MCP ticket")
            path = "/api/tickets/" + ticket["id"]
            try:
                self.assertEqual(call(path)[1]["subject"], "MCP ticket")
                updated = await client.call_tool("ticket_update", {"pk": ticket["id"], "resolved": True})
                self.assertFalse(updated.is_error, updated.structured_content)
                self.assertTrue(call(path)[1]["resolved"])
                invalid = await client.call_tool("ticket_create", {"subject": "   "})
                self.assertTrue(invalid.is_error)
                self.assertEqual(invalid.structured_content["error"]["code"], "schema_mismatch")
                self.assertEqual(call("/api/tickets/", "POST", {"subject": "   "}, token=os.environ["APP_MCP_TOKEN"])[0], 422)
                deleted = await client.call_tool("ticket_delete", {"pk": ticket["id"]})
                self.assertFalse(deleted.is_error, deleted.structured_content)
                self.assertEqual(call(path)[0], 404)
            finally:
                call(path, "DELETE")

    async def test_read_scope_and_expiry_are_enforced(self):
        async with connect("APP_MCP_READ_TOKEN") as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            self.assertIn("ticket_list", names)
            self.assertNotIn("ticket_create", names)
            denied = await client.call_tool("ticket_create", {"subject": "Forbidden"})
            self.assertTrue(denied.is_error)
            self.assertEqual(denied.structured_content["error"]["code"], "missing_scope")
        async with connect("APP_MCP_EXPIRED_TOKEN") as client:
            denied = await client.call_tool("ticket_list", {})
            self.assertTrue(denied.is_error)
            self.assertEqual(denied.structured_content["error"]["code"], "credential_expired")

    async def test_cross_tenant_and_forged_field_are_denied(self):
        b = os.environ["APP_TENANT_B_TOKEN"]
        status, ticket = call("/api/tickets/", "POST", {"subject": "Customer B"}, token=b)
        self.assertEqual(status, 201)
        try:
            async with connect("APP_MCP_TOKEN") as client:
                hidden = await client.call_tool("ticket_retrieve", {"pk": ticket["id"]})
                self.assertTrue(hidden.is_error)
                self.assertEqual(hidden.structured_content["error"]["code"], "not_found")
                forged = await client.call_tool("ticket_create", {
                    "subject": "Forged", "tenant_id": "00000000-0000-0000-0000-000000000002",
                })
                self.assertTrue(forged.is_error)
                self.assertEqual(forged.structured_content["error"]["code"], "forbidden_field")
        finally:
            call("/api/tickets/" + ticket["id"], "DELETE", token=b)

    async def test_role_is_rechecked_after_discovery(self):
        original = json.loads(MEMBERSHIPS.read_text())
        changed = json.loads(MEMBERSHIPS.read_text())
        async with connect("APP_MCP_TOKEN") as client:
            self.assertIn("ticket_create", {tool.name for tool in (await client.list_tools()).tools})
            try:
                changed["editor-a"]["roles"] = ["reader"]
                write_memberships(changed)
                denied = await client.call_tool("ticket_create", {"subject": "Revoked"})
                self.assertTrue(denied.is_error)
                self.assertEqual(denied.structured_content["error"]["code"], "permission_denied")
                self.assertEqual(call("/api/tickets/", "POST", {"subject": "Revoked"}, token=os.environ["APP_MCP_TOKEN"])[0], 403)
            finally:
                write_memberships(original)

    async def test_anonymous_and_human_principals_cannot_execute(self):
        for variable, expected in [(None, "unauthenticated"), ("APP_API_TOKEN", "invalid_principal_type")]:
            async with connect(variable) as client:
                denied = await client.call_tool("ticket_list", {})
                self.assertTrue(denied.is_error)
                self.assertEqual(denied.structured_content["error"]["code"], expected)

    async def test_mcp_tasks_and_durable_dispatch_are_not_implied(self):
        async with connect("APP_MCP_TOKEN") as client:
            self.assertNotIn("tasks", client.server_capabilities.model_dump(exclude_none=True))
        status, _ = call("/durable/operations", "POST", {
            "action": "ticket.resolve", "action_version": "1",
            "command": {"ticket_id": "00000000-0000-0000-0000-000000000001"},
        }, token=os.environ["APP_MCP_TOKEN"])
        self.assertEqual(status, 403)

```

With HTTP running and no continuous durable worker, run:

```bash
python -m unittest discover -s tests -v
```

Expect 28 tests at the final stage. The six new tests cover generated discovery,
CRUD persistence visible through REST, shared validation, read-only scope,
expiry, tenant isolation, server-owned field rejection, role revocation after
discovery, and Principal type. They also check that protocol MCP Tasks are not
advertised and machine credentials do not dispatch this human-only durable action.

The local membership file is briefly edited during revocation tests and restored
in `finally`; run this only against the dedicated tutorial project. SDK results
use `is_error` and `structured_content`: distinguish a successful tool result
from a protocol connection that merely opened successfully.

## Boundaries to carry into a real app

Tool discovery is not permission. Invocation rechecks authority, and failures
have structured categories. The same input can be rejected as HTTP 422 in REST
and as a structured tool error over MCP; transport envelopes differ while the
application rule stays the same.

This chapter does not implement OAuth, durable agent dispatch, approval UI,
external effects, provider quality or a production identity service. Synchronous
MCP sessions/replay tracking are not durable across workers. Use the
[MCP protocol guide](../ai-mode/mcp.md) for bounded approvals, audit sinks and
limits, and [deployment](deployment.md) for operator responsibilities.
