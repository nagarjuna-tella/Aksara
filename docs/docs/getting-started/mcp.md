# MCP Quickstart

Aksara exports your model and ViewSet surface as MCP-compatible tools.

## Where the Catalog Lives

```text
http://127.0.0.1:8000/ai/tools/mcp
```

Inspect it locally:

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

## How Tools Are Generated

Aksara reads:

- Registered models
- ViewSets
- Custom `@action` methods
- Field metadata such as `ai_description`
- Safety metadata such as `ai_sensitive` and `ai_agent_writable`

The result is a tool catalog that external MCP clients can inspect before calling your API.

## Inspect MCP Output

Start the app:

```bash
aksara dev
```

Then run:

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

Confirm sensitive fields are omitted and read-only fields are marked correctly.

## Connect an External MCP Client Later

Use the catalog URL from your running Aksara app:

```text
http://127.0.0.1:8000/ai/tools/mcp
```

For production deployments, add authentication and review which actions should be exposed before connecting external clients.
