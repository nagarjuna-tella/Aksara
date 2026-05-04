"""
Internationalization and timezone helpers for Aksara.

Provides request-scoped locale and timezone helpers, gettext-backed lazy
translations, and datetime normalization for ORM fields and serializers.
"""

from __future__ import annotations

import gettext as gettext_module
import os
from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aksara.context_state import locale_var, timezone_var


def _get_settings():
    """Lazy import settings to avoid configuration cycles at import time."""
    from aksara.conf import settings

    return settings


_translation_cache: dict[tuple[str, str, tuple[str, ...]], gettext_module.NullTranslations] = {}


def clear_i18n_cache() -> None:
    """Clear cached translation catalogs."""
    _translation_cache.clear()


def _normalize_locale(locale: Optional[str]) -> Optional[str]:
    """Normalize locale identifiers to a hyphenated lowercase form."""
    if locale is None:
        return None
    normalized = locale.strip().replace("_", "-")
    return normalized or None


def _split_list_env(value: str) -> list[str]:
    """Split comma or path-separated env values into a normalized list."""
    raw_parts = value.replace(os.pathsep, ",").split(",")
    return [part.strip() for part in raw_parts if part.strip()]


def get_locale() -> str:
    """Return the active locale for the current context."""
    settings = _get_settings()
    active_locale = _normalize_locale(locale_var.get())
    if active_locale:
        return active_locale
    return _normalize_locale(getattr(settings, "default_locale", "en")) or "en"


def activate_locale(locale: Optional[str]) -> Any:
    """Activate a locale for the current async context."""
    return locale_var.set(_normalize_locale(locale))


def reset_locale(token: Any) -> None:
    """Reset the locale context variable using a previously returned token."""
    locale_var.reset(token)


def parse_accept_language(
    header_value: Optional[str],
    *,
    supported_locales: Optional[Sequence[str]] = None,
    default_locale: Optional[str] = None,
) -> str:
    """Resolve the best locale from an Accept-Language header."""
    settings = _get_settings()
    configured_locales = supported_locales or getattr(settings, "supported_locales", ["en"])
    normalized_supported = {
        (_normalize_locale(locale) or "en"): locale
        for locale in configured_locales
    }
    fallback_locale = _normalize_locale(default_locale) or _normalize_locale(
        getattr(settings, "default_locale", None)
    ) or next(iter(normalized_supported.keys()), "en")

    if not header_value:
        return normalized_supported.get(fallback_locale, fallback_locale)

    candidates: list[tuple[float, str]] = []
    for raw_part in header_value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        locale_name = part
        quality = 1.0
        if ";" in part:
            locale_name, _, params = part.partition(";")
            locale_name = locale_name.strip()
            for param in params.split(";"):
                param = param.strip()
                if param.startswith("q="):
                    try:
                        quality = float(param[2:])
                    except ValueError:
                        quality = 0.0
        normalized_name = _normalize_locale(locale_name)
        if normalized_name:
            candidates.append((quality, normalized_name))

    for _, candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
        if candidate in normalized_supported:
            return normalized_supported[candidate]
        primary = candidate.split("-", 1)[0]
        if primary in normalized_supported:
            return normalized_supported[primary]

    return normalized_supported.get(fallback_locale, fallback_locale)


def get_timezone_name() -> str:
    """Return the active timezone name for the current context."""
    settings = _get_settings()
    active_timezone = timezone_var.get()
    if active_timezone:
        return active_timezone
    return getattr(settings, "time_zone", "UTC") or "UTC"


def get_timezone() -> ZoneInfo:
    """Return the active ZoneInfo object for the current context."""
    timezone_name = get_timezone_name()
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def activate_timezone(timezone_name: Optional[str]) -> Any:
    """Activate a timezone for the current async context."""
    normalized_name = timezone_name or None
    return timezone_var.set(normalized_name)


def reset_timezone(token: Any) -> None:
    """Reset the timezone context variable using a previously returned token."""
    timezone_var.reset(token)


def _get_locale_paths() -> tuple[str, ...]:
    """Return configured locale search paths."""
    settings = _get_settings()
    raw_paths = getattr(settings, "locale_paths", None) or ["locale"]
    return tuple(str(path) for path in raw_paths)


