# Grow the ticket desk: relationships and validation

Continue in the `ticket_desk` project from [First project](../getting-started/first-project.md).
Keep its database, authentication adapter and existing tickets. Stop the server
before editing; this chapter adds a nullable assignee without deleting data.

You will add a related model, generate a second migration, and enforce an
application rule: a subject must contain visible text after whitespace is
trimmed. Identity and permissions from the first chapter continue to apply.

## 1. Add an assignee relation

Replace `app/models.py` with:

```python title="app/models.py"
from aksara import Model, fields


class Agent(Model):
    name = fields.String(max_length=120)

    class Meta:
        table_name = "tutorial_agents"


class Ticket(Model):
    subject = fields.String(max_length=200)
    description = fields.Text(default="")
    resolved = fields.Boolean(default=False)
    assigned_to = fields.ForeignKey("Agent", nullable=True, on_delete="SET NULL")

    class Meta:
        table_name = "tutorial_tickets"
```

`assigned_to` is a relationship. Its stored identifier is `assigned_to_id`.
Existing tickets can remain unassigned because the new column permits null.
Deleting an agent sets the relation to null rather than deleting their tickets.
Neither model is tenant-scoped yet; do not use this stage as a multi-tenant app.

## 2. Validate application input

Create `app/serializers.py`:

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
        read_only_fields = ["id"]

    def validate_subject(self, value):
        return normalize_subject(value)
```

The serializer validates creation input and normalizes the subject. It raises
Aksara's `ValidationError`, whose application response is HTTP 422. A plain
`ValueError` from arbitrary application code is not an HTTP response contract.

The generated partial-update schema remains useful for PATCH. Apply the same
normalizer only when a PATCH supplies `subject`; omitting the field must not
replace it with a default. Replace `app/views.py` with:

```python title="app/views.py"
from aksara import ModelViewSet
from aksara.permissions import IsAuthenticated

from .models import Agent, Ticket
from .serializers import TicketCreateSerializer, normalize_subject


class AgentViewSet(ModelViewSet):
    model = Agent
    prefix = "/api/agents"
    permission_classes = [IsAuthenticated]
    ai_exposed = False
    stream_enabled = False


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated]
    create_serializer_class = TicketCreateSerializer
    ai_exposed = False
    stream_enabled = False

    async def update(self, pk, data, request):
        self.check_permissions(request)
        if "subject" in data:
            data = {**data, "subject": normalize_subject(data["subject"])}
        return await super().update(pk, data, request)
```

This override calls the base implementation, preserving its object permission,
field-policy and persistence checks. Custom input validation is not a substitute
for those checks. This small example does not claim every internal ORM write
runs the HTTP serializer; background code must enforce its own application rule.

Replace `app/urls.py` with:

```python title="app/urls.py"
from aksara import include_viewset

from .views import AgentViewSet, TicketViewSet


urlpatterns = [AgentViewSet, TicketViewSet]


def register_routes(app):
    for viewset in urlpatterns:
        include_viewset(app, viewset)
```

## 3. Migrate the existing database

```bash
aksara makemigrations --app app.models
aksara migrate
aksara run main:app --host 127.0.0.1 --port 8000
```

Review the new migration before applying it. It should add the agent table and
nullable ticket relationship; it should not replace or drop the ticket table.
Keep both migration files. The tickets created in the first chapter should
still be present, with no assignee until you set one.

This is a deliberately additive change. Adding a required field to populated
data needs a backfill and a staged migration plan; do not assume every model
edit is safe just because this one is.

## 4. Exercise the relationship

In the client terminal with the same `APP_API_TOKEN`, create an agent:

```bash
curl http://127.0.0.1:8000/api/agents/ \
  -H "Authorization: Bearer $APP_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Sam"}'
```

Use the returned agent `id` in a ticket's `assigned_to_id` field. The executable
test below performs the complete create/assign/read/delete sequence and verifies
that `SET NULL` preserves the ticket. This is an identifier relationship; do not
assume a nested object will be accepted as a writable relation.

## 5. Extend the tests

Keep `tests/test_api.py`. Add `tests/test_relations.py`:

```python title="tests/test_relations.py"
import unittest

from test_api import call


class TicketRelations(unittest.TestCase):
    def test_assignment_and_set_null(self):
        status, agent = call("/api/agents/", "POST", {"name": "Test agent"})
        self.assertEqual(status, 201)
        agent_path = "/api/agents/" + agent["id"]
        ticket_path = None
        try:
            status, ticket = call("/api/tickets/", "POST", {
                "subject": "  Needs help  ", "assigned_to_id": agent["id"],
            })
            self.assertEqual(status, 201)
            ticket_path = "/api/tickets/" + ticket["id"]
            self.assertEqual(ticket["subject"], "Needs help")
            self.assertEqual(ticket["assigned_to_id"], agent["id"])
            status, _ = call(agent_path, "DELETE")
            self.assertIn(status, (200, 204))
            status, ticket = call(ticket_path)
            self.assertEqual(status, 200)
            self.assertIsNone(ticket["assigned_to_id"])
        finally:
            if ticket_path:
                call(ticket_path, "DELETE")
            call(agent_path, "DELETE")

    def test_blank_subject_is_rejected_on_create_and_update(self):
        status, _ = call("/api/tickets/", "POST", {"subject": "   "})
        self.assertEqual(status, 422)
        status, ticket = call("/api/tickets/", "POST", {"subject": "Keep this"})
        self.assertEqual(status, 201)
        path = "/api/tickets/" + ticket["id"]
        try:
            status, _ = call(path, "PATCH", {"subject": "   "})
            self.assertEqual(status, 422)
            status, loaded = call(path)
            self.assertEqual(status, 200)
            self.assertEqual(loaded["subject"], "Keep this")
        finally:
            call(path, "DELETE")
```

Run the complete application test directory while the server is running:

```bash
python -m unittest discover -s tests -v
```

The original CRUD and denial tests remain in place. The added tests cover
normalization, invalid create/update input, relation persistence and deletion
behavior. They deliberately make requests through the installed application
rather than importing framework internals.

## Continue with tenant isolation

This application has one local identity and shared data. It is not yet a tenant
boundary, production login system, task queue demonstration or durable-action
example. Continue with [tenant isolation](ticket-desk-tenancy.md) to assign existing
rows to a customer, provision a restricted role, and test cross-tenant denial. For background on the next concepts, read
[tenant isolation](../security/multi-tenancy.md),
[ordinary tasks](../advanced/background-tasks.md), and
[Durable Operations](../advanced/durable-operations.md).
