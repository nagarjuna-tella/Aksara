# Roadmap

> Updated September 2026

Aksara's roadmap is directional, not a promise. Release evidence overrides
roadmap assumptions, serious production bugs interrupt planned sequencing, and
features can move when validation exposes prerequisite work. Patch releases may
be driven by compatibility and adoption. A public surface becomes stable only
after its contract and failure behavior are tested; a version number alone does
not make it stable.

## Where Aksara is now

v0.6.0 established a bounded Production Mode contract for Aksara's async
PostgreSQL ORM, migrations, generated REST APIs, identity, permissions,
`PolicyEngine`, tenant isolation, core CLI and Doctor, background tasks, and
generated MCP tools over Streamable HTTP at `/mcp/`.

REST and MCP mutations use the same server-owned `Principal`, permissions,
field policy, tenant, ORM, transaction, and PostgreSQL RLS path. v0.6 therefore
makes an individual tool invocation safe within that documented boundary.

Planner behavior, process-local investigation sessions, persistent AI memory,
multi-agent and autonomous workflows, provider-specific quality, Studio AI,
application approval workflow UX, durable compliance retention, and
protocol-level MCP Tasks remain experimental, application-owned, or deferred.

The v0.7.0 release candidate adds an opt-in Durable Authorized Operations
substrate. PostgreSQL retains one logical Operation, its physical Attempts,
scoped idempotency identity, current-authorization provenance, approval and
cancellation intent, transition/outbox evidence, and bounded retention. See the
[v0.7 durable operations stability contract](roadmap/v0-7-stability-contract.md)
for the exact new boundary.

## v0.7 release candidate

The v0.7 candidate milestone is **durable authorized operations**.

