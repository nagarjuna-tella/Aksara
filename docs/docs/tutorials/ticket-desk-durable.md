# Resolve a ticket with a Durable Operation

**Stable within the `postgres_atomic` contract.** Continue the same
[ticket desk and report application](ticket-desk-reports.md). An ordinary report
task restores a tenant but not the requesting person's current authority. Here,
a stored request to resolve a ticket must still be permitted when a worker runs
it later, and the ticket change must commit with its success record.

An **Operation** is the logical request. An **Attempt** is one worker's try.
The same Operation may have several Attempts; retrying a failed Attempt does
not mean admitting a new request. We will demonstrate this with separate worker
processes, idempotent dispatch, a cancellation and a role change after admission.

Keep the earlier migrations, restricted role, RLS and tests. Stop the web server
before editing. No application model or schema change is needed in this chapter;
the previously applied framework migrations provide the operation tables.

## 1. Give HTTP and workers the same current identity source

The earlier local token map baked in roles. A delayed worker needs to ask what
those roles are **now**. This local exercise uses a server-owned JSON file for
memberships, not a database of bearer tokens. Create `app/identities.py`:

```python title="app/identities.py"
import json
import os
from pathlib import Path
from uuid import UUID

from aksara.security.principal import Principal

MEMBERSHIPS = Path(os.environ.get("APP_MEMBERSHIPS_FILE", "memberships.json"))


def current_principal(subject_id):
    records = json.loads(MEMBERSHIPS.read_text())
    record = records.get(subject_id)
    if record is None or record.get("enabled") is not True:
        return None
    tenant = record["tenant_id"]
    if tenant is not None:
        tenant = str(UUID(tenant))
    roles = record["roles"]
    if not isinstance(roles, list) or any(role not in {"editor", "reader"} for role in roles):
        raise ValueError("Invalid membership roles")
    return Principal.for_user(
        subject_id, tenant_id=tenant, roles=tuple(roles), auth_method="api_key",
    )

```

Create `seed_memberships.py` and run it once:

```python title="seed_memberships.py"
import json
from app.identities import MEMBERSHIPS

records = {
    "editor-a": {"tenant_id": "00000000-0000-0000-0000-000000000001", "roles": ["editor"], "enabled": True},
    "editor-b": {"tenant_id": "00000000-0000-0000-0000-000000000002", "roles": ["editor"], "enabled": True},
    "reader-a": {"tenant_id": "00000000-0000-0000-0000-000000000001", "roles": ["reader"], "enabled": True},
    "unscoped-user": {"tenant_id": None, "roles": ["editor"], "enabled": True},
}
# Do not overwrite an existing identity file or undo a deliberate revocation.
with MEMBERSHIPS.open("x") as output:
    output.write(json.dumps(records, indent=2) + "\n")

```

```bash
python seed_memberships.py
```

The resulting `memberships.json` contains only user IDs, tenant IDs, enabled
flags and roles. Keep it writable only by the application's identity operator.
For production, replace this adapter with your real current membership source;
do not use a local file as a distributed identity service. HTTP and worker
processes must use the same authoritative source.

Replace `app/auth.py` so a validated bearer token identifies a subject, then
loads that subject's current membership:

```python title="app/auth.py"
import hmac
import os
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

The four environment secrets stay unchanged. An unavailable or malformed store
fails closed with 503; a removed/disabled identity becomes anonymous. Neither
HTTP nor the durable resolver falls back to cached admission-time roles.

## 2. Register one bounded action and its authorizer

Create `app/operations.py`:

```python title="app/operations.py"
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from aksara.durable import (
    DurableAction, DurableActionRegistry, DurableOperationService, EffectClass,
    PrincipalReference, PrincipalResolution, PrincipalResolverRegistry,
)
from aksara.durable.registry import ResolutionStatus
from aksara.security.policy import get_policy_engine

from .identities import current_principal
from .models import Ticket

PAUSE_FILE = Path("resolution-paused")


class ResolveTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: UUID


class ResolutionPaused(Exception):
    """A local exercise flag simulates a temporary application outage."""


async def resolve_ticket(context, command):
    row = await context.database.fetchrow(
        """UPDATE tutorial_tickets SET resolved = TRUE
           WHERE id = $1 AND tenant_id = $2 RETURNING id""",
        UUID(command["ticket_id"]), UUID(context.tenant_id),
    )
    if row is None:
        raise ValueError("Ticket is no longer available")
    if PAUSE_FILE.exists():
        # Local fault exercise: fail after SQL and prove the transaction rolls back.
        raise ResolutionPaused("Simulated interruption after ticket update")
    return {"ticket_id": str(row["id"]), "resolved": True}


