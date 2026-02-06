# Aksara Studio Integration

Aksara Studio is an IDE integration that provides visual tools for working with your Aksara applications. This section covers how to set up and use Studio integration.

## What is Aksara Studio?

Aksara Studio is a companion IDE that connects to your running Aksara application to provide:

- **Visual Model Browser** - Explore your database schema visually
- **Query Builder** - Build and test queries without writing code
- **Migration Manager** - Visualize and manage database migrations
- **AI Assistant** - Get AI-powered help with your codebase
- **Real-time Monitoring** - View logs, queries, and performance

## Quick Start

### 1. Enable Studio (Default)

Studio is enabled by default in debug mode. No additional setup is required.

```python
from aksara import Aksara

app = Aksara(
    database_url="postgresql://...",
    debug=True,  # Studio automatically enabled
)
```

### 2. Check Studio Endpoints

Your app exposes these Studio endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /studio/handshake` | Complete project info for Studio |
| `GET /studio/context/summary` | Lightweight schema summary |
| `GET /studio/health` | Health check with DB status |

### 3. Test Locally with CLI

```bash
# Test handshake locally
aksara studio handshake

# View endpoint URLs
aksara studio url
```

### 4. Connect Aksara Studio

In Aksara Studio, add your application:

1. Click "Add Project"
2. Enter your app URL (e.g., `http://localhost:8000`)
3. Studio will automatically discover your schema

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
