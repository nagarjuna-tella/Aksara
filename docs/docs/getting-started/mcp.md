# MCP-shaped tool catalog

Aksara can describe registered model and ViewSet operations as an MCP-shaped
JSON catalog.

## Supported boundary

```text
GET http://127.0.0.1:8000/ai/tools/mcp
```

The response contains permission-filtered tool names, descriptions, JSON input
schemas, and HTTP method/path metadata. Aksara v0.6 does not provide an MCP
protocol server, transport negotiation, or a protocol tool-call endpoint. An
MCP client therefore needs an adapter that reads this catalog and invokes the
described REST route.

## Inspect the catalog

Start the app, authenticate as required by your application, and fetch the
catalog:

```bash
aksara dev
curl -H "Authorization: Bearer $APP_TOKEN" \
  http://127.0.0.1:8000/ai/tools/mcp
```

Aksara derives entries from registered ViewSets and custom `@action` methods.
Field metadata such as `ai_description`, `ai_sensitive`, and
`ai_agent_writable` affects generated schemas and runtime write policy.

Before enabling the catalog in production:

1. Resolve the credential to a server-owned `Principal`.
2. Require explicit scopes, audience, tenant binding, and expiry.
3. Review every AI-exposed model field and set `ai_agent_writable` explicitly.
4. Execute the described REST operation through normal authentication,
   permission, field-policy, and RLS checks.
5. Run `aksara doctor production-check --release`.

See the [MCP integration boundary](../ai-mode/mcp.md) and the
[production contract](../roadmap/v0-6-stability-contract.md).
