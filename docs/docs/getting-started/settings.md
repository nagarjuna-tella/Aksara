# Configure your application

Use deployment environment variables for database credentials and other
per-environment values. Use `configure()` for deliberate Python overrides and
application registration. The [settings reference](../reference/settings-reference.md)
is the authoritative list of defaults, environment mappings and precedence.

## Load configuration before the app

Keep configuration in the generated settings module and import it before
constructing your application. Do not introduce an `AKSARA = {...}` dictionary
or a settings subclass with uppercase class attributes: those do not configure
the global `aksara.conf.settings` object.

```python
from aksara import Aksara, configure, settings

configure(installed_apps=["aksara.contrib.auth", "aksara.contrib.admin", "app"])

if not settings.database_url:
    raise RuntimeError("Set AKSARA_DATABASE_URL or DATABASE_URL before startup")

app = Aksara(
    database_url=settings.database_url,
    min_pool_size=settings.pool_min_size,
    max_pool_size=settings.pool_max_size,
    debug=settings.debug,
)
```

This is the settings-to-constructor handoff, not a complete application. Keep
the generated routes, lifespan and other project wiring from the
[first-project guide](first-project.md). A database-backed Aksara lifespan starts
ordinary background tasks when `tasks_enabled` is true, its default. Durable
Operations require separate explicit registration and execution.

## Environment and overrides

Set `AKSARA_DATABASE_URL` or the supported alias `DATABASE_URL` before importing
the app; the former wins if both are nonempty. Keep credentials out of version
control. When dotenv support is installed, Aksara searches upward from the
working directory for `.env`; existing process environment wins over that file.

```dotenv
AKSARA_DEBUG=false
AKSARA_LOG_LEVEL=INFO
AKSARA_POOL_MIN_SIZE=5
AKSARA_POOL_MAX_SIZE=20
AKSARA_MCP_ENABLED=false
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
```

Keyword overrides such as `configure(log_level="DEBUG")` win over values already
loaded into settings. Constructing a `Settings(...)` object separately invokes
its environment loader, so do not assume its constructor arguments have that
same priority. See [precedence](../reference/settings-reference.md#precedence).

Changing the environment after import does not automatically reload settings.
A settings field is also not automatically forwarded to every `Aksara(...)`
constructor argument. Use the explicit handoff above and avoid maintaining
competing environment parsers in several modules.

## Choose the next configuration task

- [Authentication](../api/authentication.md): verify credentials and establish identity.
- [Tenant isolation](../security/multi-tenancy.md): bind trusted tenant identity and RLS.
- [Background tasks](../advanced/background-tasks.md): worker and retry settings.
- [Durable Operations](../advanced/durable-operations.md): service/worker configuration.
- [Media and email](../advanced/media-and-email.md): optional storage and mail backends.
- [MCP](mcp.md): authenticated tool access, separately from experimental AI.
- [Production deployment](../tutorials/deployment.md): restricted roles and operating responsibilities.
