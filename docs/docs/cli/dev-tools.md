# Dev Tools

Development utilities and productivity features.

---

## Overview

Aksara includes developer tools for:

- **Code generation** — Models, viewsets, tests
- **Debugging** — Error pages, query profiling
- **Analysis** — Route listing, model info
- **Scaffolding** — Apps, migrations

---

## Code Generation

### Generate Model

```bash
aksara generate model Post --fields "title:string:200 content:text author:fk:User"
```

Creates:
```python
class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    author = fields.ForeignKey("User", on_delete=fields.CASCADE)
```

**Field syntax:**
```
name:type[:options]
```

**Field types:**
| Type | Example |
|------|---------|
| `string` | `title:string:200` |
| `text` | `content:text` |
| `int` | `count:int` |
| `decimal` | `price:decimal:10:2` |
| `bool` | `is_active:bool` |
| `datetime` | `published_at:datetime` |
| `fk` | `author:fk:User` |
| `m2m` | `tags:m2m:Tag` |
| `uuid` | `external_id:uuid` |
| `json` | `metadata:json` |

---

### Generate ViewSet

```bash
aksara generate viewset Post
```

Creates:
```python
from aksara.api import ModelViewSet
from .models import Post
from .serializers import PostSerializer

class PostViewSet(ModelViewSet):
    model = Post
    serializer_class = PostSerializer
```

**Options:**
```bash
aksara generate viewset Post --actions list,create,retrieve
aksara generate viewset Post --pagination
aksara generate viewset Post --search title,content
```

---

### Generate Serializer

```bash
aksara generate serializer Post
```

Creates:
```python
from aksara.api import ModelSerializer
from .models import Post

class PostSerializer(ModelSerializer):
    class Meta:
        model = Post
        fields = ["id", "title", "content", "author", "created_at"]
```

---

### Generate Test

```bash
aksara generate test Post
```

Creates:
```python
import pytest
from aksara.testing import AksaraTestCase
from .models import Post

class TestPost(AksaraTestCase):
    async def test_create_post(self):
        post = await Post.objects.create(
            title="Test Post",
            content="Test content",
        )
        assert post.id is not None

    async def test_update_post(self):
        ...

    async def test_delete_post(self):
        ...
```

**Options:**
```bash
aksara generate test Post --type api    # API tests
aksara generate test Post --type model  # Model tests (default)
aksara generate test Post --type full   # Both
```

---

### Generate CRUD

Generate model, serializer, viewset, and tests together:

```bash
aksara generate crud Post --fields "title:string:200 content:text"
```

Creates:
- `models.py` — Post model
- `serializers.py` — PostSerializer
- `viewsets.py` — PostViewSet
- `tests/test_post.py` — Tests

---

## Project Analysis

### List Routes

```bash
aksara routes
```

Output:
```
Method    Path                      Name              ViewSet
--------  ------------------------  ----------------  -----------
GET       /api/posts/               posts-list        PostViewSet
POST      /api/posts/               posts-create      PostViewSet
GET       /api/posts/{id}/          posts-detail      PostViewSet
PUT       /api/posts/{id}/          posts-update      PostViewSet
DELETE    /api/posts/{id}/          posts-delete      PostViewSet
POST      /api/posts/{id}/publish/  posts-publish     PostViewSet
```

**Filtering:**
```bash
aksara routes --filter posts
aksara routes --method GET
aksara routes --format json
```

---

### List Models

```bash
aksara models
```

Output:
```
App      Model      Fields    Relations
-------  ---------  --------  -----------
blog     Post       8         2 FK, 1 M2M
blog     Comment    5         2 FK
blog     Tag        3         0
users    User       10        0
users    Profile    6         1 FK
```

**Detailed view:**
```bash
aksara models --app blog --detail
```

Output:
```
blog.Post
  Fields:
    - id: UUID (primary_key)
    - title: String (max_length=200)
    - content: Text
    - author: ForeignKey -> User
    - tags: ManyToMany -> Tag
    - created_at: DateTime (auto_now_add)
    - updated_at: DateTime (auto_now)
  
  Indexes:
    - title (unique)
    - created_at
```

---

### Show Settings

```bash
aksara settings
```

Output:
```
Current Settings:
  DEBUG: True
  DATABASE_URL: postgresql://localhost/mydb
  INSTALLED_APPS: ['blog', 'users']
  AI_MODE: True
```

**Filter by prefix:**
```bash
aksara settings --prefix AI_
```

---

### Check Project

```bash
aksara check
```

Output:
```
✓ Settings loaded
✓ Database connection OK
✓ All migrations applied
✓ Models valid
⚠ Debug mode enabled (not for production)

Checks passed: 4
Warnings: 1
Errors: 0
```

