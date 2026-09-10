# Quickstart

Build a working API in 5 minutes. No prior framework experience needed.

---

## What We're Building

A small **Ops Playbook API** that shows what Aksara generates from one model definition.

- Create and list operational playbooks over REST
- Inspect the same model in Studio at `/studio/ui`
- Ask the AI Console to explain the model and endpoints
- Connect an MCP client and inspect generated tools at `/mcp/`

The point of the demo is that one Aksara model becomes a database table, a
REST API, a Studio surface, and executable MCP tools without separate schemas.

---

## Prerequisites

Before you start, make sure you have:

| Tool | How to Check | What It's For |
|------|--------------|---------------|
| Python 3.11–3.14 | `python --version` | Running Aksara |
| PostgreSQL 16 | `psql --version` | Release CI; the packaged app also runs on 18.4 |
| pip | `pip --version` | Installing packages |

**PostgreSQL is strictly required.** Unlike Django, Aksara uses advanced Postgres-native features (JSONB, pgvector, Listen/Notify) and does not fall back to SQLite. Ensure you have a running PostgreSQL instance (either native, via Docker, or cloud-hosted) before proceeding.

**AI Configuration:** To use features that call a model provider, such as AI
Console or AI Debugger, configure that provider. Catalog export itself does not
call a model.
*   **Anthropic:** `ANTHROPIC_API_KEY="<ANTHROPIC_API_KEY>"`
*   **OpenAI:** `OPENAI_API_KEY="<OPENAI_API_KEY>"`
*   *(Ollama is also supported for local models)*

---

## Step 1: Install Aksara

Open your terminal and run:

```bash
pip install aksara-framework
```

**What this does:** Downloads Aksara and its dependencies (FastAPI, Pydantic, asyncpg, etc.).

Verify it worked:

```bash
aksara --version
# Published release: aksara, version 0.5.54
# v0.6 candidate: aksara, version 0.6.0rc2
```

---

## Step 2: Create Your Project

Run the scaffolding command:

```bash
aksara startproject opsdesk
cd opsdesk
```

**What this does:** Creates a complete project with Admin, Studio, and AI Mode pre-configured.

You'll see this structure:

```
opsdesk/
├── main.py           ← Starts your application
├── settings.py       ← Configuration (AKSARA dict)
├── .env              ← Secret settings (not committed to git)
├── app/
│   ├── models.py     ← Your model definitions
│   ├── views.py      ← Your ViewSets
│   ├── urls.py       ← Route registration
│   └── admin.py      ← Admin registrations
└── migrations/       ← Database schema changes
```

**What's Included Out-of-the-Box:**

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Welcome | `/` | Welcome page with quick links |
| API Docs | `/docs` | Swagger UI for your API |
| Admin | `/admin` | Admin interface (debug mode) |
| Studio | `/studio/ui` | Visual dashboard with the built-in AI Console |
| AI Tools | `/ai/tools` | Generic AI tool discovery |
| MCP server | `/mcp/` | Permission-filtered generated tools over Streamable HTTP |
| Example API | `/api/posts` | Scaffolded example you can replace |

---

## Step 3: Configure Your Database

Run the interactive database setup:

```bash
aksara dbsetup
```

This will:

1. Check that PostgreSQL is running
2. Prompt for database name, username, and password
3. Test the connection
4. Create the database if it doesn't exist
5. Write `DATABASE_URL` to your `.env` file

After the prompts, a successful run ends with output like this:

```
  ⚡ Aksara v0.6.0rc2
  Database Setup

  ✓ found (localhost:5432)
  > Database name [opsdesk]:
  > Username [postgres]:
  > Password:
  ✓ connected
  ✓ created
  ✓ done

  ✓ Ready. Run aksara migrate to continue.
```

!!! tip "Manual configuration"
    You can also configure the database manually by editing `.env`:
    ```bash
    DATABASE_URL=postgresql://postgres:password@localhost:5432/opsdesk
    ```

---

## Step 4: Define One AI-Aware Model

Open `app/models.py` and add:

```python
from aksara import Model, fields

class Playbook(Model):
    """
  An operational playbook entry.

  This model is intentionally small so you can see how the same
  definition drives the database table, REST API, Studio UI,
  AI Console context, and MCP tool export.
    """
  title = fields.String(
    max_length=200,
    ai_description="Short title for the operational scenario"
  )
  symptom = fields.Text(
    ai_description="What the operator or customer is seeing"
  )
  fix = fields.Text(
    ai_description="Recommended remediation steps"
  )
  internal_only = fields.Boolean(
    default=False,
    ai_description="Whether the playbook is restricted to internal operators",
    ai_agent_writable=False,
  )
    created_at = fields.DateTime(auto_now_add=True)
```

**What this does:** Defines one model with both normal field types and AI metadata. Aksara uses the same definition for storage, API generation, Studio introspection, and external tool export.

