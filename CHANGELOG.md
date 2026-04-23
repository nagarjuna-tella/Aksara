# Changelog

All notable changes to Aksara are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.5.41] — Security Hardening & AI Module Consolidation

### Security

- **S1** — Added `validate_patch_ast()` in `aksara/ai/patch.py` to reject
  AI-generated patches containing dangerous imports or built-in calls before
  application. Introduces `PatchRejectedError`.
- **S2** — Split Studio protection into two independent FastAPI dependencies:
  `_check_studio_origin` (403) and `verify_studio_auth` (401).
- **S3** — Added HMAC-SHA256 signed agent tokens in `aksara/ai/auth.py` using
  stdlib only. Constant-time comparison via `hmac.compare_digest`.
- **S4** — Added `sanitize_identifier()` and `sanitize_column_type()` in
  `aksara/ai/codegen.py` to prevent SQL injection through AI-generated schema
  operations.

### Refactoring

- **A1** — Audited `aksara/ai/llm_clients/`; confirmed all HTTP adapters use
  stdlib `urllib` with no vendor SDK dependencies.
- **A2** — Merged `aksara/ai/intent_engine_v2.py` content into
  `aksara/ai/intent_engine.py`. The `intent_engine_v2` module is now a
  backward-compatibility shim re-exporting all symbols. Updated
  `aksara/ai/__init__.py` and `aksara/ai/plan_builder.py` to import directly
  from `intent_engine`.

### Added

- `aksara/exceptions.py`: `ImproperlyConfigured(ConfigurationError)` for
  configuration-time errors distinct from runtime `ConfigurationError`.
- `aksara/ai/patch.py`: `validate_patch_ast()`, `PatchRejectedError`
- `aksara/ai/auth.py`: `sign_agent_token()`, `verify_agent_token()`
- `aksara/ai/codegen.py`: `sanitize_identifier()`, `sanitize_column_type()`,
  `IDENTIFIER_PATTERN`, `_ALLOWED_COLUMN_TYPES`
- `SECURITY.md`: Documents all security fixes and responsible disclosure policy

---

## [0.5.40] — Intent Engine v2, Investigation Continuation, Daily Briefing

- Intent Engine v2 (`aksara/ai/intent_engine_v2.py`) with structured
  classification, entity extraction, and confidence scoring
- Investigation continuation session management
- Daily briefing AI flow
- Studio authentication hardening (origin + session checks)
