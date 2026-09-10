# MCP quickstart

Aksara turns registered, AI-exposed ViewSets into real MCP tools over
Streamable HTTP.

## Enable the server

```python
from aksara import Aksara, configure

configure(mcp_enabled=True, mcp_token_audience="my-app")
app = Aksara()
```

Start the app and connect an MCP client to:

```text
http://127.0.0.1:8000/mcp/
```

Authentication middleware must resolve the bearer credential into an MCP
`Principal` with a tenant, expiry, audience, token ID, agent and owner identity,
and explicit scopes. A model named `Ticket` uses `mcp:read:ticket` for GET tools
and `mcp:write:ticket` for mutations.

The server negotiates the protocol, lists generated CRUD tools and schemas,
and executes calls through the same generated API, permissions, `PolicyEngine`,
ORM validation, transaction, tenancy, and RLS path used by REST.

The inspection catalog remains available at:

```bash
curl -H "Authorization: Bearer $APP_TOKEN" \
  http://127.0.0.1:8000/ai/tools/mcp
```

Before production use, review `ai_sensitive` and `ai_agent_writable` on every
exposed field and run `aksara doctor production-check --release`.

See [MCP protocol server](../ai-mode/mcp.md) for approval, audit, errors,
transport settings, and stability limits.
