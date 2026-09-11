"""Production entry point for the multi-tenant support desk reference app."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request

from aksara import Aksara
from aksara.manager import DoesNotExist
from aksara.mcp import JsonlMCPAuditSink
from aksara.migrations.executor import discover_migrations
from aksara.permissions import check_permissions
from aksara.security.principal import Principal
from aksara.tasks import get_task_record

from . import admin  # noqa: F401
from .auth import SupportDeskAuthMiddleware
from .models import Ticket
from .permissions import SupportDeskPermission
from .settings import DATABASE_URL, PACKAGE_ROOT
from .tasks import deliver_ticket
from .views import VIEWSETS


@asynccontextmanager
async def lifespan(app: Aksara):
    assert app.db is not None
    expected = {name for name, _ in discover_migrations(PACKAGE_ROOT / "migrations")}
    rows = await app.db.fetch("SELECT name FROM aksara_migrations")
    applied = {row["name"] for row in rows}
    pending = sorted(expected - applied)
    if pending:
        raise RuntimeError(
            "Unapplied support desk migrations: "
            + ", ".join(pending)
            + ". Run `aksara migrate` before starting the service."
        )
    yield


_audit_path = os.getenv("SUPPORT_DESK_MCP_AUDIT_PATH")

app = Aksara(
    database_url=DATABASE_URL,
    title="Aksara Support Desk",
    description="Production-shaped multi-tenant support desk reference application",
    version="0.7.0rc1",
    debug=False,
    enable_admin=True,
    auto_discover_views=False,
    lifespan=lifespan,
    mcp_audit_sink=JsonlMCPAuditSink(_audit_path) if _audit_path else None,
)
app.add_middleware(SupportDeskAuthMiddleware)
app.register_viewsets(VIEWSETS)


@app.get("/health/live", tags=["Operations"])
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["Operations"])
async def readiness() -> dict[str, str]:
    if app.db is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    await app.db.fetchval("SELECT 1")
    return {"status": "ready"}


@app.post("/api/tickets/{ticket_id}/deliver", tags=["Support tickets"])
async def enqueue_delivery(
    ticket_id: str,
    request: Request,
    fail_until_attempt: int = 0,
) -> dict[str, str]:
    allowed, message = check_permissions([SupportDeskPermission], request)
    if not allowed:
        raise HTTPException(status_code=403, detail=message)
    if app.db is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        await Ticket.objects.get(id=ticket_id)
    except DoesNotExist as exc:
        raise HTTPException(status_code=404, detail="ticket not found") from exc
    queued = await deliver_ticket.enqueue(
        ticket_id,
        fail_until_attempt=fail_until_attempt,
        db=app.db,
    )
    return {"task_id": str(queued.id), "status": queued.status}


@app.get("/api/tasks/{task_id}", tags=["Operations"])
async def task_status(task_id: str, request: Request) -> dict[str, object]:
    allowed, message = check_permissions([SupportDeskPermission], request)
    if not allowed:
        raise HTTPException(status_code=403, detail=message)
    if app.db is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    record = await get_task_record(task_id, db=app.db)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal) or record.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="task not found")
    return record.to_dict()
