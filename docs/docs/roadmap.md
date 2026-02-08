# Aksara Roadmap

> **Updated Feb 7, 2026**

Aksara is now an AI-first application framework with a fully integrated
developer studio, automatic diagnostics, code-generation agents, and
intelligent tooling. This roadmap reflects the reality of Aksara’s rapid
2026 development cadence.

---

## Current Stable Version

### v0.5.20 — Agent Playbooks (Feb 2026)

Includes:

- Studio 2.0
- Diagnostics 2.0
- Query Inspector
- Agent Mode
- Playbook Engine
- Provider Integration Toolkit
- AI Profiles / Hints
- Studio Keyboard Shortcuts
- Full FastAPI/ORM integration
- 2900+ test suite

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
