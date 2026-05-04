"""Tests for model streaming and event publication."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from aksara import Model, TenantModel, fields
from aksara.api.router import include_viewset
from aksara.api.streaming import (
    build_model_event_payload,
    get_model_stream_channel,
    publish_model_event,
    should_deliver_model_event,
)
from aksara.api.viewsets import ModelViewSet
from aksara.db.engine import Database


class StreamItem(Model):
    name = fields.String(max_length=100)

    class Meta:
        table_name = "stream_items"


class StreamItemViewSet(ModelViewSet):
    model = StreamItem
    prefix = "/items"


class TenantEvent(TenantModel):
    title = fields.String(max_length=100)

    class Meta:
        table_name = "tenant_events"


class TestStreamingRoutes:
    """Tests for default stream route wiring."""

    def test_include_viewset_adds_stream_route(self):
        app = FastAPI()

        include_viewset(app, StreamItemViewSet)

        routes = [route.path for route in app.routes]
        assert "/items/stream" in routes

    def test_stream_endpoint_returns_sse_response(self):
        app = FastAPI()
        response = StreamingResponse(iter(["event: ready\ndata: {}\n\n"]), media_type="text/event-stream")

        with patch("aksara.api.viewsets.build_model_stream_response", return_value=response) as mock_builder:
            include_viewset(app, StreamItemViewSet)
            client = TestClient(app)
            result = client.get("/items/stream")

        assert result.status_code == 200
        assert result.headers["content-type"].startswith("text/event-stream")
        mock_builder.assert_called_once()


class TestStreamingPublisher:
    """Tests for PG NOTIFY event publication."""

    @pytest.mark.asyncio
    async def test_publish_model_event_uses_pg_notify(self, monkeypatch):
        db = Mock(execute=AsyncMock())
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: db))

        item = StreamItem(name="Widget")
        item._data["id"] = uuid4()
        item._data["created_at"] = datetime.now(timezone.utc)
        item._data["updated_at"] = datetime.now(timezone.utc)
        item._is_new = False

        await publish_model_event("INSERT", StreamItem, item)

        db.execute.assert_awaited_once()
        sql, channel, payload = db.execute.await_args.args
        assert sql == "SELECT pg_notify($1, $2)"
        assert channel == get_model_stream_channel(StreamItem)
        assert '"action": "INSERT"' in payload
        assert '"model": "StreamItem"' in payload

    def test_should_deliver_event_filters_tenant_payloads(self):
        payload = {"action": "UPDATE", "tenant_id": "acme"}

        assert should_deliver_model_event(payload, "acme") is True
        assert should_deliver_model_event(payload, "globex") is False
        assert should_deliver_model_event(payload, None) is False

    def test_build_model_event_payload_includes_tenant_id(self):
        event = TenantEvent(title="Alpha")
        event._data["id"] = uuid4()
        event._data["tenant_id"] = uuid4()
        event._is_new = False

        payload = build_model_event_payload("UPDATE", TenantEvent, event)

        assert payload["action"] == "UPDATE"
        assert payload["model"] == "TenantEvent"
        assert payload["tenant_id"] is not None