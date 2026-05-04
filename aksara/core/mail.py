"""
Async email backends for Aksara.

Provides SMTP, console, and in-memory backends plus convenience helpers for
sending individual or batched emails.
"""

from __future__ import annotations

import importlib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage as PythonEmailMessage
from typing import Iterable, Optional

from aksara.exceptions import ImproperlyConfigured


def _get_settings():
    """Lazy import to avoid loading settings at module import time."""
    from aksara.conf import settings

    return settings


@dataclass(slots=True)
class EmailMessage:
    """Representation of an outbound email message."""

    subject: str
    body: str
    to: list[str]
    from_email: Optional[str] = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    html_body: Optional[str] = None

    def as_python_email(self) -> PythonEmailMessage:
        """Convert the message into the stdlib email representation."""
        settings = _get_settings()

        if not self.to:
            raise ValueError("EmailMessage requires at least one recipient")

        message = PythonEmailMessage()
        message["Subject"] = self.subject
        message["From"] = self.from_email or getattr(settings, "default_from_email", "webmaster@localhost")
        message["To"] = ", ".join(self.to)
        if self.cc:
            message["Cc"] = ", ".join(self.cc)
        if self.reply_to:
            message["Reply-To"] = ", ".join(self.reply_to)
        for key, value in self.headers.items():
            message[key] = value

        if self.html_body is not None:
            message.set_content(self.body)
            message.add_alternative(self.html_body, subtype="html")
        else:
            message.set_content(self.body)

        return message

    @property
    def all_recipients(self) -> list[str]:
        """Return all recipient addresses across to/cc/bcc."""
        return [*self.to, *self.cc, *self.bcc]


class BaseEmailBackend(ABC):
    """Base async interface for outbound email delivery backends."""

    def __init__(self, *, fail_silently: bool = False):
        self.fail_silently = fail_silently

    @abstractmethod
    async def send_messages(self, email_messages: list[EmailMessage]) -> int:
        """Send a batch of outbound emails and return the number delivered."""


outbox: list[EmailMessage] = []


class ConsoleBackend(BaseEmailBackend):
    """Development backend that prints messages to stdout."""

    async def send_messages(self, email_messages: list[EmailMessage]) -> int:
        sent = 0
        stream = sys.stdout
        for message in email_messages:
            stream.write("=" * 72 + "\n")
            stream.write(f"Subject: {message.subject}\n")
            stream.write(f"From: {message.from_email or _get_settings().default_from_email}\n")
            stream.write(f"To: {', '.join(message.to)}\n")
            if message.cc:
                stream.write(f"Cc: {', '.join(message.cc)}\n")
            stream.write("\n")
            stream.write(f"{message.body}\n")
            if message.html_body:
                stream.write("\n-- HTML alternative attached --\n")
            stream.write("=" * 72 + "\n")
            sent += 1
        stream.flush()
        return sent


class LocMemBackend(BaseEmailBackend):
    """Testing backend that stores outbound messages in a process-local outbox."""

    async def send_messages(self, email_messages: list[EmailMessage]) -> int:
        outbox.extend(email_messages)
        return len(email_messages)


class SMTPBackend(BaseEmailBackend):
    """SMTP backend powered by aiosmtplib."""

    async def send_messages(self, email_messages: list[EmailMessage]) -> int:
        settings = _get_settings()

        try:
            import aiosmtplib
        except ImportError as exc:
            raise ImproperlyConfigured(
                "SMTPBackend requires aiosmtplib. Install with: pip install aiosmtplib"
            ) from exc

        sent = 0
        for message in email_messages:
            try:
                await aiosmtplib.send(
                    message.as_python_email(),
                    hostname=settings.email_host,
                    port=settings.email_port,
                    username=settings.email_host_user,
                    password=settings.email_host_password,
                    start_tls=settings.email_use_tls,
                    use_tls=settings.email_use_ssl,
                    timeout=settings.email_timeout,
                    recipients=message.all_recipients,
                )
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent


def get_email_backend(
    backend: Optional[str] = None,
    *,
    fail_silently: bool = False,
) -> BaseEmailBackend:
    """Return a configured email backend instance."""
    backend_name = backend or getattr(_get_settings(), "email_backend", "console")

    if backend_name in {"console", "aksara.core.mail.ConsoleBackend"}:
        return ConsoleBackend(fail_silently=fail_silently)
    if backend_name in {"locmem", "memory", "aksara.core.mail.LocMemBackend"}:
        return LocMemBackend(fail_silently=fail_silently)
    if backend_name in {"smtp", "aksara.core.mail.SMTPBackend"}:
        return SMTPBackend(fail_silently=fail_silently)

    if isinstance(backend_name, str) and "." in backend_name:
        module_name, class_name = backend_name.rsplit(".", 1)
        module = importlib.import_module(module_name)
        backend_class = getattr(module, class_name)
        return backend_class(fail_silently=fail_silently)

    raise ImproperlyConfigured(f"Unsupported email backend: {backend_name}")


async def send_mail(
    subject: str,
    message: str,
    from_email: Optional[str],
    recipient_list: list[str],
    *,
    html_message: Optional[str] = None,
    backend: Optional[str] = None,
    fail_silently: bool = False,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    reply_to: Optional[list[str]] = None,
    headers: Optional[dict[str, str]] = None,
) -> int:
    """Send a single email message using the configured backend."""
    email_message = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=list(recipient_list),
        cc=list(cc or []),
        bcc=list(bcc or []),
        reply_to=list(reply_to or []),
        headers=dict(headers or {}),
        html_body=html_message,
    )
    connection = get_email_backend(backend, fail_silently=fail_silently)
    return await connection.send_messages([email_message])


async def send_mass_mail(
    datatuple: Iterable[tuple[str, str, Optional[str], list[str]]],
    *,
    backend: Optional[str] = None,
    fail_silently: bool = False,
) -> int:
    """Send multiple plain-text email messages in one backend call."""
    messages = [
        EmailMessage(subject=subject, body=body, from_email=from_email, to=list(recipients))
        for subject, body, from_email, recipients in datatuple
    ]
    connection = get_email_backend(backend, fail_silently=fail_silently)
    return await connection.send_messages(messages)


def reset_outbox() -> None:
    """Clear the in-memory test outbox."""
    outbox.clear()


__all__ = [
    "EmailMessage",
    "BaseEmailBackend",
    "ConsoleBackend",
    "LocMemBackend",
    "SMTPBackend",
    "outbox",
    "reset_outbox",
    "get_email_backend",
    "send_mail",
    "send_mass_mail",
]