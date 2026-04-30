# Blog Example

A complete blogging backend demonstrating real-world Aksara patterns.

## Features

- **Post model** with:
  - Title, slug, content, excerpt
  - Tags as JSON array
  - Publish workflow (draft → published)
  - View counter (`ai_agent_writable=False` — AI can read but not modify)
  - Timestamps

- **Comment model** with:
  - Foreign key to Post
  - Author name and email (`ai_sensitive=True` — excluded from AI context)
  - Moderation via `is_approved` (`ai_agent_writable=False` — humans moderate, not agents)

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

## AI Metadata Patterns

This template demonstrates three AI metadata attributes:

| Attribute | Used On | Why |
|-----------|---------|-----|
| `ai_description` | Every field | Tells the AI Console and MCP tool catalog what each field means |
| `ai_sensitive=True` | `Comment.author_email` | Excludes PII from AI context and MCP exports |
| `ai_agent_writable=False` | `Post.view_count`, `Comment.is_approved` | AI agents can read these fields but cannot modify them |

## Quick Start

```bash
# Navigate to blog example
cd examples/blog

# Set up database interactively
aksara dbsetup

# Run migrations
aksara makemigrations --app examples.blog.models
aksara migrate

# Create admin user (optional)
aksara createsuperuser

# Start server
aksara dev
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
