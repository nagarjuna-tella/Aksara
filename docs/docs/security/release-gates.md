# Security Release Gates

> **Status:** This document is part of the Aksara security-hardening milestone (Round 1).
> The gates listed here are the target criteria for Aksara to claim production-mode status.
> Round 1 establishes the baseline. Release gates will be wired into CI in later rounds.

## Goal

Aksara should not claim production readiness until security checks are a required part of the
release process. This document defines the criteria that must pass before a production-mode
release can be made.

## Current Status (Round 1)

- [x] `security_matrix.yml` exists and validates
- [x] `aksara doctor security-check` is implemented
- [x] `aksara doctor production-check` is implemented
- [x] Security docs skeleton exists
- [ ] All gates below are met (in progress across multiple rounds)

## Planned Release Gates

The following must all be true before Aksara can claim v0.6.0 Production Mode:

### Security checks

- [ ] `aksara doctor production-check` exits 0 on a clean production config
- [ ] `security_matrix.yml` validates without errors
- [ ] All `status: planned` scenarios in the matrix are either `covered` or explicitly accepted
- [ ] No known critical or high open security issues

### Policy engine (Round 2)

- [ ] Centralized `Principal` object resolves actor identity for all surfaces
- [ ] `policy.can()` is used for every mutating operation
- [ ] `policy.visible_fields()` and `policy.writable_fields()` enforce field-level access
- [ ] Runtime field enforcement: crafted payloads with forbidden fields are rejected

### AI/MCP (Round 2–3)

- [ ] MCP deny-by-default mode implemented (`ai_agent_writable` defaults to `False`)
- [ ] AI field controls enforced at runtime (not only schema-time)
- [ ] Scoped MCP credentials with per-tool scope claims
- [ ] Field-level audit logging for AI/MCP tool calls

### Tenant isolation (Round 3)

- [ ] Cross-tenant property-based tests passing for all surfaces
- [ ] Forged tenant header rejected at all surfaces
- [ ] Empty tenant context fails closed at all surfaces

### ORM / fuzzing (Round 4)

- [ ] ORM/migration/filter/serializer fuzz smoke tests pass in CI
- [ ] OpenAPI fuzzing (Schemathesis) in CI

### Supply chain (Round 5)

- [ ] No critical/high dependency vulnerabilities (pip-audit / osv-scanner)
- [ ] No secrets detected in codebase or history (secret scanning)
- [ ] SBOM generated and published with each release
- [ ] Release provenance (signed tags, PyPI Trusted Publishing)

### External review

- [ ] External security review completed
- [ ] Public hardening report published:
  - Critical: 0 open
  - High: 0 open
  - Medium: accepted/fixed with documentation
  - Low: documented

### Operational

- [ ] At least one real application dogfooded in production-like conditions
- [ ] Production hardening guide reviewed and accurate
- [ ] Threat model reviewed by external reviewer

## Gate Verification Process (Planned)

When these gates are wired into CI, the release process will be:

```
1. git tag vX.Y.Z
2. CI: runs full test suite (must pass)
3. CI: runs aksara doctor production-check (must exit 0 on production config)
4. CI: runs security matrix scenario tests (covered scenarios must pass)
5. CI: runs supply-chain scan (no critical/high deps)
6. CI: builds wheel/sdist
7. CI: publishes via PyPI Trusted Publishing
8. CI: generates SBOM and attaches to GitHub Release
9. GitHub Release: links changelog, security notes, and hardening report
```

## Versioning and Scope

These gates apply to the production-mode claim. Pre-production releases (v0.5.x) may
be used for development and testing without all gates being met. The gates become
mandatory for any release claiming `production: true` or `v0.6.0+`.
