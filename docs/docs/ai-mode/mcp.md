# MCP catalog and REST execution

Aksara exposes a permission-filtered, MCP-shaped tool catalog at
`GET /ai/tools/mcp`. The generic Aksara representation remains available at
`GET /ai/tools`.

## Protocol boundary

The catalog is JSON shaped like an MCP tool description. It is not an MCP
protocol server. Aksara v0.6 does not implement MCP transport negotiation,
client sessions, protocol tool invocation, or protocol conformance testing.

An external MCP client needs an adapter with two responsibilities:

1. Fetch and translate the catalog into the client's tool-registration API.
2. Invoke each catalog entry's HTTP method and path as an authenticated REST
   request.

The REST request then passes through the same application permissions, payload
policy, tenant context, and PostgreSQL RLS as any other generated API request.

## Catalog shape

```bash
curl -H "Authorization: Bearer $APP_TOKEN" \
  http://127.0.0.1:8000/ai/tools/mcp
```

A catalog response has this shape:

```json
{
  "tools": [
    {
      "name": "ticket_update",
      "description": "Update a support ticket",
      "inputSchema": {
        "type": "object",
        "properties": {
          "status": {"type": "string"}
        },
        "required": []
      },
      "metadata": {
        "http_method": "PATCH",
        "path": "/api/tickets/{pk}",
        "kind": "update",
        "requires_auth": true
      }
    }
  ],
  "count": 1,
  "version": "0.6.0rc1"
}
```

Registered models, ViewSets, custom `@action` methods, route metadata,
permissions, and AI field annotations determine which entries a caller sees.
The method's docstring and type hints contribute to custom-action schemas.

## Credential and authorization requirements

Catalog schemas are descriptive and are never an authorization control. Resolve
credentials into a server-owned `Principal`, then enforce:

- explicit per-operation scopes
- a service audience
- a tenant claim for multi-tenant operations
- an expiry
- field policy at execution time
- database isolation with a restricted role and forced RLS

Relevant framework helpers include `MCPCredentialClaims`,
`principal_from_mcp_claims()`, `require_scope()`,
`require_mcp_audience()`, and `require_mcp_tenant()`.

`ai_sensitive=True` removes a field from generated AI context.
`ai_agent_writable=False` rejects an AI/MCP principal's attempt to write that
field on covered generated paths. Review every exposed field explicitly before
setting `AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true` for release diagnostics.

The packaged `examples/support_desk` app demonstrates a same-tenant
catalog-described mutation, denial of the same operation across tenants,
scoped and expiring claims, and Doctor release configuration.

## Stable and experimental pieces

The catalog fields and catalog-described generated REST execution boundary are
part of the v0.6 production contract. Generic/OpenAI/third-party adapters and
autonomous agent orchestration remain experimental. See the
[stability and production contract](../roadmap/v0-6-stability-contract.md).
