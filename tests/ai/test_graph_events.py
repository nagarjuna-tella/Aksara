"""
v0.5.32 — Graph Event Timeline: unit tests.

Tests cover:
    - emit_graph_event() — creates events with all fields
    - get_recent_graph_events() — retrieval and ordering
    - clear_graph_events() — clearing and count reset
    - event_count() — accurate count tracking
    - Bounded deque — max 500; older events evicted
    - Thread safety — concurrent emission doesn't corrupt
    - GraphEvent.to_dict() — serialisation shape
    - Severity validation and defaults
    - Payload passthrough
    - Event kinds from the public constant list
"""

from __future__ import annotations

import threading
import pytest

from aksara.ai.graph_events import (
    GraphEvent,
    GRAPH_EVENTS,
    emit_graph_event,
    get_recent_graph_events,
    clear_graph_events,
    event_count,
    EVENT_KINDS,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _clear():
    """Reset event store between tests."""
    clear_graph_events()


# ═══════════════════════════════════════════════════════════════════════════
# Tests: emit_graph_event
# ═══════════════════════════════════════════════════════════════════════════


class TestEmitGraphEvent:
    def setup_method(self):
        _clear()

    def test_returns_graph_event(self):
        ev = emit_graph_event("route_error", "route", "/api/foo")
        assert isinstance(ev, GraphEvent)

    def test_event_has_kind(self):
        ev = emit_graph_event("route_error", "route", "/api/foo")
        assert ev.kind == "route_error"

    def test_event_has_source(self):
        ev = emit_graph_event("slow_query_detected", "query", "q1")
        assert ev.source_type == "query"
        assert ev.source_id == "q1"

    def test_event_has_timestamp(self):
        ev = emit_graph_event("route_error", "route", "/api/foo")
        assert ev.timestamp  # non-empty ISO string
        assert "T" in ev.timestamp

    def test_default_severity_is_info(self):
        ev = emit_graph_event("route_error", "route", "/api/foo")
        assert ev.severity == "info"

    def test_custom_severity(self):
        ev = emit_graph_event("route_error", "route", "/api/foo", severity="error")
        assert ev.severity == "error"

    def test_custom_message(self):
        ev = emit_graph_event("route_error", "route", "/", message="boom")
        assert ev.message == "boom"

    def test_payload_passthrough(self):
        ev = emit_graph_event("route_error", "route", "/", extra="data", count=42)
        assert ev.payload["extra"] == "data"
        assert ev.payload["count"] == 42

    def test_empty_payload(self):
        ev = emit_graph_event("route_error", "route", "/")
        assert ev.payload == {}

    def test_event_appended_to_store(self):
        emit_graph_event("route_error", "route", "/")
        assert event_count() >= 1

    def test_multiple_emissions(self):
        for i in range(5):
            emit_graph_event("migration_applied", "migration", f"m{i}")
        assert event_count() == 5


# ═══════════════════════════════════════════════════════════════════════════
# Tests: get_recent_graph_events
# ═══════════════════════════════════════════════════════════════════════════


class TestGetRecentGraphEvents:
    def setup_method(self):
        _clear()

    def test_empty_store_returns_empty_list(self):
        assert get_recent_graph_events() == []

    def test_returns_list(self):
        emit_graph_event("route_error", "route", "/")
        result = get_recent_graph_events()
        assert isinstance(result, list)

    def test_returns_correct_count(self):
        for i in range(10):
            emit_graph_event("route_error", "route", f"/{i}")
        assert len(get_recent_graph_events()) == 10

    def test_limit_respected(self):
        for i in range(20):
            emit_graph_event("route_error", "route", f"/{i}")
        result = get_recent_graph_events(limit=5)
        assert len(result) == 5

    def test_newest_last(self):
        emit_graph_event("route_error", "route", "/first")
        emit_graph_event("route_error", "route", "/second")
        events = get_recent_graph_events()
        assert events[-1].source_id == "/second"
        assert events[0].source_id == "/first"

    def test_limit_larger_than_store(self):
        emit_graph_event("route_error", "route", "/")
        result = get_recent_graph_events(limit=1000)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests: clear_graph_events
# ═══════════════════════════════════════════════════════════════════════════


class TestClearGraphEvents:
    def setup_method(self):
        _clear()

    def test_clear_returns_count(self):
        for i in range(3):
            emit_graph_event("route_error", "route", f"/{i}")
        removed = clear_graph_events()
        assert removed == 3

    def test_clear_empties_store(self):
        emit_graph_event("route_error", "route", "/")
        clear_graph_events()
        assert event_count() == 0
        assert get_recent_graph_events() == []

    def test_clear_empty_returns_zero(self):
        assert clear_graph_events() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests: event_count
# ═══════════════════════════════════════════════════════════════════════════


class TestEventCount:
    def setup_method(self):
        _clear()

    def test_zero_initially(self):
        assert event_count() == 0

    def test_increments(self):
        emit_graph_event("route_error", "route", "/")
        assert event_count() == 1
        emit_graph_event("route_error", "route", "/")
        assert event_count() == 2

    def test_count_after_clear(self):
        emit_graph_event("route_error", "route", "/")
        clear_graph_events()
        assert event_count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Bounded deque (maxlen=500)
# ═══════════════════════════════════════════════════════════════════════════


class TestBoundedDeque:
    def setup_method(self):
        _clear()

    def test_max_500_events(self):
        for i in range(550):
            emit_graph_event("route_error", "route", f"/{i}")
        assert event_count() == 500

    def test_oldest_evicted(self):
        for i in range(510):
            emit_graph_event("route_error", "route", f"/{i}")
        events = get_recent_graph_events(limit=500)
        # Oldest (0-9) should be evicted; 10+ should remain
        ids = [e.source_id for e in events]
        assert "/0" not in ids
        assert "/509" in ids


# ═══════════════════════════════════════════════════════════════════════════
# Tests: GraphEvent.to_dict()
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphEventToDict:
    def test_returns_dict(self):
        ev = emit_graph_event("route_error", "route", "/")
        d = ev.to_dict()
        assert isinstance(d, dict)

    def test_required_keys(self):
        ev = emit_graph_event("route_error", "route", "/", severity="warning", message="bad")
        d = ev.to_dict()
        for key in ("kind", "timestamp", "source_type", "source_id", "severity", "message", "payload"):
            assert key in d, f"Missing key: {key}"

    def test_values_match(self):
        ev = emit_graph_event("slow_query_detected", "query", "q1", severity="warning", message="slow")
        d = ev.to_dict()
        assert d["kind"] == "slow_query_detected"
        assert d["source_type"] == "query"
        assert d["source_id"] == "q1"
        assert d["severity"] == "warning"
        assert d["message"] == "slow"

    def test_payload_included(self):
        ev = emit_graph_event("route_error", "route", "/", status=500)
        d = ev.to_dict()
        assert d["payload"]["status"] == 500


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Thread Safety
# ═══════════════════════════════════════════════════════════════════════════


class TestThreadSafety:
    def setup_method(self):
        _clear()

    def test_concurrent_emissions(self):
        """Many threads emitting simultaneously should not corrupt the store."""
        n_threads = 10
        n_events = 40
        barriers = []

        def _emit_batch(start):
            for i in range(n_events):
                emit_graph_event("route_error", "route", f"/{start + i}")

        threads = [
            threading.Thread(target=_emit_batch, args=(t * n_events,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert event_count() == n_threads * n_events

    def test_concurrent_read_write(self):
        """Reading while writing should not raise."""
        results = []

        def _writer():
            for i in range(100):
                emit_graph_event("route_error", "route", f"/{i}")

        def _reader():
            for _ in range(100):
                events = get_recent_graph_events(limit=50)
                results.append(len(events))

        w = threading.Thread(target=_writer)
        r = threading.Thread(target=_reader)
        w.start()
        r.start()
        w.join()
        r.join()

        assert len(results) == 100


# ═══════════════════════════════════════════════════════════════════════════
# Tests: EVENT_KINDS constant
# ═══════════════════════════════════════════════════════════════════════════


class TestEventKinds:
    def test_event_kinds_is_frozenset(self):
        assert isinstance(EVENT_KINDS, frozenset)

    def test_contains_expected_kinds(self):
        expected = {
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
        }
        for kind in expected:
            assert kind in EVENT_KINDS, f"Missing kind: {kind}"

    def test_not_empty(self):
        assert len(EVENT_KINDS) >= 10
