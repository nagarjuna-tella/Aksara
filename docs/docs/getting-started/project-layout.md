# Project Layout

Learn the recommended directory structure for Aksara applications.

---

## Standard Project Structure

When you run `aksara startproject myproject`, you get:

```
myproject/
├── main.py                 # Application entry point
├── settings.py             # Aksara configuration
├── pyproject.toml          # Project metadata & dependencies
├── requirements.txt        # Pip requirements
├── .env                    # Environment variables (gitignored)
├── .gitignore              # Git ignore rules
├── .pre-commit-config.yaml # Pre-commit hooks
├── .editorconfig           # Editor configuration
├── README.md               # Project documentation
├── app/                    # Default application module
│   ├── __init__.py
│   ├── models.py           # Database models
│   ├── views.py            # ViewSets and API endpoints
│   ├── urls.py             # Route registration
│   └── serializers.py      # Request/response serializers
└── migrations/             # Database migrations
    └── (auto-generated)
```

---

## File Descriptions

### `main.py`

The application entry point. Initializes the `Aksara` app and registers routes:

```python
from aksara import Aksara
from app.urls import register_routes

import settings  # noqa: F401 — configures Aksara

app = Aksara(
    database_url=settings.DATABASE_URL,
    title="My Project",
    description="An Aksara application",
    enable_admin=True,
    debug=True,
)

# Register ViewSets from app/urls.py
register_routes(app)
```

### `settings.py`

Centralized configuration using environment variables:

```python
import os
from aksara import configure

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/myproject")
DEBUG = os.getenv("AKSARA_DEBUG", "false").lower() == "true"

configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    installed_apps=[
        "aksara.contrib.auth",
        "aksara.contrib.admin",
        "app",
    ],
)
```

### `app/models.py`

Define your database models:

```python
from aksara import Model, fields

class Article(Model):
    title = fields.String(max_length=200)
    slug = fields.String(max_length=200, unique=True)
    content = fields.Text()
    published = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)
```

### `app/views.py`

Define ViewSets for your API:

```python
from aksara.api import ModelViewSet
from app.models import Article

class ArticleViewSet(ModelViewSet):
    model = Article
    prefix = "/articles"
    tags = ["Articles"]
```

### `app/urls.py`

Register your ViewSets:

```python
from aksara import include_viewset
from app.views import ArticleViewSet

urlpatterns = [
    ArticleViewSet,
]

def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
```

### `app/serializers.py`

Custom serializers for complex validation:

```python
from aksara.api import ModelSerializer
from app.models import Article

class ArticleSerializer(ModelSerializer):
    class Meta:
        model = Article
        fields = ["id", "title", "slug", "content", "published"]
        read_only_fields = ["id"]
    
    def validate_slug(self, value):
        return value.lower().replace(" ", "-")
```

---

## Multi-App Structure

For larger projects, organize code into multiple apps:

```
myproject/
├── main.py
├── settings.py
├── apps/
│   ├── __init__.py
│   ├── blog/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── serializers.py
│   ├── users/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── serializers.py
│   └── products/
│       ├── __init__.py
│       ├── models.py
│       ├── views.py
│       ├── urls.py
│       └── serializers.py
└── migrations/
    ├── blog/
    ├── users/
    └── products/
```

Configure apps in `settings.py`:

```python
configure(
    installed_apps=[
        "aksara.contrib.auth",
        "aksara.contrib.admin",
        "apps.blog",
        "apps.users",
        "apps.products",
    ],
)
```

Create new apps using the CLI:

```bash
aksara startapp blog --directory apps
aksara startapp users --directory apps
```

---

## Adding New Apps

Use the `startapp` command to create a new app:

```bash
aksara startapp myapp
```

This creates:

```
myapp/
├── __init__.py
├── models.py
├── views.py
├── urls.py
└── serializers.py
```

Then register it in your settings:

```python
installed_apps=[
    # ... existing apps
    "myapp",
]
```

And include routes in `main.py`:

```python
from myapp.urls import register_routes as register_myapp
register_myapp(app)
```

---

## Migrations Directory

Migrations are stored in the `migrations/` directory:

```
migrations/
├── 0001_initial.py
├── 0002_add_article_slug.py
├── 0003_add_user_profile.py
└── __init__.py
```

Each migration file contains:

```python
# migrations/0001_initial.py
from aksara.migrations import Migration, operations

class Migration(Migration):
    dependencies = []
    
    operations = [
        operations.CreateTable(
            "articles",
            columns=[
                operations.UUID(primary_key=True),
                operations.String("title", max_length=200),
                operations.Text("content"),
            ],
        ),
    ]
```

---

## Static Files and Templates

For admin customization or static assets:

```
myproject/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
└── templates/
    └── admin/
        └── custom_base.html
```

Mount static files in `main.py`:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

---

## Tests Directory

Organize tests alongside or separate from your app code:

```
myproject/
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures
│   ├── test_models.py
│   ├── test_views.py
│   └── test_api.py
```

Example `conftest.py`:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
import pytest
from aksara.testing import TestClient, setup_test_database

@pytest.fixture
async def client():
    await setup_test_database()
    yield TestClient(app)
```

---

## Best Practices

### Keep Apps Focused

Each app should have a single responsibility:

- ✅ `blog` — Blog posts and categories
- ✅ `users` — User management
- ❌ `misc` — Random utilities (avoid this)

### Use Consistent Naming

| Component | Convention | Example |
|-----------|------------|---------|
| Apps | lowercase, singular | `blog`, `user`, `product` |
| Models | PascalCase, singular | `Article`, `User`, `Product` |
| ViewSets | PascalCase + ViewSet | `ArticleViewSet`, `UserViewSet` |
| Tables | lowercase, plural | `articles`, `users`, `products` |

### Environment-Specific Settings

Use different `.env` files for environments:

```
.env              # Local development (gitignored)
.env.example      # Template (committed)
.env.test         # Testing
.env.production   # Production (never commit!)
```

---

## Related Documentation

- [Settings](settings.md) — Configuration options
- [First App](first-app.md) — Build your first application
- [Multitenant Pattern](../patterns/multitenant.md) — Example of a larger application layout
