# Roadmap

> Reviewed September 11, 2026. Release horizons are directional, not a promise.

Aksara is a PostgreSQL-backed Python application framework with generated APIs,
shared authorization boundaries, and durable actions that recheck authority
before supported effects. The next priority is making that application boundary
easier to learn, integrate, operate, and upgrade.

Release evidence overrides roadmap assumptions. Correctness, security and
compatibility defects can interrupt this sequence. No dates are committed here.

## Where Aksara is now

The released version is **v0.7.0**. The stable backend foundation includes the
ORM and migrations, generated REST APIs, serializers, identity and permissions,
PolicyEngine, tenant/RLS enforcement, core Admin/CLI/Doctor surfaces, background
tasks, and synchronous generated MCP tools over Streamable HTTP at `/mcp/`.

The v0.7 release established **durable authorized operations**: one logical
Operation, physical Attempts, scoped idempotency, fenced ownership, current
authorization, approval and cancellation intent, bounded history, and recovery.
For `postgres_atomic`, supported application mutation and authoritative success
share one PostgreSQL transaction. External effects require provider-specific
idempotency and reconciliation; they can remain `external_outcome_unknown`.
There is no unconditional exactly-once promise for external calls.

Read the [v0.6 foundation contract](roadmap/v0-6-stability-contract.md) and
[v0.7 durable contract](roadmap/v0-7-stability-contract.md) for exact guarantees,
required production configuration, and exclusions. The
[application boundaries guide](concepts/application-boundaries.md) explains how
the parts fit together.

Ordinary tasks do not automatically retain a complete Principal. Delayed
Operations require application-owned identity resolvers and action policy.
Custom code must participate in the supported enforcement paths. AI agents are
optional consumers of this backend, not a prerequisite for building an app.

## Now — v0.7.1 public truth and developer experience

v0.7.1-rc1 is the current candidate. It is a documentation and developer-experience release
with **no intentional production semantic changes**. Its acceptance work is:

- an executable Quick Start and one progressive application tutorial;
- a coherent manual for models, APIs, identity, tenants, tasks and Operations;
- accurate configuration, production, recovery and upgrade instructions;
- runnable examples verified from an installed wheel;
- clearer scaffold instructions with equivalent executable output and defaults;
- visible stable, evolving and experimental boundaries; and
- automated documentation gates plus the established runtime regression suite.

A successful build of the documentation is not enough: a new developer must be
able to build the application using the published instructions. The operator
must be able to discover required roles, workers, migrations, diagnostics,
retention, export and backup responsibilities.

### v0.7.x maintenance

Later patches may address verified bugs, security, compatibility, packaging,
documentation and narrow adoption defects. Functional fixes need explicit review
and regression evidence; they will not be hidden in this documentation release.
No later patch number is reserved for speculative work.

## Next — operating authorized application work

The recommended **v0.8 thesis** is to make the existing application execution
contract operable by an independent backend team. This is a proposed outcome,
not a committed feature list or permission to start implementation.

Use one production reference application to prove:

- identity-provider integration and current authorization after delay;
- action/resolver registration and version compatibility through deployment;
- worker startup, supervision, shutdown and recovery under restricted roles;
- inspection of pending, denied, failed and uncertain work;
- correlation from request to Operation, Attempt and exported evidence; and
- retention, idempotency-window and upgrade/recovery procedures.

Use existing public APIs and standard integrations where they suffice. Propose
new APIs only for demonstrated gaps, with separate design and failure tests.
Revisit this thesis if independent users encounter more fundamental modeling or
identity blockers first. No v0.8 runtime work belongs in v0.7.1.

## Later — supported modeling, integrations and stabilization

Address relation or application-modeling gaps when a concrete application is
blocked. Expand a small set of maintained integrations where they reduce
adoption cost without introducing a competing authority model. Consolidate the
supported compatibility, deprecation and upgrade policy on the path to 1.0.

A v0.9 feature set is deliberately unassigned. Evidence from the next real
applications should decide the order, rather than filling version numbers.

## Explore — integrations and demand

Candidate experiments include a real external identity provider, an agent client
using the same authenticated REST/MCP boundary, and a telemetry/export backend.
A hosted-PostgreSQL recipe must verify its role, pooling and RLS behavior before
it becomes a supported deployment. External policy engines may be useful when
an application needs richer access relationships; integration must preserve
freshness, field/query policy, tenant binding and fail-closed behavior.

PostgreSQL remains the stable database. Its RLS, tenant settings, row locks,
JSONB and transaction behavior underpin current guarantees. A development-only
SQLite path would not test those guarantees. Improve local PostgreSQL setup
first; revisit database expansion only with qualified user demand and an
explicit semantic/maintenance plan.

## Not planned

This sequence does not include:

- a general workflow/DAG engine or a replacement for Temporal;
- autonomous multi-agent orchestration, a vector database or an AI memory platform;
- a model gateway, frontend builder or managed backend service;
- broad database portability or a new mandatory Redis/Kafka service; or
- a Kubernetes operator or a large plugin framework without demonstrated need.

Protocol-level MCP Tasks are not promised here. Any adoption requires a separate
review of the protocol, official SDK support and Aksara's execution contract.

## Experimental / deferred

Planner behavior, provider-specific quality, investigation sessions, persistent
agent memory, autonomous workflows, Studio internals and higher-level
`DurableStep` composition remain outside the stable durable-operation guarantee.
Custom many-to-many through models and object-valued lazy forward foreign keys
remain declared relation exclusions. See [stability](concepts/stability.md).

Applications own identity verification, business policy, human approval UX,
external-effect reconciliation, long-term audit retention and infrastructure
operations. Approval records intent; it does not replace current permission.

## v1.0 readiness

A bounded 1.0 requires:

1. An explicit supported public API and stability/compatibility policy.
2. Proven migrations and upgrades within the declared ORM/relation scope.
3. Tested auth, field policy, tenant and REST/MCP enforcement boundaries.
4. Clear task and durable contracts, including failure and external uncertainty.
5. Executable installed-wheel onboarding and production reference applications.
6. Rehearsed deployment, recovery, retention/export and backup-restore procedures.
7. Supported runtime matrices, security reporting and repeatable release gates.
8. No unresolved release-blocking defect within the supported surface.

It does not require every database, auth provider, workflow feature or AI
integration. Experimental systems may remain experimental at 1.0. Independent
usability and operational evidence matter alongside automated regression tests.

## Principles and research

Preserve current authority across delayed work. Prefer integration over new
infrastructure. Treat public examples as executable product surface. Separate
stored intent, scheduling and authorization. Stabilize promises only after
upgrade and failure evidence exists.

The [post-v0.7 market and roadmap review](https://github.com/nagarjuna-tella/Aksara/blob/main/AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md)
records the primary-source research, alternatives, capability gaps and demand
assumptions behind this direction. It recommends a Python application-backend
category and tests delayed authorized actions as the distinguishing use case;
it does not claim measured customer demand or comparative performance.
