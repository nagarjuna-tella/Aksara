"""Deterministic, vendor-neutral audit records for MCP execution."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

logger = logging.getLogger("aksara.mcp.audit")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def safe_argument_summary(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Describe arguments without retaining their values or secrets."""

    def describe(value: Any) -> dict[str, Any]:
        summary: dict[str, Any] = {"type": type(value).__name__}
        if isinstance(value, (str, bytes, list, tuple, dict)):
            summary["size"] = len(value)
        summary["sha256"] = hashlib.sha256(_canonical_json(value)).hexdigest()
        return summary

    clean = {
        key: value
        for key, value in arguments.items()
        if key not in {"_approval_token"}
    }
    return {
        "fields": {key: describe(clean[key]) for key in sorted(clean)},
        "sha256": hashlib.sha256(_canonical_json(clean)).hexdigest(),
    }


@dataclass(frozen=True, slots=True)
class MCPExecutionAuditEvent:
    """One final record for one resolved tool invocation."""

    timestamp: str
    request_id: str
    run_id: str
    tool_call_id: str
    tool_name: str
    operation: str
    http_method: str
    resource: str | None
    object_id: str | None
    principal_type: str
    user_id: str | None
    human_owner_id: str | None
    agent_id: str | None
    token_id: str | None
    tenant_id: str | None
    argument_summary: Mapping[str, Any]
    policy_decision: str
    approval_required: bool
    approval_id: str | None
    approved_by: str | None
    outcome: str
    error_code: str | None
    http_status: int | None
    duration_ms: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def timestamp_now(cls) -> str:
        return datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MCPAuditSink(Protocol):
    """Application hook for durable or external audit storage."""

    async def emit(self, event: MCPExecutionAuditEvent) -> None: ...


class LoggingMCPAuditSink:
    """Default sink: emit a stable JSON record through Python logging."""

    async def emit(self, event: MCPExecutionAuditEvent) -> None:
        logger.info("mcp_execution %s", json.dumps(event.to_dict(), sort_keys=True))


class JsonlMCPAuditSink:
    """Append audit records to a local JSONL file for simple deployments/tests."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = Lock()

    async def emit(self, event: MCPExecutionAuditEvent) -> None:
        line = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")


class MemoryMCPAuditSink:
    """Collect records for deterministic tests; intentionally process-local."""

    def __init__(self) -> None:
        self.events: list[MCPExecutionAuditEvent] = []

    async def emit(self, event: MCPExecutionAuditEvent) -> None:
        self.events.append(event)


__all__ = [
    "JsonlMCPAuditSink",
    "LoggingMCPAuditSink",
    "MCPAuditSink",
    "MCPExecutionAuditEvent",
    "MemoryMCPAuditSink",
    "safe_argument_summary",
]
