# Blog Example

A complete blogging backend demonstrating real-world Aksara patterns.

## Features

- **Post model** with:
  - Title, slug, content, excerpt
  - Tags as JSON array
  - Publish workflow (draft → published)
  - View counter
  - Timestamps

- **Comment model** with:
  - Foreign key to Post
  - Author name and email
  - Moderation (approve/reject)

- **API endpoints**:
  - `GET /api/posts/` - List posts
  - `POST /api/posts/` - Create post
  - `GET /api/posts/{id}/` - Get post
  - `PUT /api/posts/{id}/` - Update post
  - `DELETE /api/posts/{id}/` - Delete post
  - `POST /api/posts/{id}/publish/` - Publish post
  - `POST /api/posts/{id}/view/` - Increment views
  - `GET /api/posts/published/` - List published only
  - `GET /api/posts/by_tag/?tag=python` - Filter by tag

- **Admin panel** at `/admin/`
- **Studio** at `/studio/ui`
- **AI Tools** at `/ai/tools`

## Quick Start

```bash
# Navigate to blog example
cd examples/blog

# Set database URL
export DATABASE_URL=postgresql://postgres:password@localhost:5432/aksara_blog

# Create database
createdb aksara_blog

# Run migrations
aksara makemigrations --app examples.blog.models
aksara migrate

# Create admin user (optional)
aksara createsuperuser

# Start server
uvicorn examples.blog.main:app --reload
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Welcome page |
| `/docs` | API documentation |
| `/admin/` | Admin panel |
| `/studio/ui` | Studio dashboard |
| `/ai/tools` | AI tools discovery |
| `/api/posts/` | Posts CRUD |
| `/api/comments/` | Comments CRUD |

## Example Requests

### Create a post

```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "slug": "my-first-post",
    "content": "Hello, world!",
    "tags": ["intro", "tutorial"]
  }'
```

### Publish a post

```bash
curl -X POST http://localhost:8000/api/posts/{id}/publish/
```

### Add a comment

```bash
curl -X POST http://localhost:8000/api/comments/ \
  -H "Content-Type: application/json" \
  -d '{
    "post_id": "<post-uuid>",
    "author_name": "Reader",
    "text": "Great post!"
  }'
```

## AI Integration

This example is fully integrated with Aksara AI Mode:

- Models are exposed via `/ai/tools`
- Studio provides AI context at `/studio/ai/context`
- ViewSet actions available as AI tools

Use with any LLM that supports function calling or tool use.
