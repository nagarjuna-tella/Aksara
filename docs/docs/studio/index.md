# Aksara Studio

Aksara Studio is a **built-in web UI** that comes with every Aksara application. It runs inside your app — no external tool, no IDE plugin, no extra installation required.

Start your app with `aksara dev`, then open **http://localhost:8000/studio/ui** in your browser.

## What is Aksara Studio?

Studio is a visual dashboard embedded in your Aksara application. It gives you a live view of everything happening in your backend:

- **Model Browser** — Explore your database schema and field definitions
- **Query Explorer** — Inspect live queries, query plans, and N+1 alerts
- **Migration Manager** — View pending and applied migrations
- **API Inspector** — Browse your auto-generated REST endpoints
- **AI Console** — Ask questions about your data in plain English
- **Runtime Panel** — View settings, connection pool status, and health checks

!!! info "Studio docs vs AI Mode docs"
    Read the Studio docs for the built-in web UI, Studio endpoints, and Studio configuration.
    Read [AI Mode](../ai-mode/index.md) for the AI Console, AI Flows, MCP tools,
    AI Debugger, Architecture Review, and Performance Analyzer that run inside Studio
    or connect to external agents.

## Quick Start

### 1. Enable Studio (On By Default)

Studio is enabled automatically in debug mode. No configuration needed.

```python
from aksara import Aksara

app = Aksara(
    database_url="postgresql://...",
    debug=True,  # Studio UI is on at /studio/ui
)
```

### 2. Start Your App

```bash
aksara dev
```

### 3. Open Studio in Your Browser

Navigate to **http://localhost:8000/studio/ui**

That's it. Studio reads your app's live state — models, routes, queries, and migrations — all from the same process.

### 4. Studio API Endpoints

Studio also exposes a JSON API used by the UI. These are available while your app runs:

| Endpoint | Description |
|----------|-------------|
| `GET /studio/handshake` | Full project schema and route manifest |
| `GET /studio/context/summary` | Lightweight schema summary |
| `GET /studio/health` | Database and service health check |

### 5. CLI Utilities

```bash
# Test the handshake endpoint from the terminal
aksara studio handshake

# Print Studio endpoint URLs for your running app
aksara studio url
```

## Documentation

<div class="grid cards" markdown>

-   :material-api: **[Studio API](api.md)**

    ---

    Complete API reference for Studio endpoints

-   :material-console: **[CLI Commands](cli.md)**

    ---

    Command-line tools for Studio integration

-   :material-cog: **[Configuration](configuration.md)**

    ---

    Settings and environment variables

-   :material-robot: **[AI Mode](../ai-mode/index.md)**

    ---

    Console, flows, MCP tools, and AI analysis features

</div>

## Security

By default, Studio endpoints are **only enabled in debug mode**. In production:

1. Set `enable_studio=False` to disable completely
2. Or set `studio_expose_in_production=True` to explicitly enable

```python
# Disable Studio entirely
app = Aksara(
    database_url="...",
    debug=False,
)

# Enable in production (requires explicit flag)
from aksara.conf import configure, Settings

configure(Settings(
    enable_studio=True,
    studio_expose_in_production=True,
    studio_allowed_origins=["https://studio.mycompany.com"],
))
```

## Next Steps

- [Studio API Reference](api.md) - Detailed endpoint documentation
- [CLI Commands](cli.md) - Test and manage Studio from the terminal
- [Configuration](configuration.md) - Security and settings
