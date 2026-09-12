# Separate customers with tenant isolation

**Stable, within the documented PostgreSQL and permission contracts.**

Continue the same [ticket desk](ticket-desk.md). This chapter assigns its
existing agents and tickets to customer A, adds customer B, and introduces a
read-only identity. Keep the earlier migration files and tests. Stop the server
while applying the migration; this tutorial is a maintenance-window transition,
not a zero-downtime conversion of a populated production service.

There are three cooperating boundaries: the server resolves identity and tenant,
permissions decide which requests may run, and PostgreSQL RLS limits rows on the
application connection. A client-supplied tenant header is not identity.

## 1. Make both models tenant-scoped

Replace `app/models.py`:

```python title="app/models.py"
from aksara import TenantModel, fields


class Agent(TenantModel):
    name = fields.String(max_length=120)

    class Meta:
        table_name = "tutorial_agents"


class Ticket(TenantModel):
    subject = fields.String(max_length=200)
    description = fields.Text(default="")
    resolved = fields.Boolean(default=False)
    assigned_to = fields.ForeignKey("Agent", nullable=True, on_delete="SET NULL")

    class Meta:
        table_name = "tutorial_tickets"

```

`TenantModel` adds the required UUID `tenant_id` column. Inheriting from it does
not provision customer accounts or select a tenant. Generated creates get the
tenant from the authenticated Principal; the application must supply that
Principal and set the database context.

## 2. Backfill before requiring tenant identity

Using the migration-role database URL, generate but **do not apply** the migration:

```bash
aksara makemigrations --app app.models --name tenant_boundary
```

Open the newly generated `migrations/*_tenant_boundary.py`. Keep its imports,
class and `dependencies`. Replace only the class's `operations = [...]` block
with the following, indented inside the class:

```python title="migration operations (replace)"
operations = [
    op.AddField(table="tutorial_agents", name="tenant_id", field=op.UUIDField(nullable=True)),
    op.AddField(table="tutorial_tickets", name="tenant_id", field=op.UUIDField(nullable=True)),
    op.RunSQL(sql="""
        UPDATE tutorial_agents
        SET tenant_id = '00000000-0000-0000-0000-000000000001'
        WHERE tenant_id IS NULL;
        UPDATE tutorial_tickets
        SET tenant_id = '00000000-0000-0000-0000-000000000001'
        WHERE tenant_id IS NULL;
    """),
    op.AlterFieldNull(table="tutorial_agents", name="tenant_id", nullable=False),
    op.AlterFieldNull(table="tutorial_tickets", name="tenant_id", nullable=False),
    *[
        op.RunSQL(sql=f"""
            ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
            ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            CREATE POLICY tutorial_tenant_isolation ON {table}
            USING (tenant_id = NULLIF(current_setting('aksara.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('aksara.current_tenant_id', true), '')::uuid);
        """)
        for table in ("tutorial_agents", "tutorial_tickets")
    ],
]

```

Review the entire file before running `aksara migrate`. The two fixed table names
in this SQL come from this application, never from request input. All existing
rows belong to customer A in this tutorial. For real data, establish and verify
the correct owner of every row; do not copy that backfill assumption.

The migration adds nullable columns, assigns ownership, requires non-null values,
then enables and forces RLS. It is deliberately not a reversible tenant-removal
recipe. Review backup/restore and roll-forward plans before production changes.

```bash
aksara migrate
```

Run the web server with a **different, restricted application role**:
`NOSUPERUSER NOBYPASSRLS`, schema usage, and SELECT/INSERT/UPDATE/DELETE on application
and framework tables, plus sequence privileges. In `psql`, connected to this dedicated tutorial
database as its administrator, provision the role without embedding a password:

```sql
CREATE ROLE ticket_desk_app LOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO ticket_desk_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ticket_desk_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ticket_desk_app;
```

Run `\password ticket_desk_app` at the `psql` prompt to set its password. This
example uses the scaffold's default `public` schema in a dedicated database.
For another schema, grant only that schema; never apply this blanket tutorial
grant to a shared application database. Repeat grants for new tables after
later migrations or configure reviewed owner-specific default privileges.
See [deployment](deployment.md) for the production responsibilities. Apply
migrations as the migration role; then switch `AKSARA_DATABASE_URL` to the application URL before starting the
server or Doctor. Do not run this isolation test with a PostgreSQL superuser.
`FORCE ROW LEVEL SECURITY` covers the table owner, but does not constrain a
superuser or a role with `BYPASSRLS`.

## 3. Resolve tenant and role on the server

Keep `APP_API_TOKEN` for customer A's editor. Generate three different additional
local secrets and supply the same values to server and client terminals:

