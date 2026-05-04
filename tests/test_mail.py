"""
Tests for async email backends.
"""

from __future__ import annotations

import io
import sys

import pytest

from aksara.conf import settings
from aksara.core.mail import (
    ConsoleBackend,
    EmailMessage,
    SMTPBackend,
    get_email_backend,
    outbox,
    reset_outbox,
    send_mail,
    send_mass_mail,
)


class TestMailBackends:
    """Focused email backend tests for Phase 3."""

    @pytest.fixture(autouse=True)
    def clear_outbox(self):
        reset_outbox()
        yield
        reset_outbox()

    @pytest.mark.asyncio
    async def test_locmem_backend_collects_messages(self, monkeypatch):
        monkeypatch.setattr(settings, "email_backend", "locmem", raising=False)

        sent = await send_mail(
            "Welcome",
            "Hello from Aksara",
            None,
            ["user@example.com"],
        )

        assert sent == 1
        assert len(outbox) == 1
        assert outbox[0].subject == "Welcome"
        assert outbox[0].to == ["user@example.com"]

    @pytest.mark.asyncio
    async def test_console_backend_writes_to_stdout(self, monkeypatch):
        stream = io.StringIO()
        monkeypatch.setattr(sys, "stdout", stream)

        backend = ConsoleBackend()
        sent = await backend.send_messages([
            EmailMessage(subject="Status", body="ok", to=["ops@example.com"]),
        ])

        assert sent == 1
        content = stream.getvalue()
        assert "Subject: Status" in content
        assert "ops@example.com" in content

    @pytest.mark.asyncio
    async def test_send_mass_mail_uses_configured_backend(self, monkeypatch):
        monkeypatch.setattr(settings, "email_backend", "locmem", raising=False)

        sent = await send_mass_mail([
            ("One", "Body one", None, ["one@example.com"]),
            ("Two", "Body two", None, ["two@example.com"]),
        ])

        assert sent == 2
        assert [message.subject for message in outbox] == ["One", "Two"]

    @pytest.mark.asyncio
    async def test_smtp_backend_uses_aiosmtplib(self, monkeypatch):
        calls = []

        class FakeAioSmtplib:
            @staticmethod
            async def send(message, **kwargs):
                calls.append((message, kwargs))
                return {}, "ok"

        monkeypatch.setitem(sys.modules, "aiosmtplib", FakeAioSmtplib)
        monkeypatch.setattr(settings, "email_host", "smtp.example.com", raising=False)
        monkeypatch.setattr(settings, "email_port", 2525, raising=False)
        monkeypatch.setattr(settings, "email_host_user", "mailer", raising=False)
        monkeypatch.setattr(settings, "email_host_password", "secret", raising=False)
        monkeypatch.setattr(settings, "email_use_tls", True, raising=False)
        monkeypatch.setattr(settings, "email_use_ssl", False, raising=False)
        monkeypatch.setattr(settings, "email_timeout", 5.0, raising=False)

        backend = SMTPBackend()
        sent = await backend.send_messages([
            EmailMessage(subject="Alert", body="Body", to=["to@example.com"]),
        ])

        assert sent == 1
        assert len(calls) == 1
        _, kwargs = calls[0]
        assert kwargs["hostname"] == "smtp.example.com"
        assert kwargs["port"] == 2525
        assert kwargs["start_tls"] is True

    def test_get_email_backend_supports_known_aliases(self, monkeypatch):
        monkeypatch.setattr(settings, "email_backend", "console", raising=False)
        backend = get_email_backend()
        assert isinstance(backend, ConsoleBackend)