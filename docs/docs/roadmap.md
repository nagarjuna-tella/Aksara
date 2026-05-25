# Aksara Roadmap

Maintained by [Nagarjuna Tella](https://github.com/nagarjuna-tella).

> Updated May 2026

Aksara is public and pre-1.0. The near-term roadmap prioritizes trust, first-user success, and production readiness over feature sprawl.

---

## Current Stable Version

### v0.5.49 - Security Hardening & Release Trust

- Added centralized Principal and PolicyEngine foundations.
- Added runtime field enforcement for covered generated write paths.
- Added tenant isolation and MCP credential hardening helpers.
- Added bounded security, diagnostics, and fuzz/adversarial test coverage.
- Added public-safe security docs and private security matrix handling.
- Added Security CI, Release Gate, CodeQL, Dependabot, secret scanning,
  static analysis, dependency audit, SBOM generation, package verification,
  and PyPI Trusted Publishing prep.
- Does not claim production readiness or replace external security review.

---

## Recent Releases

### v0.5.48 - Launch Hardening & Golden Path

- Added `aksara doctor launch-check` for first-run readiness.
- Added `aksara examples validate` for bundled example sanity checks.
- Promoted `basic_app`, `blog`, `crm`, `multitenant`, and `ai_providers` as golden-path examples.
- Refreshed README, getting-started docs, roadmap, and changelog for public launch clarity.
- Added packaging, docs, examples, launch-check, and no-secrets test coverage.
- Kept AI provider setup optional for first launch.

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

### v0.5.50 - Durable AI Session Store

Persist investigation sessions, AI Console transcripts, and AI review state so multi-step analysis can resume reliably across process restarts.

### v0.5.51 - AI Memory Foundation

Introduce a minimal, explicit memory foundation for project-level AI context. This is not part of v0.5.49.

### v0.5.52 - AI System Radar

Add system-level monitoring surfaces for AI-assisted project health. This is not part of v0.5.49.

### v0.6.0-alpha.1 - Stability, Auditability, and Reference App

First alpha toward v0.6. Focus is on stability contracts, operational
auditability, and validating the stack against something that looks like real
use — not new features.

Planned items:

- **v0.6 stability contract** — published commitment to stable vs. evolving
  areas, compatibility policy before v1.0, security-fix behavior, generated
  surface change policy, and migration note expectations. Draft available:
  [v0.6 Stability Contract](roadmap/v0-6-stability-contract.md).
- **Multi-tenant support desk reference app** — a deployable Aksara application
  using multi-tenancy, AI tools, and the security controls stack. Intended to
  validate the framework against real deployment patterns.
- **AI/MCP audit logging** — field-level and action-level audit logs for AI
  agent writes, so tenant administrators can see what AI agents have done.
- **Production checklist to doctor mapping** — each item on a production
  readiness checklist corresponds to a specific `aksara doctor` check. Machine-
  checkable, not just human-readable.
- **External review package** — bundled scope, threat model, and findings
  template ready for an external security reviewer.
- **Benchmark plan** — performance baseline and regression detection before
  v0.6.0 ships.

### v0.6.0 - Production Mode

Focus on production safety: connection-pool guidance, read-only Studio posture, deployment checks, stronger security defaults, and operational documentation.

---

## Long-Term Direction

- Keep the first ten minutes simple and inspectable.
- Make generated APIs, Studio, MCP, and AI context feel like one system.
- Preserve local-first and provider-optional workflows.
- Graduate toward stable production contracts before 1.0.