```bash
export APP_TENANT_B_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_READER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_UNSCOPED_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

The unscoped identity is a negative test: authenticated users without a customer
must be denied. These static mappings are still a local learning adapter.
A production identity integration must validate its credentials and load current
membership/roles server-side. Replace `app/auth.py` (keep its existing middleware
registration in `main.py`):

```python title="app/auth.py"
import hmac
import os
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware

from aksara.middleware.context import tenant_id_var, user_id_var
from aksara.security.principal import Principal

TENANT_A = "00000000-0000-0000-0000-000000000001"
TENANT_B = "00000000-0000-0000-0000-000000000002"


class LocalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        principal = Principal.anonymous()
        identities = [
            ("APP_API_TOKEN", "editor-a", TENANT_A, "editor"),
            ("APP_TENANT_B_TOKEN", "editor-b", TENANT_B, "editor"),
            ("APP_READER_TOKEN", "reader-a", TENANT_A, "reader"),
            ("APP_UNSCOPED_TOKEN", "unscoped-user", None, "editor"),
        ]
        if scheme.lower() == "bearer":
            for variable, user, tenant, role in identities:
                expected = os.environ.get(variable, "")
                if expected and hmac.compare_digest(token, expected):
                    principal = Principal.for_user(
                        user, tenant_id=tenant, roles=(role,), auth_method="api_key",
                    )
                    break
        request.state.principal = principal
        request.state.tenant_id = principal.tenant_id
        request.state.user = SimpleNamespace(
            id=principal.user_id,
            is_authenticated=principal.is_authenticated,
            is_active=principal.is_authenticated,
            is_staff=False,
            is_superuser=False,
        )
        tenant_token = tenant_id_var.set(principal.tenant_id)
        user_token = user_id_var.set(principal.user_id)
        try:
            return await call_next(request)
        finally:
            user_id_var.reset(user_token)
            tenant_id_var.reset(tenant_token)

```

`request.state.principal` is the policy identity. The context variables make its
tenant available to database acquisition; Aksara sets the PostgreSQL session
value on acquisition and clears it when returning the connection. The `finally`
block also restores the Python context. A raw query on a connection acquired
outside that supported path needs its own trusted tenant setup.

## 4. Apply read/write permissions and relation checks

Create `app/permissions.py`:

```python title="app/permissions.py"
from aksara.permissions import BasePermission
from aksara.security.principal import Principal


class TicketDeskPermission(BasePermission):
    message = "Ticket desk access requires a tenant and a permitted role"

    def has_permission(self, request, view=None):
        principal = getattr(request.state, "principal", None)
        if not isinstance(principal, Principal):
            return False
        if not principal.is_authenticated or not principal.tenant_id:
            return False
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return principal.has_any_role(("reader", "editor"))
        return principal.has_role("editor")

    def has_object_permission(self, request, view, obj):
        return str(obj.tenant_id) == str(request.state.principal.tenant_id)

```

Both ViewSets use this permission, so anonymous and tenant-less callers fail
before querying. Object checks are an additional layer; PostgreSQL RLS is what
makes another customer's UUID look absent on direct retrieval.

Replace `app/serializers.py` with the earlier validator plus a server-owned
`tenant_id` declaration:

```python title="app/serializers.py"
from aksara.api.serializers import ModelSerializer
from aksara.exceptions import ValidationError

from .models import Ticket


def normalize_subject(value):
    subject = value.strip()
    if not subject or len(subject) > 200:
        raise ValidationError(
            "Invalid ticket subject",
            errors={"subject": "Use 1 to 200 characters of visible text"},
        )
    return subject


class TicketCreateSerializer(ModelSerializer):
    class Meta:
        model = Ticket
        fields = "__all__"
        read_only_fields = ["id", "tenant_id"]

    def validate_subject(self, value):
        return normalize_subject(value)

```

Replace `app/views.py`:

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
    ai_exposed = False
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

A foreign key proves that an agent exists, not that the agent belongs to the
same customer. PostgreSQL referential-integrity checks are not a replacement for
that application rule. The assignee lookup runs with the current tenant's RLS
context, rejects an inaccessible identifier, and uses the same error for a
nonexistent identifier. The generated create and PATCH schemas reject `tenant_id` with HTTP 422; runtime
field-policy enforcement also protects server-owned fields on covered write paths. Custom code and background writes must preserve both rules.

Keep the existing routes. Start the server with the application role:

```bash
aksara doctor launch-check
aksara run main:app --host 127.0.0.1 --port 8000
```

## 5. Test two tenants, not just a successful request

Replace `tests/test_api.py` to let tests choose a token or add a forged header;
its original three CRUD tests remain unchanged:

```python title="tests/test_api.py"
import json
import os
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")


