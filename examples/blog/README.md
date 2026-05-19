# Aksara Example: Blog

This example demonstrates:
- Models
- ViewSets
- Migrations
- Studio
- MCP tools
- AI Console usage

Classic relational app. It includes author-style user data, posts, comments, category/tag metadata, relationships, filtering, Studio graph inspection, and AI Console explanation prompts.

## Run

```bash
cd examples/blog
python -m venv .venv
source .venv/bin/activate
pip install -e ../..
aksara doctor launch-check
aksara migrate
aksara dev
```

Set `DATABASE_URL` if your local PostgreSQL credentials differ from the development default:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aksara_blog"
```

## Seed

No seed command is required. Create a first post through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Hello Aksara","slug":"hello-aksara","content":"First post","tags":["intro"]}'
```

## Open

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* MCP: http://127.0.0.1:8000/ai/tools/mcp

## Test API

```bash
curl http://127.0.0.1:8000/api/posts/
curl http://127.0.0.1:8000/api/comments/
curl http://127.0.0.1:8000/api/posts/published/
```

## Test MCP

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

Confirm the catalog describes post/comment tools and marks sensitive fields as protected.

## Try in AI Console

Ask:

```text
Explain the BlogPost model
Review the blog architecture
Investigate this project
```

AI provider setup is optional for first launch. For local-first AI later, configure Ollama through AI Hub instead of committing provider secrets.
