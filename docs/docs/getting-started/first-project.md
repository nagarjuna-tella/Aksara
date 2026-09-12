# First project: a ticket desk

Build a small support-ticket API from an installed Aksara package. This is the
first stage of the application tutorial: model → migration → REST → identity →
tests. You need Python 3.11+ and a disposable local PostgreSQL database.

The example uses a single local bearer secret to teach server-owned identity.
It is a development adapter, not a login service. Keep the server on loopback;
a production app needs its real identity source and the
[restricted-role deployment profile](../tutorials/deployment.md).

## 1. Install and create the project

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "aksara-framework==0.7.1rc1"
aksara --version
aksara startproject ticket_desk
cd ticket_desk
aksara dbsetup
```

`dbsetup` asks for PostgreSQL connection details and writes `DATABASE_URL` to
`.env`. Use a database reserved for this tutorial; migrations will create tables.
You may edit `.env` directly instead. If both are set, `AKSARA_DATABASE_URL`
takes priority over `DATABASE_URL`. See [database setup](database-setup.md) if
you need to provision PostgreSQL first.

Keep the generated settings and application entry point. They connect settings
to Aksara's database lifespan. Set a local API secret in the same terminal:

```bash
export APP_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Keep that terminal for the server. Export the same token in the terminal used
for API calls/tests. Do not commit it or paste it into source files.

## 2. Define a model

Replace `app/models.py` with:

```python title="app/models.py"
from aksara import Model, fields


class Ticket(Model):
    subject = fields.String(max_length=200)
    description = fields.Text(default="")
    resolved = fields.Boolean(default=False)

    class Meta:
        table_name = "tutorial_tickets"
```

A model maps Python fields to a PostgreSQL table. The default primary key is a
UUID. A field definition is not a schema update by itself; migrations record
and apply changes to the database.

## 3. Protect the generated API

Replace `app/views.py` with:

```python title="app/views.py"
from aksara import ModelViewSet
from aksara.permissions import IsAuthenticated

from .models import Ticket


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated]
    ai_exposed = False
    stream_enabled = False
```

The ViewSet provides list, create, retrieve, update and delete routes.
`IsAuthenticated` requires identity for this API, including reads. The next
step supplies that identity; accepting a role in client JSON would not do so.

Replace `app/urls.py` with:

```python title="app/urls.py"
from aksara import include_viewset

from .views import TicketViewSet


urlpatterns = [TicketViewSet]


def register_routes(app):
    for viewset in urlpatterns:
        include_viewset(app, viewset)
```

Create `app/auth.py`:

```python title="app/auth.py"
import hmac
import os
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware

from aksara.security.principal import Principal


class LocalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        expected = os.environ.get("APP_API_TOKEN", "")
        valid = (
            scheme.lower() == "bearer"
            and bool(expected)
            and hmac.compare_digest(token, expected)
        )
        principal = (
            Principal.for_user("local-developer", auth_method="api_key")
            if valid else Principal.anonymous()
        )
        request.state.principal = principal
        request.state.user = SimpleNamespace(
            id=principal.user_id,
            is_authenticated=principal.is_authenticated,
            is_active=principal.is_authenticated,
            is_staff=False,
            is_superuser=False,
        )
        return await call_next(request)
```

The token is checked on the server, which maps it to one ordinary human
Principal. It does not grant administrator or system access. A missing token
cannot match an unset environment secret.

Append these lines to the generated `main.py`, after `app` is constructed:

```python title="main.py (append)"
from app.auth import LocalAuthMiddleware

app.add_middleware(LocalAuthMiddleware)
```

## 4. Create and apply the migration

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
```

Inspect and keep the generated migration file. Run `migrate` before the server,
not independently inside every request or worker. `launch-check` diagnoses the
local project. With Studio and AI disabled, it can report `PARTIAL` and exit
with code 1 solely for those optional recommendations. Confirm that its project,
database and migration checks pass; do not ignore other failures. Those optional
services are not required. Production uses a different [Doctor profile](../tutorials/deployment.md).

## 5. Run and call the API

```bash
aksara run main:app --host 127.0.0.1 --port 8000
```

In the other terminal, with the same `APP_API_TOKEN` exported:

```bash
curl -i http://127.0.0.1:8000/api/tickets/
curl -i http://127.0.0.1:8000/api/tickets/ \
  -H "Authorization: Bearer $APP_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject":"Printer offline","description":"Third floor"}'
curl http://127.0.0.1:8000/api/tickets/ \
  -H "Authorization: Bearer $APP_API_TOKEN"
```

The anonymous call is denied. The authenticated POST returns a created ticket
with an `id`; the list contains it. Open `http://127.0.0.1:8000/docs` to inspect
the generated API schema. Use the authenticated curl calls below the schema
rather than assuming Swagger supplies your custom bearer adapter automatically.

## 6. Test the running application

Create a `tests` directory and save this as `tests/test_api.py`. It uses only
Python's standard library. Tests create and delete their own ticket.

```python title="tests/test_api.py"
import json
import os
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")


def call(path, method="GET", payload=None, authenticated=True):
    headers = {"Content-Type": "application/json"}
    if authenticated:
        headers["Authorization"] = "Bearer " + os.environ["APP_API_TOKEN"]
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(BASE + path, data=data, method=method, headers=headers)
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        return response.status, json.loads(body) if body else None


class TicketAPI(unittest.TestCase):
    def test_anonymous_request_is_denied(self):
        status, _ = call("/api/tickets/", authenticated=False)
        self.assertEqual(status, 403)

    def test_authenticated_crud(self):
        status, ticket = call("/api/tickets/", "POST", {"subject": "Test ticket"})
        self.assertEqual(status, 201)
        path = "/api/tickets/" + ticket["id"]
        try:
            status, loaded = call(path)
            self.assertEqual(status, 200)
            self.assertEqual(loaded["subject"], "Test ticket")
            status, updated = call(path, "PATCH", {"resolved": True})
            self.assertEqual(status, 200)
            self.assertTrue(updated["resolved"])
        finally:
            status, _ = call(path, "DELETE")
            self.assertIn(status, (200, 204))
        status, _ = call(path)
        self.assertEqual(status, 404)

    def test_field_length_is_validated(self):
        status, _ = call("/api/tickets/", "POST", {"subject": "x" * 201})
        self.assertEqual(status, 422)
```

With the server still running, run from the project directory:

```bash
python -m unittest discover -s tests -v
```

These tests prove a small protected CRUD path. They do not test tenant isolation,
production identity, or recovery. Use a dedicated database and review permission
rules before exposing the application beyond your machine.

## What to learn next

Continue with [relationships and validation](../tutorials/ticket-desk.md) in
the same application before introducing tenancy, background work or durable
actions. The [models](../orm/models.md), [serializers](../api/serializers.md) and
[application boundaries](../concepts/application-boundaries.md) explain those
concepts.

MCP is optional and remains disabled. When you are ready to add a tool client,
read the [MCP guide](mcp.md): `/mcp/` is the Streamable HTTP endpoint;
`/ai/tools/mcp` is the separate inspection catalog. Provider-backed AI and
Studio are experimental and unnecessary for this REST application.
