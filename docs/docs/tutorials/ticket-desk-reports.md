# Queue a tenant report and download its result

**Stable ordinary-task API.** Continue the [tenant-scoped ticket desk](ticket-desk-tenancy.md)
with the same restricted database role, RLS policies, models and tests.

An editor requests a small report; a background task counts their customer's
open and resolved tickets; authorized readers can inspect and download the result.
This teaches ordinary tasks and protected data export. It does not send email,
call an external service, or authorize a delayed application mutation.

## 1. Register a task

Create `app/tasks.py`:

```python title="app/tasks.py"
from aksara import task
from aksara.middleware.context import tenant_id_var

from .models import Ticket


@task(name="ticket_desk.count_tickets", max_attempts=3)
async def count_tickets():
    tenant = tenant_id_var.get()
    if not tenant:
        raise RuntimeError("A report requires tenant context")
    return {
        "tenant_id": str(tenant),
        "open": await Ticket.objects.filter(resolved=False).count(),
        "resolved": await Ticket.objects.filter(resolved=True).count(),
    }

```

A task name is the persistent registration key. Every process that may execute
this task must import this module. The decorator supplies `.enqueue()` without
running the function inside the HTTP request.

`enqueue()` captures the current tenant; the worker restores it for database
access. Ordinary tasks do **not** persist the full Principal or recheck the
enqueuer's current role. This report performs internal read-only work; each
status/download request checks the caller's current identity and role again.
Use a Durable Operation for delayed mutations that must reauthorize the original
actor. The two counts are separate queries, not a transactionally consistent
snapshot during concurrent edits; use an appropriate reporting snapshot design
when that distinction matters.

## 2. Expose guarded report routes

Create `app/reports.py`:

```python title="app/reports.py"
import csv
import io
from uuid import UUID

from fastapi import HTTPException, Request, Response

from aksara.permissions import IsAuthenticated, check_permissions
from aksara.tasks import get_task_record

from .permissions import TicketDeskPermission
from .tasks import count_tickets


def require_access(request):
    allowed, message = check_permissions([IsAuthenticated, TicketDeskPermission], request)
    if not allowed:
        raise HTTPException(status_code=403, detail=message)


def register_report_routes(app):
    async def load_report(task_id, request):
        require_access(request)
        record = await get_task_record(task_id, db=app.db)
        principal = request.state.principal
        if (
            record is None
            or record.tenant_id != principal.tenant_id
            or record.task_name != "ticket_desk.count_tickets"
        ):
            raise HTTPException(status_code=404, detail="Report not found")
        return record

    @app.post("/api/reports/", status_code=202)
    async def enqueue_report(request: Request):
        require_access(request)
        queued = await count_tickets.enqueue(db=app.db)
        return {"task_id": str(queued.id), "status": queued.status}

    @app.get("/api/reports/{task_id}")
    async def report_status(task_id: UUID, request: Request):
        record = await load_report(task_id, request)
        # Do not expose task payloads, exception text, or unrelated task results.
        return {
            "task_id": str(record.id), "status": record.status,
            "attempts": record.attempts,
            "result": record.result if record.status == "completed" else None,
        }

    @app.get("/api/reports/{task_id}/download")
    async def download_report(task_id: UUID, request: Request):
        record = await load_report(task_id, request)
        if record.status != "completed":
            raise HTTPException(status_code=409, detail="Report is not complete")
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["metric", "count"])
        writer.writerow(["open", record.result["open"]])
        writer.writerow(["resolved", record.result["resolved"]])
        return Response(
            buffer.getvalue(), media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="ticket-report.csv"',
                "Cache-Control": "no-store",
            },
        )

```

Custom routes do not inherit a ViewSet's permission classes. They call the same
application permission explicitly. Task metadata is framework-wide, so
`get_task_record()` alone is not an authorization check: `load_report()` checks
the tenant and registered task name before exposing selected fields.

The CSV response is generated after authorization. It is not a file under a
public static-media mount and is not a public bearer URL. Its cells contain only
fixed metric names and numeric counts. Exports containing user-provided strings
need their own spreadsheet-formula and data-disclosure handling.

Append to `main.py`, after the existing app and auth middleware:

```python title="main.py (append)"
from app.reports import register_report_routes

register_report_routes(app)

```

This import also registers `count_tickets` before the application starts.
No model changes are needed in this chapter. The earlier `migrate` commands
already installed the framework's ordinary-task tables. Keep the application's
DML privileges on those tables. With its database lifespan active and default
`tasks_enabled=True`, Aksara starts an ordinary `TaskWorker` on startup.
Do not start a second worker just to make this tutorial run.

```bash
aksara run main:app --host 127.0.0.1 --port 8000
```

In another terminal, request a report with the editor token:

```bash
curl -X POST http://127.0.0.1:8000/api/reports/ \
  -H "Authorization: Bearer $APP_API_TOKEN"
```

