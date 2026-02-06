# CLI

Command-line interface for Aksara development.

---

## Overview

The Aksara CLI provides commands for:

| Category | Commands |
|----------|----------|
| **Project** | `startproject`, `startapp` |
| **Database** | `makemigrations`, `migrate`, `shell` |
| **Development** | `run`, `routes`, `info` |
| **AI** | `ai query`, `ai generate`, `ai doctor` |

---

## Quick Start

### Installation

The CLI is included with Aksara:

```bash
pip install aksara
```

### Basic Usage

```bash
# Show help
aksara --help

# Show version
aksara --version

# Run a command
aksara run main:app
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
aksara makemigrations --app blog        # Specific app
aksara makemigrations --name add_slug   # Custom name
aksara makemigrations --empty           # Empty migration
aksara makemigrations --dry-run         # Preview only
```

### migrate

Apply pending migrations:

```bash
aksara migrate
```

Output:
```
Applying blog.0001_initial... OK
Applying blog.0002_add_post_slug... OK
```

Options:
```bash
aksara migrate --app blog               # Specific app
aksara migrate blog 0001                # Migrate to specific version
aksara migrate --fake                   # Mark as applied without running
aksara migrate --plan                   # Show migration plan
```

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
aksara shell --ipython    # Use IPython if available
aksara shell --bpython    # Use bpython if available
```

---

## Development Commands

### run

Start the development server:

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

### info

Show project information:

```bash
aksara info
```

Output:
```
Aksara Project Information
==========================
Version: 0.4.11
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

### Quiet Mode

Suppress non-essential output:

```bash
aksara migrate --quiet
```

### Verbose Mode

Show more details:

```bash
aksara migrate --verbose
aksara makemigrations --verbose
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
