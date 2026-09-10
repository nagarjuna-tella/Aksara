"""Stable MCP tool error taxonomy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolError:
    code: str
    category: str
    message: str
    retryable: bool = False
    details: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            result["details"] = dict(self.details)
        return result


def from_http(status: int, payload: Any) -> ToolError:
    """Map the generated API's response to a transport-independent category."""

    detail = payload.get("detail") if isinstance(payload, dict) else payload
    nested_code = detail.get("code") if isinstance(detail, dict) else None
    if status == 401:
        return ToolError("unauthenticated", "authorization", "Authentication is required.")
    if status == 403:
        code = nested_code or "permission_denied"
        if isinstance(detail, dict) and detail.get("denied_fields"):
            code = "forbidden_field"
        return ToolError(code, "authorization", "The operation was denied by application policy.")
    if status == 404:
        return ToolError("not_found", "client", "The requested resource does not exist.")
    if status in {400, 409, 422}:
        code = nested_code or ("conflict" if status == 409 else "schema_mismatch")
        return ToolError(code, "client", "The operation arguments were rejected.")
    if status in {502, 503, 504}:
        return ToolError("infrastructure_error", "transient", "A required service is unavailable.", True)
    return ToolError("internal_error", "internal", "The application could not complete the operation.")


__all__ = ["ToolError", "from_http"]