def call(path, method="GET", payload=None, authenticated=True, *, token=None, extra_headers=None):
    headers = {"Content-Type": "application/json"}
    if authenticated:
        headers["Authorization"] = "Bearer " + (token if token is not None else os.environ["APP_API_TOKEN"])
    headers.update(extra_headers or {})
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

Keep `tests/test_relations.py`. Add `tests/test_tenants.py`:

```python title="tests/test_tenants.py"
import os
import unittest
from uuid import uuid4

from test_api import call

TENANT_A = "00000000-0000-0000-0000-000000000001"
TENANT_B = "00000000-0000-0000-0000-000000000002"


class TenantBoundary(unittest.TestCase):
    def setUp(self):
        self.b = os.environ["APP_TENANT_B_TOKEN"]
        self.reader = os.environ["APP_READER_TOKEN"]
        self.unscoped = os.environ["APP_UNSCOPED_TOKEN"]
        status, self.ticket = call("/api/tickets/", "POST", {"subject": "Tenant A ticket"})
        self.assertEqual(status, 201)
        self.path = "/api/tickets/" + self.ticket["id"]

    def tearDown(self):
        call(self.path, "DELETE")

    def test_other_tenant_cannot_read_update_or_delete(self):
        for method, payload in [("GET", None), ("PATCH", {"resolved": True}), ("DELETE", None)]:
            status, _ = call(self.path, method, payload, token=self.b)
            self.assertEqual(status, 404)
        status, own = call(self.path)
        self.assertEqual(status, 200)
        self.assertFalse(own["resolved"])

    def test_interleaved_lists_do_not_leak_tenant_context(self):
        status, other = call("/api/tickets/", "POST", {"subject": "Tenant B ticket"}, token=self.b)
        self.assertEqual(status, 201)
        try:
            for token, forbidden in [(self.b, self.ticket["id"]), (None, other["id"])] * 3:
                status, page = call("/api/tickets/", token=token)
                self.assertEqual(status, 200)
                self.assertNotIn(forbidden, [row["id"] for row in page["results"]])
        finally:
            call("/api/tickets/" + other["id"], "DELETE", token=self.b)

    def test_reader_can_read_but_cannot_write(self):
        self.assertEqual(call(self.path, token=self.reader)[0], 200)
        for method, path, payload in [
            ("POST", "/api/tickets/", {"subject": "Forbidden"}),
            ("PATCH", self.path, {"resolved": True}),
            ("DELETE", self.path, None),
        ]:
            self.assertEqual(call(path, method, payload, token=self.reader)[0], 403)

    def test_missing_tenant_is_denied(self):
        self.assertEqual(call("/api/tickets/", token=self.unscoped)[0], 403)
        self.assertEqual(call("/api/tickets/", "POST", {"subject": "No tenant"}, token=self.unscoped)[0], 403)

    def test_forged_header_does_not_change_tenant(self):
        headers = {"X-Tenant-ID": TENANT_B}
        self.assertEqual(call(self.path, extra_headers=headers)[0], 200)
        self.assertEqual(call(self.path, token=self.b, extra_headers={"X-Tenant-ID": TENANT_A})[0], 404)

    def test_payload_cannot_assign_tenant(self):
        self.assertEqual(call(self.path, "PATCH", {"tenant_id": TENANT_B})[0], 422)
        self.assertEqual(call("/api/tickets/", "POST", {"subject": "Forged", "tenant_id": TENANT_B})[0], 422)

        status, unchanged = call(self.path)
        self.assertEqual(status, 200)
        self.assertEqual(unchanged["tenant_id"], TENANT_A)

    def test_cross_tenant_assignee_is_rejected(self):
        status, agent = call("/api/agents/", "POST", {"name": "Other tenant"}, token=self.b)
        self.assertEqual(status, 201)
        try:
            for identifier in (agent["id"], str(uuid4())):
                self.assertEqual(call(self.path, "PATCH", {"assigned_to_id": identifier})[0], 422)
                self.assertEqual(call("/api/tickets/", "POST", {
                    "subject": "Wrong assignee", "assigned_to_id": identifier,
                })[0], 422)
        finally:
            call("/api/agents/" + agent["id"], "DELETE", token=self.b)

```

Run all application tests against the running server:

```bash
python -m unittest discover -s tests -v
```

Expect 12 tests at this stage: the original five plus seven tenant/permission
checks. Keep the database restricted-role posture as part of the test fixture;
a green list-filter test alone does not prove RLS protects raw queries.

Continue with [queued reports and protected downloads](ticket-desk-reports.md).

This chapter establishes a tenant-aware HTTP application. It has not yet added
background work, durable execution or MCP. Those paths need explicit identity,
tenant and permission handling; none inherits authority merely by sharing a
model. See [application boundaries](../concepts/application-boundaries.md).
