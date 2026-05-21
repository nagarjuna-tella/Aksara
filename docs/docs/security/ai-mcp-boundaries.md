# AI and MCP Security Boundaries

> **Status:** This document is part of the Aksara security-hardening milestone (Round 1).
> Some controls are implemented today; others are planned for upcoming rounds.

## Core Principle

**Generated schemas are not security controls. Runtime enforcement is required.**

When Aksara generates an MCP tool schema or an AI prompt pack, it filters out fields
marked `ai_sensitive=True` or `ai_agent_writable=False`. However, that schema is a
*hint* to clients — it is not enforced at the server.

A malicious or misconfigured client can send a payload containing forbidden fields,
and the server will currently accept them. Runtime enforcement (planned for Round 2)
will strip or reject forbidden fields regardless of what the schema says.

## Current Controls

### MCP disabled by default

`mcp_enabled=False` in `aksara/conf.py`. MCP tools are only active when explicitly
enabled via `AKSARA_MCP_ENABLED=true`.

### AI field metadata controls

Two field-level flags control AI surface exposure:

```python
# In model field definitions:
class Invoice(AksaraModel):
    internal_notes: str = Field(
        ai_sensitive=True,       # Exclude from AI/MCP schemas and prompt exports
        ai_agent_writable=False, # Mark as read-only for AI agents
    )
```

| Flag | Default | Meaning |
|------|---------|---------|
| `ai_sensitive` | `False` | If `True`, field is excluded from AI/MCP schemas and prompt packs |
| `ai_agent_writable` | `True` | If `False`, field should not be written by AI agents |

**Current enforcement:** Schema-time only. Forbidden fields are excluded from generated
schemas, but crafted payloads are not yet rejected at runtime.

### HMAC agent token authentication

AI/MCP agents must present an `X-Aksara-AI-Token` header containing a short-lived
HMAC-SHA256 token. Token format: `header.payload.signature` (compact JWS-style).
Default TTL: 300 seconds.

Tokens are validated by `AIAgentMiddleware` via `verify_agent_token()` in
`aksara/ai/auth.py`.

### `DenyAI` permission class

Routes or viewsets can apply `DenyAI` to block all AI agent access:

```python
from aksara.permissions import DenyAI

class SensitiveResource(AksaraViewSet):
    permission_classes = [IsAuthenticated, DenyAI]
```

## Known Gaps (as of Round 1)

| Gap | Severity | Planned Round |
|-----|----------|---------------|
| Runtime field enforcement | High | Round 2 |
| Per-tool MCP scope claims | High | Round 3 |
| Field-level audit logging (fields_requested / fields_allowed / fields_denied) | High | Round 2 |
| Audience-bound MCP tokens | Medium | Round 3 |
| Centralized policy engine for all surfaces | High | Round 2 |
| `ai_agent_writable=True` default (opt-out rather than opt-in) | Medium | Round 2 |

## Security Testing Matrix (current coverage)

| Scenario | Status |
|----------|--------|
| MCP enabled without auth → `production-check` blocks | Covered (Round 1) |
| `ai_sensitive` field excluded from MCP schema | Covered (schema-time) |
| `ai_agent_writable=False` excluded from MCP schema | Covered (schema-time) |
| Crafted payload with `ai_sensitive` field rejected at runtime | **Planned Round 2** |
| Crafted payload with `ai_agent_writable=False` field rejected | **Planned Round 2** |
| Cross-tenant access via MCP tool | **Planned Round 3** |
| Field-level audit trail per MCP call | **Planned Round 2** |

## Future Direction

The long-term design goal for Aksara's AI/MCP security:

1. **Deny-by-default in production mode.** `ai_exposed=False`, `ai_agent_writable=False`, `ai_sensitive=True` should be the production defaults. Developers must explicitly opt in.
2. **Scoped, short-lived credentials.** MCP tokens should carry per-tool scope claims (`mcp:read:invoice`, `mcp:update:invoice.status`) and `audience` binding.
3. **Runtime payload validation.** Every MCP tool call and REST write from an AI agent must be validated against a central policy engine, not just a generated schema.
4. **Audit logging.** Every tool call must log: actor, tool, tenant, fields_requested, fields_allowed, fields_denied, decision, and reason.

These controls are planned for Rounds 2–3 of the hardening milestone.
