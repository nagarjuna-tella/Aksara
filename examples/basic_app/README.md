# Aksara Example: Basic App

This example demonstrates:
- Models
- ViewSets
- Migrations
- Studio
- MCP tools
- AI Console usage

Smallest working Aksara app. It includes `User`, `Post`, and `Article` models, ViewSet-generated APIs, one committed migration, Studio routes, and MCP tool export.

## Run

```bash
cd examples/basic_app
python -m venv .venv
source .venv/bin/activate
pip install -e ../..
aksara doctor launch-check
aksara migrate
aksara dev
```

Set `DATABASE_URL` if your local PostgreSQL credentials differ from the development default:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aksara_example"
```

## Seed

No seed command is required. Create a first user through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","name":"Demo User"}'
```

## Open

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* MCP: http://127.0.0.1:8000/ai/tools/mcp

## Test API

```bash
curl http://127.0.0.1:8000/api/users/
curl http://127.0.0.1:8000/api/posts/
curl http://127.0.0.1:8000/health
```

## Test MCP

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

Confirm the catalog includes tools for the `User` and `Post` ViewSets.

## Try in AI Console

Ask:

```text
Explain the User model
Review the basic app architecture
Investigate this project
```

AI provider setup is optional for first launch. Non-AI Studio tools, API docs, and MCP inspection do not require OpenAI, Anthropic, Azure, or Ollama.
