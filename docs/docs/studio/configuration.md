# Studio configuration

!!! warning "Experimental surface"
    Studio and Studio AI internals are experimental in v0.7.0. New projects
    keep Studio disabled.

Studio mounts only when `enable_studio=True`. In production it also requires
`studio_expose_in_production=True`.

## Recommended environment configuration

```dotenv
AKSARA_ENABLE_STUDIO=true
AKSARA_STUDIO_SECRET_TOKEN=replace-with-a-random-secret
AKSARA_STUDIO_REQUIRE_AUTH=true
AKSARA_STUDIO_AUTH_TOKEN=replace-with-a-separate-bearer-secret
AKSARA_STUDIO_ALLOWED_ORIGINS=http://localhost:3000
AKSARA_STUDIO_EXPOSE_IN_PRODUCTION=false
```

`AKSARA_STUDIO_DISABLED=true` is retained as a compatibility switch and wins
when Studio was otherwise enabled. `AKSARA_ENABLE_STUDIO=false` is the clearer
current path.

The relevant global settings are:

| Setting | Default | Environment variable |
| --- | --- | --- |
| `enable_studio` | `False` | `AKSARA_ENABLE_STUDIO` |
| `studio_secret_token` | `None` | `AKSARA_STUDIO_SECRET_TOKEN` |
| `studio_expose_in_production` | `False` | `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION` |
| `studio_require_auth` | `True` | `AKSARA_STUDIO_REQUIRE_AUTH` |
| `studio_auth_token` | `None` | `AKSARA_STUDIO_AUTH_TOKEN` |
| `studio_allowed_origins` | Aksara-hosted Studio and local development origins | `AKSARA_STUDIO_ALLOWED_ORIGINS` |

Enabling Studio without `AKSARA_STUDIO_SECRET_TOKEN` raises
`ImproperlyConfigured` during settings construction.

## Explicit Python configuration

Use the same global settings path as core configuration:

```python
from aksara import configure

configure(
    enable_studio=True,
    studio_secret_token="replace-with-a-random-secret",
    studio_require_auth=True,
    studio_auth_token="replace-with-a-separate-bearer-secret",
    studio_allowed_origins=["http://localhost:3000"],
    studio_expose_in_production=False,
)
```

## Exposure behavior

| Configuration | Result |
| --- | --- |
| `enable_studio=False` | Studio routes are not mounted |
| Debug plus `enable_studio=True` | Studio routes are mounted |
| Production plus `enable_studio=True` and `studio_expose_in_production=False` | Studio routes are not mounted |
| Production plus both exposure flags | Studio routes are mounted and require the configured application security boundary |

## Origin and credential checks

The Studio router checks Origin separately from authentication:

- A missing Origin header is allowed by the origin check.
- The server's own origin is allowed, even when absent from the list.
- An empty list or a list containing `"*"` allows every origin.
- Other origins require an exact match; rejection returns HTTP 403.

These rules do not constitute a network allowlist or tenant boundary. A caller
can omit Origin, so credential verification and network controls remain essential.

With `studio_require_auth=True`, the router accepts a matching case-sensitive
`Authorization: Bearer <studio_auth_token>` header or a valid database-backed
staff session cookie named `session_token`. Otherwise it returns HTTP 401.
`studio_secret_token` is required for enabled settings construction; it is not
the bearer credential checked by this router. Do not confuse the two settings.
These checks gate developer access, not per-record application permissions.

With `studio_require_auth=False`, the router bypasses credential checking.
The local quickstart uses that mode only on loopback; never infer production
security merely from having set the required Studio secret.

Check the configured deployment with:

```bash
aksara doctor security-check
aksara doctor production-check --release
```
