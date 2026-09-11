# Internationalization and Timezones

Phase 4 starts with request-scoped locale and timezone context so responses can
stay user-aware while storage remains normalized.

---

## Locale Resolution

Use `LocaleMiddleware` to resolve the active locale from `Accept-Language` and
store it in request state and a context variable.

```python
from aksara import Aksara
from aksara.middleware import LocaleMiddleware

app = Aksara(
    database_url="postgresql://localhost/myapp",
    middlewares=[
        (LocaleMiddleware, {
            "supported_locales": ["en", "fr", "de"],
            "default_locale": "en",
        }),
    ],
)
```

Inside request handlers you can access the resolved locale from either
`request.state.locale` or `aksara.middleware.locale_var`.

---

## Lazy Translations

`_()` returns a lazy string wrapper that resolves when coerced to `str()` or
when it flows through Aksara's serializer/model export helpers.

```python
from aksara import _

headline = _("Welcome back, {name}", name="Ada")
str(headline)  # "Welcome back, Ada"
```

Translation lookup uses Python's built-in `gettext` catalogs from
`Settings.locale_paths`.

---

## Timezone Resolution

Use `TimezoneMiddleware` to resolve a request timezone from `X-Timezone`.

```python
from aksara.middleware import TimezoneMiddleware

app = Aksara(
    database_url="postgresql://localhost/myapp",
    middlewares=[
        (TimezoneMiddleware, {"default_timezone": "UTC"}),
    ],
)
```

The resolved timezone is available through `request.state.timezone` and
`aksara.middleware.timezone_var`.

---

## Datetime Storage and Serialization

When `use_tz=True`, `DateTime` fields behave as follows:

- naive datetimes are interpreted in the active request timezone (or
  `TIME_ZONE` when no request timezone is active)
- persisted values are normalized to UTC
- model and API serialization convert datetimes into the active request
  timezone

```python
from datetime import datetime
from aksara import Model, fields


class Event(Model):
    starts_at = fields.DateTime()


event = Event(starts_at=datetime(2026, 1, 15, 9, 30, 0))
await event.save()
```

If the active request timezone is `America/New_York`, the naive input above is
treated as local New York time and stored in UTC.

---

## Settings

```python
from aksara.conf import configure

configure(
    supported_locales=["en", "fr", "de"],
    default_locale="en",
    locale_paths=["locale"],
    use_tz=True,
    time_zone="UTC",
)
```

See [Settings Reference](../reference/settings-reference.md) for the full list
of related settings.