**Understanding the code:**

| Line | What It Means |
|------|---------------|
| `class Playbook(Model)` | `Playbook` becomes a PostgreSQL table and a first-class app resource |
| `ai_description="..."` | Gives Studio AI features and MCP exports human-readable field meaning |
| `fields.Text(...)` | Stores longer narrative content without a max length |
| `ai_agent_writable=False` | Keeps the field visible to AI but blocks agent-driven writes |
| `fields.DateTime(auto_now_add=True)` | Timestamp, automatically set when created |

---

## Step 5: Create the API in One Class

Open `app/views.py`:

```python
from aksara.api import ModelViewSet
from app.models import Playbook

class PlaybookViewSet(ModelViewSet):
    """
  One class gives you full CRUD for playbooks.
    """
  model = Playbook
```

**What this does:** Uses Aksara's model-aware viewset to generate the standard CRUD surface from the model directly.

### URLs (Route Mapping)

Open `app/urls.py`:

```python
from aksara import include_viewset
from app.views import PlaybookViewSet

urlpatterns = [
    PlaybookViewSet,
]

def register_routes(app):
    for viewset in urlpatterns:
        include_viewset(app, viewset)

# This creates these URLs:
# - /api/playbooks/
# - /api/playbooks/{id}/
```

**What this does:** Publishes the REST endpoints, which then also show up in Studio and in the generated tool exports.

---

## Step 6: Create the Database Table

Run migrations to create your table:

```bash
# Generate a migration file (like a recipe for changing the database)
aksara makemigrations

# Apply the migration (actually create the table)
aksara migrate
```

**What this does:**

1. `makemigrations` looks at your models and creates instructions for the database
2. `migrate` runs those instructions to create the actual tables

---

## Step 7: Export AI Keys & Start Your Server

If you want to use the AI Console and diagnostic features in Studio, export the API key for your preferred AI provider first:

```bash
# For Anthropic (Recommended)
export ANTHROPIC_API_KEY="<ANTHROPIC_API_KEY>"

# Or for OpenAI
export OPENAI_API_KEY="<OPENAI_API_KEY>"
```

Start the development server:

```bash
aksara dev
```

Or specify a custom app path:

```bash
aksara dev main:app
```

**What you'll see:**

```
         ████╗   █████╗  ██╗    ██╗ ███████╗  █████╗  ██████╗   █████╗ 
        ████╔╝  ██╔══██╗ ██║   ██╔╝ ██╔════╝ ██╔══██╗ ██╔══██╗ ██╔══██╗
       ████╔╝   ██║  ██║ ██║  ██╔╝  ██║      ██║  ██║ ██║  ██║ ██║  ██║
      ████╔╝    ██║  ██║ ██║ ██╔╝   ██║      ██║  ██║ ██║  ██║ ██║  ██║
     ████████╗  ███████║ █████╔╝    ███████╗ ███████║ ██████╔╝ ███████║
     ╚══████╔╝  ██╔══██║ ██╔═██╗    ╚════██║ ██╔══██║ ██╔══██╗ ██╔══██║
       ████╔╝   ██║  ██║ ██║  ██╗        ██║ ██║  ██║ ██║  ██║ ██║  ██║
      ████╔╝    ██║  ██║ ██║   ██╗       ██║ ██║  ██║ ██║  ██║ ██║  ██║
     ████╔╝     ██║  ██║ ██║    ██╗ ███████║ ██║  ██║ ██║  ██║ ██║  ██║
     ╚═══╝      ╚═╝  ╚═╝ ╚═╝    ╚═╝ ╚══════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝

    AI-native async backend  ·  Dev Server  ·  v0.6.0rc2

  ● App       http://127.0.0.1:8000/
  ● Admin     http://127.0.0.1:8000/admin/
  ● Studio    http://127.0.0.1:8000/studio/ui
  ● Docs      http://127.0.0.1:8000/docs

  Env dev  ·  Reload enabled  ·  Log info
```

!!! tip "Power-user output controls"
    Output controls are global flags, so place them before the command name: `aksara --quiet dev` suppresses non-error Aksara UI output, `aksara --plain dev` disables Rich rendering and animation, and `aksara --no-color dev` keeps the same layout without ANSI color. `--quiet` does not suppress Uvicorn's own logs.

**Your API is now running!**

### Welcome Page

Open **http://localhost:8000/** in your browser to see the welcome page with quick links to Admin, Studio, API, and Docs.

---

## Step 8: Test the API and the AI Surfaces

### Using the Interactive Docs

Open your browser to: **http://localhost:8000/docs**

You'll see Swagger UI with the generated `/api/playbooks/` endpoints. Try them out there or from the command line.

### Using curl (Command Line)

**Create a playbook entry:**

