"""
Request-scoped context variables shared across middleware and framework helpers.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar(
    "aksara_request_id",
    default=None,
)

tenant_id_var: ContextVar[Optional[str]] = ContextVar(
    "aksara_tenant_id",
    default=None,
)

user_id_var: ContextVar[Optional[str]] = ContextVar(
    "aksara_user_id",
    default=None,
)

locale_var: ContextVar[Optional[str]] = ContextVar(
    "aksara_locale",
    default=None,
)

timezone_var: ContextVar[Optional[str]] = ContextVar(
    "aksara_timezone",
    default=None,
)


__all__ = [
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
    "locale_var",
    "timezone_var",
]