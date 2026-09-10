"""Generated CRUD surfaces for the support desk domain."""

import os
from typing import ClassVar

from fastapi import Request

from aksara import ModelViewSet, action
from aksara.permissions import IsAuthenticated
from aksara.security.context import principal_from_request

from .models import SupportAgent, Ticket
from .permissions import SupportDeskPermission


class SupportAgentViewSet(ModelViewSet):
    model = SupportAgent
    prefix = "/api/agents"
    tags: ClassVar = ["Support agents"]
    permission_classes: ClassVar = [IsAuthenticated, SupportDeskPermission]
    ai_exposed = True
    stream_enabled = False


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    tags: ClassVar = ["Support tickets"]
    permission_classes: ClassVar = [IsAuthenticated, SupportDeskPermission]
    ai_exposed = True
    mcp_approval_required_actions: ClassVar[set[str]] = {"delete"}
    stream_enabled = False

    @action(detail=False, methods=["POST"], ai_exposed=True)
    async def rollback_probe(self, request: Request):
        """Exercise MCP transaction rollback in the packaged release gate."""
        if os.getenv("SUPPORT_DESK_ENABLE_FAILURE_PROBES") != "true":
            return {"enabled": False}
        principal = principal_from_request(request)
        await self.model.objects.create(
            subject="MCP rollback probe must not persist",
            description="The action fails after this insert.",
            tenant_id=principal.tenant_id,
        )
        raise RuntimeError("intentional MCP rollback probe")


VIEWSETS = [SupportAgentViewSet, TicketViewSet]
