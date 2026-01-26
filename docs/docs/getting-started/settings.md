# Settings

Configure your Vidyut application using the settings system.

---

## Overview

Vidyut provides a flexible configuration system that supports:

- **Environment variables** — For production deployments
- **Explicit configuration** — For development and testing
- **Sensible defaults** — Minimal setup required

---

## Configuration Methods

### Method 1: Environment Variables

The simplest approach for production:

```bash
# .env file
DATABASE_URL=postgresql://user:pass@localhost:5432/myapp
VIDYUT_DEBUG=false
VIDYUT_LOG_LEVEL=INFO
VIDYUT_POOL_MAX_SIZE=20
```

Vidyut automatically loads from environment variables prefixed with `VIDYUT_`.

### Method 2: Explicit Configuration

For programmatic control, use `configure()`:

```python
from vidyut import configure

configure(
    database_url="postgresql://localhost/myapp",
    debug=True,
    pool_min_size=5,
    pool_max_size=20,
    log_level="DEBUG",
    installed_apps=[
        "vidyut.contrib.auth",
        "vidyut.contrib.admin",
        "app",
    ],
)
```

### Method 3: Settings File

Create a `settings.py` file and import it early:

```python
# settings.py
import os
from vidyut import configure

configure(
    database_url=os.getenv("DATABASE_URL"),
    debug=os.getenv("VIDYUT_DEBUG", "false").lower() == "true",
    pool_min_size=int(os.getenv("VIDYUT_POOL_MIN_SIZE", "5")),
    pool_max_size=int(os.getenv("VIDYUT_POOL_MAX_SIZE", "20")),
)
```

```python
# main.py
import settings  # Load configuration first
from vidyut import Vidyut

app = Vidyut(title="My App")
```

---

## Available Settings

### Database Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `database_url` | `str` | `None` | PostgreSQL connection URL |
| `pool_min_size` | `int` | `5` | Minimum connections in pool |
| `pool_max_size` | `int` | `20` | Maximum connections in pool |

```python
configure(
    database_url="postgresql://user:pass@localhost:5432/myapp",
    pool_min_size=5,
    pool_max_size=20,
)
```

### Debug & Logging

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `debug` | `bool` | `False` | Enable debug mode |
| `log_level` | `str` | `"INFO"` | Logging level |
| `log_requests` | `bool` | `True` | Log HTTP requests |
| `log_json` | `bool` | `False` | Use JSON log format |

```python
configure(
    debug=True,
    log_level="DEBUG",
    log_requests=True,
    log_json=False,
)
```

!!! warning "Debug Mode in Production"
    Never enable `debug=True` in production. Debug mode exposes detailed error information and enables development features.

### Application Metadata

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `app_title` | `str` | `None` | Application title |
| `app_version` | `str` | `None` | Application version |

```python
configure(
    app_title="My Blog API",
    app_version="1.0.0",
)
```

### Migrations

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `migrations_dir` | `str` | `"migrations"` | Path to migrations directory |

```python
configure(
    migrations_dir="db/migrations",
)
```

### Installed Apps

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `installed_apps` | `list[str]` | See below | Apps to auto-load |
| `apps` | `list[str]` | `["app"]` | Legacy app list |

Default `installed_apps`:
```python
[
    "vidyut.contrib.auth",   # User authentication
    "vidyut.contrib.admin",  # Admin interface
    "app",                   # Default user app
]
```

