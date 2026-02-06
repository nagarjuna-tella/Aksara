# Aksara Basic Example (v0.5.5)

A FastAPI application demonstrating Aksara ORM with all v0.2-v0.5.5 features.

## Project Structure

```
basic_app/
├── __init__.py          # Package init
├── main.py              # FastAPI application with ViewSets
├── models.py            # Model definitions (single source of truth)
├── settings.py          # Aksara settings configuration
├── migrations/          # Database migrations
│   ├── __init__.py
│   ├── 0001_initial.sql
│   ├── 0002_add_posts.sql
│   └── 0003_add_articles.sql
└── README.md
```

## Setup

1. Make sure you have PostgreSQL running locally
2. Create a database:
   ```bash
   createdb aksara_example
   ```

3. Install dependencies:
   ```bash
   cd /path/to/aksara
   pip install -e ".[dev]"
   ```

4. Set database URL:
   ```bash
   export DATABASE_URL="postgresql://postgres:password@localhost:5432/aksara_example"
   ```

5. Apply migrations using Aksara CLI:
   ```bash
   cd examples/basic_app
   aksara migrate --migrations-dir migrations
   ```

   Or generate new migrations from models:
   ```bash
   aksara makemigrations --app models --name initial --output migrations
   aksara migrate --migrations-dir migrations
   ```

   Check migration status:
   ```bash
   aksara status
   ```

## Running the App

```bash
cd examples/basic_app
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## URLs

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | API Documentation (Swagger UI) |
| http://localhost:8000/admin | Admin Interface (debug mode) |
| http://localhost:8000/studio/ui | Studio Dashboard (v0.5.0+) |
| http://localhost:8000/ai/tools | AI Tools Discovery (v0.4.0+) |
| http://localhost:8000/health | Health Check |

### v0.3 ViewSet-generated CRUD (Recommended!)

**Users (`/api/users/`)**
- `GET /api/users/` - List users (with pagination)
- `POST /api/users/` - Create user
- `GET /api/users/{id}` - Get user
- `PATCH /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user

**Posts (`/api/posts/`)**
- `GET /api/posts/` - List posts (with pagination)
- `POST /api/posts/` - Create post
- `GET /api/posts/{id}` - Get post
- `PATCH /api/posts/{id}` - Update post
- `DELETE /api/posts/{id}` - Delete post

### v0.3.1 Custom Actions (NEW!)

**User Actions**
- `POST /api/users/{pk}/deactivate` - Deactivate user
- `POST /api/users/{pk}/activate` - Activate user
- `GET /api/users/active` - List active users only
- `GET /api/users/stats` - Get user statistics

**Post Actions**
- `POST /api/posts/{pk}/publish` - Publish post
- `POST /api/posts/{pk}/unpublish` - Unpublish post
- `GET /api/posts/published` - List published posts
- `POST /api/posts/{pk}/view` - Increment view count

### Legacy Manual Endpoints (for comparison)

- `POST /users`, `GET /users`, `GET /users/{id}`, etc.
- `POST /posts`, `GET /posts`, `GET /posts/{id}`

### AI Schema Endpoints (v0.2)

- `GET /ai/schema` - Get all AI-exposed model schemas
- `GET /ai/schema/{model}` - Get specific model schema

### Health

- `GET /health` - Check database connection

## Example Usage

```bash
# v0.3 CRUD via ViewSets
curl http://localhost:8000/api/users/

# v0.3.1 Custom actions
curl http://localhost:8000/api/users/stats
curl http://localhost:8000/api/users/active
curl -X POST http://localhost:8000/api/users/{id}/deactivate

# Create a user
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}'

# Create a post with author
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello World", "content": "My first post!", "author_id": "USER_ID"}'

# Publish the post
curl -X POST http://localhost:8000/api/posts/{id}/publish

# Get published posts
curl http://localhost:8000/api/posts/published
```

## Features Demonstrated

### v0.3.1
- `@action(detail=True)` - Actions on specific items (`/{pk}/action`)
- `@action(detail=False)` - Collection-level actions (`/action`)
- Full Swagger/OpenAPI documentation for custom actions

### v0.3
- `ModelViewSet` - Auto-generated CRUD endpoints
- `include_viewset()` - Wire ViewSets to FastAPI routers
- Auto-generated Pydantic schemas from models

### v0.2
- Centralized settings with env var support
- ForeignKey relationships
- AI metadata on models and fields
- Query lookups (`__gt`, `__gte`, `__lt`, `__lte`, `__in`, `__isnull`, `__icontains`)
- Custom exceptions with proper error mapping

## Interactive Docs

Visit http://localhost:8000/docs for Swagger UI documentation with full action support!
