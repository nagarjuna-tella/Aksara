from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import mcp.types as mcp_types
import pytest

from aksara.ai.models import AiTool
from aksara.ai.registry import AiToolRegistry
from aksara.conf import settings
from aksara.mcp import MCPRuntime, MemoryMCPAuditSink
from aksara.security.principal import Principal


def _tool(*, approval: bool = False, tenant_scoped: bool = True) -> AiTool:
    return AiTool(
        name="ticket_update",
        title="Update ticket",
        description="Update a support ticket",
        http_method="PATCH",
        path="/api/tickets/{pk}",
        model="Ticket",
        kind="mutation",
        tenant_scoped=tenant_scoped,
        approval_required=approval,
        input_schema={
            "type": "object",
            "properties": {"pk": {"type": "string"}, "status": {"type": "string"}},
            "required": ["pk"],
            "additionalProperties": False,
        },
    )


def _principal(**changes) -> Principal:
    values = {
        "token_id": "token-a",
        "human_owner_id": "owner-a",
        "agent_id": "agent-a",
        "tenant_id": "tenant-a",
        "roles": ("agent",),
        "scopes": ("mcp:write:ticket",),
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "metadata": {"audience": "test-mcp"},
    }
    values.update(changes)
    return Principal.for_mcp_agent(**values)


def _request(principal: Principal):
    return SimpleNamespace(
        state=SimpleNamespace(principal=principal, is_ai_agent=principal.is_ai_agent),
        headers={"authorization": "Bearer opaque"},
    )


def _ctx(principal: Principal, *, call_id: str | None = None):
    meta = {"aksara.run_id": "run-one"}
    if call_id:
        meta["aksara.tool_call_id"] = call_id
    return SimpleNamespace(
        request=_request(principal),
        request_id="request-one",
        meta=meta,
        protocol_version="2026-07-28",
    )


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(settings, "mcp_token_audience", "test-mcp")
    monkeypatch.setattr(settings, "mcp_require_scoped_tokens", True)
    monkeypatch.setattr(settings, "mcp_tool_timeout_seconds", 0.05)
    monkeypatch.setattr(settings, "mcp_replay_ttl_seconds", 60.0)
    monkeypatch.setattr(settings, "mcp_approval_secret", "test-approval-secret")
    registry = AiToolRegistry()
    registry.register_tool(_tool())
    app = SimpleNamespace(title="Test", debug=False, ai_registry=registry, db=None)
    sink = MemoryMCPAuditSink()
    return MCPRuntime(app, audit_sink=sink), sink


def _params(arguments=None, name="ticket_update"):
    return mcp_types.CallToolRequestParams(name=name, arguments=arguments or {})


@pytest.mark.asyncio
async def test_success_is_structured_and_audited_without_argument_values(runtime) -> None:
    boundary, sink = runtime
    boundary._invoke_generated_api = AsyncMock(
        return_value=httpx.Response(200, json={"id": "one", "status": "closed"})
    )
    result = await boundary._call_tool(_ctx(_principal()), _params({"pk": "one", "status": "closed"}))
    assert result.is_error is False
    assert result.structured_content == {"id": "one", "status": "closed"}
    assert len(sink.events) == 1
    event = sink.events[0]
    assert (event.run_id, event.tool_call_id, event.tenant_id, event.agent_id) == (
        "run-one", "request-one", "tenant-a", "agent-a"
    )
    assert "closed" not in repr(event.argument_summary)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("principal", "code"),
    [
        (Principal.anonymous(), "unauthenticated"),
        (Principal.for_user("human", tenant_id="tenant-a"), "invalid_principal_type"),
        (_principal(expires_at=datetime.now(UTC) - timedelta(seconds=1)), "credential_expired"),
        (_principal(metadata={"audience": "wrong"}), "wrong_audience"),
        (_principal(tenant_id=None), "tenant_context_required"),
        (_principal(scopes=()), "missing_scope"),
    ],
)
async def test_execution_time_credential_checks(runtime, principal, code) -> None:
    boundary, sink = runtime
    boundary._invoke_generated_api = AsyncMock()
    result = await boundary._call_tool(_ctx(principal), _params({"pk": "one"}))
    assert result.is_error is True
    assert result.structured_content["error"]["code"] == code
    boundary._invoke_generated_api.assert_not_awaited()
    assert sink.events[-1].error_code == code


@pytest.mark.asyncio
async def test_unknown_schema_forbidden_permission_db_and_replay_errors(runtime) -> None:
    boundary, sink = runtime
    unknown = await boundary._call_tool(_ctx(_principal()), _params(name="hidden_tool"))
    assert unknown.structured_content["error"]["code"] == "unknown_tool"

    boundary._invoke_generated_api = AsyncMock()
    malformed = await boundary._call_tool(_ctx(_principal()), _params({"pk": "one", "tenant_id": "tenant-b"}))
    assert malformed.structured_content["error"]["code"] == "forbidden_field"
    boundary._invoke_generated_api.assert_not_awaited()

    boundary._invoke_generated_api = AsyncMock(return_value=httpx.Response(403, json={"detail": "changed"}))
    denied = await boundary._call_tool(_ctx(_principal()), _params({"pk": "one"}))
    assert denied.structured_content["error"]["category"] == "authorization"

    boundary._invoke_generated_api = AsyncMock(return_value=httpx.Response(500, json={"detail": "db"}))
    failed = await boundary._call_tool(_ctx(_principal()), _params({"pk": "one"}))
    assert failed.structured_content["error"]["code"] == "internal_error"

    boundary._invoke_generated_api = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    first = await boundary._call_tool(_ctx(_principal(), call_id="same"), _params({"pk": "one"}))
    second = await boundary._call_tool(_ctx(_principal(), call_id="same"), _params({"pk": "one"}))
    assert first.is_error is False
    assert second.structured_content["error"]["code"] == "repeated_tool_request"
    assert sink.events[-1].error_code == "repeated_tool_request"


@pytest.mark.asyncio
async def test_approval_gates_before_mutation_and_rechecks_exact_action(runtime) -> None:
    boundary, _ = runtime
    boundary.app.ai_registry.register_tool(_tool(approval=True))
    boundary._invoke_generated_api = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    principal = _principal()
    proposed = {"pk": "one", "status": "closed"}

    missing = await boundary._call_tool(_ctx(principal), _params(proposed))
    assert missing.structured_content["error"]["code"] == "approval_required"
    boundary._invoke_generated_api.assert_not_awaited()

    grant = boundary.approvals.issue(
        principal=principal,
        tool_name="ticket_update",
        arguments=proposed,
        approved_by="reviewer",
    )
    changed = await boundary._call_tool(
        _ctx(principal), _params({"pk": "one", "status": "deleted", "_approval_token": grant})
    )
    assert changed.structured_content["error"]["code"] == "approval_arguments_mismatch"
    boundary._invoke_generated_api.assert_not_awaited()

    approved = await boundary._call_tool(
        _ctx(principal), _params({**proposed, "_approval_token": grant})
    )
    assert approved.is_error is False
    boundary._invoke_generated_api.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_timeout_and_cancellation_are_distinct(runtime) -> None:
    boundary, sink = runtime

    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    boundary._invoke_generated_api = slow
    timed_out = await boundary._call_tool(_ctx(_principal()), _params({"pk": "one"}))
    assert timed_out.structured_content["error"]["code"] == "tool_timeout"

    boundary.settings.mcp_tool_timeout_seconds = 5
    task = asyncio.create_task(boundary._call_tool(_ctx(_principal()), _params({"pk": "one"})))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sink.events[-1].error_code == "cancelled"