def _load_translation(locale: str, domain: str) -> gettext_module.NullTranslations:
    """Load or cache a gettext translation for the active locale."""
    cache_key = (locale, domain, _get_locale_paths())
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    translation: gettext_module.NullTranslations = gettext_module.NullTranslations()
    for localedir in cache_key[2]:
        try:
            translation = gettext_module.translation(
                domain,
                localedir=localedir,
                languages=[locale],
                fallback=True,
            )
        except Exception:
            translation = gettext_module.NullTranslations()

        if not isinstance(translation, gettext_module.NullTranslations) or getattr(translation, "_catalog", None):
            break

    _translation_cache[cache_key] = translation
    return translation


def translate(message: str, *, locale: Optional[str] = None, domain: str = "messages") -> str:
    """Translate a message for the current or provided locale."""
    active_locale = _normalize_locale(locale) or get_locale()
    return _load_translation(active_locale, domain).gettext(message)


class LazyString:
    """Lazy gettext-backed string resolved at serialization or string coercion."""

    def __init__(
        self,
        message: str,
        *,
        domain: str = "messages",
        locale: Optional[str] = None,
        format_args: tuple[Any, ...] = (),
        format_kwargs: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.domain = domain
        self.locale = _normalize_locale(locale)
        self.format_args = format_args
        self.format_kwargs = format_kwargs or {}

    def __str__(self) -> str:
        translated = translate(self.message, locale=self.locale, domain=self.domain)
        if self.format_args or self.format_kwargs:
            return translated.format(*self.format_args, **self.format_kwargs)
        return translated

    def __repr__(self) -> str:
        return f"LazyString({self.message!r})"

    def format(self, *args: Any, **kwargs: Any) -> "LazyString":
        """Return a formatted lazy string without forcing translation."""
        return LazyString(
            self.message,
            domain=self.domain,
            locale=self.locale,
            format_args=args,
            format_kwargs=kwargs,
        )


def _(message: str, *args: Any, **kwargs: Any) -> LazyString:
    """Return a lazy translation wrapper for a message."""
    return LazyString(message, format_args=args, format_kwargs=kwargs)


def normalize_datetime_for_storage(value: Any) -> Any:
    """Normalize datetimes to UTC before database persistence when USE_TZ is enabled."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        return value

    settings = _get_settings()
    if not getattr(settings, "use_tz", True):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=get_timezone())

    return value.astimezone(timezone.utc)


def normalize_datetime_from_storage(value: Any) -> Any:
    """Attach UTC tzinfo to persisted datetimes when USE_TZ is enabled."""
    if value is None:
        return None
    parsed_from_string = isinstance(value, str)
    if parsed_from_string:
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        return value

    settings = _get_settings()
    if not getattr(settings, "use_tz", True):
        return value

    if value.tzinfo is None:
        if parsed_from_string:
            return value.replace(tzinfo=timezone.utc)
        return value
    return value.astimezone(timezone.utc)


def localtime(value: datetime, *, timezone_name: Optional[str] = None) -> datetime:
    """Convert a datetime to the active request timezone for serialization."""
    normalized = normalize_datetime_from_storage(value)
    if not isinstance(normalized, datetime):
        raise TypeError("localtime() expects a datetime value")

    settings = _get_settings()
    if not getattr(settings, "use_tz", True):
        return normalized

    if timezone_name:
        try:
            target_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            target_timezone = ZoneInfo("UTC")
    else:
        target_timezone = get_timezone()

    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(target_timezone)


def serialize_value(value: Any) -> Any:
    """Resolve lazy strings and localize datetimes during serialization."""
    if isinstance(value, LazyString):
        return str(value)
    if isinstance(value, datetime):
        return localtime(value)
    return value


__all__ = [
    "LazyString",
    "_",
    "activate_locale",
    "activate_timezone",
    "clear_i18n_cache",
    "get_locale",
    "get_timezone",
    "get_timezone_name",
    "localtime",
    "normalize_datetime_for_storage",
    "normalize_datetime_from_storage",
    "parse_accept_language",
    "reset_locale",
    "reset_timezone",
    "serialize_value",
    "translate",
]