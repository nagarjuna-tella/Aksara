# Aksara Roadmap

> **Updated Feb 21, 2026**

Aksara is now an AI-first application framework with a fully integrated
developer studio, automatic diagnostics, code-generation agents, and
intelligent tooling. This roadmap reflects the reality of Aksara’s rapid
2026 development cadence.

---

## Current Stable Version

### v0.5.27 — Sanity Sweep & Docs Lock (Feb 2026)

- **Studio Gap Analysis panel** — nav item, template, `renderGaps()` /
  `loadGapAnalysis()` with severity filter buttons and Re-scan action
- Consolidated 3 duplicate `jsonPost` definitions in Studio app.js
- Replaced `alert()` with `showToast()` for consistent Studio UX
- `aksara inspect queries` now handles missing `DATABASE_URL` gracefully
- `run_gap_analysis_for_category` logs warnings instead of silent swallow
- CLI help text fixes (grammar, stale version tags removed)
- Keyboard shortcuts reorganised: `6`=Gaps, `7`=DB Queries, `8`=AI Hub, `g`=Gaps
- Docs and help text aligned with current behaviour
- Full suite at **3551+ passed**

---

## Recent Releases

### v0.5.26 — Gap Analysis Engine (Feb 2026)

- **Gap Analysis Engine** (`aksara/gapanalysis.py`) — static pre-flight scanner
  with 8 check categories: `imports`, `db`, `migrations`, `routers`, `providers`,
  `studio`, `environment`, `ai_pipeline`
- `GapIssueSeverity` adds a `"critical"` tier above diagnostics' `"error"`
- `aksara gaps` CLI group — 6 subcommands: `run`, `summary`, `json`,
  `list-errors`, `list-critical`, `fix-plan`
- Studio panel at `/studio/gaps` (`GET` + `POST /studio/gaps/run`)
- `build_fix_plan()` — severity-ordered actionable fix list with per-issue
  shell commands and required env vars
- 112 new tests; full suite at **3409 passed**

### v0.5.25 — AI Hub & Unified Provider System (Feb 2026)

- AI Hub Studio panel — provider registration, health checks, model listing
- Unified Provider abstraction (OpenAI, Anthropic, Azure OpenAI, Ollama)
- `aksara ai` CLI group with `list-providers`, `test-provider`, `run-agent`
- Internal API routes hidden from Swagger (`include_in_schema=False`)
- `admin.py` added to `startapp` scaffold
- Studio dark mode fixes; Studio menu simplification
- Admin 2.0 UI audit + theme/logo unification pass
- 3297 tests passing

### v0.5.24 — Stability & Refactor Pass (Feb 2026)

Includes everything from v0.5.0–v0.5.23 plus:

- Studio 2.0 with Spotlight search (⌘K)
- Diagnostics 2.0 with autoremediation
- Query Inspector 2.0
- Agent Mode with agentic workflows
- Playbook Engine (8 built-in playbooks)
- Semantic Search (TF-IDF + pluggable embeddings)
- Provider Integration Toolkit (OpenAI, Anthropic, Azure, Ollama)
- AI Profiles / Hints / Schema Doctor
- Studio Keyboard Shortcuts
- Full FastAPI/ORM integration
- Lazy-import helper pattern for testability
- CLI error handling hardened (exit codes, hints)
- Studio error feedback (toast notifications)
- Complete migration system overhaul — new autodetector (1 060 lines), 22 migration bugs fixed, 27 new tests
- ORM / Fields / Migrations deep audit — 35 bugs fixed
- 3 250+ test suite

---

## v0.6.0 — Production Mode

**Target: Feb–Mar 2026**

Focus: Make Aksara production-ready for real applications and enterprise loads.

### Production Infrastructure

- PgBouncer-ready connection pooling
- Query caching layer
- Read replica routing
- Async migrations
- Database failover support
- Zero-downtime reload signals
- Schema drift detection

### Studio Production Tools

- Slow Query Heatmaps
- Replica Lag Monitor
- Connection Pool Dashboard
- Index Recommendation Engine
- “Production Mode” UI (read-only safety)

---

## v0.7.0 — AI Mode 3.0

**Target: Apr–May 2026**

Next-gen agent capabilities.

### Agentic Development

- Auto PR Reviews
- Agent Test Writer
- Regression Analyzer
- “Fix with AI” buttons throughout Studio
- Model/Viewset/Serializer refactor assistant

### Multi-Agent Runtime

- Parallel agents
- Shared session memory
- Provider orchestration (OpenAI+Azure+Anthropic switching)

### AI Documentation Engine

- API doc generation
- README/Module doc generation
- Example snippet generation

---

## v0.8.0 — Enterprise Data & Permissions

**Target: Jun–Jul 2026**

### Multi-Tenancy 2.0

- Schema-per-tenant
- Tenant-aware migrations
- Cross-tenant admin queries
- Tenant-level DB Inspector

### Advanced Permissioning

- Row-level access policies (RLS)
- Field-level rules
- Policy sandboxing & simulation
- Condition-based dynamic rules

### Audit & Compliance

- Full audit event system
- Compliance export pipeline
- Studio Audit Explorer

---

## v0.9.0 — Plugins & Ecosystem

**Target: Aug–Sep 2026**

### Plugin Architecture

- `aksara add plugin-name`
- Aksara Registry
- Official Plugins
  - Email
  - Uploads
  - WebSockets
  - SSE
  - PDF exporter

### Developer Experience

- VS Code Extension
- Aksara Playground (browser dev environment)
- Dev Server Inspector
- Latency profiling

---

## v1.0.0 — General Availability (GA)

**Target: Oct–Dec 2026**

### Release Goals

- API Stability Guarantee
- 18-Month LTS Window
- Migration Guide (Django/FastAPI → Aksara)
- Complete Documentation Rewrite
- Performance Benchmarks (vs Django/FastAPI/Node)
- Enterprise Support Tier

---

## Feature Requests — Updated Priorities

### High Priority

- WebSockets
- File Uploads
- Email
- Background Task Runner

### Medium

- GraphQL
- gRPC
- Server-Sent Events

### Low

- PDF Toolkit
- UI Components Pack

---

## Long-Term Vision

Aksara is aiming to become:

- The fastest framework to go from idea → production
- The first AI-native dev framework
- A complete batteries-included enterprise platform
- An ecosystem & marketplace for plugins & agent workflows
