# Aksara Example: CRM

This example demonstrates:
- Models
- ViewSets
- Migrations
- Studio
- MCP tools
- AI Console usage

Business app pattern. It includes contacts/customers, companies, deals/opportunities, activities/tasks, status fields, and query examples for pipeline reporting.

## Run

```bash
cd examples/crm
python -m venv .venv
source .venv/bin/activate
pip install -e ../..
aksara doctor launch-check
aksara migrate
aksara dev
```

Set `DATABASE_URL` if your local PostgreSQL credentials differ from the development default:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aksara_crm"
```

## Seed

No seed command is required. Create a first customer and deal through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/customers/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","email":"hello@example.com","industry":"SaaS"}'
```

## Open

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* MCP: http://127.0.0.1:8000/ai/tools/mcp

## Test API

```bash
curl http://127.0.0.1:8000/api/customers/
curl http://127.0.0.1:8000/api/deals/
curl http://127.0.0.1:8000/api/deals/pipeline/
```

## Test MCP

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

Confirm the catalog includes customer, deal, and activity tools.

## Try in AI Console

Ask:

```text
Explain the CRM data model
Review the sales pipeline architecture
Investigate this project
```

AI provider setup is optional for first launch. Non-AI Studio tools and MCP inspection work without paid providers.
