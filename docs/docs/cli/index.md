# CLI

Command-line interface for Vidyut development.

---

## Overview

The Vidyut CLI provides commands for:

| Category | Commands |
|----------|----------|
| **Project** | `startproject`, `startapp` |
| **Database** | `makemigrations`, `migrate`, `shell` |
| **Development** | `runserver`, `routes`, `info` |
| **AI** | `ai query`, `ai generate`, `ai doctor` |

---

## Quick Start

### Installation

The CLI is included with Vidyut:

```bash
pip install vidyut
```

### Basic Usage

```bash
# Show help
vidyut --help

# Show version
vidyut --version

# Run a command
vidyut runserver
```

---

## Project Commands

### startproject

Create a new Vidyut project:

```bash
vidyut startproject myproject
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
vidyut startproject myproject --directory /path/to/dir
vidyut startproject myproject --template minimal  # or "full", "api"
```

### startapp

Create a new app within your project:

```bash
vidyut startapp blog
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

### makemigrations

Generate migrations from model changes:

```bash
vidyut makemigrations
```

Output:
```
Migrations for 'blog':
  blog/migrations/0002_add_post_slug.py
    - Add field slug to post
```

Options:
```bash
vidyut makemigrations --app blog        # Specific app
vidyut makemigrations --name add_slug   # Custom name
vidyut makemigrations --empty           # Empty migration
vidyut makemigrations --dry-run         # Preview only
```

### migrate

Apply pending migrations:

```bash
vidyut migrate
```

Output:
```
Applying blog.0001_initial... OK
Applying blog.0002_add_post_slug... OK
```

Options:
```bash
vidyut migrate --app blog               # Specific app
vidyut migrate blog 0001                # Migrate to specific version
vidyut migrate --fake                   # Mark as applied without running
vidyut migrate --plan                   # Show migration plan
```

### shell

Interactive Python shell with models loaded:

```bash
vidyut shell
```

```python
>>> from blog.models import Post
>>> posts = await Post.objects.all()
>>> len(posts)
42
```

Options:
```bash
vidyut shell --ipython    # Use IPython if available
vidyut shell --bpython    # Use bpython if available
```

---

## Development Commands

### runserver

Start the development server:

```bash
vidyut runserver
```

Output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started reloader process
```

Options:
```bash
vidyut runserver --port 3000
vidyut runserver --host 0.0.0.0
vidyut runserver --reload           # Auto-reload on changes (default)
vidyut runserver --no-reload        # Disable auto-reload
vidyut runserver --workers 4        # Multiple workers
```

### routes

List all registered routes:

```bash
vidyut routes
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
vidyut routes --format json
vidyut routes --filter posts
```

### info

Show project information:

```bash
vidyut info
```

Output:
```
Vidyut Project Information
==========================
Version: 0.4.9
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
vidyut ai query "Users who signed up this week"
```

### ai generate

Generate code from descriptions:

```bash
vidyut ai generate model "BlogPost with title, content, author FK"
```

### ai doctor

Analyze schema for issues:

```bash
vidyut ai doctor
```

### ai plan

Create multi-step plans:

```bash
vidyut ai plan "Add tagging system to posts"
```

---

## Configuration

### Settings File

The CLI looks for settings in:

1. `VIDYUT_SETTINGS` environment variable
2. `settings.py` in current directory
3. `{project}/settings.py`

### Environment Variables

```bash
export VIDYUT_SETTINGS=myproject.settings
export VIDYUT_DEBUG=true
export DATABASE_URL=postgresql://localhost/mydb
```

---

## Output Formatting

### JSON Output

Many commands support JSON output:

```bash
vidyut routes --format json
vidyut info --format json
vidyut ai doctor --output report.json
```

### Quiet Mode

Suppress non-essential output:

```bash
vidyut migrate --quiet
```

### Verbose Mode

Show more details:

```bash
vidyut migrate --verbose
vidyut makemigrations --verbose
```

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
vidyut migrate && echo "Migration successful"
```

---

## Aliases

Create shell aliases for common commands:

```bash
# ~/.bashrc or ~/.zshrc
alias vr='vidyut runserver'
alias vm='vidyut migrate'
alias vmm='vidyut makemigrations'
alias vs='vidyut shell'
```

---

## Related Documentation

- [Commands Reference](commands.md) — All commands
- [Dev Tools](dev-tools.md) — Development utilities
- [AI Commands](ai-commands.md) — AI features
- [Extending](extending.md) — Custom commands
