# CLI

Command-line interface for Aksara development.

---

## Overview

The Aksara CLI provides commands for:

| Category | Commands |
|----------|----------|
| **Project** | `startproject`, `startapp` |
| **Database** | `dbsetup`, `makemigrations`, `migrate`, `shell` |
| **Development** | `dev`, `run`, `routes`, `info` |
| **Codegen** | `generate sdk` |
| **AI** | `ai query`, `ai generate`, `ai doctor` |

---

## Quick Start

### Installation

The CLI is included with Aksara:

```bash
pip install aksara-framework
```

### Basic Usage

```bash
# Show help
aksara --help

# Show version
aksara --version

# Start development server
aksara dev

# Suppress non-error Aksara UI output
aksara --quiet dev
```

---

## Project Commands

### startproject

Create a new Aksara project:

```bash
aksara startproject myproject
```

Creates:
```
myproject/
├── myproject/
│   ├── __init__.py
│   ├── settings.py
│   ├── app.py
│   └── models.py
├── tests/
│   └── __init__.py
└── pyproject.toml
```

Options:
```bash
aksara startproject myproject --directory /path/to/dir
aksara startproject myproject --template minimal  # or "full", "api"
```

### startapp

Create a new app within your project:

```bash
aksara startapp blog
```

Creates:
```
blog/
├── __init__.py
├── models.py
├── viewsets.py
├── serializers.py
└── tests/
    └── __init__.py
```

---

## Database Commands

### dbsetup

Interactively set up a PostgreSQL database for the current project:

```bash
aksara dbsetup
```

This checks for PostgreSQL, prompts for credentials, tests the connection, creates the database, and writes `DATABASE_URL` to `.env`.

Options:
```bash
aksara dbsetup --host db.example.com  # Custom host
aksara dbsetup --port 5433            # Custom port
```

### makemigrations

Generate migrations from model changes:

```bash
aksara makemigrations
```

Output:
```
Migrations for 'blog':
  blog/migrations/0002_add_post_slug.py
    - Add field slug to post
```

Options:
```bash
aksara makemigrations --app app.models  # Specify models module
aksara makemigrations --name add_slug   # Custom name
aksara makemigrations --output dir      # Custom output directory
aksara makemigrations --stdout          # Preview to stdout
```

### migrate

Apply pending migrations from the project `migrations/` directory:

```bash
aksara migrate
```

Output:
```
Applying 0001_auto_initial... ✓ Applied successfully
Applying 0002_auto_add_post_slug... ✓ Applied successfully
```

Options:
```bash
aksara migrate --dry-run                # Preview without applying
aksara migrate --fake                   # Mark as applied without running
aksara migrate --migrations-dir dir     # Custom migrations directory
aksara migrate --database-url URL       # Specify database
```

When migration files exist, `aksara migrate` applies them through the canonical
executor: each migration runs in a transaction, a PostgreSQL advisory lock
prevents concurrent runners, already-applied migrations are skipped after their
checksums are verified, a checksum mismatch fails clearly, historical
migrations without a checksum may warn, and pending migrations skipped after a
failure are reported. If no migration files exist, the command can still fall
back to a legacy model-based bootstrap path, which does not provide the full
file-based migration integrity model. See [Migration Safety](../orm/migration-safety.md).

### shell

Interactive Python shell with models loaded:

```bash
aksara shell
```

```python
>>> from blog.models import Post
>>> posts = await Post.objects.all()
>>> len(posts)
42
```

Options:
```bash
aksara shell --database-url postgresql://postgres:password@localhost:5432/myapp
aksara shell --no-ipython
```

---

## Development Commands

### dev

Preferred development server with the rich startup banner:

```bash
aksara dev
```

You can also reach the same path with the alias:

```bash
aksara run dev
```

Options:
```bash
aksara dev --port 3000
aksara dev --host 0.0.0.0
aksara dev --no-reload
aksara dev myproject.main:app --log-level debug
```

