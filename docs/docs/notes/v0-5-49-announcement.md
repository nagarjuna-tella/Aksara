# Aksara v0.5.49 — Security Hardening & Release Trust

*May 2026*

---

Aksara v0.5.49 is out. This release is focused on one thing: making generated
APIs and AI/MCP tools real security boundaries, and making the release process
observable enough to trust.

Here is what shipped.

---

## Generated APIs and MCP Tools as Security Boundaries

Aksara generates REST APIs, OpenAPI schemas, Studio admin surfaces, and MCP
tool catalogs from model definitions. Generated surfaces are useful — they
eliminate the glue code you would otherwise write yourself. But generated
surfaces also multiply exposure. Every endpoint you didn't write by hand is
an endpoint you might not have reviewed by hand either.

v0.5.49 adds the infrastructure to make those surfaces actual security
boundaries rather than schema hints:

**Principal model.** Every request resolves to a typed Principal: User,
AIAgent, Anonymous, or System. AI agents are not treated as users with a
different name — they are a distinct principal type with distinct policy
decisions.

**PolicyEngine.** Authorization decisions live in one place: `can()`,
`visible_fields()`, `writable_fields()`, `query_filter()`,
`validate_payload()`. Centralizing this makes it auditable.

**Runtime field enforcement.** Generated write paths now enforce field policy
before the database write. A field marked `ai_agent_writable=False` is not
just hidden in the MCP schema — it is blocked at runtime. The rejection is
explicit: a 403 with `denied_fields` in the response.

**Tenant isolation hardening.** Tenant-scoped querysets, blocked `tenant_id`
mutation in write paths, and adversarial test coverage for cross-tenant access,
missing tenant context, and forged tenant headers.

**MCP credential controls.** MCP is disabled by default. When enabled,
credential helpers validate scopes, audience, tenant binding, and expiration.
Doctor diagnostics warn on misconfiguration; production diagnostics block on
it.

**Fuzz coverage.** Generated filter parameters, ordering fields, serializer
inputs, and migration identifiers now have bounded adversarial test coverage.

---

## Release Trust

The release process has observable security properties now:

- **Security CI** runs dependency audit, Bandit static analysis, Gitleaks
  secret scanning, security tests, diagnostics tests, and fuzz tests on every
  pull request.
- **Release gate CI** is the gate before publication: full test suite,
  production diagnostics pass, package build and `twine check`, wheel import
  verification, and SBOM generation.
- **CodeQL** runs on every push.
- **Dependabot** keeps dependencies visible.
- **PyPI Trusted Publishing** with OIDC and a protected environment. No API
  tokens. Publishing is manual and gated.

Release trust means the path from commit to published package is auditable. It
is not an external security audit.

---

## What This Release Does Not Claim

Aksara v0.5.49 is **pre-1.0 and does not claim production readiness.**

The hardening is real. The test coverage is real. The release infrastructure
is real. But:

- An external security review has not been completed.
- Bulk/upsert manager-level paths and direct MCP tool calls that bypass
  REST paths are not universally covered by runtime enforcement.
- Production readiness requires operational validation beyond what a
  framework can provide on its own.

The goal of this release is to get to the starting line for an external review
with a credible security posture, not to claim a finish line that has not
been crossed.

---

## What's Next

v0.6 is focused on stability, auditability, and operational trust:

- Published v0.6 stability contract (what is stable, what can change, and how
  migration notes will work)
- Multi-tenant support desk reference app to validate the stack against
  something that looks like real use
- AI/MCP audit logging
- Production checklist mapped to doctor checks
- External review package and benchmark plan

The near-term goal is to get from "security hardening done by the maintainer"
to "external security review completed and accepted risks documented."

---

If you are building with Aksara, I want to hear what you run into. Open an
issue on [GitHub](https://github.com/nagarjuna-tella/Aksara/issues), even a
rough one. That feedback is how this improves.

Nagarjuna

---

*For the full technical architecture note, see
[v0.5.49 Security Architecture](v0-5-49-security-architecture.md).*
*For the current security posture, see the
[Security Guide](../security/overview.md).*