async def resolve_identity(reference):
    if reference.identity_namespace != "ticket-desk":
        return PrincipalResolution(ResolutionStatus.MALFORMED)
    try:
        principal = current_principal(reference.subject_id)
    except (OSError, ValueError, KeyError, TypeError):
        return PrincipalResolution(ResolutionStatus.TEMPORARILY_UNAVAILABLE)
    if principal is None:
        return PrincipalResolution(ResolutionStatus.REVOKED)
    return PrincipalResolution.resolved(principal)


def principal_reference(principal, request):
    return PrincipalReference.from_principal(
        principal, resolver_key="ticket-membership", resolver_version="1",
        identity_namespace="ticket-desk",
    )


def build_operations(database):
    async def authorize(principal, command):
        if not principal.is_authenticated or not principal.tenant_id or not principal.has_role("editor"):
            return False
        decision = get_policy_engine().validate_payload(
            principal, "update", Ticket, {"resolved": True}, tenant_required=True,
        )
        if not decision.allowed:
            return False
        return bool(await database.fetchval(
            "SELECT EXISTS(SELECT 1 FROM tutorial_tickets WHERE id = $1 AND tenant_id = $2)",
            UUID(command["ticket_id"]), UUID(principal.tenant_id),
        ))

    actions = DurableActionRegistry()
    actions.register(DurableAction(
        name="ticket.resolve", version="1", handler=resolve_ticket,
        effect_class=EffectClass.POSTGRES_ATOMIC,
        command_normalizer=ResolveTicket,
        authorizer=authorize,
        retry_classifier=lambda error: isinstance(error, ResolutionPaused),
    ))
    resolvers = PrincipalResolverRegistry()
    resolvers.register("ticket-membership", "1", resolve_identity)
    return DurableOperationService(
        database, application_namespace="ticket-desk",
        actions=actions, resolvers=resolvers, default_max_attempts=3,
    )

```

The action accepts only a validated ticket UUID. It cannot select arbitrary
Python, SQL or an unregistered action version. The authorizer checks the current
editor role, field policy, tenant and ticket access. The handler checks that its
UPDATE actually matched a row before returning success.

A stored `PrincipalReference` is a locator, not permission: it contains the
subject, tenant and resolver identity, not the bearer secret or a copy of roles.
The worker resolves it again and invokes the authorizer at the guarded boundary.

All mutation SQL uses `context.database`. Aksara commits this mutation together
with the Operation/Attempt success. Do not create another connection, start a
child-task database write, send email or call a provider inside this handler.
A lease and increasing fence prevent a replaced worker from finalizing through
the supported boundary. They do not make arbitrary external actions exactly-once.

The `resolution-paused` file is an explicit local failure exercise **after** the
UPDATE statement, so the failed Attempt must roll that statement back. Only
`ResolutionPaused` is classified as retryable; unrelated exceptions are not
silently retried. With the three-attempt limit, a continuously running worker
can exhaust retries while this file remains present. The test uses one poll at
a time to control that experiment. It is not a production retry/backoff policy.

## 3. Mount the explicit API on the application's database

Replace `main.py` with:

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

The generated settings still register installed apps. Models, routes, ordinary
tasks and the same local authentication are loaded explicitly. The custom
lifespan runs after Aksara opens `app.db`, so the durable service uses that exact
database object. The durable router is registered during startup and appears in
OpenAPI after startup. Construct a fresh `create_app()` per application lifecycle
(for example, per test client); do not repeatedly start the same instance and
register its router again. The scaffold welcome page is intentionally replaced
by this application entry point; API routes from earlier chapters are preserved.

Admission is permissioned through `require_durable_access`: the service's
storage admission API is not a substitute for an application dispatch gate.
The action's authorizer is checked again for execution and protected status or
cancellation. A reader can read tickets but cannot execute this editor action or
read its protected Operation status. Possessing an Operation ID grants no access.

Start HTTP with the same restricted-role URL:

```bash
aksara run main:app --host 127.0.0.1 --port 8000
```

Dispatch with a new idempotency key and an existing ticket UUID:

```bash
curl -X POST http://127.0.0.1:8000/durable/operations \
  -H "Authorization: Bearer $APP_API_TOKEN" \
  -H "Idempotency-Key: resolve-ticket-example-1" \
  -H "Content-Type: application/json" \
  -d '{"action":"ticket.resolve","action_version":"1","command":{"ticket_id":"REPLACE_WITH_TICKET_UUID"}}'
```

The response contains `operation.id` and `status_url`. Reuse the same key only
for the same logical input: a duplicate returns the existing Operation; changed
input returns 409. The default deduplication window is bounded (see the
[settings reference](../reference/settings-reference.md)); it is not permanent.
Read `/durable/operations/<id>` with the editor token. `ready` means admitted,
not executed. The ordinary task worker from the report chapter does not execute
this inline durable action.

## 4. Start an explicit durable worker

Create `worker.py`:

```python title="worker.py"
import argparse
import asyncio
from uuid import UUID

