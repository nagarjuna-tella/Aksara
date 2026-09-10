"""Authorization policy for generated support desk APIs."""

from __future__ import annotations

import os
from typing import Any

from aksara.permissions import BasePermission
from aksara.security.mcp import require_mcp_audience, require_mcp_tenant
from aksara.security.principal import Principal


class SupportDeskPermission(BasePermission):
    message = "Support desk access denied."
    ai_allow = True

    def has_permission(self, request: Any, view: Any = None) -> bool:
        principal = getattr(getattr(request, "state", None), "principal", None)
        if not isinstance(principal, Principal) or not principal.is_authenticated:
            return False
        if principal.is_ai_agent:
            expected_audience = os.getenv(
                "SUPPORT_DESK_MCP_AUDIENCE",
                "support-desk",
            )
            if principal.is_expired:
                return False
            if not require_mcp_audience(principal, expected_audience).allowed:
                return False
            if not require_mcp_tenant(principal).allowed:
                return False
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return not principal.is_ai_agent or principal.has_scope("mcp:read:ticket")
        if principal.is_ai_agent:
            return principal.has_scope("mcp:write:ticket")
        return principal.has_any_role(("agent", "admin"))
