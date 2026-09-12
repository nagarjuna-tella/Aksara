# Authentication and Principals

For application setup, follow [authentication and request identity](../api/authentication.md)
and the [permissions guide](../api/permissions.md). They explain credential
verification, the required request state and synchronous permission hooks.
This page describes the security model; its identity labels do not install an
authentication adapter. See [application boundaries](../concepts/application-boundaries.md)
for the relationship between Principal, policy, tenancy and delayed work.

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

These are identity labels represented by the security model, not a list of
automatically installed credential validators:

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
auth token or the supported staff-session path. See
[Studio configuration](../studio/configuration.md) for exact authentication and
Origin rules.

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

Claim normalization is not signature verification. Authenticate the credential
with a trusted verifier before converting its claims into a principal; never
treat a client-supplied claims dictionary as proof of identity.

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
- The execution contract covers claims enforced on generated REST and MCP
  execution paths. Applications remain responsible for issuing, rotating, and
  revoking tokens.
- The `/mcp/` endpoint authenticates and authorizes protocol requests at
  execution time. Its session and replay state is process-local and does not
  provide durable or cross-worker continuity. `/ai/tools/mcp` remains an
  inspection catalog.
