# Settings reference

Aksara has one runtime configuration object: the global
`aksara.conf.settings`, an instance of the `Settings` dataclass.

## Recommended path

Use environment variables for deploy-time values and call `configure()` once,
before constructing `Aksara`, for explicit Python overrides:

```python
from aksara import Aksara, configure

configure(
    installed_apps=["aksara.contrib.auth", "aksara.contrib.admin", "app"],
)
app = Aksara()
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

1. explicit values passed to `configure(Settings(...))` or `configure(...)`;
2. `AKSARA_*` environment variables loaded when `Settings` is created;
3. documented compatibility environment aliases;
4. dataclass defaults.

For the database, `AKSARA_DATABASE_URL` takes precedence over `DATABASE_URL`.
The scaffold emits `DATABASE_URL`; both settings and database CLI commands honor
the same ordering.

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
| `installed_apps` | explicit `configure()` value | auth, admin, app |

Aksara supports PostgreSQL. A database URL is required for migrations and
normal ORM use.

## Stable MCP settings

| Python field | Environment variable | Default |
| --- | --- | --- |
| `mcp_enabled` | `AKSARA_MCP_ENABLED` | `False` |
| `mcp_path` | `AKSARA_MCP_PATH` | `/mcp` |
| `mcp_transport_host` | `AKSARA_MCP_TRANSPORT_HOST` | `127.0.0.1` |
| `mcp_allowed_hosts` | `AKSARA_MCP_ALLOWED_HOSTS` | local/test hosts |
| `mcp_allowed_origins` | `AKSARA_MCP_ALLOWED_ORIGINS` | local/test origins |
| `mcp_max_request_body_size` | `AKSARA_MCP_MAX_REQUEST_BODY_SIZE` | `1048576` |
| `mcp_tool_timeout_seconds` | `AKSARA_MCP_TOOL_TIMEOUT_SECONDS` | `30` |
| `mcp_replay_ttl_seconds` | `AKSARA_MCP_REPLAY_TTL_SECONDS` | `300` |
| `mcp_require_scoped_tokens` | `AKSARA_MCP_REQUIRE_SCOPED_TOKENS` | `True` |
| `mcp_token_audience` | `AKSARA_MCP_TOKEN_AUDIENCE` | `None` |
| `mcp_approval_secret` | `AKSARA_MCP_APPROVAL_SECRET` | `None` |

`/mcp/` is the protocol endpoint. `/ai/tools/mcp` is an HTTP inspection catalog.
Authentication middleware must resolve credentials to a server-owned
`Principal`; these settings do not verify tokens by themselves.

## Background task settings

| Python field | Environment variable | Default |
| --- | --- | --- |
| `tasks_enabled` | `AKSARA_TASKS_ENABLED` | `True` |
| `task_poll_interval_seconds` | `AKSARA_TASK_POLL_INTERVAL` | `1.0` |
| `task_retry_delay_seconds` | `AKSARA_TASK_RETRY_DELAY` | `5.0` |
| `task_max_attempts` | `AKSARA_TASK_MAX_ATTEMPTS` | `3` |
| `task_concurrency` | `AKSARA_TASK_CONCURRENCY` | `1` |
| `task_stale_lock_timeout_seconds` | `AKSARA_TASK_STALE_LOCK_TIMEOUT` | `300` |
| `task_lock_recovery_interval_seconds` | `AKSARA_TASK_LOCK_RECOVERY_INTERVAL` | `60` |
| `task_retry_backoff_base` | `AKSARA_TASK_RETRY_BACKOFF_BASE` | `2.0` |
| `task_retry_max_delay_seconds` | `AKSARA_TASK_RETRY_MAX_DELAY` | `3600` |
| `task_result_ttl_seconds` | `AKSARA_TASK_RESULT_TTL_SECONDS` | `None` |

See [Background Tasks](../advanced/background-tasks.md) for retry and identity
semantics.

## Optional and evolving features

Media, email, locale, timezone, Studio, query tracing, and semantic-search
settings are typed fields on `Settings`. Inspect the installed
`aksara.conf.Settings` dataclass for the exact list supported by your package.
Use lowercase field names with `configure()` and the documented `AKSARA_*`
environment names.

Provider-backed AI and Studio are opt-in:

```dotenv
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
```

Studio requires additional authentication and production exposure settings.
Provider configuration belongs to [AI Providers](../ai-mode/providers.md), and
its quality/selection contract remains experimental.

## Doctor

`aksara doctor launch-check` inspects the active project, database, migrations,
Studio, MCP/tool catalog, AI provider state, and examples. The stricter release
profile is:

```bash
aksara doctor production-check --release
```

Doctor reads the same effective environment and settings surfaces. It does not
turn an unsupported `AKSARA` dictionary into runtime configuration.