**Deployment checks:**
```bash
aksara check --deploy
```

Checks for:
- Debug mode off
- Secret key set
- Allowed hosts configured
- SSL configured
- Etc.

---

## Development Server

### Enhanced Run

```bash
aksara run main:app
```

Features:
- **Auto-reload** — Restarts on file changes (with `--reload`)
- **Error overlay** — Rich error pages
- **Query logging** — See SQL queries
- **Request logging** — HTTP request details

**Options:**
```bash
aksara run main:app --port 3000
aksara run main:app --host 0.0.0.0
aksara run main:app --reload
aksara run main:app --workers 4
```

---

### Watch Mode

Separate file watcher with custom commands:

```bash
aksara watch --command "pytest tests/"
```

Runs pytest whenever Python files change.

**Multiple commands:**
```bash
aksara watch \
  --command "aksara check" \
  --command "pytest tests/ -x"
```

---

## Database Tools

### Show Migration Status

```bash
aksara status
```

Output:
```
📁 Migrations directory: migrations
📊 Applied migrations: 2

  [X] 0001_auto_initial
  [X] 0002_auto_add_post_slug
  [ ] 0003_auto_add_post_views
```

---

### Preview Migration

```bash
aksara migrate --dry-run
```

Output:
```
[DRY RUN] Would apply: 0003_auto_add_post_views
    → AddField post.views Integer
CREATE INDEX blog_post_slug ON blog_post(slug);
COMMIT;
```

---

### Dump Data

```bash
aksara dumpdata blog.Post --output posts.json
```

**Options:**
```bash
aksara dumpdata --all --output backup.json
aksara dumpdata blog --indent 2
aksara dumpdata --format yaml
```

---

### Load Data

```bash
aksara loaddata fixtures.json
```

---

## Shell Enhancements

### Enhanced Shell

```bash
aksara shell
```

Pre-loaded:
- All models
- Common utilities
- Async support

```python
>>> posts = await Post.objects.filter(is_published=True).all()
>>> for post in posts[:5]:
...     print(post.title)
```

### Shell Plus

```bash
aksara shell_plus
```

Additional features:
- Auto-import all models
- Pretty printing
- History persistence
- Tab completion

---

## Debugging Tools

### SQL Logging

Enable detailed SQL logging by setting DEBUG=True in settings:

```python
# settings.py
AKSARA = {
    "DEBUG": True,
    "SQL_LOG": True,  # Log all SQL queries
}
```

Output:
```
[SQL] SELECT * FROM posts WHERE is_published = true (12ms)
[SQL] SELECT * FROM users WHERE id = 'abc-123' (3ms)
```

---

### Profile Request

Profile a specific endpoint:

```bash
aksara profile /api/posts/
```

Output:
```
Profile: GET /api/posts/

Total time: 145ms

Breakdown:
  Database: 89ms (15 queries)
  Python: 45ms
  Serialization: 11ms

Slowest queries:
  1. SELECT * FROM posts... (45ms)
  2. SELECT * FROM users... (12ms)
```

---

### Query Count

Check query count for endpoints:

```bash
aksara querycount /api/posts/
```

Output:
```
Endpoint: GET /api/posts/

Queries: 15
  - SELECT: 12
  - INSERT: 0
  - UPDATE: 0
  - DELETE: 0

Potential N+1: Yes (12 similar queries to users table)
```

---

## Scaffolding

### New App

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
├── admin.py
├── urls.py
└── tests/
    ├── __init__.py
    ├── test_models.py
    └── test_api.py
```

---

### New Migration

```bash
aksara makemigrations --empty --name populate_data
```

Creates empty migration for data operations:

```python
async def forwards(apps, schema_editor):
    # Add your data migration here
    pass

async def backwards(apps, schema_editor):
    # Add reverse migration here
    pass

class Migration:
    dependencies = [("blog", "0002_add_slug")]
    operations = [
        RunPython(forwards, backwards),
    ]
```

---

## Configuration

### Dev Tools Settings

```python
# settings.py
AKSARA = {
    "DEV_TOOLS": {
        "SQL_LOGGING": True,
        "SQL_LOG_LEVEL": "DEBUG",
        "QUERY_WARNINGS": True,
        "QUERY_WARNING_THRESHOLD": 100,  # ms
        "PROFILE_REQUESTS": False,
    },
}
```

---

## Related Documentation

- [CLI Overview](index.md)
- [Commands](commands.md)
- [AI Commands](ai-commands.md)
- [Debugging](../debugging/index.md)
