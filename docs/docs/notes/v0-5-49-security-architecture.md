# v0.5.49 Security Architecture Note

*May 2026 — Nagarjuna Tella, Aksara maintainer*

---

Aksara v0.5.49 is a security hardening release. This note explains the
architectural decisions behind it: why generated surfaces need runtime
enforcement, how the Principal/PolicyEngine model works, what tenant isolation
and MCP/AI credential boundaries cover, how we fuzz the generated surfaces,
and what the release-trust infrastructure actually consists of. It also says
plainly what this release does not claim, and what comes next.

---

## Why Generated Surfaces Are Security Boundaries

Aksara generates a lot from one model definition. A single `Model` class
produces REST endpoints, OpenAPI schemas, serializers, migration DDL, Studio
admin views, AI prompt context, and MCP tool descriptions. That's the point —
it removes the glue code you would otherwise write yourself.

But generated surfaces multiply exposure. Every surface you didn't write by
hand is a surface you might not have reviewed by hand either. The OpenAPI schema
your client reads, the MCP tool catalog an AI agent queries, the filter
parameters your generated list view accepts — these are all derived from your
model definition, and they all face external callers.

The core risk is trusting the schema as the boundary. If the server enforces
security by generating client-readable schemas that say "this field is
read-only" or "this field is hidden from AI," and then trusts those schemas
to stop bad payloads, a caller who ignores the schema and sends the field
anyway will get through. Field visibility in a schema is a UX hint. It is not
a security control.

Aksara's answer is to push enforcement server-side and make the generated
schema secondary. The schema describes what a well-behaved client can do. The
runtime check decides what any client is allowed to do.

---

## Principal and PolicyEngine

Every request in Aksara resolves to a `Principal`: a structured representation
of who is calling.

There are four principal types:

- **User**: An authenticated human caller with a user ID, optional tenant, and
  optional roles/permissions.
- **AIAgent**: An AI system calling through the MCP layer or AI Console. Carries
  MCP credential claims, scopes, audience, and tenant binding.
- **Anonymous**: An unauthenticated caller. PolicyEngine can grant or deny access
  to anonymous principals explicitly; nothing is implicit.
- **System**: An internal task such as a background worker or migration step.
  Runs with elevated trust that is explicitly granted, not inferred.

`PolicyEngine` is the single place where authorization decisions are made. It
answers:

- `can(principal, action, resource)` — is this principal allowed to perform
  this action on this resource?
- `visible_fields(principal, model)` — which fields can this principal read?
- `writable_fields(principal, model)` — which fields can this principal write?
- `query_filter(principal, model)` — what filter scopes this principal to the
  rows they are allowed to see?
- `validate_payload(principal, model, payload)` — given a write payload, which
  fields are denied?

Centralizing these decisions in one object rather than scattering checks across
viewsets and serializers has a concrete benefit: it is possible to audit what
the authorization model says about any given (principal, action, resource)
triple without tracing through layers of framework machinery.

---

## Runtime Field Enforcement

The most important guarantee in v0.5.49 is that generated write paths enforce
the principal's field-level policy at runtime, not just in schema generation.

When a `ModelViewSet` create or update path runs, it calls
`enforce_payload_policy()` before the write reaches the database. If the
payload contains fields the resolved principal is not allowed to write,
the request is rejected with a structured 403 that includes `denied_fields`.
The denied fields do not get silently stripped or ignored — the response tells
the caller explicitly what was blocked, so debugging does not require guessing.

The key field-level annotations and what they do:

- `ai_sensitive=True` — excluded from AI/MCP-visible schemas and from AI
  Console context. A principal that is an AI agent is blocked from seeing
  this field in the PolicyEngine's `visible_fields()` output.
- `ai_agent_writable=False` — an `AIAgent` principal cannot write this field
  through any covered write path. Runtime enforcement backs this up.
