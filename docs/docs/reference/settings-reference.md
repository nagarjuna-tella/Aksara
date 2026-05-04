# Settings Reference

Complete reference for all Aksara configuration options.

---

## Configuration

The current Aksara configuration surface is the `Settings` dataclass in
`aksara.conf`.

```python
from aksara.conf import Settings, configure

configure(Settings(
    database_url="postgresql://user:pass@localhost:5432/myapp",
    debug=True,
))
```

Or load from environment:

```python
export DATABASE_URL=postgresql://user:pass@localhost:5432/myapp
export AKSARA_DEBUG=true
export AKSARA_MEDIA_ROOT=media
export AKSARA_EMAIL_BACKEND=console
```

---

## Core Settings

### DEBUG

Type: `bool`
Default: `False`

Enable debug mode. Shows detailed error pages and enables debug toolbar.

```python
"DEBUG": True
```

!!! warning
    Never enable DEBUG in production.

### SECRET_KEY

Type: `str`
Required in production

Secret key for cryptographic signing.

```python
"SECRET_KEY": "your-secret-key-at-least-50-characters-long"
```

Generate a secure key:

```python
import secrets
print(secrets.token_urlsafe(50))
```

### ALLOWED_HOSTS

Type: `list[str]`
Default: `["*"]` in debug, `[]` in production

Allowed host headers.

```python
"ALLOWED_HOSTS": ["example.com", "www.example.com"]
```

### ROOT_URLCONF

Type: `str`
Default: Auto-detected

Module containing URL configuration.

```python
"ROOT_URLCONF": "myapp.urls"
```

---

## Database Settings

### DATABASE_URL

Type: `str`
Required

Database connection URL.

```python
# PostgreSQL
"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"
```

!!! note
    Aksara is PostgreSQL-only. SQLite and other database engines are not
    supported as of now. New engines will be added when we find time. 😅

### DATABASE_POOL

Type: `dict`
Default: `{}`

Connection pool configuration.

```python
"DATABASE_POOL": {
    "min_size": 5,
    "max_size": 20,
    "max_queries": 50000,
    "max_inactive_connection_lifetime": 300,
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `min_size` | int | 5 | Minimum connections |
| `max_size` | int | 20 | Maximum connections |
| `max_queries` | int | 50000 | Max queries per connection |
| `max_inactive_connection_lifetime` | int | 300 | Idle timeout (seconds) |

---

## Media Storage Settings

### MEDIA_ROOT

Type: `str`
Default: `"media"`

Local directory used by `FileSystemStorage`.

### MEDIA_URL

Type: `str`
Default: `"/media/"`

Public URL prefix for locally served media. In debug mode, `Aksara` mounts this
path automatically when filesystem storage is active.

### MEDIA_STORAGE

Type: `str`
Default: `"filesystem"`

Storage backend selector.

Supported values:

- `filesystem`
- `s3`
- Dotted import path to a custom storage backend class

### Filesystem Example

```python
from aksara.conf import Settings, configure

