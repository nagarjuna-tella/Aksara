# Authentication and Principals

## Principal Model

Aksara represents actors through a centralized `Principal` object:

- Anonymous users
- Authenticated users
- AI agents
- MCP agents
- System tasks

`Principal` records user identity, tenant identity, roles, scopes, auth method,
agent ownership, token ID, expiration, and additional metadata.

## Auth Methods

The security model represents these auth methods:

- `anonymous`
- `session`
- `jwt`
- `api_key`
- `mcp_token`
- `ai_agent`
- `system`

Generated REST endpoints also use Aksara's permission classes, including
`AllowAny`, `IsAuthenticated`, `IsAdminUser`, `IsActiveUser`,
`IsOwnerOrReadOnly`, and `DenyAI`.

## Studio

Studio should not be exposed in production unless intentionally configured.
`studio_expose_in_production=False` and `studio_require_auth=True` are the safe
defaults. If Studio is exposed, it must require authentication and use a strong
auth token.

## MCP Credentials

MCP agents are represented as AI-agent principals with `auth_method="mcp_token"`.
MCP credential helpers support:

- Scope checks with `require_scope()`, `require_any_scope()`, and
  `require_all_scopes()`
- Audience checks with `require_mcp_audience()`
- Tenant binding with `require_mcp_tenant()`
- Expiration parsing through `MCPCredentialClaims`
- Token ID metadata through `token_id` or `jti`
- Claim normalization through `principal_from_mcp_claims()`

`PolicyEngine.can()` also accepts `required_scopes`, `required_audience`, and
`tenant_required` context for authorization decisions.

## Tenant Context

Raw tenant headers are not authoritative. Tenant identity should be established
by trusted middleware or server-side context, such as `request.state.tenant_id`
or a trusted request attribute.

Tenant-required operations fail closed when tenant context is missing for
non-system principals. System principals should use explicit trusted tenant
context for tenant-scoped work.

## Known Limitations

- Replay protection storage is not implemented by the core credential helpers.
- Scoped and audience-bound token issuance is not a complete core issuance
  system; applications should issue and rotate credentials carefully.
- The v0.6 production contract covers claims used on the generated REST path.
  Applications remain responsible for issuing, rotating, and revoking tokens.
- The `/ai/tools/mcp` endpoint is a catalog; protocol-level MCP authentication
  and sessions are not implemented.
