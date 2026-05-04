"""
Aksara Core Utilities

Core utilities for Aksara framework including:
- Auto-discovery of ViewSets from modules
"""

from aksara.core.discovery import (
    discover_viewsets_from_module,
    import_module_safely,
    discover_viewsets_from_apps,
    auto_discover_viewsets,
)
from aksara.core.mail import (
    EmailMessage,
    BaseEmailBackend,
    ConsoleBackend,
    LocMemBackend,
    SMTPBackend,
    get_email_backend,
    send_mail,
    send_mass_mail,
    outbox,
    reset_outbox,
)

__all__ = [
    "discover_viewsets_from_module",
    "import_module_safely",
    "discover_viewsets_from_apps",
    "auto_discover_viewsets",
    "EmailMessage",
    "BaseEmailBackend",
    "ConsoleBackend",
    "LocMemBackend",
    "SMTPBackend",
    "get_email_backend",
    "send_mail",
    "send_mass_mail",
    "outbox",
    "reset_outbox",
]
