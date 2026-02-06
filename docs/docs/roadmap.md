# Roadmap

Future plans for Aksara development.

---

## Current Version

**v0.4.11** — Stable release with AI Mode, full ORM, API framework, Admin UI/UX Overhaul, and comprehensive tooling.

---

## Upcoming Releases

### v0.5.0 — Performance & Scale

**Planned: Q2 2025**

Focus on performance optimization and enterprise-scale features.

#### Planned Features

- [ ] **Query Optimization**
  - Automatic query plan analysis
  - Index recommendation engine
  - Query result caching improvements

- [ ] **Connection Pooling**
  - PgBouncer integration
  - Connection health monitoring
  - Automatic failover

- [ ] **Horizontal Scaling**
  - Read replica support
  - Database sharding helpers
  - Distributed caching with Redis Cluster

- [ ] **Background Tasks**
  - Built-in task queue
  - Scheduled tasks (cron-like)
  - Task monitoring dashboard

---

### v0.6.0 — Enterprise Features

**Planned: Q3 2025**

Enterprise-ready features for large organizations.

#### Planned Features

- [ ] **Advanced Multi-Tenancy**
  - Schema-per-tenant isolation
  - Tenant-aware migrations
  - Cross-tenant queries (admin)

- [ ] **Audit Logging**
  - Automatic change tracking
  - Compliance reporting
  - Data retention policies

- [ ] **Advanced Permissions**
  - Row-level security
  - Dynamic permissions
  - Permission inheritance

- [ ] **SSO Integration**
  - SAML 2.0 support
  - OAuth 2.0 / OIDC
  - LDAP/Active Directory

---

### v0.7.0 — AI Mode 2.0

**Planned: Q4 2025**

Next generation AI-powered development.

#### Planned Features

- [ ] **AI Code Review**
  - Automatic PR reviews
  - Security vulnerability detection
  - Performance suggestions

- [ ] **AI Testing**
  - Automatic test generation
  - Test coverage analysis
  - Regression detection

- [ ] **AI Documentation**
  - Auto-generate API docs
  - Code comment generation
  - README generation

- [ ] **Custom AI Agents**
  - User-defined agent workflows
  - Domain-specific training
  - Agent marketplace

---

### v1.0.0 — Stable Release

**Planned: Q1 2026**

Production-ready stable release.

#### Goals

- [ ] API stability guarantee
- [ ] Long-term support (LTS)
- [ ] Comprehensive documentation
- [ ] Migration guides from Django/FastAPI
- [ ] Enterprise support tier

---

## Feature Requests

### Under Consideration

| Feature | Status | Priority |
|---------|--------|----------|
| GraphQL support | Evaluating | Medium |
| gRPC support | Evaluating | Medium |
| WebSocket improvements | Planned | High |
| File uploads | Planned | High |
| Email sending | Planned | Medium |
| PDF generation | Evaluating | Low |

### Community Requests

Vote on features and submit requests:

- [GitHub Discussions](https://github.com/aksara/aksara/discussions)
- [Feature Requests](https://github.com/aksara/aksara/issues?q=label%3Aenhancement)

---

## Long-Term Vision

### Goals

1. **Developer Experience**
   - Fastest time from idea to production
   - AI-assisted development at every step
   - Zero-configuration defaults that scale

2. **Performance**
   - Competitive with bare FastAPI
   - Automatic optimization
   - Built-in profiling

3. **Ecosystem**
   - Plugin marketplace
   - Community templates
   - Integration library

### Non-Goals

- Replacing general-purpose frameworks
- Supporting legacy Python versions
- Synchronous-first design

---

## Contributing

### How to Contribute

1. **Code contributions**
   - Fix bugs
   - Implement features
   - Improve documentation

2. **Testing**
   - Report bugs
   - Test pre-releases
   - Write tests

3. **Documentation**
   - Fix typos
   - Add examples
   - Translate docs

4. **Community**
   - Answer questions
   - Write tutorials
   - Share projects

### Contribution Guide

See [CONTRIBUTING.md](https://github.com/aksara/aksara/blob/main/CONTRIBUTING.md)

---

## Version Support

| Version | Status | Support Until |
|---------|--------|---------------|
| 0.4.x | Current | Active |
| 0.3.x | Maintenance | 2025-06 |
| 0.2.x | End of Life | — |
| 0.1.x | End of Life | — |

---

## Stay Updated

- [GitHub Releases](https://github.com/aksara/aksara/releases)
- [Changelog](changelog.md)
- [Blog](https://aksara.dev/blog)
- [Twitter](https://twitter.com/aksaraframework)

---

## Related

- [Changelog](changelog.md)
- [Getting Started](getting-started/index.md)
