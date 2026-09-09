"""Authorization policy for generated support desk APIs."""

from __future__ import annotations

from typing import Any

from aksara.permissions import BasePermission
from aksara.security.principal import Principal


class SupportDeskPermission(BasePermission):
    message = "Support desk access denied."
    ai_allow = True

    def has_permission(self, request: Any, view: Any = None) -> bool:
        principal = getattr(getattr(request, "state", None), "principal", None)
        if not isinstance(principal, Principal) or not principal.is_authenticated:
            return False
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return not principal.is_ai_agent or principal.has_scope("mcp:read:ticket")
        if principal.is_ai_agent:
            return principal.has_scope("mcp:write:ticket")
        return principal.has_any_role(("agent", "admin"))