The accepted architecture is recorded in
[ADR 0001 — Durable Authorized Operations](https://github.com/nagarjuna-tella/Aksara/blob/main/docs/adr/0001-durable-authorized-operations.md).

The change in guarantee is precise: framework-managed work that opts into
durable execution remains identifiable, queryable, bounded,
recoverable, reauthorized, and auditable after a response, process, or worker
is lost.

This work follows existing code. MCP already provides secure invocation
identity and policy enforcement. The PostgreSQL task queue already provides
durable records, atomic multi-worker claims, retries, and stale-lock recovery.
Approvals, replay protection, audit correlation, runtime budgets,
cancellation, and investigation state stop at request or process lifetime.
v0.7 connects the application-operation boundaries through a small shared
model while leaving those experimental systems unchanged.

## Current adoption patch

### v0.6.1 — installed-package truth

This patch is driven by verified adoption and compatibility defects. It:

- makes public AI examples use APIs the wheel actually exports;
- consistently identifies `/mcp/` as the protocol endpoint and
  `/ai/tools/mcp` as an inspection catalog;
- reconciles the documented background-task Principal claim with the persisted
  tenant-only task context;
- aligns provider/configuration guidance, generated-project guidance, package
  metadata, and final release evidence with v0.6.0; and
- executes important documentation imports and the clean-wheel quickstart in CI.

The strengthened guarantee is documentation and packaging fidelity: a user can
follow the supported path from install to PostgreSQL, REST, Principal, and a
real MCP client without encountering conceptual or stale APIs. Acceptance
requires an isolated wheel, a clean PostgreSQL database, executable snippets,
an official MCP client at `/mcp/`, direct task-context tests, strict docs, and
the normal release diagnostics. The work is backward compatible and adds no
mandatory dependency.

This patch belongs in the framework because it corrects its public contract.
It does not add durable tables, planner features, AI memory, or a stable Studio
surface. Later v0.6.x numbers are not reserved; use them only for validated
bugs, security, compatibility, packaging, MCP interoperability, or adoption
work.

## Delivered in v0.7

The candidate implements the architectural sequence as follows:

1. **State and authorization contract.** Centralized terminal states,
   attempts, leases, fencing, retry rules, retention, and reauthorization are
   tested while existing synchronous REST and MCP behavior remains valid.
2. **One PostgreSQL source of truth.** Migrated operation and attempt
   records with an authoritative state, correlation, bounded result/error
   envelopes, and a policy-filtered read API cover upgrade, rollback, invalid
   transitions, restricted-role DML, concurrent updates, restart queries, and
   lost responses after commit.
3. **Cross-worker recovery and idempotency.** Atomic claims,
   lease/heartbeat, fencing, retry schedules, and a principal/tenant-scoped
   idempotency key with canonical input hashing survive worker death before,
   during, and after commit; late workers; concurrent duplicates; changed input;
   retry exhaustion; and database disconnects.
4. **Current authority across delay.** Identity provenance replaces stored raw
   credentials; execution resolves current identity and reruns
   expiry, audience, scope, permission, policy, field, tenant, and RLS checks
   before resumed mutations. Tests cover revocation, expiry, role and tenant
   changes, missing resolvers, and cross-tenant resume.
5. **Durable decisions and limits.** Exact approval decisions,
   cancellation intent, and bounded attempt/tool/step/provider-reported usage
   counters persist across restart. Approval, cancellation, claim races, and
   Attempt exhaustion are deterministic.
6. **Incremental integration.** Existing tasks can execute linked Operations;
   explicit REST/Python durable dispatch is additive. Synchronous generated REST
   and MCP retain their v0.6 behavior. Protocol-level MCP Tasks are deferred
   until the official Python SDK implements the current extension.

These capabilities introduce a stable framework guarantee and therefore belong
inside Aksara. Application code continues to own credential verification,
business policy, human-review UX, external-effect idempotency, indefinite audit
retention, and provider/model quality. PostgreSQL is sufficient for the
smallest useful implementation; no additional mandatory service is planned.

## Stable v0.7 additions

v0.7 makes the following explicit durable-execution contract stable:

- a framework-issued operation ID and one authoritative PostgreSQL state;
- bounded attempt and transition history with typed result or failure;
- atomic worker claims, leases, fencing, restart recovery, and bounded retry;
- scoped idempotency which returns the same operation for the same canonical
  input and rejects changed input;
- requester, agent, and tenant provenance plus current authorization checks
  before delayed mutation;
- durable, exact-operation approval binding and single consumption;
- durable cancellation intent and persisted framework counters;
- policy-filtered operation status and transactionally correlated audit export;
  and
- compatibility with the stable v0.6 synchronous REST, MCP, ORM, migration,
  security, and task contracts.

Release acceptance includes multi-process PostgreSQL tests at claim, mutation,
commit, and acknowledgement boundaries; lost-response recovery; duplicate and
approval races; cancellation and budget enforcement across restart;
authorization revocation and cross-tenant denial; migration upgrade/replay;
restricted application roles; packaged-wheel validation; a real MCP client;
and strict Doctor/release gates.

The contract covers framework-owned database effects. External calls follow the
executor/provider idempotency and reconciliation contract. When their outcome
cannot be established safely, v0.7 reports `external_outcome_unknown` rather
than blindly retrying or claiming provider success or failure. v0.7 will not
implement arbitrary workflow graphs, exactly-once external side effects,
persistent conversations, semantic memory, planner or provider quality
guarantees, multi-agent autonomy, a production Studio contract, or a new
mandatory runtime service.

## Experimental / deferred

The following remain experimental or deferred through v0.7 even when they use
the durable operation substrate:

- planners, autonomous loops, investigation content and session APIs;
- persistent conversations, semantic memory, and multi-agent coordination;
- provider registries, provider-specific quality, and live-provider accounting;
- Studio UI and Studio AI internal APIs;
- code and patch generation/application workflows;
- generic tool adapters outside the stable MCP contract;
- `DurableStep` and higher-level workflow composition until they share v0.7
  attempt, lease, identity, cancellation, and migration semantics;
- custom many-to-many through models and object-valued lazy forward foreign
  keys; and
- MCP transports other than Streamable HTTP;
- protocol-level MCP Tasks until the official Python SDK implements the
  current `io.modelcontextprotocol/tasks` extension.

Applications continue to own human approval experiences, long-term audit
retention and certification, infrastructure operations, and safe interaction
with external side effects.

## Principles

- Roadmap items are directional, not promises.
- Release evidence overrides roadmap assumptions.
- Serious correctness, security, compatibility, packaging, and production bugs
  interrupt planned sequencing.
- Patch releases may be adoption-driven; version numbers are not preallocated
  for speculative work.
- Features move when validation exposes prerequisite work.
- Public stability is earned through a written contract, upgrade path, and
  failure/recovery evidence.
- PostgreSQL remains the first choice for framework state until a measured
  requirement proves it insufficient.
- Framework guarantees stop where application policy, external systems, model
  quality, and operator retention begin.
- Existing stable paths remain compatible while experimental abstractions may
  be consolidated or removed with clear release notes.
- Recovery semantics and authorization under failure take priority over
  happy-path feature breadth.

## Beyond v0.7

Evidence from real durable-operation use should decide what follows. Possible
future work may stabilize selected higher-level consumers, reduce public and
internal API duplication, or address proven ORM and operational needs. No v0.8
feature set is committed here.
