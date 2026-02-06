# Aksara Studio UI

The embedded Studio UI is a zero-build, zero-dependency admin dashboard served directly from your Aksara backend.

## Overview

Aksara Studio UI provides a lightweight dashboard for:

- **System Overview** — Version info, uptime, environment status
- **Models & Schema** — Browse your database models and relationships
- **Routes Explorer** — View all registered API endpoints
- **Migrations** — Check migration status and conflicts
- **Diagnostics** — Live runtime monitoring with auto-refresh
- **API Explorer** — Quick reference for available endpoints

## Opening the Dashboard

### Via Browser

Navigate to: `http://localhost:8000/studio/ui`

### Via CLI

```bash
# Open in default browser
aksara studio open

# Custom port
aksara studio open --port 8080

# HTTPS
aksara studio open --https
```

## Architecture

The Studio UI uses a "zero-JS-build" architecture:

- **No React, Vue, or Svelte** — Pure vanilla JavaScript
- **No npm/webpack/vite** — No build step required
- **Single HTML file** — Templates embedded using `<template>` tags
- **CSS Variables** — Light/dark theme support
- **Fetch API** — Loads data from Studio REST endpoints

This means:

1. No node_modules or build artifacts
2. Instant loading (no bundle parsing)
3. Works offline with cached responses
4. Easy to customize (edit HTML/CSS/JS directly)

## Dashboard Sections

### System Overview

Displays real-time system information:

- Aksara version
- Python version
- Server uptime
- Environment (development/production)
- Debug mode status
- Database connection status
- Migration summary
- Quick stats (models, routes, viewsets, AI tools)

### Models & Schema

Lists all registered models with:

- Model name and table name
- Field count
- Relationship indicators
- Search/filter functionality

### Routes Explorer

Complete route listing with:

- HTTP methods (GET, POST, PUT, DELETE)
- Route path patterns
- Route names
- Type badges (Studio, Admin, AI, API)
- Filter by route type
- Search functionality

### Migrations

Migration status dashboard:

- Total/applied/pending counts
- Conflict detection
- Per-app breakdown
- Last applied migration

### Diagnostics

Live monitoring with auto-refresh (5 seconds):

- Process ID
- Start time
- Uptime
- Database status
- Pending migrations
- Studio configuration
- Installed apps list

### API Explorer

Static reference for commonly used endpoints:

- Studio endpoints
- AI endpoints
- Documentation endpoints

### AI Helpers

*Added in v0.5.4*

The AI Helpers panel provides tools for integrating external AI assistants with your Aksara project:

#### AI Context Export

Export a comprehensive JSON snapshot of your project for AI consumption:

- **Project metadata** — Version, Python version, installed apps
- **Models summary** — All models with field counts, relationships, table names
- **Routes summary** — All endpoints with methods, paths, names
- **AI tools inventory** — Available AI tools and their status

Click "Copy Context JSON" to copy the entire context to your clipboard, ready to paste into ChatGPT, Claude, or any LLM.

#### AI Schemas

Browse Pydantic schemas used by Aksara's AI APIs:

| Schema | Description |
|--------|-------------|
| `AiPlan` | Structured output from AI planners |
| `AiPatchRequest` | Code modification requests |
| `AiQueryPlan` | Natural language → SQL query plans |
| `AiFullContext` | Complete project context for AI |
| `AiCodegenRequest` | Code generation requests |

These schemas help when building custom AI integrations or validating AI responses.

#### Prompt Templates

Pre-built prompt scaffolds for common tasks:

- **add-field** — Add a new field to an existing model
- **refactor-model** — Refactor a model (rename, split, merge)
- **fix-migrations** — Fix migration conflicts or errors
- **natural-query** — Convert natural language to database queries
- **generate-model** — Generate a new model from description
- **explain-schema** — Get an explanation of your schema

Click on any template to view the full prompt text with placeholders.

## Using Studio with AI Tools

Studio's AI integration endpoints enable powerful workflows with external AI assistants.

### Workflow: Context → AI → Code

1. Open **AI Helpers** in Studio
2. Click **Copy Context JSON** to grab your project snapshot
3. Paste into your AI assistant (ChatGPT, Claude, Copilot, etc.)
4. Ask questions or request changes
5. The AI understands your models, routes, and schema

