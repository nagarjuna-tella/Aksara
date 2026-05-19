# Aksara Roadmap

Maintained by [Nagarjuna Tella](https://github.com/nagarjuna-tella).

> Updated May 2026

Aksara is public and pre-1.0. The near-term roadmap prioritizes trust, first-user success, and production readiness over feature sprawl.

---

## Current Stable Version

### v0.5.48 - Launch Hardening & Golden Path

- Added `aksara doctor launch-check` for first-run readiness.
- Added `aksara examples validate` for bundled example sanity checks.
- Promoted `basic_app`, `blog`, `crm`, `multitenant`, and `ai_providers` as golden-path examples.
- Refreshed README, getting-started docs, roadmap, and changelog for public launch clarity.
- Added packaging, docs, examples, launch-check, and no-secrets test coverage.
- Kept AI provider setup optional for first launch.

---

## Recent Releases

### v0.5.47 - ORM/Admin/Write-path/Security Stabilization

- Fixed AI metadata propagation across tool schemas, MCP export, and console prompt packs.
- Hardened ORM write paths for field conversion, bulk operations, and upsert behavior.
- Improved migration ordering and generated DDL correctness.
- Fixed API schema output and pagination behavior.
- Tightened Studio/auth and tenant/task handling.

### v0.5.46 - Packaging and Docs Release Polish

- Aligned package metadata, CLI version output, scaffold templates, and docs.
- Fixed PyPI README asset rendering.
- Hardened docs deployment with required MkDocs plugins.

### v0.5.45 - ORM Expressions, Native Multi-Tenancy, SDK Generation, and Real-Time Streams

- Added `Q()` objects, `F()` expressions, aggregation, transactions, tenant-aware models, TypeScript SDK generation, SSE streams, media/email, i18n/timezones, generic relations, durable workflows, and additional field types.

---

## Future Roadmap

### v0.5.49 - Durable AI Session Store

Persist investigation sessions, AI Console transcripts, and AI review state so multi-step analysis can resume reliably across process restarts.

### v0.5.50 - AI Memory Foundation

Introduce a minimal, explicit memory foundation for project-level AI context. This is not part of v0.5.48.

### v0.5.51 - AI System Radar

Add system-level monitoring surfaces for AI-assisted project health. This is not part of v0.5.48.

### v0.6.0 - Production Mode

Focus on production safety: connection-pool guidance, read-only Studio posture, deployment checks, stronger security defaults, and operational documentation.

---

## Long-Term Direction

- Keep the first ten minutes simple and inspectable.
- Make generated APIs, Studio, MCP, and AI context feel like one system.
- Preserve local-first and provider-optional workflows.
- Graduate toward stable production contracts before 1.0.
