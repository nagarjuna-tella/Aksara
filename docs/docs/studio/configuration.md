# Studio Configuration

Configure Aksara Studio integration through settings and environment variables.

## Settings

Studio settings can be configured in your `Settings` class or via environment variables.

### enable_studio

Enable or disable Studio endpoints.

| Type | Default | Env Variable |
|------|---------|--------------|
| `bool` | `True` | `AKSARA_STUDIO_DISABLED` |

```python
from aksara.conf import configure, Settings

# Disable Studio entirely
configure(Settings(enable_studio=False))
```

Or via environment:

```bash
export AKSARA_STUDIO_DISABLED=true
```

### studio_expose_in_production

Allow Studio endpoints in production (non-debug mode).

| Type | Default | Env Variable |
|------|---------|--------------|
| `bool` | `False` | `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION` |

```python
from aksara.conf import configure, Settings

# Enable Studio in production
configure(Settings(
    enable_studio=True,
    studio_expose_in_production=True,
))
```

Or via environment:

```bash
export AKSARA_STUDIO_EXPOSE_IN_PRODUCTION=true
```

!!! warning "Security Note"
    Only enable Studio in production if your endpoints are properly secured (e.g., behind a VPN or with authentication).

### studio_allowed_origins

CORS origins allowed to access Studio endpoints.

| Type | Default | Env Variable |
|------|---------|--------------|
| `List[str]` | `["https://studio.aksara.dev", "http://localhost:3000"]` | `AKSARA_STUDIO_ALLOWED_ORIGINS` |

```python
from aksara.conf import configure, Settings

configure(Settings(
    studio_allowed_origins=[
        "https://studio.mycompany.com",
        "http://localhost:3000",
    ],
))
```

Or via environment (comma-separated):

```bash
export AKSARA_STUDIO_ALLOWED_ORIGINS="https://studio.mycompany.com,http://localhost:3000"
```

#### Origin Security (v0.5.1)

Starting in v0.5.1, Studio endpoints validate the `Origin` header on incoming requests:

| Scenario | Result |
|----------|--------|
| Origin in allowed list | ✅ Request proceeds |
| No Origin header | ✅ Request proceeds (CLI, same-origin, server-to-server) |
| Origin not in allowed list | ❌ 403 Forbidden |
| `*` in allowed origins | ✅ All origins allowed |
| Empty allowed origins list | ✅ All origins allowed |

```python
# Development: Allow all origins
configure(Settings(
    studio_allowed_origins=["*"],
))

# Production: Strict whitelist
configure(Settings(
    studio_allowed_origins=[
        "https://studio.aksara.dev",
    ],
))
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AKSARA_STUDIO_DISABLED` | Set to `true` to disable Studio |
| `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION` | Set to `true` to enable in production |
| `AKSARA_STUDIO_ALLOWED_ORIGINS` | Comma-separated list of allowed origins |

---

## Security Best Practices

### Development

Studio is enabled by default in debug mode. No special configuration needed.

```python
app = Aksara(
    database_url="postgresql://...",
    debug=True,  # Studio automatically enabled
)
```

### Production

By default, Studio endpoints are disabled in production (when `debug=False`). This is the safest default.

**Option 1: Keep disabled (recommended)**

```python
app = Aksara(
    database_url="postgresql://...",
    debug=False,  # Studio disabled
)
```

**Option 2: Enable with restrictions**

If you need Studio in production:

```python
from aksara.conf import configure, Settings

configure(Settings(
    debug=False,
    enable_studio=True,
    studio_expose_in_production=True,
    studio_allowed_origins=["https://studio.mycompany.internal"],
))
```

And add additional security:

1. **VPN**: Only expose Studio endpoints on internal network
2. **Authentication**: Add authentication middleware to `/studio/*` routes
3. **IP Whitelist**: Restrict access to known IPs

---

## Endpoint Behavior by Mode

| Mode | Studio Enabled | Notes |
|------|----------------|-------|
| Debug (`debug=True`) | ✅ Yes | Default behavior |
| Production (`debug=False`) | ❌ No | Unless `studio_expose_in_production=True` |
| Explicitly disabled | ❌ No | When `enable_studio=False` |

---

## Checking Studio Status

### Via CLI

```bash
aksara studio handshake
```

If Studio is disabled, the handshake will still work (it tests locally), but the HTTP endpoints won't be available.

### Via HTTP

```bash
curl http://localhost:8000/studio/health
```

If disabled, you'll get a 404 response.

### Via Code

```python
from aksara.conf import settings

print(f"Studio enabled: {settings.enable_studio}")
print(f"Expose in production: {settings.studio_expose_in_production}")
```
