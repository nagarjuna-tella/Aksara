"""
Server-sent event streaming for Aksara ModelViewSets.

v0.5.45: Publishes model lifecycle events via PostgreSQL LISTEN/NOTIFY and
exposes default SSE responses for model-specific stream endpoints.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, TYPE_CHECKING

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from aksara.db.engine import Database
from aksara.middleware.context import tenant_id_var
from aksara.signals import post_delete, post_save

if TYPE_CHECKING:
    from aksara.model.base import Model


MODEL_STREAM_CHANNEL_PREFIX = "aksara_model_events"
_stream_signal_receivers_connected = False


def get_model_stream_channel(model_class: type["Model"]) -> str:
    """Return the PostgreSQL channel name for a model stream."""
    return f"{MODEL_STREAM_CHANNEL_PREFIX}_{model_class.__tablename__}"


def build_model_event_payload(action: str, sender: type["Model"], instance: "Model") -> dict[str, Any]:
    """Build a JSON-serializable payload for a model lifecycle event."""
    payload: dict[str, Any] = {
        "action": action,
        "model": sender.__name__,
        "table": sender.__tablename__,
        "id": None,
    }

    instance_id = instance._data.get("id") if hasattr(instance, "_data") else None
    if instance_id is not None:
        payload["id"] = str(instance_id)

    if "tenant_id" in getattr(sender, "_fields", {}):
        tenant_id = instance._data.get("tenant_id") if hasattr(instance, "_data") else None
        payload["tenant_id"] = str(tenant_id) if tenant_id is not None else None

    return payload


def should_deliver_model_event(payload: dict[str, Any], current_tenant_id: str | None) -> bool:
    """Return True when a streamed event is visible to the current subscriber."""
    payload_tenant = payload.get("tenant_id")
    if payload_tenant is None:
        return True
    if not current_tenant_id:
        return False
    return str(payload_tenant) == str(current_tenant_id)


def encode_sse_event(payload: dict[str, Any], *, event: str = "message") -> str:
    """Encode a payload as a server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


async def publish_model_event(action: str, sender: type["Model"], instance: "Model") -> None:
    """Publish a model lifecycle event via PostgreSQL NOTIFY."""
    try:
        db = Database.get_instance()
    except RuntimeError:
        return

    payload = build_model_event_payload(action, sender, instance)
    await db.execute(
        "SELECT pg_notify($1, $2)",
        get_model_stream_channel(sender),
        json.dumps(payload, default=str),
    )


async def _handle_post_save(sender: type["Model"], instance: "Model") -> None:
    action = getattr(instance, "_stream_action", "UPDATE") or "UPDATE"
    await publish_model_event(action, sender, instance)


async def _handle_post_delete(sender: type["Model"], instance: "Model") -> None:
    await publish_model_event("DELETE", sender, instance)


def ensure_model_stream_signal_receivers() -> None:
    """Connect lifecycle signal receivers for streaming exactly once."""
    global _stream_signal_receivers_connected
    if _stream_signal_receivers_connected:
        return

    post_save.connect(_handle_post_save)
    post_delete.connect(_handle_post_delete)
    _stream_signal_receivers_connected = True


def build_model_stream_response(request: Request, model_class: type["Model"]) -> StreamingResponse:
    """Build a StreamingResponse that emits model lifecycle events."""
    try:
        db = Database.get_instance()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Database is not initialized") from exc

    ensure_model_stream_signal_receivers()
    channel = get_model_stream_channel(model_class)
    current_tenant_id = getattr(request.state, "tenant_id", None) or tenant_id_var.get()

    async def event_stream():
        queue: asyncio.Queue[str] = asyncio.Queue()

        def listener(connection, pid, channel_name, payload):
            queue.put_nowait(payload)

        async with db.pool.acquire() as connection:
            await connection.add_listener(channel, listener)
            try:
                yield encode_sse_event(
                    {"channel": channel, "model": model_class.__name__, "status": "connected"},
                    event="ready",
                )
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        raw_payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue

                    payload = json.loads(raw_payload)
                    if not should_deliver_model_event(payload, current_tenant_id):
                        continue
                    yield encode_sse_event(payload)
            finally:
                await connection.remove_listener(channel, listener)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


ensure_model_stream_signal_receivers()


__all__ = [
    "MODEL_STREAM_CHANNEL_PREFIX",
    "build_model_event_payload",
    "build_model_stream_response",
    "encode_sse_event",
    "ensure_model_stream_signal_receivers",
    "get_model_stream_channel",
    "publish_model_event",
    "should_deliver_model_event",
]