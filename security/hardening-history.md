# Security Hardening History

This is an internal engineering history document. It is not public product
documentation and should not be used as a production-readiness claim.

If this repository publishes everything under `security/`, keep this document
plainly marked as internal engineering history.

## Summary

Aksara security hardening has moved through several internal rounds. Public docs
should describe the current product posture instead of this sequence.

## Round 1: Baseline and Diagnostics

- Added security diagnostics for `aksara doctor security-check`.
- Added stricter production diagnostics for `aksara doctor production-check`.
- Established checks for `SECRET_KEY`, debug mode, CORS, Studio exposure, MCP
  exposure, cookie settings, rate limits, tenancy/RLS configuration, and
  security matrix validity.
- Created the security matrix concept for tracking generated surfaces, actors,
  risks, and adversarial scenarios.

## Round 2: Principal and Policy Foundation

- Added the centralized `Principal` representation for users, AI/MCP agents,
  anonymous callers, and system tasks.
- Added `PolicyEngine` authorization decisions with `can()`,
  `visible_fields()`, `writable_fields()`, `query_filter()`, and
  `validate_payload()`.
- Added request, user, AI agent, MCP claims, and system principal resolver
  helpers.
- Added structured policy decisions and security exceptions.

## Round 3: Runtime Field Enforcement

- Added runtime payload enforcement for covered generated REST write paths.
- Wired field-level policy enforcement into generated create and update paths.
- Added structured 403 responses with `denied_fields`.
- Ensured generated schemas are treated as client hints rather than the security
  boundary.
- Added helper-level validation entry points for request payload enforcement.

## Round 4: Tenant and MCP Hardening

- Added tenant-aware policy checks and tenant-required fail-closed behavior.
- Added tests for cross-tenant resource access, missing tenant context, forged
  tenant headers, tenant body overrides, and system principal behavior.
- Added MCP credential helpers for scope checks, audience checks, tenant binding,
  expiration, and token metadata.
- Added MCP hardening diagnostics for scoped tokens, token TTL, audience checks,
  and tenant-bound tokens in multi-tenant deployments.

## Round 5: Fuzzing and Generated Surface Hardening

- Added bounded adversarial tests for generated filters, ordering, pagination,
  serializers, runtime field enforcement, malformed payloads, oversized payloads,
  and migration identifiers/defaults.
- Added helper-level bulk and upsert payload validation coverage.
- Added an explicit skipped placeholder for OpenAPI fuzzing when Schemathesis is
  unavailable.
- Preserved known limitations around manager-level bulk/upsert integration,
  direct MCP tool-call enforcement, release gates, supply-chain automation, and
  external review.

## Matrix Cleanup

- Removed the private `security/security_matrix.yml` from the public repository.
- Kept `security/security_matrix.example.yml` as the public-safe example.
- Kept `security/security_matrix.yml` git-ignored.
- Preserved default warning behavior for a missing private matrix.
- Preserved strict behavior when `AKSARA_REQUIRE_SECURITY_MATRIX=true`.

## Remaining Release-Trust Work

- Wire security, fuzzing, and production diagnostics into release gates.
- Add supply-chain CI such as dependency audit, static analysis, secret scanning,
  SBOM generation, provenance, and PyPI Trusted Publishing.
- Complete or explicitly scope external security review before any
  production-mode claim.
- Decide whether manager-level bulk/upsert principal enforcement should be wired
  beyond helper-level validation.
- Add direct MCP tool-call runtime enforcement where tools bypass REST paths.

## Round 6: Release Trust Preparation

- Added security CI for dependency audit, static analysis, secret scanning,
  security tests, diagnostics tests, fuzz tests, and public security docs checks.
- Added release-gate CI for full tests, production diagnostics, package build
  verification, dependency audit, static analysis, secret scanning, SBOM
  generation, and strict docs builds.
- Added CodeQL and Dependabot configuration.
- Added a manual PyPI Trusted Publishing workflow using GitHub OIDC and a
  protected `pypi` environment.
- Added external review scope and hardening report templates.
- Updated public release-security docs without making a production-readiness
  claim.