configure(Settings(
    media_root="media",
    media_url="/media/",
    media_storage="filesystem",
))
```

### S3 Settings

These settings are used when `media_storage="s3"`:

| Setting | Type | Description |
|--------|------|-------------|
| `media_s3_bucket` | `str` | Bucket name |
| `media_s3_region` | `str` | AWS region |
| `media_s3_endpoint_url` | `str` | Optional S3-compatible endpoint |
| `media_s3_access_key` | `str` | Access key |
| `media_s3_secret_key` | `str` | Secret key |
| `media_public_base_url` | `str` | Optional public CDN/base URL |

```python
configure(Settings(
    media_storage="s3",
    media_s3_bucket="my-app-media",
    media_s3_region="us-east-1",
    media_public_base_url="https://cdn.example.com/media",
))
```

---

## Email Settings

### EMAIL_BACKEND

Type: `str`
Default: `"console"`

Supported values:

- `console`
- `locmem`
- `smtp`
- Dotted import path to a custom backend class

### DEFAULT_FROM_EMAIL

Type: `str`
Default: `"webmaster@localhost"`

Sender address used when `send_mail()` is called without `from_email`.

### SMTP Settings

| Setting | Type | Default |
|--------|------|---------|
| `email_host` | `str` | `localhost` |
| `email_port` | `int` | `25` |
| `email_host_user` | `str \| None` | `None` |
| `email_host_password` | `str \| None` | `None` |
| `email_use_tls` | `bool` | `False` |
| `email_use_ssl` | `bool` | `False` |
| `email_timeout` | `float` | `10.0` |

```python
configure(Settings(
    email_backend="smtp",
    default_from_email="noreply@example.com",
    email_host="smtp.example.com",
    email_port=587,
    email_host_user="mailer",
    email_host_password="super-secret",
    email_use_tls=True,
))
```

See [Advanced Media & Email](../advanced/media-and-email.md) for usage examples.

---

## Application Settings

### INSTALLED_APPS

Type: `list[str]`
Default: `[]`

List of installed applications.

```python
"INSTALLED_APPS": [
    "users",
    "posts",
    "aksara.contrib.admin",
]
```

### MIDDLEWARE

Type: `list[str]`
Default: `[]`

Middleware classes.

```python
"MIDDLEWARE": [
    "aksara.middleware.RequestIDMiddleware",
    "aksara.middleware.LoggingMiddleware",
    "myapp.middleware.CustomMiddleware",
]
```

---

## API Settings

### DEFAULT_PERMISSION_CLASSES

Type: `list[str]`
Default: `["aksara.api.permissions.AllowAny"]`

Default permissions for all ViewSets.

```python
"DEFAULT_PERMISSION_CLASSES": [
    "aksara.api.permissions.IsAuthenticated",
]
```

### DEFAULT_AUTHENTICATION_CLASSES

Type: `list[str]`
Default: `[]`

Authentication backends.

```python
"DEFAULT_AUTHENTICATION_CLASSES": [
    "aksara.api.authentication.TokenAuthentication",
    "aksara.api.authentication.SessionAuthentication",
]
```

### DEFAULT_PAGINATION_CLASS

Type: `str`
Default: `None`

Default pagination class.

```python
"DEFAULT_PAGINATION_CLASS": "aksara.api.pagination.PageNumberPagination"
```

### PAGE_SIZE

Type: `int`
Default: `20`

Default page size for pagination.

```python
"PAGE_SIZE": 50
```

### MAX_PAGE_SIZE

Type: `int`
Default: `100`

Maximum allowed page size.

```python
"MAX_PAGE_SIZE": 200
```

---

## Authentication Settings

### AUTH_TOKEN_EXPIRY

Type: `int`
Default: `86400` (24 hours)

Token expiration time in seconds.

```python
"AUTH_TOKEN_EXPIRY": 3600  # 1 hour
```

### AUTH_REFRESH_TOKEN_EXPIRY

Type: `int`
Default: `604800` (7 days)

Refresh token expiration.

```python
"AUTH_REFRESH_TOKEN_EXPIRY": 2592000  # 30 days
```

### AUTH_ALGORITHM

Type: `str`
Default: `"HS256"`

JWT signing algorithm.

```python
"AUTH_ALGORITHM": "RS256"
```

---

## CORS Settings

### CORS_ORIGINS

Type: `list[str]`
Default: `[]`

Allowed origins.

```python
"CORS_ORIGINS": [
    "https://example.com",
    "https://app.example.com",
]
```

### CORS_ALLOW_CREDENTIALS

Type: `bool`
Default: `False`

Allow credentials (cookies, auth headers).

```python
"CORS_ALLOW_CREDENTIALS": True
```

### CORS_ALLOW_METHODS

Type: `list[str]`
Default: `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]`

Allowed HTTP methods.

### CORS_ALLOW_HEADERS

Type: `list[str]`
Default: `["*"]`

Allowed request headers.

---

## Cache Settings

### CACHE

Type: `dict`
Default: `{}`

Cache configuration.

```python
"CACHE": {
    "default": {
        "backend": "redis",
        "url": "redis://localhost:6379/0",
        "ttl": 300,
        "key_prefix": "myapp:",
    }
}
```

| Option | Type | Description |
|--------|------|-------------|
| `backend` | str | `"memory"`, `"redis"`, or custom class |
| `url` | str | Connection URL (Redis) |
| `ttl` | int | Default TTL in seconds |
| `key_prefix` | str | Prefix for all keys |
| `max_size` | int | Max entries (memory backend) |

---

## Logging Settings

### LOGGING

Type: `dict`
Default: `{}`

Logging configuration.

```python
"LOGGING": {
    "level": "INFO",
    "format": "json",
    "handlers": ["console"],
    "file_path": "/var/log/myapp/app.log",
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | str | `"INFO"` | Log level |
| `format` | str | `"text"` | `"text"` or `"json"` |
| `handlers` | list | `["console"]` | Output handlers |
| `file_path` | str | None | Log file path |

### LOG_QUERIES

Type: `bool`
Default: `False`

Log all database queries.

```python
"LOG_QUERIES": True
```

---

## AI Mode Settings

### AI_MODE

Type: `bool`
Default: `False`

Enable AI features.

```python
"AI_MODE": True
```

### AI_PROVIDER

Type: `str`
Default: `"openai"`

AI provider: `"openai"` or `"anthropic"`.

```python
"AI_PROVIDER": "anthropic"
```

### AI_API_KEY

Type: `str`
Default: `None`

API key for AI provider.

```python
"AI_API_KEY": os.environ["OPENAI_API_KEY"]
```

### AI_MODEL

Type: `str`
Default: Provider-specific

AI model to use.

```python
"AI_MODEL": "gpt-4"
# or
"AI_MODEL": "claude-3-opus-20240229"
```

### AI_SAFETY

Type: `dict`
Default: `{}`

AI safety configuration.

```python
"AI_SAFETY": {
    "read_only_mode": True,
    "require_confirmation": True,
    "audit_log": True,
    "audit_log_file": "logs/ai_audit.log",
    "rate_limit_requests": 100,
    "rate_limit_window": 3600,
    "max_tokens": 4000,
}
```

---

## Multi-Tenant Settings

### MULTI_TENANT

Type: `bool`
Default: `False`

Enable multi-tenancy.

```python
"MULTI_TENANT": True
```

### TENANT_MODEL

Type: `str`
Default: `None`

Tenant model path.

```python
"TENANT_MODEL": "tenants.Tenant"
```

### TENANT_HEADER

Type: `str`
Default: `"X-Tenant-ID"`

Header for tenant identification.

```python
"TENANT_HEADER": "X-Organization-ID"
```

### TENANT_SUBDOMAIN

Type: `bool`
Default: `False`

Use subdomain for tenant identification.

```python
"TENANT_SUBDOMAIN": True
```

---

## Security Settings

### SECURITY

Type: `dict`
Default: `{}`

Security configuration.

```python
"SECURITY": {
    "SECURE_SSL_REDIRECT": True,
    "SECURE_HSTS_SECONDS": 31536000,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "SECURE_BROWSER_XSS_FILTER": True,
    "X_FRAME_OPTIONS": "DENY",
}
```

---

## Admin Settings

### ADMIN_SITE_TITLE

Type: `str`
Default: `"Admin"`

Admin site title.

```python
"ADMIN_SITE_TITLE": "My App Admin"
```

### ADMIN_SITE_HEADER

Type: `str`
Default: `"Administration"`

Admin header text.

### ADMIN_URL_PREFIX

Type: `str`
Default: `"/admin"`

Admin URL prefix.

```python
"ADMIN_URL_PREFIX": "/dashboard"
```

---

## Static Files

### STATIC_URL

Type: `str`
Default: `"/static/"`

URL prefix for static files.

### STATIC_ROOT

Type: `str`
Default: `None`

Directory for collected static files.

```python
"STATIC_ROOT": "/var/www/myapp/static"
```

---

## Complete Example

```python
# settings.py
import os

AKSARA = {
    # Core
    "DEBUG": os.getenv("DEBUG", "false").lower() == "true",
    "SECRET_KEY": os.environ["SECRET_KEY"],
    "ALLOWED_HOSTS": os.getenv("ALLOWED_HOSTS", "").split(","),
    
    # Database
    "DATABASE_URL": os.environ["DATABASE_URL"],
    "DATABASE_POOL": {
        "min_size": 5,
        "max_size": 20,
    },
    
    # Apps
    "INSTALLED_APPS": [
        "users",
        "posts",
        "aksara.contrib.admin",
    ],
    
    # API
    "DEFAULT_PERMISSION_CLASSES": [
        "aksara.api.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "aksara.api.authentication.TokenAuthentication",
    ],
    "PAGE_SIZE": 20,
    
    # CORS
    "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "").split(","),
    "CORS_ALLOW_CREDENTIALS": True,
    
    # Cache
    "CACHE": {
        "default": {
            "backend": "redis",
            "url": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            "ttl": 300,
        }
    },
    
    # Logging
    "LOGGING": {
        "level": "INFO",
        "format": "json",
    },
    
    # AI
    "AI_MODE": os.getenv("AI_MODE", "false").lower() == "true",
    "AI_API_KEY": os.getenv("AI_API_KEY"),
    "AI_SAFETY": {
        "read_only_mode": True,
        "audit_log": True,
    },
}
```

---

## Environment Variables

Common environment variables:

| Variable | Description |
|----------|-------------|
| `DEBUG` | Enable debug mode |
| `SECRET_KEY` | Application secret key |
| `DATABASE_URL` | Database connection URL |
| `REDIS_URL` | Redis connection URL |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `CORS_ORIGINS` | Comma-separated CORS origins |
| `AI_API_KEY` | AI provider API key |

---

## Related Documentation

- [Getting Started](../getting-started/settings.md)
- [Database Setup](../getting-started/database-setup.md)
- [Middleware](../middleware/index.md)
