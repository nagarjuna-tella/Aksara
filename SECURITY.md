# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.5.x   | ✅ Yes    |
| < 0.5   | ❌ No     |

## Reporting a Vulnerability

Please report security issues by email rather than opening a public GitHub issue.
We aim to respond within 48 hours and issue a patch within 7 days.

---

## Security Fixes in v0.5.41

### S1 — AI Patch AST Validator (`aksara/ai/patch.py`)

Added `validate_patch_ast(content: str) -> Tuple[bool, str]` which parses
AI-generated code patches with `ast.parse` before applying them and rejects:

- Any `import` or `from ... import` statements
- Dangerous built-in calls: `eval`, `exec`, `compile`, `__import__`, `open`,
  `vars`, `dir`, `getattr`, `setattr`, `delattr`
- Dangerous attribute access: `__class__`, `__bases__`, `__subclasses__`,
  `__globals__`, `__builtins__`, `__dict__`

A `PatchRejectedError` (subclass of `AksaraError`) is raised when a patch
fails validation.

### S2 — Studio Origin & Authentication (`aksara/studio/fastapi.py`)

Split studio protection into two independent FastAPI router dependencies:

- `_check_studio_origin` — validates `Origin`/`Referer` headers, returns 403
  on mismatch (prevents CSRF from cross-origin requests)
- `verify_studio_auth` — checks session credentials, returns 401 when
  unauthenticated

### S3 — Signed Agent Tokens (`aksara/ai/auth.py`)

Added HMAC-SHA256 signed agent tokens using **stdlib only** (no third-party
JWT libraries):

- `sign_agent_token(agent_id, secret, *, ttl_seconds=300, extra=None) -> str`
- `verify_agent_token(token, secret, *, clock_skew_seconds=0) -> dict`

Token format: `header.payload.signature` (URL-safe base64, no padding).
`hmac.compare_digest` is used for constant-time signature comparison to
prevent timing attacks. Expired, future-dated, and tampered tokens all raise
`ValueError`.

### S4 — SQL Codegen Identifier Sanitization (`aksara/ai/codegen.py`)

Added strict input sanitization for AI-generated SQL:

- `sanitize_identifier(name: str) -> str` — validates table/column names
  against `^[a-zA-Z_][a-zA-Z0-9_]*$`, raising `ValueError` on invalid input
- `sanitize_column_type(type_str: str) -> str` — validates the base type
  against an allowlist (`_ALLOWED_COLUMN_TYPES`) of PostgreSQL types

These functions prevent SQL injection through AI-generated schema operations.

### A1 — LLM Client Audit (`aksara/ai/llm_clients/`)

Audited all LLM adapter modules. Confirmed all HTTP communication uses Python
stdlib `urllib` — no vendor SDK dependencies that could introduce supply-chain
risk or unexpected network behaviour.