### Endpoint Reference

| Endpoint | Description |
|----------|-------------|
| `GET /studio/ai/context` | Full AI context export |
| `GET /studio/ai/schemas` | AI API schemas |
| `GET /studio/ai/prompts` | Prompt templates |

### CLI Export

Export context from the command line:

```bash
# Full JSON export
aksara studio ai-context

# Human-readable summary
aksara studio ai-context --format summary
```

### For Editor Plugins / External Agents

The endpoints return pure JSON with no authentication required by default. External tools can fetch context directly:

```python
import httpx

# Fetch project context
context = httpx.get("http://localhost:8000/studio/ai/context").json()

# Use with any AI client
messages = [
    {"role": "system", "content": f"Project context: {context}"},
    {"role": "user", "content": "Add an email field to the User model"}
]
```

!!! info "LLM-Agnostic"
    These endpoints provide **data only** — no actual LLM calls are made.
    You bring your own AI provider (OpenAI, Anthropic, local models, etc.).

!!! warning "Security Note"
    AI context endpoints expose your schema and routes.
    In production with `studio_expose_in_production=True`, ensure
    proper authentication is in place.

## Configuration

### Settings

Configure Studio UI in your settings:

```python
from aksara.conf import configure, Settings

configure(Settings(
    # Enable/disable Studio entirely
    enable_studio=True,
    
    # Enable/disable just the UI
    studio_ui_enabled=True,
    
    # Allow in production (requires explicit opt-in)
    studio_expose_in_production=False,
    
    # Allowed origins for CORS
    studio_allowed_origins=["http://localhost:3000"],
    
    # UI title (future customization)
    studio_ui_title="Aksara Studio",
))
```

### Environment Variables

```bash
# Disable Studio entirely
AKSARA_STUDIO_DISABLED=true

# Allow Studio in production
AKSARA_STUDIO_EXPOSE_IN_PRODUCTION=true

# Custom allowed origins (comma-separated)
AKSARA_STUDIO_ALLOWED_ORIGINS=https://myapp.com,http://localhost:3000
```

## Production Security

By default, Studio UI is **disabled in production** mode. To enable:

1. Set `debug=False` (production mode)
2. Set `studio_expose_in_production=True`

```python
configure(Settings(
    debug=False,
    studio_expose_in_production=True,
))
```

!!! warning "Security Considerations"
    Only expose Studio UI in production if:
    
    - Your server is behind authentication
    - You trust all users who can access it
    - You've configured `studio_allowed_origins` appropriately

## Themes

The UI supports light and dark themes:

- **Auto-detection** — Follows system preference
- **Manual toggle** — Click the sun/moon icon in the sidebar
- **Persistent** — Choice saved in localStorage

## CLI Commands

```bash
# Open dashboard in browser
aksara studio open
aksara studio open --port 8080
aksara studio open --host 192.168.1.100
aksara studio open --https

# Show static assets path
aksara studio ui-path

# Show all endpoint URLs
aksara studio url
```

## Customization

### Finding Static Files

```bash
aksara studio ui-path
# Output: /path/to/aksara/studio/static
```

### Modifying Styles

Edit `aksara/studio/static/styles.css`:

```css
/* Add custom theme colors */
:root[data-theme="light"] {
    --accent-primary: #your-brand-color;
}
```

### Adding Dashboard Sections

1. Add a `<template>` in `index.html`
2. Add a nav item with `data-section`
3. Create a render function in `app.js`

## Troubleshooting

### "Connection Error" on load

1. Ensure your Aksara server is running
2. Check the browser console for CORS errors
3. Verify `studio_allowed_origins` includes your origin

### "Studio is disabled" message

1. Check `enable_studio=True` in settings
2. Check `studio_ui_enabled=True` in settings
3. In production, ensure `studio_expose_in_production=True`

### Assets not loading (404)

1. Run `aksara studio ui-path` to verify the path
2. Ensure the static directory exists
3. Check that files weren't accidentally deleted

### Theme not persisting

- Check if localStorage is blocked by your browser
- Try clearing browser storage and refreshing
