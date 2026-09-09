"""Generated CRUD surfaces for the support desk domain."""

from typing import ClassVar

from aksara import ModelViewSet
from aksara.permissions import IsAuthenticated

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
    stream_enabled = False


VIEWSETS = [SupportAgentViewSet, TicketViewSet]