The response is HTTP 202 with `task_id`. Read `/api/reports/<task_id>` with the
same token until `status` is `completed`, then fetch
`/api/reports/<task_id>/download`. `failed` is a terminal failure after the task's
retry budget; a pending or running report is not ready to download (HTTP 409).
A missing or other-tenant report returns 404 after access checks.

## 3. Test the worker through the public API

Keep all existing tests. Add `tests/test_reports.py`:

```python title="tests/test_reports.py"
import csv
import io
import os
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_api import BASE, call


def download(task_id, token=None):
    request = Request(BASE + "/api/reports/" + task_id + "/download", headers={
        "Authorization": "Bearer " + (token or os.environ["APP_API_TOKEN"]),
    })
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.read().decode(), response.headers


def wait_for_report(task_id, token=None):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status, report = call("/api/reports/" + task_id, token=token)
        if status != 200:
            raise AssertionError((status, report))
        if report["status"] == "completed":
            return report
        if report["status"] == "failed":
            raise AssertionError("Report task failed")
        time.sleep(0.1)
    raise AssertionError("Report did not complete within 15 seconds")


class TicketReports(unittest.TestCase):
    def test_report_matches_tenant_data_and_download(self):
        status, page = call("/api/tickets/")
        self.assertEqual(status, 200)
        expected = {
            "open": sum(not row["resolved"] for row in page["results"]),
            "resolved": sum(row["resolved"] for row in page["results"]),
        }
        status, queued = call("/api/reports/", "POST")
        self.assertEqual(status, 202)
        report = wait_for_report(queued["task_id"])
        self.assertEqual(report["result"]["tenant_id"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual({key: report["result"][key] for key in expected}, expected)
        status, content, headers = download(queued["task_id"])
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/csv"))
        self.assertEqual(headers["Cache-Control"], "no-store")
        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(rows[0], ["metric", "count"])
        self.assertEqual({name: int(value) for name, value in rows[1:]}, expected)

    def test_another_tenant_cannot_inspect_or_download_report(self):
        status, queued = call("/api/reports/", "POST")
        self.assertEqual(status, 202)
        b = os.environ["APP_TENANT_B_TOKEN"]
        self.assertEqual(call("/api/reports/" + queued["task_id"], token=b)[0], 404)
        self.assertEqual(download(queued["task_id"], token=b)[0], 404)
        status, other = call("/api/reports/", "POST", token=b)
        self.assertEqual(status, 202)
        report = wait_for_report(other["task_id"], token=b)
        self.assertEqual(report["result"]["tenant_id"], "00000000-0000-0000-0000-000000000002")
        self.assertEqual(report["result"]["open"], 0)
        self.assertEqual(report["result"]["resolved"], 0)
        wait_for_report(queued["task_id"])

    def test_reader_can_read_report_but_cannot_enqueue(self):
        reader = os.environ["APP_READER_TOKEN"]
        self.assertEqual(call("/api/reports/", "POST", token=reader)[0], 403)
        status, queued = call("/api/reports/", "POST")
        self.assertEqual(status, 202)
        wait_for_report(queued["task_id"])
        self.assertEqual(call("/api/reports/" + queued["task_id"], token=reader)[0], 200)
        self.assertEqual(download(queued["task_id"], token=reader)[0], 200)

    def test_anonymous_and_unscoped_requests_are_denied(self):
        self.assertEqual(call("/api/reports/", "POST", authenticated=False)[0], 403)
        self.assertEqual(call("/api/reports/", "POST", token=os.environ["APP_UNSCOPED_TOKEN"])[0], 403)

```

Run from the project directory while the server is running:

```bash
python -m unittest discover -s tests -v
```

Expect 16 tests: the earlier 12 plus four report tests. These tests assume the
small dedicated tutorial database, no other clients mutating it, and an empty
customer B after each test cleans up. They verify asynchronous completion,
tenant provenance, guarded status access and an authorized CSV download.

## Continue with durable actions

Continue with [durable ticket resolution](ticket-desk-durable.md) to reauthorize
a delayed mutation and commit it with its Operation success.

## Operation and retention responsibilities

Ordinary tasks may retry. This read-only report has no non-idempotent external
effect. A real export could run against changed data on a later attempt.
Task results remain in the database until the configured cleanup policy removes
them; choose `AKSARA_TASK_RESULT_TTL_SECONDS` and
`AKSARA_TASK_CLEANUP_INTERVAL_SECONDS` for your retention needs. After cleanup,
the report ID returns 404. These tests do not claim a retention or worker-loss
recovery proof.

When scaling, account for one embedded worker per web process, or disable it
and deploy a dedicated worker that imports the same registrations. See
[background tasks](../advanced/background-tasks.md) for queue/concurrency and
[deployment](deployment.md) for supervision. This chapter starts no durable
worker. [Durable Operations](../advanced/durable-operations.md) are a separate
choice for application actions whose authorization and commit must survive time.