- Read-only fields — denied for all write principals regardless of type.
- `tenant_id` — denied for mutation in any covered write path. A tenant ID
  in a payload cannot be used to reassign a record to a different tenant.

What is covered: generated REST create and update paths, and any MCP agent
that routes through those paths. What is explicitly not universal: direct
manager-level bulk and upsert calls that bypass the REST layer, and MCP tool
calls that invoke database writes through a custom tool path rather than the
REST viewset. Both have helper-level validation available; application paths
that need it must wire it in explicitly.

---

## Tenant Isolation

Multi-tenant deployments in Aksara use `TenantModel` and PostgreSQL row-level
security. The framework provides tenant-aware principal resolution and
tenant-required fail-closed behavior.

What this means in practice:

- The `PolicyEngine.query_filter()` for a tenant-scoped principal always
  restricts the queryset to rows belonging to the caller's tenant. A principal
  that does not have a tenant context cannot reach tenant-scoped resources.
- Requests that attempt to set or mutate `tenant_id` through a covered write
  path are denied by runtime enforcement. A caller cannot forge a tenant
  assignment for a new or existing record.
- Explicit adversarial test cases cover: cross-tenant resource access, missing
  tenant context, forged tenant headers, tenant body overrides, and system
  principal behavior in tenant contexts.
- Studio and MCP exposure diagnostics warn when multi-tenant apps expose these
  surfaces without the token controls described in the next section.

Tenant isolation in Aksara is a framework-level assist, not an OS- or
database-level hard guarantee. The framework provides the query filters, policy
checks, and diagnostic coverage. Application code that bypasses the framework's
ORM layer, executes raw SQL, or directly mutates `tenant_id` outside covered
paths does not inherit these guarantees automatically.

---

## MCP/AI Credential Boundaries

MCP is disabled by default. When it is enabled, the framework provides
credential validation helpers and diagnostics to surface misconfiguration.

MCP credential validation covers:

- **Scopes** — the credential must carry the scopes required by the called
  action. `require_scope()`, `require_any_scope()`, and `require_all_scopes()`
  helpers enforce this.
- **Audience** — the token must be issued for this application's audience.
  Tokens from other applications are rejected.
- **Tenant binding** — in multi-tenant deployments, the token must be bound to
  a specific tenant. A token without a tenant claim cannot reach tenant-scoped
  data through covered paths.
- **Expiration** — expired tokens are rejected. Short TTLs are enforced through
  diagnostics that warn when token TTL exceeds 3600 seconds.
- **Token IDs** — for replay protection at the application level, token IDs can
  be tracked. Core MCP helpers do not implement replay storage; that is
  application-level work.

Doctor diagnostics fire when MCP is enabled but configured without
authentication, without scoped tokens, without audience restrictions, or
(in multi-tenant deployments) without tenant-bound tokens. Production-mode
diagnostics block on critical MCP misconfiguration.

The principal separation matters here: AI agents resolve to an `AIAgent`
principal, not a `User` principal. PolicyEngine decisions for `AIAgent`
principals can be made more restrictive than those for authenticated users.
`ai_agent_writable=False` is one example — there is no equivalent
`user_writable=False` because human users are not expected to have the same
automated call patterns. That separation is intentional.

---

## Fuzzing Generated Surfaces

Generated surfaces have properties that make fuzzing useful: the set of valid
filter parameters, ordering fields, pagination bounds, and serializer inputs is
mechanically derived from the model definition. Adversarial inputs can target
the generation logic itself, not just the application's custom business logic.

v0.5.49 adds bounded adversarial tests across:

- **Generated filters** — unexpected filter parameter names, SQL injection
  patterns in filter values, and oversized filter inputs.
- **Ordering** — ordering by fields that exist but should not be orderable
  given the model configuration, and injected ordering strings.
- **Pagination** — negative page sizes, extremely large limits, non-integer
  page parameters.
- **Serializers** — extra fields not in the model, mistyped field values,
  deeply nested structures, and oversized payloads.