import settings as project_settings  # Same installed-app configuration as HTTP.
from aksara.conf import settings
from aksara.db import Database
from aksara.durable import DurableOperationWorker
from app.operations import build_operations


async def run(args):
    if not settings.database_url:
        raise RuntimeError("Set the restricted-role database URL")
    database = Database(settings.database_url)
    await database.connect()
    try:
        worker = DurableOperationWorker(build_operations(database), lease_seconds=30)
        if args.once:
            result = await worker.poll_once(
                tenant_id=str(args.tenant_id), operation_id=args.operation_id,
            )
            print(result.state.value if result is not None else "no eligible operation")
        else:
            await worker.run(tenant_id=str(args.tenant_id))
    finally:
        await database.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the ticket desk durable worker")
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--once", action="store_true", help="Claim at most one eligible Operation and exit")
    parser.add_argument("--operation-id", type=UUID, help="Limit --once to one Operation")
    args = parser.parse_args()
    if args.operation_id is not None and not args.once:
        parser.error("--operation-id requires --once")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass

```

From the project directory, in another terminal with the same database URL and
membership-file location, run one customer's worker:

```bash
python worker.py --tenant-id 00000000-0000-0000-0000-000000000001
```

Use `--once --operation-id <id>` to claim at most one eligible operation and
exit. This one-shot command is useful for the tests below; it does not wait for
a future `available_at`. A customer-B process uses customer B's tenant UUID.
These are operator-selected scopes, not a customer-controlled header. Production
must supervise workers and deploy all action/resolver versions needed by pending
Operations. This chapter does not build a fleet scheduler.

Cancel ready work with an authenticated POST to
`/durable/operations/<id>/cancel` and a JSON body such as
`{"reason":"No longer needed"}`. A ready Operation becomes cancelled without
mutating the ticket. Cancellation after a successful commit does not undo it.

## 5. Prove retries and current authorization

**Stop continuously running durable workers before this test suite.** Keep the
HTTP server running. Tests start isolated one-shot worker processes and alter
the local membership file briefly. Use only the dedicated tutorial database and
file; do not run this suite against a shared identity store.

Add `tests/test_durable.py`:

```python title="tests/test_durable.py"
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

from test_api import call

TENANT_A = "00000000-0000-0000-0000-000000000001"
MEMBERSHIPS = Path(os.environ.get("APP_MEMBERSHIPS_FILE", "memberships.json"))


def dispatch(ticket_id, key, **extra):
    return call("/durable/operations", "POST", {
        "action": "ticket.resolve", "action_version": "1",
        "command": {"ticket_id": ticket_id}, **extra,
    }, extra_headers={"Idempotency-Key": key})


