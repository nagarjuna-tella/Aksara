"""
Admin bulk actions.

Actions are operations applied to a set of selected rows from the list view.
Declare them with the ``@action`` decorator and list their names in
``ModelAdmin.actions``:

    class PostAdmin(ModelAdmin):
        actions = ["publish_selected"]

        @action(description="Publish selected posts", permissions=["change"])
        async def publish_selected(self, request, queryset):
            count = await queryset.update(is_published=True)
            self.message_user(request, f"Published {count} posts.")

User-facing messages are surfaced with ``message_user`` and shown on the next
list render via a short-lived cookie (post/redirect/get).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, List, Optional

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response

ADMIN_MESSAGE_COOKIE = "aksara_admin_messages"

# Recognised message levels and the CSS alert class each maps to in templates.
MESSAGE_LEVELS = {
    "success": "alert-success",
    "info": "alert-info",
    "warning": "alert-warning",
    "error": "alert-danger",
}


def action(
    description: Optional[str] = None,
    permissions: Optional[List[str]] = None,
) -> Callable:
    """
    Mark a ``ModelAdmin`` method as a bulk action.

    Args:
        description: Human-readable label shown in the actions dropdown.
        permissions: Permission names required to run the action. Each name
            ``X`` is checked against ``has_X_permission(request)`` on the admin
            (e.g. ``["change"]`` requires ``has_change_permission``).
    """

    def decorator(func: Callable) -> Callable:
        func._is_admin_action = True  # type: ignore[attr-defined]
        func.action_description = (  # type: ignore[attr-defined]
            description or func.__name__.replace("_", " ").capitalize()
        )
        if permissions is not None:
            func.allowed_permissions = list(permissions)  # type: ignore[attr-defined]
        return func

    return decorator


@action(description="Delete selected items", permissions=["delete"])
async def delete_selected(model_admin: Any, request: "Request", queryset: Any) -> None:
    """Built-in action: delete every selected object."""
    objects = await queryset.all()
    count = 0
    for obj in objects:
        await model_admin.delete_model(request, obj)
        count += 1
    model_admin.message_user(
        request,
        f"Deleted {count} {model_admin.model.__name__} object(s).",
        level="success",
    )


def queue_message(request: "Request", message: str, level: str = "info") -> None:
    """Append a flash message to be shown on the next list render."""
    if level not in MESSAGE_LEVELS:
        level = "info"
    store = getattr(request.state, "_admin_messages", None)
    if store is None:
        store = []
        request.state._admin_messages = store
    store.append({"level": level, "text": str(message)})


def write_messages_cookie(request: "Request", response: "Response") -> None:
    """Persist queued messages onto a redirect response, if any were queued."""
    store = getattr(request.state, "_admin_messages", None)
    if not store:
        return
    response.set_cookie(
        key=ADMIN_MESSAGE_COOKIE,
        value=json.dumps(store),
        max_age=30,
        httponly=True,
        samesite="strict",
        path="/",
    )


def pop_messages(request: "Request") -> List[dict]:
    """Read and parse any flash messages from the incoming request cookie."""
    raw = request.cookies.get(ADMIN_MESSAGE_COOKIE)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    cleaned = []
    for item in data:
        if isinstance(item, dict) and "text" in item:
            level = item.get("level", "info")
            cleaned.append(
                {
                    "level": level if level in MESSAGE_LEVELS else "info",
                    "alert_class": MESSAGE_LEVELS.get(level, "alert-info"),
                    "text": str(item["text"]),
                }
            )
    return cleaned


def clear_messages_cookie(response: "Response") -> None:
    """Delete the flash-message cookie after it has been read."""
    response.delete_cookie(ADMIN_MESSAGE_COOKIE, path="/")