```bash
curl -X POST http://localhost:8000/api/playbooks/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API latency spike",
    "symptom": "Requests over 2 seconds from the public API",
    "fix": "Check database saturation, inspect slow queries, then scale workers",
    "internal_only": true
  }'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "API latency spike",
  "symptom": "Requests over 2 seconds from the public API",
  "fix": "Check database saturation, inspect slow queries, then scale workers",
  "internal_only": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**List all playbooks:**

```bash
curl http://localhost:8000/api/playbooks/
```

**Inspect the compatibility catalog:**

```bash
curl http://localhost:8000/ai/tools/mcp
```

**Open Studio and ask the AI Console:**

```bash
Explain the Playbook model
```

That request uses the same model metadata you defined in `app/models.py`. No second AI schema file is required.

### Using Python

```python
import httpx

# Create a playbook entry
response = httpx.post(
  "http://localhost:8000/api/playbooks/",
  json={
    "title": "Cache invalidation drift",
    "symptom": "Stale values returned after product updates",
    "fix": "Invalidate product detail cache after write operations",
    "internal_only": False,
  }
)
playbook = response.json()
print(f"Created playbook: {playbook['id']}")

# List playbooks
playbooks = httpx.get("http://localhost:8000/api/playbooks/").json()
print(f"You have {len(playbooks)} playbooks")
```

---

## What You Built

Congratulations! You created one model and got all of this from it:

✅ A **database table** to store playbooks  
✅ A **REST API** with full CRUD operations  
✅ **Interactive documentation** at `/docs`  
✅ **Automatic validation** of incoming data  
✅ **Admin interface** at `/admin`  
✅ **Studio dashboard** at `/studio/ui`  
✅ **AI Console** inside Studio  
✅ **AI tools** at `/ai/tools`  
✅ **MCP protocol tools** at `/mcp/`

**Without maintaining separate API, Studio, and AI schemas.**

### Explore the Dashboards

Now that your server is running, try these URLs:

| URL | What You'll See |
|-----|-----------------|
| http://localhost:8000/docs | Swagger UI with your Playbook API |
| http://localhost:8000/admin | Admin panel to manage playbooks |
| http://localhost:8000/studio/ui | Studio dashboard with schema info and the AI Console |
| http://localhost:8000/ai/tools | Generic AI tools generated from your model and ViewSet |
| http://localhost:8000/mcp/ | MCP Streamable HTTP server for generated tools |
| http://localhost:8000/ai/tools/mcp | Permission-filtered inspection catalog |

!!! info "MCP execution boundary"
    `/mcp/` negotiates MCP and invokes generated tools through the same
    authentication, permission, policy, transaction, and tenant path as REST.
    `/ai/tools/mcp` remains available for inspection. See
    [MCP Integration](ai-mode/mcp.md).

!!! tip "When the app does not start cleanly"
  Run `aksara doctor run` for a live health report. If Aksara detects issues it can
  explain, `aksara doctor fix-plan` prints the remediation sequence to follow.

---

## Next Steps

Now that you have a working app, learn more:

| Want to... | Read This |
|------------|-----------|
| Add more fields to your model | [Fields Reference](orm/fields.md) |
| Filter and search tasks | [Querying Data](orm/querying.md) |
| Add user authentication | [Authentication](api/authentication.md) |
| Protect your endpoints | [Permissions](api/permissions.md) |
| Add an admin dashboard | [Admin Guide](admin/index.md) |
| Use AI to query your data | [AI Mode](ai-mode/index.md) |
| Troubleshoot startup and schema problems | [Diagnostics & Doctor](diagnostics.md) |

---

## Common Issues

### "Connection refused" when running migrate

**Problem:** PostgreSQL isn't running.

**Solution:**
```bash
# macOS
brew services start postgresql

# Linux  
sudo systemctl start postgresql

# Docker
docker start postgres
```

### "Database does not exist"

**Problem:** You need to create the database first.

**Solution:**
```bash
aksara dbsetup
```

### "Module not found" errors

**Problem:** Aksara isn't installed in your current environment.

**Solution:**
```bash
pip install aksara-framework
# or if using a virtual environment, activate it first
source venv/bin/activate
pip install aksara-framework
```

---

## Quick Reference Card

```bash
# Create a new project
aksara startproject <name>

# Set up the database interactively
aksara dbsetup

# Create migrations
aksara makemigrations

# Apply migrations
aksara migrate

# Start development server
aksara dev

# Start with specific port
aksara dev --port 8080

# Start the admin panel
aksara admin
```

**API Endpoints (automatic with ModelViewSet):**

| Method | URL | Action |
|--------|-----|--------|
| GET | `/api/{resource}/` | List all |
| POST | `/api/{resource}/` | Create new |
| GET | `/api/{resource}/{id}/` | Get one |
| PUT | `/api/{resource}/{id}/` | Update |
| PATCH | `/api/{resource}/{id}/` | Partial update |
| DELETE | `/api/{resource}/{id}/` | Delete |