def poll_once(operation_id):
    result = subprocess.run([
        sys.executable, "worker.py", "--tenant-id", TENANT_A,
        "--operation-id", operation_id, "--once",
    ], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise AssertionError(result.stderr)


def write_memberships(records):
    temporary = MEMBERSHIPS.with_suffix(".tmp")
    temporary.write_text(json.dumps(records))
    temporary.replace(MEMBERSHIPS)


class DurableTickets(unittest.TestCase):
    def setUp(self):
        status, ticket = call("/api/tickets/", "POST", {"subject": "Resolve durably"})
        self.assertEqual(status, 201)
        self.ticket_id = ticket["id"]
        self.ticket_path = "/api/tickets/" + self.ticket_id
        self.key = str(uuid4())

    def tearDown(self):
        call(self.ticket_path, "DELETE")

    def admit(self):
        status, payload = dispatch(self.ticket_id, self.key)
        self.assertEqual(status, 202)
        self.assertTrue(payload["created"])
        return payload["operation"]["id"]

    def status(self, operation_id):
        status, payload = call("/durable/operations/" + operation_id)
        self.assertEqual(status, 200)
        return payload

    def test_success_and_idempotency(self):
        operation_id = self.admit()
        status, duplicate = dispatch(self.ticket_id, self.key)
        self.assertEqual(status, 202)
        self.assertFalse(duplicate["created"])
        self.assertEqual(duplicate["operation"]["id"], operation_id)
        self.assertEqual(dispatch(str(uuid4()), self.key)[0], 409)
        poll_once(operation_id)
        completed = self.status(operation_id)
        self.assertEqual(completed["state"], "succeeded")
        self.assertEqual(completed["attempt_count"], 1)
        self.assertTrue(call(self.ticket_path)[1]["resolved"])
        status, terminal = dispatch(self.ticket_id, self.key)
        self.assertEqual(status, 200)
        self.assertEqual(terminal["operation"]["id"], operation_id)
        poll_once(operation_id)
        self.assertEqual(self.status(operation_id)["attempt_count"], 1)

    def test_cancellation_before_claim_preserves_ticket(self):
        operation_id = self.admit()
        status, cancelled = call("/durable/operations/" + operation_id + "/cancel", "POST", {"reason": "No longer needed"})
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["state"], "cancelled")
        poll_once(operation_id)
        self.assertFalse(call(self.ticket_path)[1]["resolved"])
        self.assertEqual(self.status(operation_id)["attempt_count"], 0)

    def test_role_revocation_after_admission_prevents_mutation(self):
        operation_id = self.admit()
        original = json.loads(MEMBERSHIPS.read_text())
        changed = json.loads(MEMBERSHIPS.read_text())
        changed["editor-a"]["roles"] = ["reader"]
        try:
            write_memberships(changed)
            poll_once(operation_id)
            self.assertFalse(call(self.ticket_path)[1]["resolved"])
            self.assertEqual(call("/durable/operations/" + operation_id)[0], 403)
        finally:
            write_memberships(original)
        failed = self.status(operation_id)
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["error"]["code"], "authorization_denied")

    def test_retry_uses_a_new_worker_process(self):
        operation_id = self.admit()
        pause = Path("resolution-paused")
        self.assertFalse(pause.exists())
        try:
            pause.touch()
            poll_once(operation_id)
            failed_attempt = self.status(operation_id)
            self.assertEqual(failed_attempt["state"], "ready")
            self.assertEqual(failed_attempt["attempt_count"], 1)
            self.assertTrue(failed_attempt["error"]["retryable"])
            self.assertFalse(call(self.ticket_path)[1]["resolved"])
        finally:
            pause.unlink(missing_ok=True)
        poll_once(operation_id)
        succeeded = self.status(operation_id)
        self.assertEqual(succeeded["state"], "succeeded")
        self.assertEqual(succeeded["attempt_count"], 2)
        self.assertTrue(call(self.ticket_path)[1]["resolved"])

    def test_other_tenant_and_reader_cannot_operate_on_command(self):
        operation_id = self.admit()
        other = os.environ["APP_TENANT_B_TOKEN"]
        self.assertEqual(call("/durable/operations/" + operation_id, token=other)[0], 404)
        self.assertEqual(call("/durable/operations/" + operation_id + "/cancel", "POST", {}, token=other)[0], 404)
        payload = {"action": "ticket.resolve", "action_version": "1", "command": {"ticket_id": self.ticket_id}}
        for variable in ("APP_READER_TOKEN", "APP_UNSCOPED_TOKEN"):
            self.assertEqual(call("/durable/operations", "POST", payload, token=os.environ[variable])[0], 403)
        # Leave no eligible work after this test.
        self.assertEqual(call("/durable/operations/" + operation_id + "/cancel", "POST", {})[0], 200)

    def test_unknown_action_version_and_invalid_command_are_rejected(self):
        self.assertEqual(dispatch(self.ticket_id, self.key, action="not.registered")[0], 422)
        self.assertEqual(dispatch(self.ticket_id, self.key, action_version="99")[0], 422)
        self.assertEqual(dispatch("not-a-uuid", self.key)[0], 422)
        self.assertEqual(dispatch(self.ticket_id, self.key, command={"ticket_id": self.ticket_id, "sql": "not allowed"})[0], 422)

```

```bash
python -m unittest discover -s tests -v
```

The final application has 22 tests. The six new tests prove admission, duplicate
and conflicting input, status, a new worker for retry, cancellation before claim,
current role revocation, tenant/role denial and the command allowlist. Earlier
CRUD, relations, tenant and ordinary-task/export tests still run.

During the revocation test the requester's status read is denied too; the test
restores the role before inspecting the terminal failure. Restoring permission
does not revive that failed Operation. The retry test verifies two Attempts on
one Operation and no ticket change after the failed Attempt. The first attempt executes SQL and then fails, so reading an unresolved ticket
verifies rollback rather than merely an early return. A retryable failure
returns the Operation to `ready`; there is no public `retry_pending` state.

## Guarantees and remaining responsibilities

This example proves a same-database ticket mutation, not external delivery or a
full crash campaign. After a lost response, reread the Operation or resubmit its
same idempotency identity; do not admit a fresh mutation blindly. `succeeded`
means the ticket change and authoritative execution success committed together
inside the supported boundary.

Approval is optional: it records intent but never restores revoked permission.
See [approval and cancellation](../advanced/durable-operations.md#approval-and-cancellation)
for that separate choice. Provider calls need an external-effect contract and
may remain `external_outcome_unknown`; never relabel them exactly-once.
Operators still own worker supervision, identity availability, retention,
outbox export, backups and monitoring. See [deployment](deployment.md).
Continue with the optional [MCP client chapter](ticket-desk-mcp.md). Protocol-level
MCP Tasks are not implemented by this application.
