# Settings reference

Aksara has one runtime configuration object: the global
`aksara.conf.settings`, an instance of the `Settings` dataclass.

## Recommended path

Use environment variables for deploy-time values and call `configure()` once,
before constructing `Aksara`, for explicit Python overrides:

```python
from aksara import Aksara, configure, settings

configure(
    installed_apps=["aksara.contrib.auth", "aksara.contrib.admin", "app"],
)
app = Aksara(
    database_url=settings.database_url,
    min_pool_size=settings.pool_min_size,
    max_pool_size=settings.pool_max_size,
    debug=settings.debug,
)
```

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/myapp
AKSARA_DEBUG=false
AKSARA_LOG_LEVEL=INFO
```

Do not create an `AKSARA = {...}` dictionary or a subclass with class-level
values. Neither pattern configures the global dataclass instance.

## Precedence

From highest to lowest:

1. explicit keyword values passed to `configure(...)`;
2. `AKSARA_*` environment variables loaded when `Settings` is created;
3. documented compatibility environment aliases;
4. dataclass defaults.

For the database, `AKSARA_DATABASE_URL` takes precedence over `DATABASE_URL`.
The scaffold emits `DATABASE_URL`; both settings and database CLI commands honor
the same ordering.

`Settings(...)` is different from `configure(...)`: constructing a dataclass
runs its environment loader. Some environment values, including pool size and
log level, can replace constructor arguments. Passing that already constructed
object to `configure()` copies its effective values; it does not recover the
original arguments. Use keyword `configure(pool_max_size=10)` when an explicit
Python override must win.

Environment is read when the global settings object is created, not on each
attribute access. When `python-dotenv` is available, import-time loading searches
from the current directory upward for `.env`; existing process environment
values take precedence. Start from the intended project directory and set
production environment before importing the app. Changing `os.environ` after
import does not automatically refresh the object.

`Aksara(...)` constructor arguments are a separate configuration surface. In
particular, pass the effective database URL, pool sizes and debug flag as shown
above. Setting `settings.database_url` alone does not start the application's
database lifespan. Keep one explicit handoff from settings to the constructor.
Application settings modules may implement their own precedence; avoid reading
`DATABASE_URL` directly when you intend the framework's two-variable ordering.

Calling `configure()` mutates the existing global object in place so modules
that already imported `settings` observe the updated values.

## Configuration truth map

| Surface | Role | Status |
| --- | --- | --- |
| `aksara.conf.Settings` fields | Canonical typed configuration | current |
| `aksara.conf.settings` | Single global runtime object | current |
| `configure(...)` | Explicit programmatic override | current |
| `AKSARA_*` variables | Deployment configuration | current |
| `DATABASE_URL` | Common database alias used by the scaffold | supported compatibility alias |
| uppercase properties such as `settings.DATABASE_URL` | Read compatibility | compatibility-only; use lowercase fields in new Python code |
| `AKSARA = {...}` dictionaries | Historical documentation pattern | unsupported |
| `Settings.ai_default_provider`, `ai_providers`, `ai_secret_hints` | Old profile metadata configuration | deprecated compatibility fields |
| AI Hub files and provider variables | Provider-backed AI configuration | current experimental provider path |

## Core settings

| Python field | Environment variable | Default |
| --- | --- | --- |
| `database_url` | `AKSARA_DATABASE_URL`, then `DATABASE_URL` | `None` |
| `pool_min_size` | `AKSARA_POOL_MIN_SIZE` | `5` |
| `pool_max_size` | `AKSARA_POOL_SIZE` or `AKSARA_POOL_MAX_SIZE` | `20` |
| `debug` | `AKSARA_DEBUG` | `False` |
| `log_level` | `AKSARA_LOG_LEVEL` | `INFO` |
| `log_requests` | disabled by `AKSARA_LOG_REQUESTS_DISABLED` | `True` |
| `log_json` | `AKSARA_LOG_JSON` | `False` |
| `app_title` | `AKSARA_APP_TITLE` | `None` |
| `app_version` | `AKSARA_APP_VERSION` | `None` |
| `migrations_dir` | `AKSARA_MIGRATIONS_DIR` | `migrations` |
| `installed_apps` | explicit `configure()` value | `["aksara.contrib.auth", "aksara.contrib.admin", "app"]` |

Aksara supports PostgreSQL. A database URL is required for migrations and
normal ORM use.

## Authentication and tenant posture

Authentication middleware verifies credentials and installs server-owned user
and Principal state. Settings do not supply an identity provider or establish
that a caller belongs to a tenant. Follow [authentication](../api/authentication.md)
and [tenant isolation](../security/multi-tenancy.md).

| Python field | Environment variable | Default |
| --- | --- | --- |
| `cookie_secure` | `AKSARA_COOKIE_SECURE` | `True` |
| `admin_csrf_enabled` | `AKSARA_ADMIN_CSRF_ENABLED` | `True` |
| `admin_rate_limit_enabled` | `AKSARA_ADMIN_RATE_LIMIT_ENABLED` | `True` |
| `admin_rate_limit_requests` | `AKSARA_ADMIN_RATE_LIMIT_REQUESTS` | `20` |
| `admin_rate_limit_window_seconds` | `AKSARA_ADMIN_RATE_LIMIT_WINDOW_SECONDS` | `60` |

These settings control their corresponding application surfaces; they are not
proof of a secure deployment. Keep secure cookies, CSRF protection and rate
limits enabled for production. The [production guide](../tutorials/deployment.md)
connects the settings to actual roles, middleware and diagnostics.

`AKSARA_ENV`, `AKSARA_SECRET_KEY` (fallback `SECRET_KEY`),
`AKSARA_MULTI_TENANT`, `AKSARA_RLS_ENABLED` and
`AKSARA_SECURITY_MATRIX_PATH` are read by security/diagnostic components. They
are **not** fields of `Settings`. The tenant/RLS flags declare posture; they do
not create PostgreSQL policies. The secret-key check does not configure an
arbitrary application's token verifier. Provision those components explicitly.

## Stable MCP settings

| Python field | Environment variable | Default |
| --- | --- | --- |
| `mcp_enabled` | `AKSARA_MCP_ENABLED` | `False` |
| `mcp_path` | `AKSARA_MCP_PATH` | `/mcp` |
| `mcp_transport_host` | `AKSARA_MCP_TRANSPORT_HOST` | `127.0.0.1` |
| `mcp_allowed_hosts` | `AKSARA_MCP_ALLOWED_HOSTS` | `["127.0.0.1:*", "localhost:*", "[::1]:*", "testserver:*", "testserver"]` |
| `mcp_allowed_origins` | `AKSARA_MCP_ALLOWED_ORIGINS` | `["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*", "http://testserver:*", "http://testserver"]` |
| `mcp_max_request_body_size` | `AKSARA_MCP_MAX_REQUEST_BODY_SIZE` | `1048576` |
| `mcp_tool_timeout_seconds` | `AKSARA_MCP_TOOL_TIMEOUT_SECONDS` | `30` |
| `mcp_replay_ttl_seconds` | `AKSARA_MCP_REPLAY_TTL_SECONDS` | `300` |
| `mcp_require_scoped_tokens` | `AKSARA_MCP_REQUIRE_SCOPED_TOKENS` | `True` |
| `mcp_token_audience` | `AKSARA_MCP_TOKEN_AUDIENCE` | `None` |
| `mcp_approval_secret` | `AKSARA_MCP_APPROVAL_SECRET` | `None` |

`/mcp/` is the protocol endpoint. `/ai/tools/mcp` is an HTTP inspection catalog.
Authentication middleware must resolve credentials to a server-owned
`Principal`; these settings do not verify tokens by themselves.

List-valued environment settings use a platform-independent grammar. Supply a
comma-separated list for ordinary values, or a JSON string array when a value
itself needs comma-safe representation. Colons and semicolons are data, so URI
schemes, ports, and IPv6 addresses remain intact:

```bash
export AKSARA_MCP_ALLOWED_ORIGINS='https://app.example.com,https://admin.example.com:8443'
export AKSARA_MCP_ALLOWED_HOSTS='["api.example.com:443", "[2001:db8::1]:8443"]'
```

Explicit Python lists remain supported:

```python
from aksara import configure

