# Dev Tools

Development utilities and productivity features.

---

## Overview

Vidyut includes developer tools for:

- **Code generation** — Models, viewsets, tests
- **Debugging** — Error pages, query profiling
- **Analysis** — Route listing, model info
- **Scaffolding** — Apps, migrations

---

## Code Generation

### Generate Model

```bash
vidyut generate model Post --fields "title:string:200 content:text author:fk:User"
```

Creates:
```python
class Post(Model):
    title = fields.StringField(max_length=200)
    content = fields.TextField()
    author = fields.ForeignKey("User", on_delete="CASCADE")
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
vidyut generate viewset Post
```

Creates:
```python
from vidyut.api import ModelViewSet
from .models import Post
from .serializers import PostSerializer

class PostViewSet(ModelViewSet):
    model = Post
    serializer_class = PostSerializer
```

**Options:**
```bash
vidyut generate viewset Post --actions list,create,retrieve
vidyut generate viewset Post --pagination
vidyut generate viewset Post --search title,content
```

---

### Generate Serializer

```bash
vidyut generate serializer Post
```

Creates:
```python
from vidyut.api import ModelSerializer
from .models import Post

class PostSerializer(ModelSerializer):
    class Meta:
        model = Post
        fields = ["id", "title", "content", "author", "created_at"]
```

---

### Generate Test

```bash
vidyut generate test Post
```

Creates:
```python
import pytest
from vidyut.testing import VidyutTestCase
from .models import Post

class TestPost(VidyutTestCase):
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
vidyut generate test Post --type api    # API tests
vidyut generate test Post --type model  # Model tests (default)
vidyut generate test Post --type full   # Both
```

---

### Generate CRUD

Generate model, serializer, viewset, and tests together:

```bash
vidyut generate crud Post --fields "title:string:200 content:text"
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
vidyut routes
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
vidyut routes --filter posts
vidyut routes --method GET
vidyut routes --format json
```

---

### List Models

```bash
vidyut models
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
vidyut models --app blog --detail
```

Output:
```
blog.Post
  Fields:
    - id: UUIDField (primary_key)
    - title: StringField (max_length=200)
    - content: TextField
    - author: ForeignKey -> User
    - tags: ManyToManyField -> Tag
    - created_at: DateTimeField (auto_now_add)
    - updated_at: DateTimeField (auto_now)
  
  Indexes:
    - title (unique)
    - created_at
```

---

### Show Settings

```bash
vidyut settings
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
vidyut settings --prefix AI_
```

---

### Check Project

```bash
vidyut check
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
vidyut check --deploy
```

Checks for:
- Debug mode off
- Secret key set
- Allowed hosts configured
- SSL configured
- Etc.

---

## Development Server

### Enhanced Runserver

```bash
vidyut runserver
```

Features:
- **Auto-reload** — Restarts on file changes
- **Error overlay** — Rich error pages
- **Query logging** — See SQL queries
- **Request logging** — HTTP request details

**Options:**
```bash
vidyut runserver --port 3000
vidyut runserver --host 0.0.0.0
vidyut runserver --no-reload
vidyut runserver --log-level debug
```

---

### Watch Mode

Separate file watcher with custom commands:

```bash
vidyut watch --command "pytest tests/"
```

Runs pytest whenever Python files change.

**Multiple commands:**
```bash
vidyut watch \
  --command "vidyut check" \
  --command "pytest tests/ -x"
```

---

## Database Tools

### Show Migrations

```bash
vidyut showmigrations
```

Output:
```
blog
  [X] 0001_initial
  [X] 0002_add_post_slug
  [ ] 0003_add_post_views

users
  [X] 0001_initial
```

---

### SQL for Migration

```bash
vidyut sqlmigrate blog 0002
```

Output:
```sql
BEGIN;
ALTER TABLE blog_post ADD COLUMN slug VARCHAR(200) NOT NULL;
CREATE INDEX blog_post_slug ON blog_post(slug);
COMMIT;
```

---

### Dump Data

```bash
vidyut dumpdata blog.Post --output posts.json
```

**Options:**
```bash
vidyut dumpdata --all --output backup.json
vidyut dumpdata blog --indent 2
vidyut dumpdata --format yaml
```

---

### Load Data

```bash
vidyut loaddata fixtures.json
```

---

## Shell Enhancements

### Enhanced Shell

```bash
vidyut shell
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
vidyut shell_plus
```

Additional features:
- Auto-import all models
- Pretty printing
- History persistence
- Tab completion

---

## Debugging Tools

### SQL Logging

Enable detailed SQL logging:

```bash
vidyut runserver --sql-log
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
vidyut profile /api/posts/
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
vidyut querycount /api/posts/
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
vidyut startapp blog
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
vidyut makemigrations --empty --name populate_data
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
VIDYUT = {
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
