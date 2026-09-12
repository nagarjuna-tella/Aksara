# Locale and timezone context

Locale selects translated text; timezone selects how an instant is displayed
and how a naive datetime is interpreted. Neither establishes identity or tenant
membership. Install the two middleware classes explicitly when the application
needs request preferences.

## A complete request example

Save this as `locale_app.py`. It needs no database or translation catalog; its
message therefore falls back to the English source string.

```python title="locale_app.py"
from datetime import datetime, timezone
from starlette.requests import Request
from aksara import Aksara, _
from aksara.conf import configure, settings
from aksara.i18n import localtime
from aksara.middleware import LocaleMiddleware, TimezoneMiddleware

configure(
    supported_locales=["en", "fr", "de"],
    default_locale="en",
    locale_paths=["locale"],
    use_tz=True,
    time_zone="UTC",
)

app = Aksara(
    database_url=None,
    auto_discover_views=False,
    middlewares=[
        (LocaleMiddleware, {
            "supported_locales": settings.supported_locales,
            "default_locale": settings.default_locale,
        }),
        (TimezoneMiddleware, {"default_timezone": settings.time_zone}),
    ],
)


@app.get("/preferences")
async def preferences(request: Request):
    instant = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
    return {
        "locale": request.state.locale,
        "timezone": request.state.timezone,
        "message": str(_("Welcome back, {name}", name="Ada")),
        "local_time": localtime(instant).isoformat(),
    }
```

Run it with `uvicorn locale_app:app` after installing Uvicorn in your environment.
A request to `/preferences` with `Accept-Language: fr-CA,fr;q=0.9,en;q=0.5`
and `X-Timezone: America/New_York` selects `fr` and returns
`2026-01-15T09:30:00-05:00`. Without headers it selects `en` and `UTC`.
This demonstrates presentation preferences, not authentication.

## Locale selection and catalogs

`LocaleMiddleware` reads `Accept-Language` by default. It selects from supported
locales, trying an exact locale and then its primary language (such as `fr` for
`fr-CA`); unmatched requests use the configured default. The `header_name`
argument can select an application-specific header. Use consistent locale names
in configuration and catalogs; do not treat this helper as a complete language
negotiation or validation API.

The result is available as `request.state.locale` and
`aksara.middleware.locale_var`. Middleware resets its context token after the
request; a later request without a header uses its own default. For explicit
non-request work, use `activate_locale()` and `reset_locale(token)` from
`aksara.i18n` with `try/finally`.

`_("message", name=value)` creates a lazy wrapper. Translation and `.format()`
substitution happen when it becomes a string, or through Aksara's supported
model/serializer export helpers. Plain arbitrary JSON encoders do not thereby
gain support for lazy wrappers. Missing format keys can still raise an error.

Lookup uses standard gettext `.mo` catalogs under `settings.locale_paths`, for
example `locale/fr/LC_MESSAGES/messages.mo` for the default `messages` domain.
The application supplies and compiles catalogs; selecting French does not
translate English automatically. Missing catalogs/messages fall back to the
source message. Loaded catalogs are cached in process memory; use
`aksara.i18n.clear_i18n_cache()` after changing catalogs in a running process.
`translate(message, locale=..., domain=...)` provides an explicit lookup.

## Timezone selection

`TimezoneMiddleware` reads `X-Timezone` by default and accepts IANA names through
Python's `ZoneInfo`. A missing header uses `default_timezone`; an unknown zone
name falls back to that default. Supply a valid default. The constructor default
is `UTC`, so the example explicitly passes `settings.time_zone` when it wants
configuration to control this middleware too.

The selected name is in `request.state.timezone` and
`aksara.middleware.timezone_var`. Outside request context, helpers use
`settings.time_zone`. Explicit work can use `activate_timezone()` and
`reset_timezone(token)` with `try/finally`. A request context is not a durable
record of a user's preference; store any needed scheduling/display preference
explicitly in application data.

## Datetimes and persistence

With `settings.use_tz=True`, `DateTime.to_db()` interprets naive datetime input
in the active timezone (or `settings.time_zone`) and normalizes it to UTC.
Aware input already identifies an instant. Model/serializer export helpers
localize datetime values for output; arbitrary application responses should
convert explicitly, as the route above does.

This standalone conversion example does not write a database row:

```python title="timezone_conversion.py"
from datetime import datetime, timezone
from aksara import fields
from aksara.conf import configure
from aksara.i18n import activate_timezone, localtime, reset_timezone

configure(use_tz=True, time_zone="UTC")
token = activate_timezone("America/New_York")
try:
    stored = fields.DateTime().to_db(datetime(2026, 1, 15, 9, 30))
    assert stored == datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
    assert localtime(stored).isoformat() == "2026-01-15T09:30:00-05:00"
finally:
    reset_timezone(token)
```

For model persistence, define and migrate the model, connect PostgreSQL, and
then save it through the [normal ORM path](../orm/models.md). `use_tz=False`
disables these helper conversions; it does not change a database column's type
or migrate existing values. Prefer explicit aware inputs for consequential
schedules. Assigning a zone to a naive time is not a business policy for
ambiguous or nonexistent local times around daylight-saving transitions.

See the [settings reference](../reference/settings-reference.md) for the exact
lowercase setting names, environment variables and precedence.
