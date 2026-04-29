# MCP Integration

Aksara can expose your models and routes as MCP-compatible tools without a second service or a hand-written tool manifest. When your app is running, the tool catalog is available at `/ai/tools/mcp` and the generic JSON export remains available at `/ai/tools`.

---

## What MCP Gets You

The MCP export turns the same metadata Aksara uses for Studio and AI flows into a format that MCP-aware clients can consume directly. That means an agent can discover tool names, read descriptions, inspect JSON schemas for inputs, and understand which tools are read-only versus write-capable.

Use the MCP endpoint when you want an external AI client to work against your live Aksara app instead of a copied prompt or static schema dump.

---

## Quick Start

Start your app:

```bash
aksara dev
```

Open the MCP export in your browser or with `curl`:

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

You will receive a response shaped like this:

```json
{
  "tools": [
    {
      "name": "list_tasks",
      "description": "List Task records",
      "inputSchema": {
        "type": "object",
        "properties": {}
      },
      "metadata": {
        "method": "GET",
        "path": "/api/tasks",
        "usage_kind": "read_only"
      }
    }
  ],
  "count": 1,
  "version": "0.4.0"
}
```

---

## How Tools Are Derived

Aksara builds MCP tool definitions from the same application surface that powers the REST API and Studio. Models, viewsets, route metadata, permissions, and AI field annotations all affect what an external agent sees.

That gives you one source of truth. You define a model once, register a viewset once, and Aksara can expose that capability through HTTP, Studio, and MCP without duplicating configuration.

---

## AI Metadata Matters

The quality of the MCP export depends on the metadata attached to your fields and routes.

Use `ai_description` to make field purpose obvious to external agents. Use `ai_sensitive=True` to keep secrets and internal-only values out of exported context. Use `ai_agent_writable=False` when a field should be visible but never changed by an agent.

For route-level control, pair MCP exposure with Aksara's AI permissions and route hints so tool discovery stays aligned with your application's safety rules.

---

## MCP vs Generic Tool Export

Use `/ai/tools` when you want Aksara's generic JSON representation of tool definitions. Use `/ai/tools/mcp` when the consumer expects MCP-shaped tools with `inputSchema` and transport metadata.

Both endpoints are derived from the same underlying tool registry, so the tool count and permissions stay in sync.

---

## Related Docs

- [AI Mode](index.md)
- [Tools](tools.md)
- [Providers](providers.md)
- [Fields](../orm/fields.md)
- [Studio API](../studio/api.md)