### AI Features

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ai_enabled` | `bool` | `False` | Enable AI endpoints |
| `mcp_enabled` | `bool` | `False` | Enable MCP protocol |
| `ai_debug_enabled` | `bool` | `True` | Enable AI debug suggestions |

```python
configure(
    ai_enabled=True,
    mcp_enabled=True,
    ai_debug_enabled=True,
)
```

---

## Environment Variables Reference

All settings can be set via environment variables:

| Environment Variable | Setting | Example |
|---------------------|---------|---------|
| `DATABASE_URL` | `database_url` | `postgresql://...` |
| `VIDYUT_DATABASE_URL` | `database_url` (priority) | `postgresql://...` |
| `VIDYUT_DEBUG` | `debug` | `true`, `false` |
| `VIDYUT_LOG_LEVEL` | `log_level` | `DEBUG`, `INFO`, `WARNING` |
| `VIDYUT_LOG_REQUESTS_DISABLED` | `log_requests` | `true` to disable |
| `VIDYUT_LOG_JSON` | `log_json` | `true`, `false` |
| `VIDYUT_POOL_MIN_SIZE` | `pool_min_size` | `5` |
| `VIDYUT_POOL_SIZE` | `pool_max_size` | `20` |
| `VIDYUT_POOL_MAX_SIZE` | `pool_max_size` | `20` |
| `VIDYUT_APP_TITLE` | `app_title` | `My App` |
| `VIDYUT_APP_VERSION` | `app_version` | `1.0.0` |
| `VIDYUT_MIGRATIONS_DIR` | `migrations_dir` | `migrations` |

---

## Accessing Settings

After configuration, access settings via the `settings` object:

```python
from vidyut import settings

# Access any setting
print(settings.database_url)
print(settings.debug)
print(settings.pool_max_size)
print(settings.installed_apps)
```

---

## Configuration Priority

Settings are resolved in this order (highest priority first):

1. **Explicit `configure()` call** — Programmatic settings
2. **Environment variables** — `VIDYUT_*` prefixed
3. **Built-in defaults** — Sensible fallbacks

Example:

```python
# .env
VIDYUT_DEBUG=false

# settings.py
configure(debug=True)  # This wins - explicit configuration

from vidyut import settings
print(settings.debug)  # True
```

---

## Environment-Specific Configuration

### Development

```python
# settings_dev.py
from vidyut import configure

configure(
    database_url="postgresql://localhost/myapp_dev",
    debug=True,
    log_level="DEBUG",
    log_requests=True,
)
```

### Testing

```python
# settings_test.py
from vidyut import configure

configure(
    database_url="postgresql://localhost/myapp_test",
    debug=True,
    log_level="WARNING",
    log_requests=False,
)
```

### Production

```python
# settings_prod.py
import os
from vidyut import configure

configure(
    database_url=os.environ["DATABASE_URL"],  # Required
    debug=False,
    log_level="INFO",
    log_json=True,  # Structured logs for log aggregation
    pool_min_size=10,
    pool_max_size=50,
)
```

---

## Vidyut App Constructor Settings

The `Vidyut` class accepts additional settings at initialization:

```python
from vidyut import Vidyut

app = Vidyut(
    # Database (overrides configure())
    database_url="postgresql://localhost/myapp",
    min_pool_size=5,
    max_pool_size=20,
    
    # FastAPI settings
    title="My API",
    description="API description",
    version="1.0.0",
    debug=True,
    
    # OpenAPI
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    
    # Admin
    enable_admin=True,
    
    # Auto-discovery
    auto_discover_views=True,
    views_module="app.views",
    
    # Middleware
    middlewares=[
        (RequestIDMiddleware, {}),
        (LoggingMiddleware, {}),
    ],
)
```

---

## Best Practices

### Use `.env` Files for Secrets

Never commit secrets to version control:

```bash
# .gitignore
.env
.env.local
.env.production
```

### Validate Required Settings

```python
import os
from vidyut import configure

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

configure(database_url=DATABASE_URL)
```

### Type Hints for IDE Support

```python
from vidyut.conf import Settings

def get_database_url(settings: Settings) -> str:
    if settings.database_url is None:
        raise ValueError("Database URL not configured")
    return settings.database_url
```

---

## Related Documentation

- [Database Setup](database-setup.md) — Configure PostgreSQL
- [Settings Reference](../reference/settings-reference.md) — Complete settings API
- [Running Your App](running-your-app.md) — Development and production