### run

Start a specific ASGI app path directly with Uvicorn-style options:

```bash
aksara run main:app
```

Output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started reloader process
```

Options:
```bash
aksara run main:app --port 3000
aksara run main:app --host 0.0.0.0
aksara run main:app --reload           # Auto-reload on changes
aksara run myproject.main:app --workers 4  # Multiple workers
```

### routes

List all registered routes:

```bash
aksara routes
```

Output:
```
Method    Path                      Name
--------  ------------------------  ----------------
GET       /api/posts/               posts-list
POST      /api/posts/               posts-create
GET       /api/posts/{id}/          posts-detail
PUT       /api/posts/{id}/          posts-update
DELETE    /api/posts/{id}/          posts-delete
POST      /api/posts/{id}/publish/  posts-publish
```

Options:
```bash
aksara routes --format json
aksara routes --filter posts
```

### generate sdk

Generate a TypeScript client from discovered `ModelViewSet` classes:

```bash
aksara generate sdk --language typescript --output frontend/api.ts
```

Print the generated SDK to stdout:

```bash
aksara generate sdk --language typescript --stdout
```

Target a specific views module instead of auto-discovery from installed apps:

```bash
aksara generate sdk --language typescript --views-module myapp.viewsets --stdout
```

The generated SDK includes resolved create, update, and read interfaces, typed list parameters, and a fetch-based `AksaraClient` with CRUD methods.

### info

Show project information:

```bash
aksara info
```

Output:
```
Aksara Project Information
==========================
Version: 0.6.0rc1
Python: 3.11.0
Database: postgresql://localhost/mydb

Apps:
  - blog (3 models)
  - users (2 models)

Models:
  - blog.Post
  - blog.Comment
  - blog.Tag
  - users.User
  - users.Profile

Migrations:
  - 5 applied
  - 0 pending
```

---

## AI Commands

See [AI Commands](ai-commands.md) for detailed documentation.

### ai query

Query data using natural language:

```bash
aksara ai query "Users who signed up this week"
```

### ai generate

Generate code from descriptions:

```bash
aksara ai generate model "BlogPost with title, content, author FK"
```

### ai doctor

Analyze schema for issues:

```bash
aksara ai doctor
```

### ai plan

Create multi-step plans:

```bash
aksara ai plan "Add tagging system to posts"
```

---

## Configuration

### Settings File

The CLI looks for settings in:

1. `AKSARA_SETTINGS` environment variable
2. `settings.py` in current directory
3. `{project}/settings.py`

### Environment Variables

```bash
export AKSARA_SETTINGS=myproject.settings
export AKSARA_DEBUG=true
export DATABASE_URL=postgresql://localhost/mydb
```

---

## Output Formatting

### JSON Output

Many commands support JSON output:

```bash
aksara routes --format json
aksara info --format json
aksara ai doctor --output report.json
```

### Global Output Controls

These flags apply to the entire CLI, so place them before the command name:

```bash
aksara --quiet migrate
aksara --plain dev
aksara --no-color info
aksara --force-color dev
```

`--quiet` suppresses non-error Aksara UI output such as banners, progress lines, and success summaries. It does not suppress subprocess or Uvicorn logs. `--plain` disables Rich rendering and animation. `--no-color` removes ANSI color, and `--force-color` forces colored output when supported.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Configuration error |
| 4 | Database error |
| 5 | Migration error |

Use in scripts:

```bash
aksara migrate && echo "Migration successful"
```

---

## Aliases

Create shell aliases for common commands:

```bash
# ~/.bashrc or ~/.zshrc
alias vr='aksara run'
alias vm='aksara migrate'
alias vmm='aksara makemigrations'
alias vs='aksara shell'
```

---

## Related Documentation

- [Commands Reference](commands.md) — All commands
- [Dev Tools](dev-tools.md) — Development utilities
- [AI Commands](ai-commands.md) — AI features
- [Extending](extending.md) — Custom commands