- **Runtime field enforcement** — payloads designed to include denied fields,
  verify that rejection returns `denied_fields` in the response, and check
  that stripping does not silently occur.
- **Migration identifiers and defaults** — field names, defaults, and migration
  target names that include characters that could affect generated DDL.

OpenAPI fuzzing with Schemathesis is prepared as an optional path. When
Schemathesis is installed, the test suite wires it against the generated
OpenAPI schema. Without it, the test is skipped with an explicit skip reason
so CI does not silently omit the intent.

---

## Release-Trust Infrastructure

v0.5.49 ships a release-trust infrastructure alongside the code. "Release
trust" means the steps between a commit and a published package have
observable security properties. It does not mean the package has completed an
external security review.

What is in place:

- **`security.yml`** runs on every pull request and push: dependency audit,
  static analysis (Bandit), secret scanning (Gitleaks), security tests,
  diagnostics tests, and fuzz tests. It also checks that public security docs
  are present and contain required content.
- **`release-gate.yml`** is the gate before a release candidate can be
  published: full test suite, production diagnostics pass, package build,
  `twine check`, wheel import verification, SBOM generation, and strict docs
  build.
- **`codeql.yml`** runs GitHub CodeQL analysis for Python.
- **`publish.yml`** is manual and uses PyPI Trusted Publishing with OIDC and
  a protected `pypi` environment. It does not use API tokens. Uploading
  requires a human to trigger the workflow after the release gate has passed.
- **`dependabot.yml`** keeps Python and GitHub Actions dependencies visible
  through weekly pull requests.

The external review scope document (`security/external-review-scope.md`)
and hardening report template (`security/hardening-report-template.md`) are
pre-work for a future external review. They do not constitute an external
review having taken place.

---

## What This Release Does Not Claim

To be direct:

- **No production-mode claim.** v0.5.49 does not claim production readiness. The
  security hardening is meaningful and the test coverage is real, but
  production readiness requires external review, operational validation, and
  a production-mode claim that has not been made.
- **Not a complete external audit.** The hardening was done by the maintainer.
  An external security review is planned before a production-mode claim.
- **Not universal enforcement.** Bulk and upsert manager-level paths, direct
  MCP tool calls that bypass REST paths, and custom write paths outside the
  framework's generated layer are not universally covered. The framework
  provides helpers; application code must wire them in.
- **Not a replacement for application-level security.** The framework provides
  controls; application authors are responsible for configuring them correctly,
  not exposing raw database access, and reviewing the surfaces they enable.
- **Not a supply-chain guarantee.** SBOM generation and dependency audit are in
  CI, but supply-chain security is a posture, not a point-in-time check.

---

## What Comes Next

The v0.6 direction is stability, auditability, and operational trust — not
new features. Specifically:

- **v0.6 stability contract** — a written commitment to which areas of the API
  are stable versus still-evolving, how breaking changes will be communicated
  before v1.0, and what migration notes will look like.
- **Multi-tenant support desk reference app** — a real deployable app using
  Aksara's multi-tenancy stack, AI tools, and security controls, intended to
  validate the framework against something that looks like production use.
- **AI/MCP audit logging** — field-level and action-level audit logs for AI
  agent writes, so tenant administrators can see what AI agents have done.
- **Production checklist mapped to doctor** — a machine-checkable production
  readiness checklist where each item corresponds to a specific doctor check.
- **External review package** — a bundled scope, threat model, and
  findings-template ready for an external security reviewer.
- **Benchmark plan** — performance baseline and regression detection before
  v0.6 goes out.

The near-term goal is to get from "security hardening done by the maintainer"
to "external security review completed and accepted risks documented." That is
the gate for a production-mode claim.

---

*This note describes Aksara v0.5.49's security architecture. It is a
technical note, not a security advisory. No CVEs, no patches, no incidents
are described. For the full security posture, see the
[Security Guide](../security/overview.md).*