configure(
    mcp_allowed_hosts=["api.example.com"],
    mcp_allowed_origins=["https://app.example.com"],
)
```

Replace these domains with your deployment's allowed hosts and origins. These
forms preserve the supplied strings; they do not remove the need for
authentication. Empty comma-separated items, malformed JSON arrays, and JSON
array entries that are not non-empty strings are rejected.

## Background task settings

| Python field | Environment variable | Default |
| --- | --- | --- |
| `tasks_enabled` | `AKSARA_TASKS_ENABLED` | `True` |
| `task_poll_interval_seconds` | `AKSARA_TASK_POLL_INTERVAL_SECONDS` | `1.0` |
| `task_retry_delay_seconds` | `AKSARA_TASK_RETRY_DELAY_SECONDS` | `5.0` |
| `task_max_attempts` | `AKSARA_TASK_MAX_ATTEMPTS` | `3` |
| `task_concurrency` | `AKSARA_TASK_CONCURRENCY` | `1` |
| `task_stale_lock_timeout_seconds` | `AKSARA_TASK_STALE_LOCK_TIMEOUT_SECONDS` | `300` |
| `task_lock_recovery_interval_seconds` | `AKSARA_TASK_LOCK_RECOVERY_INTERVAL_SECONDS` | `60` |
| `task_retry_backoff_base` | `AKSARA_TASK_RETRY_BACKOFF_BASE` | `2.0` |
| `task_retry_max_delay_seconds` | `AKSARA_TASK_RETRY_MAX_DELAY_SECONDS` | `3600` |
| `task_result_ttl_seconds` | `AKSARA_TASK_RESULT_TTL_SECONDS` | `None` |
| `task_cleanup_interval_seconds` | `AKSARA_TASK_CLEANUP_INTERVAL_SECONDS` | `3600.0` |
| `task_cron_check_interval_seconds` | `AKSARA_TASK_CRON_CHECK_INTERVAL_SECONDS` | `30.0` |

`task_stale_lock_timeout_seconds` is the database-time lease duration for an
ordinary running task. Its worker renews the lease while the callable remains
active; recovery makes an expired claim eligible for another worker.

A database-backed `Aksara` lifespan starts its built-in `TaskWorker` when
`tasks_enabled=True`. This is not the durable Operation worker. Custom worker
entry points and task registrations still need application configuration. See
[Background Tasks](../advanced/background-tasks.md) for scheduling, retry and
identity semantics. Environment names ending in `_SECONDS` include that suffix;
the shortened names without it are not supported aliases.

## Durable Operations configuration

Durability is opt-in through action/resolver registries, a service and a worker.
There is no global `durable_enabled` setting or automatic tenant worker fleet.
Configure `DurableOperationService` consistently in web and worker processes.
It requires a database, `application_namespace`, `actions` and `resolvers`.

| Service constructor argument | Default | Meaning |
| --- | --- | --- |
| `default_max_attempts` | `3` | Default physical attempt limit |
| `default_lease_seconds` | `30.0` | Temporary claim ownership |
| `retention_seconds` | `604800` | Operation retention window, seven days |
| `idempotency_seconds` | `86400` | Idempotency window, one day |
| `result_retention_seconds` | `86400` | Result retention window, one day |
| `error_retention_seconds` | `604800` | Error retention window, seven days |

These are Python constructor parameters, not automatically loaded
`AKSARA_DURABLE_*` environment variables. An application may explicitly map its
own deployment variables to them. Positive limits are required. The worker's
`poll_interval` defaults to `1.0` seconds; an omitted worker `lease_seconds`
uses the service's default. Retention values do not schedule pruning or export:
the operator must run those activities. See [Durable Operations](../advanced/durable-operations.md)
for admission, approval, deadlines, cancellation and external recovery.

## Media, email and locale

**Optional / evolving integrations.** Storage and mail require their own
credentials and delivery/access policy. A configured filesystem root is not
an authorization policy for downloads. The default email backend writes to the
console; it does not send mail. See [media and email](../advanced/media-and-email.md).

| Python field | Environment variable | Default |
| --- | --- | --- |
| `media_root` | `AKSARA_MEDIA_ROOT` | `"media"` |
| `media_url` | `AKSARA_MEDIA_URL` | `"/media/"` |
| `media_storage` | `AKSARA_MEDIA_STORAGE` | `"filesystem"` |
| `media_s3_bucket` | `AKSARA_MEDIA_S3_BUCKET` | `None` |
| `media_s3_region` | `AKSARA_MEDIA_S3_REGION` | `None` |
| `media_s3_endpoint_url` | `AKSARA_MEDIA_S3_ENDPOINT_URL` | `None` |
| `media_s3_access_key` | `AKSARA_MEDIA_S3_ACCESS_KEY` | `None` |
| `media_s3_secret_key` | `AKSARA_MEDIA_S3_SECRET_KEY` | `None` |
| `media_public_base_url` | `AKSARA_MEDIA_PUBLIC_BASE_URL` | `None` |
| `email_backend` | `AKSARA_EMAIL_BACKEND` | `"console"` |
| `default_from_email` | `AKSARA_DEFAULT_FROM_EMAIL` | `"webmaster@localhost"` |
| `email_host` | `AKSARA_EMAIL_HOST` | `"localhost"` |
| `email_port` | `AKSARA_EMAIL_PORT` | `25` |
| `email_host_user` | `AKSARA_EMAIL_HOST_USER` | `None` |
| `email_host_password` | `AKSARA_EMAIL_HOST_PASSWORD` | `None` |
| `email_use_tls` | `AKSARA_EMAIL_USE_TLS` | `False` |
| `email_use_ssl` | `AKSARA_EMAIL_USE_SSL` | `False` |
| `email_timeout` | `AKSARA_EMAIL_TIMEOUT` | `10.0` |
| `supported_locales` | `AKSARA_SUPPORTED_LOCALES` | `["en"]` |
| `default_locale` | `AKSARA_DEFAULT_LOCALE` | `"en"` |
| `locale_paths` | `AKSARA_LOCALE_PATHS` | `["locale"]` |
| `use_tz` | `AKSARA_USE_TZ` | `True` |
| `time_zone` | `AKSARA_TIME_ZONE` | `"UTC"` |

## AI, Studio and query tracing

**Experimental AI/Studio; optional query tracing.** MCP and provider-backed AI
are independent opt-ins. Neither enabling MCP nor using durable Operations
requires enabling a planner or Studio.

| Python field | Environment variable | Default |
| --- | --- | --- |
| `ai_enabled` | `AKSARA_AI_ENABLED` | `False` |
| `enable_studio` | `AKSARA_ENABLE_STUDIO` | `False` |
| `studio_secret_token` | `AKSARA_STUDIO_SECRET_TOKEN` | `None` |
| `studio_expose_in_production` | `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION` | `False` |
| `studio_require_auth` | `AKSARA_STUDIO_REQUIRE_AUTH` | `True` |
| `studio_auth_token` | `AKSARA_STUDIO_AUTH_TOKEN` | `None` |
| `db_trace_enabled` | `AKSARA_DB_TRACE_ENABLED` | `False` |
| `db_trace_slow_threshold_ms` | `AKSARA_DB_TRACE_SLOW_THRESHOLD_MS` | `100.0` |
| `db_trace_max_queries` | `AKSARA_DB_TRACE_MAX_QUERIES` | `500` |

`AKSARA_STUDIO_DISABLED=true` overrides environment-enabled Studio. Studio
requires a secret when enabled and has separate authentication/exposure rules;
see [Studio configuration](../studio/configuration.md). Provider configuration
belongs to [AI Providers](../ai-mode/providers.md), including the experimental AI
Hub path. Old profile fields do not configure the current provider runtime.

Not every dataclass field has an environment variable. For example, set
`installed_apps` through `configure()`. Use only documented mappings; inventing
an uppercase name from a Python field does not configure it. Never log the
whole settings object because it may contain database or provider credentials.

## Doctor

`aksara doctor launch-check` inspects the active project, database, migrations,
Studio, MCP/tool catalog, AI provider state, and examples. The stricter release
profile is:

```bash
aksara doctor production-check --release
```

Doctor reads the same effective environment and settings surfaces. It does not
turn an unsupported `AKSARA` dictionary into runtime configuration.
