"""
Aksara AI Graph Events  (v0.5.36)

Lightweight in-memory event timeline for AI reasoning.

This is NOT a production event bus.  It is a short-lived context timeline
so the AI can correlate recent changes, failures, and system state when
answering questions about the project.

Usage::

    from aksara.ai.graph_events import emit_graph_event, get_recent_graph_events

    emit_graph_event("route_error", "route", "/api/users",
                     severity="error", message="500 on GET /api/users")

    recent = get_recent_graph_events(limit=50)

Event kinds::

    route_error, query_timeout, slow_query_detected,
    migration_applied, migration_failed, provider_unreachable,
    diagnostic_issue_detected, gap_report_changed,
    console_execution_failed, ai_flow_executed
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aksara.ai.graph_events")

# ─── Data Model ──────────────────────────────────────────────────────────────


@dataclass
class GraphEvent:
    """A single event in the project timeline."""

    kind: str
    timestamp: str
    source_type: str
    source_id: str
    severity: str = "info"
    message: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Bounded In-Memory Store ─────────────────────────────────────────────────

_MAX_EVENTS = 500
_lock = threading.Lock()
GRAPH_EVENTS: deque[GraphEvent] = deque(maxlen=_MAX_EVENTS)


# ─── Known Event Kinds ───────────────────────────────────────────────────────

EVENT_KINDS: frozenset[str] = frozenset({
    "route_error",
    "query_timeout",
    "slow_query_detected",
    "migration_applied",
    "migration_failed",
    "provider_unreachable",
    "diagnostic_issue_detected",
    "gap_report_changed",
    "console_execution_failed",
    "ai_flow_executed",
})


# ─── Public API ──────────────────────────────────────────────────────────────


def emit_graph_event(
    kind: str,
    source_type: str,
    source_id: str,
    *,
    severity: str = "info",
    message: str = "",
    **payload: Any,
) -> GraphEvent:
    """Record a new event in the timeline.

    Parameters
    ----------
    kind : str
        Event kind, e.g. ``"route_error"``, ``"ai_flow_executed"``.
    source_type : str
        Component type, e.g. ``"route"``, ``"query"``, ``"migration"``.
    source_id : str
        Identifier for the source, e.g. route path or model name.
    severity : str
        One of ``"info"``, ``"warning"``, ``"error"``.
    message : str
        Human-readable description.
    **payload
        Arbitrary extra data (must be JSON-serialisable).

    Returns
    -------
    GraphEvent
        The created event.
    """
    event = GraphEvent(
        kind=kind,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_type=source_type,
        source_id=source_id,
        severity=severity,
        message=message,
        payload=dict(payload),
    )
    if kind not in EVENT_KINDS:
        logger.warning("Unknown event kind %r — consider adding it to EVENT_KINDS", kind)
    with _lock:
        GRAPH_EVENTS.append(event)
    logger.debug("graph_event: %s %s/%s", kind, source_type, source_id)
    return event


def get_recent_graph_events(limit: int = 100) -> List[GraphEvent]:
    """Return the most recent events (newest last).

    Parameters
    ----------
    limit : int
        Maximum number of events to return (default 100, max 500).
    """
    limit = max(1, min(limit, _MAX_EVENTS))
    with _lock:
        items = list(GRAPH_EVENTS)
    # Return the last *limit* items (newest last)
    return items[-limit:]


def clear_graph_events() -> int:
    """Remove all events from the store.  Returns the count that was removed."""
    with _lock:
        count = len(GRAPH_EVENTS)
        GRAPH_EVENTS.clear()
    return count


def event_count() -> int:
    """Return the current number of stored events."""
    with _lock:
        return len(GRAPH_EVENTS)
