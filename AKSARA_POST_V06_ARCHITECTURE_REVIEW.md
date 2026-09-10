# Aksara post-v0.6 architecture review

This review derives a direction from the repository at `main` commit
`7f3c6de81b055323e8786ff32572d0f0d188c1f9`, package version `0.6.0`. The
annotated `v0.6.0` tag resolves to `6bb2e81249c38d31332a8041e1755b765ed60c39`;
the tagged source tree and this `main` source tree are identical. The public
release is [Aksara v0.6.0](https://github.com/nagarjuna-tella/Aksara/releases/tag/v0.6.0).

The review used the implementation, tests, README, changelog, v0.6 stability
contract, RC2 release evidence, examples, generated project template, package
metadata, and CI/release workflows. At the time of review there were no open
issues. The open pull requests were three dependency updates for GitHub
Actions. Relevant remote branches were `release/v0.6.0`,
`codex/v060-rc2-mcp-ai`, `fix/advanced-field-policy-v055`, and the dependency
branches. This is a point-in-time baseline, not a claim that those remote facts
will remain current.

## Executive Summary

Aksara is a production-capable PostgreSQL backend framework inside a bounded
v0.6 contract. Its strongest architectural property is not the number of AI
features. It is that a model can produce REST and MCP surfaces which converge
on the same server-owned identity, permission, policy, field, tenant,
transaction, ORM, and RLS boundaries. The packaged Support Desk gate proves
that boundary with a restricted database role and an official MCP client.

The framework does not yet have a durable concept of an authorized operation.
MCP request, run, and tool-call identifiers live for one invocation. Replay
protection is an in-process dictionary. Approval is a signed stateless grant.
Audit is emitted to a sink but is not authoritative state. Runtime budgets and
cancellation are in memory. Investigation sessions are in an in-memory store.
The PostgreSQL task queue survives workers, but its record is task-specific,
captures tenant rather than the full principal, and does not unify approvals,
authorization, idempotency, cancellation, budgets, or MCP correlation.
`DurableStep` is another separate state mechanism with weaker recovery
semantics and runtime DDL.

The repository therefore supports the directional hypothesis, with one
important correction: v0.7 should be a **durable authorized operations**
release, not a broad “durable agent runtime.” The stable promise should be
that framework-managed work has an authoritative PostgreSQL identity and
state, remains queryable after a lost response, records each attempt, recovers
from worker loss, binds a decision to the exact operation, and rechecks current
authorization before a delayed mutation. Planner quality, conversation
memory, autonomous loops, provider intelligence, and Studio AI should remain
experimental consumers of that substrate.

Before that milestone, one adoption-focused v0.6.x release should make the
published product match the installed package. It should correct executable
AI documentation, distinguish `/mcp/` from `/ai/tools/mcp`, reconcile the
background-task Principal claim with implementation, and refresh package and
release evidence. Consolidation of duplicated execution and provider concepts
is prerequisite work on the path to v0.7, not the user-facing v0.7 thesis.

## What v0.6 Changed Architecturally

Before v0.6, Aksara could generate AI-facing metadata and tools. v0.6 moved the
security boundary from discovery into execution:

- The official MCP SDK owns protocol negotiation, sessions, `tools/list`, and
  `tools/call` over Streamable HTTP at `/mcp/`.
- A credential becomes a server-owned `Principal`; the caller cannot choose a
  tenant or acquire authority through a schema field.
- `AgentInvocationContext` freezes principal and correlation data for one
  invocation and propagates it with a context variable.
- Tool execution calls the generated API in-process, so REST and MCP share
  permission, `PolicyEngine`, serializer, field-policy, ORM, tenant, and RLS
  behavior.
- Mutations execute in a transaction and roll back on framework-visible
  failure. Errors have stable categories. Time, tool-call, token, and cost
  limits are enforced outside prompts.
- Approval grants are signed and bound to the exact principal, tenant, tool,
  arguments, approver, and expiry. Every resolved call emits a correlated,
  redacted audit event.

The architectural guarantee ends when the invocation ends. v0.6 proves that a
particular call is constrained while it executes. It does not establish an
authoritative record that can decide what happened after a process crash,
resume a call on another worker, or prevent the same approved action under a
new call ID. That boundary is explicit in
[`RELEASE_EVIDENCE_v0.6.0-rc2.md`](RELEASE_EVIDENCE_v0.6.0-rc2.md) and the
[`v0.6 stability contract`](docs/docs/roadmap/v0-6-stability-contract.md).

## Current Stable Contract

“Stable” below means the v0.6 compatibility commitment, within the documented
production profile. It does not mean feature-complete or externally certified.

| Subsystem | Classification | Repository evidence and actual boundary |
| --- | --- | --- |
| Application lifecycle and database ownership | **STABLE** | [`aksara/app.py`](aksara/app.py), [`aksara/db/engine.py`](aksara/db/engine.py), and [`aksara/db/session.py`](aksara/db/session.py) coordinate startup, shutdown, acquisition, cleanup, and cancellation. The release matrix exercises failure and pool reuse. |
| Settings and configuration | **STABLE** | [`aksara/conf.py`](aksara/conf.py) and documented `AKSARA_*` settings are stable. Old AI-profile settings remain as compatibility debt. |
| ORM fields, models, queries, and relations | **STABLE** | [`aksara/fields.py`](aksara/fields.py), [`aksara/model/base.py`](aksara/model/base.py), [`aksara/manager.py`](aksara/manager.py), and [`aksara/relations.py`](aksara/relations.py) implement the documented contract. Custom M2M through models and object-valued lazy forward FKs are excluded. |
| Transactions and connection/session handling | **STABLE** | Transaction scopes, tenant reset, acquisition failure, cancellation, and cleanup are release-tested against PostgreSQL. |
| Migrations | **STABLE** | The graph, autodetector, executor, operations, checksums, advisory locks, and existing migration-file compatibility are covered by [`aksara/migrations/`](aksara/migrations/) and migration tests. Production schema changes use a migration role before application startup. |
| Generated REST APIs and serializers | **STABLE** | [`aksara/api/viewsets.py`](aksara/api/viewsets.py), serializers, routers, filters, and field policy provide the documented CRUD, custom-action, validation, pagination, and authorization contract. |
| Principal, authentication adapters, permissions, and `PolicyEngine` | **STABLE** | [`aksara/security/`](aksara/security/) defines identity and enforcement hooks. Applications still own credential verification, role design, and policy decisions. |
| Tenant isolation | **STABLE** | Tenant context and ORM/API enforcement are defense in depth; the production claim requires a restricted PostgreSQL role and forced RLS. The restricted-role security test exercises REST, MCP, tasks, and pool reset. |
| MCP transport, discovery, schema, and execution | **STABLE** | [`aksara/mcp/server.py`](aksara/mcp/server.py) uses the official SDK and executes generated tools through the REST path. Only Streamable HTTP at `/mcp/` is in the contract. |
| MCP identity, authorization, fields, errors, transaction, and per-call limits | **STABLE** | Execution rechecks agent type, expiry, audience, scopes, tenant, permissions, policy, object access, input schema, and field writes. Stable errors, rollback, timeouts, cancellation, and audit events are tested. Their durability is excluded. |
| Bounded MCP approval grant | **STABLE** | [`aksara/mcp/approval.py`](aksara/mcp/approval.py) signs and verifies an exact, expiring grant. The durable human decision and single-use enforcement are application-owned in v0.6. |
| Background task queue | **STABLE** | [`aksara/tasks.py`](aksara/tasks.py) persists tasks, retries with backoff, claims through `FOR UPDATE SKIP LOCKED`, recovers stale locks, supports queues and schedules, and restores tenant context. The documented claim of full Principal propagation is not borne out by the persisted record and must be reconciled in v0.6.x. |
| Core CLI and Doctor | **STABLE** | Core development, migration, example-validation, and release-diagnostic commands have documented exit and JSON contracts and hosted release gates. |

The formal stability contract does not separately promise every README feature.
Admin, storage backends, generated SDKs, email, i18n, search, and the generated
project layout are useful and tested, but their detailed public compatibility
surfaces are less explicit. They should be treated as **FUNCTIONAL BUT
EVOLVING** unless a narrower contract documents otherwise. File and image
*field* behavior is stable through the ORM field contract; that does not make
every storage backend stable.

## Current Experimental Contract

| Subsystem | Classification | Evidence and reason |
| --- | --- | --- |
| `AgentPrincipal` / `Principal` | **STABLE** | The identity type and MCP propagation are part of v0.6. Agent intelligence built on it is not. |
| `AgentInvocationContext` | **STABLE** for one invocation | It is immutable and concurrency-isolated, but exists only in a context variable and cannot resume after restart. |
| Provider registry, AI Hub, connectors, and LLM clients | **EXPERIMENTAL** | Multiple configuration and adapter generations coexist across `providers.py`, `providers_unified.py`, `hub_settings.py`, `connectors/`, and `llm_clients/`; live provider quality is not release-certified. |
| Prompt-pack runtime | **FUNCTIONAL BUT EVOLVING** | [`aksara/ai/runtime.py`](aksara/ai/runtime.py) resolves a provider and applies in-memory limits. It is a bounded call helper, not a durable agent runtime. |
| Documented `AgentRuntime` class | **DEAD/UNUSED documentation surface** | Public documentation instantiates `AgentRuntime`, but no such class is defined or exported. The module called `agent.py` contains request/context models and does not call an LLM. |
| Planner | **PARTIAL** | [`aksara/ai/planner.py`](aksara/ai/planner.py) has plan data and deterministic handlers; generated test steps still contain TODO stubs. The documented `Planner` class does not exist. |
| Investigation engine | **EXPERIMENTAL** | Sessions, plans, steps, and findings work, but [`aksara/ai/session_store.py`](aksara/ai/session_store.py) stores them in a process-local dictionary. Resume cannot cross restart or workers. |
| Execution/orchestration models | **EXPERIMENTAL** | `AiPlan`, `ExecutionPlan`, `InvestigationSession`, `OrchestrationResult`, task records, and durable steps overlap without a shared authoritative execution identity. |
| AI budgets | **PARTIAL** | [`aksara/ai/limits.py`](aksara/ai/limits.py) counts steps, tools, tokens, and cost in memory. Provider accounting is accepted only when reported. |
| Approval workflow | **APPLICATION-OWNED** | The framework validates a grant at execution. It does not store requests, decisions, queues, notifications, or retention. |
| Audit retention and access | **APPLICATION-OWNED** | The framework emits a stable redacted event to logging, JSONL, memory, or an application sink. Long-term storage, access control, export, and certification are operator concerns. |
| Replay and arbitrary-tool idempotency | **PARTIAL** | MCP replay uses a bounded per-process map. Task retries require application functions to handle repeated external effects. |
| `DurableStep` | **FUNCTIONAL BUT EVOLVING** | [`aksara/workflows.py`](aksara/workflows.py) reuses completed PostgreSQL results for sequential steps. It has no stale-running lease recovery, principal/tenant/attempt context, or core migration and can issue runtime DDL. |
| Studio and Studio AI | **EXPERIMENTAL** | A large internal UI/API surface directly consumes evolving AI abstractions and process-local sessions. It has no production compatibility contract. |
| Code generation and patch application | **EXPERIMENTAL** | Deterministic validation and rollback exist, but autonomous code mutation and patch workflow behavior are explicitly outside v0.6. |
| Persistent AI memory and cross-worker sessions | **DEFERRED** | No durable implementation exists, and semantic memory is not required to make execution recoverable. |
| Multi-agent and autonomous workflows | **DEFERRED** | No stable orchestration contract or durable state model supports them. |
| `intent_engine_v2` | **DEAD/UNUSED implementation; compatibility shim remains** | Its implementation was merged into `intent_engine.py`; the old module only reexports symbols for compatibility and tests. Removal needs normal deprecation evidence. |
| Current-user demand for experimental AI APIs | **UNKNOWN** | The repository has no telemetry, open issues, or published usage evidence that identifies which experimental surfaces users depend on. |

## Architectural Seams

### 1. Correlation stops before it becomes state

`MCPRuntime._call_tool()` derives `request_id`, `run_id`, and `tool_call_id`,
puts them in `AgentInvocationContext`, then emits them to audit. No database row
owns those identifiers. If the client loses the response, there is no
framework query that can distinguish “never ran,” “committed,” and “committed
but response was lost.” This is the clearest missing abstraction.

### 2. The task queue is a useful primitive but not the shared operation model

`aksara_tasks` already proves that PostgreSQL can provide durable records,
atomic claims, bounded retries, stale lock recovery, named queues, and
multi-worker coordination. It is the strongest evidence that no new mandatory
runtime service is needed. Its record is nevertheless shaped around a Python
task: name, payload, tenant, status, attempts, timestamps, error, and result.
It lacks principal provenance, policy/approval references, idempotency key,
cancellation intent, correlation with an MCP request, and a transition log.

The correct evolution is to link tasks to a shared operation record or make
tasks one executor of it. Replacing the working queue in one release would add
risk without strengthening the guarantee.

### 3. `DurableStep` and tasks solve adjacent failure problems separately

`DurableStep` atomically claims a `(workflow_id, step_name)` and reuses a
completed result. A concurrent second call fails, and failed steps may retry.
It does not reclaim a step left `running` by a dead worker, record attempts or
identity, support cancellation, or fit the production migration-only database
role. The task queue has lease recovery but no workflow step identity. A shared
operation/attempt substrate should absorb the useful semantics before either
surface grows independently.

### 4. Approval proves authorization but not a human workflow decision

The HMAC grant is correctly narrow and tamper-evident. It is still reusable for
the same arguments during its validity window when a caller supplies a new
tool-call ID. The framework cannot answer whether a pending operation was
approved, rejected, expired, superseded, or already consumed. Durable state
belongs in the framework only for binding and enforcing a decision; the inbox,
review UX, notification, escalation, and business policy remain application
work.

### 5. Audit is observable, not authoritative

MCP audit sinks are valuable integrations. Sink failure is logged and swallowed
so it cannot corrupt application behavior. That also means an emitted event
cannot be the source of truth for operation outcome. A durable operation ledger
should transactionally record state transitions and a bounded history. An
application can then export those records to its chosen retention system.

### 6. Cancellation and budgets disappear with the process

`asyncio.CancelledError`, `asyncio.timeout`, and `AgentRuntimeBudget` constrain
the active call. There is no durable cancellation request for work waiting on
another worker, and counters cannot survive resume. Persisted cancellation
intent and bounded counters are natural fields of an operation; interruption
of an arbitrary external API call remains best effort.

### 7. Delayed authorization needs a deliberate rule

The current call rechecks current credential claims and policy immediately
before mutation. A delayed operation cannot safely treat the old “allowed”
decision as permanent. It needs immutable provenance for who requested the
work and a resolver that obtains current authority at each side-effect
boundary. Expired, revoked, tenant-changed, or newly denied authority must
pause or fail the operation without mutation. Raw bearer secrets should not be
stored in the ledger.

### 8. AI has several “run” models but no one execution vocabulary

Investigation sessions, `AiPlan`, `ExecutionPlan`, orchestration results,
prompt-pack calls, task records, and MCP contexts each define parts of a run.
Promoting any one of these would freeze accidental duplication. v0.7 needs a
small substrate beneath them: durable operation identity, attempts, state
transitions, provenance, lease, result/error envelope, and idempotency. Plans,
messages, findings, and provider details remain consumer-specific.

## Current Limitations by Category

### Application-owned

- Verifying user or agent credentials and resolving a server-owned `Principal`.
- Defining roles, permissions, policy rules, tenant membership, and which
  actions require human review.
- Human approval inboxes, notifications, escalation paths, and business SLAs.
- Long-term audit retention, external archival, access controls, reporting,
  legal holds, and certification.
- Idempotency of arbitrary external side effects when the external system does
  not offer an idempotency contract.
- Process supervision, TLS, backups, disaster recovery, secrets, and service
  monitoring.
- Provider choice, prompt quality, model evaluation, and domain-specific agent
  behavior.

### Framework gap

- An authoritative, queryable operation and attempt record shared by queued
  work and durable MCP/agent mutations.
- Cross-worker and restart-safe idempotency for framework-owned database work.
- Principal provenance plus current authorization re-evaluation when delayed
  work resumes.
- Leases, heartbeats, stale attempt recovery, durable cancellation intent, and
  persisted runtime counters.
- Durable binding and single-consumption of an approval decision to one exact
  operation.
- Transactional operation transitions that can drive audit export.
- A production migration for `DurableStep` if that API remains supported.

### DX/adoption

- The public Agent Runtime and Planner pages show `AgentRuntime` and `Planner`
  APIs which the installed package does not define.
- Several first-run/example pages call `/ai/tools/mcp` “MCP”; that route is the
  inspection catalog, while clients connect to `/mcp/`.
- The v0.6 task contract says Principal and tenant propagation, but
  `TaskRecord` persists and restores only `tenant_id`.
- Provider configuration is described through old and new systems, while
  deprecated AI settings marked for v0.6 removal remain in `Settings`.
- The generated project template mixes an `AKSARA` dict, a `Settings` subclass,
  and environment variables, and enables AI Mode in the template despite the
  product message that AI is optional.
- The current docs-lock test preserves obsolete roadmap items by literal
  string, making stale planning language a test requirement.
- The release evidence file is still RC2-specific; no final v0.6 evidence
  record binds the hosted final release in the repository.
- Package index metadata should be checked on every release against the current
  README; the published v0.6 metadata observed during this review lagged the
  repository description.

### Intentionally deferred

- Custom many-to-many through models and object-valued lazy forward foreign
  keys.
- MCP transports other than Streamable HTTP.
- Durable semantic memory, persistent conversations, multi-agent coordination,
  and autonomous planning.
- Live provider certification and provider-specific quality guarantees.
- A general cache API or mandatory Redis service.
- Exactly-once delivery for arbitrary external systems.

### Low-value

- Rewriting the backend core to prepare for 1.0 without a concrete contract
  failure.
- Adding Redis, Kafka, Temporal, or Celery before PostgreSQL has failed a
  measured requirement.
- Competing on generic workflow DSLs, provider count, planner benchmarks, or
  feature parity with Django or agent frameworks.
- Stabilizing Studio internals before the underlying execution and provider
  contracts settle.
- Filling the ORM's two explicit relation gaps as the main v0.7 milestone;
  useful demand could justify them in a patch/minor stream, but they do not
  strengthen Aksara's distinctive execution boundary.

## Maintenance / Complexity Findings

The repository contains about 88,000 lines across 188 package modules and about
100,000 lines across 285 test modules. That is substantial validation, but also
a broad pre-1.0 surface. The largest files are `cli/main.py` (8,132 lines),
`fields.py` (3,870), `studio/utils.py` (3,405), `studio/fastapi.py` (2,577),
`studio/models.py` (2,337), `migrations/operations.py` (2,307), `ai/patch.py`
(2,150), `manager.py` (1,987), and `ai/planner.py` (1,665). These are
modularization targets when work touches them, not a case for a rewrite.

An AST import scan found ten multi-module strongly connected components. The
largest contains 19 AI, search, gap-analysis, and Studio modules. A second
cycle contains ten foundational model/field/manager/relation/config modules.
`cli.main` has 44 internal dependencies and `aksara.__init__` has 24. This
coupling raises the cost of changing public imports and makes it especially
risky to promote the current experimental AI object model.

The checked-in static-analysis ratchet records 7,218 Ruff findings and 501
mypy findings. A package-only Ruff scan concentrated findings in the same
large CLI, Studio, fields, patch, serializer, manager, admin, context, and
planner modules. Most are modernization or annotation debt rather than proven
runtime defects; the actionable conclusion is to prevent growth and reduce
debt opportunistically along the v0.7 dependency path.

Several overlapping generations remain:

- provider profiles, unified providers, AI Hub settings, connectors, and LLM
  clients;
- `AiPlan`, `ExecutionPlan`, investigation plans, and orchestration results;
- task durability and `DurableStep` state;
- root-level reexports plus a large lazy AI export map;
- a deprecated `intent_engine_v2` compatibility shim and settings whose
  comments said they would be removed in v0.6.

Tests are extensive and release-shaped. The RC2 evidence records 7,995 passing
tests across supported Python/web boundaries, 428 security tests, 162 fuzz
tests, 314 diagnostics tests, and 51 packaged Support Desk checks. The risk is
not lack of tests. It is that many version-named and literal documentation
tests preserve historical structure rather than a compact current contract.
New v0.7 tests should center state-machine invariants and process/worker
failure, not another version-number layer of happy-path tests.

## Adoption Findings

The initial backend path is credible. A wheel includes project templates;
`aksara startproject`, `aksara dbsetup`, `makemigrations`, `migrate`, `dev`, and
Doctor form a recognizable flow. The README explains the differentiator with
one model feeding REST and MCP, and Support Desk demonstrates the production
profile with authentication, RLS, tasks, diagnostics, and a real MCP client.
A developer can understand the core idea in 10–15 minutes from the README.

The path becomes unreliable when the developer follows AI documentation. The
Agent Runtime and Planner pages present attractive APIs which cannot be
imported. Examples blur the protocol endpoint and the inspection catalog.
Configuration guidance spans several generations. These are trust failures:
they make experimental breadth look like installed capability and obscure the
stable differentiator that is already real.

The highest-value adoption work is subtraction and executable truth:

1. Keep one tested, copy-pasteable journey from a model to REST, then to a
   server-resolved Principal and an MCP call at `/mcp/`.
2. Mark conceptual AI examples as conceptual or rewrite them against exported
   functions and models.
3. Generate projects with one obvious configuration path and explicit opt-in
   for experimental AI surfaces.
4. Validate docs by building and executing imports/snippets against an
   installed wheel and a clean PostgreSQL database.
5. Keep Support Desk as the production reference rather than multiplying
   showcase applications.

This work is important enough for the next patch, but it does not change what
the framework can guarantee. It should not consume the v0.7 thesis.

## Candidate Directions for v0.7

| Rank | Candidate | Architectural fit and repository pull | User value and differentiation | Cost, burden, and risk | Milestone judgment |
| --- | --- | --- | --- | --- |
| 1 | **Durable authorized operations** | Very high. MCP already has safe invocation identity; tasks already prove PostgreSQL claims/recovery; approvals, audit, budgets, and sessions all stop at the same durability boundary. | High. Operators can answer what happened after a lost response and recover work without bypassing identity or policy. It extends the distinctive REST/MCP security convergence. | High implementation and testing cost; medium ongoing burden if kept to a state machine rather than a workflow DSL. Additive APIs can keep compatibility risk moderate. | **Yes.** It changes the stable guarantee and deserves v0.7. |
| 2 | **Framework consolidation / 1.0 foundations** | High need: large modules, cycles, broad exports, provider and execution duplication. | Indirect user value. It reduces regression risk but is not a distinctive capability by itself. | Medium-to-high cost; lowers future burden; high compatibility risk if framed as public API reduction. | **Prerequisite, not thesis.** Consolidate only along the durable-operation path and keep stable v0.6 APIs compatible. |
| 3 | **Developer experience and adoption** | High immediate need because docs and examples drift from exports and endpoints. | Very high first-user value and low conceptual risk. It reveals the product that already exists. | Low-to-medium cost, low burden, low compatibility risk. | **Patch stream.** It earns trust but does not justify a minor architectural milestone. |
| 4 | **Operational platform** | Moderate. Doctor, tracing, audit sinks, tasks, and production gates provide a base. | Useful visibility, but generic metrics/deployment tooling would blur Aksara into another backend platform. | High breadth and ongoing integrations; compatibility risk varies. | **Take the operation-status slice only.** Query and recovery visibility belong in v0.7; a broad operations suite does not. |
| 5 | **AI application development platform** | Mixed. There is abundant AI code, but execution models, providers, sessions, and public docs are fragmented and experimental. | Potentially high, but planner/provider quality would become the product promise and dilute the proven security boundary. | Very high implementation and maintenance cost; high compatibility risk from stabilizing premature APIs. | **No for v0.7.** AI features may consume the durable substrate experimentally. |

A relation-parity or general cache release ranks below these candidates. The
repository documents those omissions clearly, and neither creates the next
coherent Aksara guarantee.

## Recommended v0.7 Thesis

**Aksara v0.7 should make authorized operations recoverable and externally
decidable across process and worker loss.**

After v0.7, an application opting into durable execution should be able to:

- receive a framework-issued operation ID before execution;
- query one authoritative state after losing the original response;
- see bounded attempts, transition times, result or structured failure, and
  current lease ownership;
- reclaim work after a dead worker without two workers owning the same active
  attempt;
- reject a reused idempotency key with different inputs and return the original
  operation for the same scoped inputs;
- retain requester/agent/tenant provenance without storing raw credentials;
- re-resolve and re-authorize current identity before every resumed mutation;
- durably request cancellation and enforce it at claim and framework step
  boundaries;
- bind and consume an approval decision for one exact operation;
- enforce persisted framework counters across attempts; and
- derive correlated audit export from transactional state transitions.

Existing synchronous REST and MCP behavior should remain compatible. Durable
execution should be explicit for queued work and operations that can outlive a
request. Experimental planners may submit and observe such operations, but the
planner, conversation, and memory APIs do not become stable merely because the
operation substrate is stable.

## Why This Direction Wins

It closes one gap repeated across independent subsystems. MCP has identity and
policy but no state; tasks have state and recovery but incomplete identity;
approval has binding but no decision record; audit has correlation but no
authority; budgets and cancellation have enforcement but no persistence;
investigations have domain state but only in memory. One small operation model
can serve all of them without merging their domain-specific payloads.

It strengthens Aksara's actual competitive identity: allowing agents to act on
application data without bypassing the backend's normal contracts. Durability
matters here because delayed and retried work is precisely where security
context is often lost or stale decisions are reused.

It is testable without subjective model evaluation. PostgreSQL integration
tests can kill workers after claim, before commit, after commit but before
acknowledgement, during approval wait, after cancellation, and while two
workers race. The result is a release-grade guarantee rather than a demo-grade
capability.

It also uses infrastructure Aksara already requires. PostgreSQL transactions,
unique constraints, JSONB, row locking, `SKIP LOCKED`, and advisory-lock
experience are sufficient for the intended scale and semantics. No evidence
in this repository establishes a need for Redis, Kafka, Temporal, or Celery.

## Why Other Directions Lose

Consolidation is necessary but does not tell a user what becomes possible.
Broad cleanup also invites accidental breaking changes across the pre-1.0 API.
Restricting consolidation to the execution path produces a smaller, reviewable
dependency inversion with direct tests.

An AI application platform would stabilize abstractions the repository has not
settled. The nonexistent documented runtime classes, multiple plan models,
process-local sessions, provider layers, and TODO planner handlers are evidence
against promotion. Model quality is also harder to make deterministic than the
backend guarantees on which Aksara has built release trust.

A broad operational platform would duplicate mature infrastructure ecosystems.
Operation status, attempt history, recovery controls, and Doctor checks are
necessary because they expose the new guarantee. Generic dashboards, metrics
backends, deployment controllers, and tracing vendors are application or
integration choices.

DX work must happen first, but a documentation and scaffold release does not
constitute the next architectural boundary. It should remain a responsive
patch stream and should interrupt v0.7 work when serious user-facing defects
appear.

## Prerequisite Capabilities

Each capability below answers the roadmap acceptance questions: present
motivation, guarantee, minimum implementation, proof and failure cases,
compatibility, dependency, ownership, and excluded scope.

### 1. Canonical operation and attempt state

- **Motivation:** MCP correlation is ephemeral; tasks and `DurableStep` keep
  incompatible partial records; investigations are process-local.
- **Guarantee:** one operation ID has one authoritative PostgreSQL state and a
  bounded sequence of attempts and transitions.
- **Smallest implementation:** migrated operation and attempt tables, an
  explicit terminal-state machine, timestamps, correlation, typed result/error
  envelopes, and a read API. Keep plan steps and messages outside this core.
- **Proof and failures:** fresh migration, upgrade, rollback, concurrent state
  transition, invalid transition, lost response after commit, restart query,
  retention cleanup, and restricted-role DML tests.
- **Compatibility:** additive. Existing synchronous calls and task IDs remain
  valid; internal table columns stay private.
- **Dependency and owner:** PostgreSQL only; this is framework-owned because
  every executor needs the same truth.
- **Non-goals:** event sourcing, arbitrary DAGs, business workflow schemas, or
  durable conversation storage.

### 2. Claims, attempts, leases, and recovery

- **Motivation:** tasks already recover stale claims, while `DurableStep` and
  AI/MCP runs do not share that behavior.
- **Guarantee:** at most one live framework lease owns an attempt, and abandoned
  work becomes reclaimable under explicit retry policy.
- **Smallest implementation:** atomic claim, lease deadline/heartbeat, attempt
  number, retry schedule, terminal ownership checks, and worker fencing token.
- **Proof and failures:** two-worker races, worker kill before work, kill during
  work, lease expiry, late completion from a fenced worker, database disconnect,
  retry exhaustion, and shutdown cancellation.
- **Compatibility:** integrate by linking existing task records before
  considering replacement. `DurableStep` stays evolving until adapted.
- **Dependency and owner:** PostgreSQL row locks and transactions; framework-owned
  because the guarantee spans workers.
- **Non-goals:** distributed scheduling across arbitrary infrastructure,
  sub-second high-throughput queues, or exactly-once external effects.

### 3. Scoped idempotency and transaction boundaries

- **Motivation:** MCP replay is per-process and a new tool-call ID can repeat an
  approved action; retries can repeat effects.
- **Guarantee:** the same principal/tenant/operation namespace and idempotency
  key with the same canonical input resolves to one operation; changed input
  conflicts. Framework database state and operation transition commit together
  where they share a database transaction.
- **Smallest implementation:** unique scoped key, canonical input hash,
  operation lookup, transactional completion helper, and explicit external
  effect classification.
- **Proof and failures:** concurrent duplicates across workers, same key with
  changed body, crash before commit, commit followed by response loss, retry,
  tenant/principal key collision, and expired retention window.
- **Compatibility:** opt-in durable calls add an idempotency field/header;
  existing replay behavior remains for ordinary synchronous MCP calls.
- **Dependency and owner:** PostgreSQL only. Framework owns database-operation
  idempotency; applications own external effect adapters and keys.
- **Non-goals:** claiming exactly-once delivery to email, payment, model, or
  arbitrary HTTP providers.

### 4. Durable identity provenance and reauthorization

- **Motivation:** queued tasks preserve only tenant, and delayed work cannot
  safely reuse an old authorization result.
- **Guarantee:** every durable operation records who and which tenant requested
  it, and no resumed mutation runs without resolving and checking current
  authority.
- **Smallest implementation:** a serializable, versioned principal reference
  and immutable request provenance; an application-supplied resolver; current
  expiry/audience/scope/permission/policy/tenant checks before side effects;
  structured `authorization_required` and `authorization_denied` states.
- **Proof and failures:** revoked user or token, expired credential, changed
  roles, deleted tenant membership, cross-tenant resume, missing resolver,
  tampered provenance, and policy change between attempts.
- **Compatibility:** do not change `Principal`; add serialization/reference
  contracts. Existing tenant-only tasks remain readable and must fail closed
  when a new durable policy requires unavailable provenance.
- **Dependency and owner:** no new service. Framework owns enforcement points;
  applications own identity resolution and current business policy.
- **Non-goals:** storing raw bearer tokens, inventing an identity provider, or
  freezing authorization at enqueue time.

### 5. Durable decisions, cancellation, and bounded counters

- **Motivation:** approvals, cancellation, and budgets are currently stateless
  or process-local.
- **Guarantee:** an exact operation can wait for, consume, or reject a recorded
  decision; cancellation intent and framework counters survive attempts.
- **Smallest implementation:** decision status/reference and payload hash,
  single-consumption constraint, cancellation-requested timestamp, counters for
  attempts/tool calls/steps/provider-reported usage, and checks at framework
  boundaries.
- **Proof and failures:** duplicate and changed approval, expiry, rejection,
  approver mismatch, cancellation before claim and between steps, late worker,
  counter exhaustion across restart, malformed provider usage, and race between
  approve/cancel/claim.
- **Compatibility:** the v0.6 signed grant remains valid for synchronous calls;
  durable operations add a stored decision path.
- **Dependency and owner:** PostgreSQL only. Framework owns exact binding and
  enforcement; applications own review UX, approver policy, and notifications.
- **Non-goals:** a generic human-workflow product, force-killing arbitrary
  external code, or trusting unreported provider usage.

### 6. Queryable status and audit export

- **Motivation:** audit events are useful but cannot determine state after a
  sink failure or lost response.
- **Guarantee:** authorized operators can query an operation and its bounded
  attempts; audit output derives from transactional transitions with stable
  correlation and redaction.
- **Smallest implementation:** policy-filtered get/list/cancel endpoints or
  Python APIs, transition records sufficient for diagnosis, redaction rules,
  retention/pruning hook, and export sink integration.
- **Proof and failures:** cross-tenant and unauthorized reads, hidden payloads,
  sink failure, pruning, concurrent pagination, unknown operation, and audit
  reconstruction after restart.
- **Compatibility:** additive; preserve the existing MCP audit sink event and
  evolve it with optional operation/attempt identifiers.
- **Dependency and owner:** PostgreSQL only. Framework owns bounded operational
  history and access enforcement; applications own indefinite retention and
  external compliance reporting.
- **Non-goals:** a full observability backend, SIEM, legal archive, or stable
  Studio dashboard.

## Recommended Release Sequence

### v0.6.x adoption stream, with v0.6.1 only when fixes are ready

**Theme:** installed-package truth.

**Problem:** incorrect AI API examples, MCP endpoint ambiguity, task Principal
contract drift, provider/configuration overlap, stale package metadata, and the
lack of a final-release evidence record undermine the v0.6 contract.

**Change and value:** correct documentation and examples against wheel exports;
add executable snippet/import checks; make `/mcp/` the only protocol-client
address; either implement the narrow documented task identity behavior safely
or narrow the contract to tenant propagation; refresh package metadata and
bind final release evidence. This lets a new developer follow the published
path without discovering conceptual APIs.

**Dependency:** none. Serious production, compatibility, security, packaging,
or MCP interoperability bugs take priority and may change the contents of the
patch.

**Acceptance:** clean-wheel quickstart against PostgreSQL; documented imports
execute; MCP examples initialize an official client at `/mcp/`; task identity
claims have direct tests; strict docs and release diagnostics pass; no stable
v0.6 API is intentionally broken.

**Non-goals:** new durable tables, planner features, memory, Studio promotion,
or a public execution API.

Do not reserve v0.6.2 or v0.6.3 now. Use later patch numbers only for validated
bugs, compatibility, adoption, or release-hygiene work.

### Architectural prerequisite stream toward v0.7

This work may proceed behind experimental/internal interfaces without being
published as a separate promised release:

1. Write the operation state-machine and authorization ADR before schema/API
   work. Resolve sync versus durable invocation and retention defaults.
2. Consolidate only the shared execution vocabulary. Keep planner and provider
   refactors out unless they remove a direct dependency cycle on that path.
3. Add migrated operation/attempt storage, claims, leases, idempotency, and a
   policy-filtered read API.
4. Link the existing task queue to operation identity and add full provenance,
   reauthorization, cancellation, and counters.
5. Add a durable dispatch path for selected MCP/agent mutations and stored
   approval decisions. Preserve synchronous MCP behavior.
6. Run prerelease failure campaigns against PostgreSQL with multiple processes,
   restricted roles, real MCP clients, restarts, and installed wheels.

### v0.7.0 — Durable authorized operations

**Stable contract:** explicit durable operations have PostgreSQL identity,
queryable state, attempt history, lease/fencing recovery, scoped idempotency,
identity provenance and current reauthorization, durable decision binding,
cancellation intent, persisted counters, and transactionally correlated audit
history.

**User-visible value:** an operator can decide whether work ran after a lost
response, safely retry framework-owned database operations, move execution to
another worker after failure, and explain which identity, approval, policy,
attempt, and result governed the operation.

**Acceptance:** upgrade and rollback-safe migrations; compatible v0.6 API;
multi-worker and process-kill tests at every commit/ack boundary; authorization
revocation and cross-tenant tests; approval/idempotency races; cancellation and
budget tests across restart; restricted-role production gate; packaged-wheel
official MCP client; strict Doctor checks for schema and worker readiness.

**Mandatory dependency:** none beyond PostgreSQL. If implementation uncovers a
requirement PostgreSQL cannot meet, the release must document the measured
limit before adding infrastructure.

**Non-goals:** exactly-once external side effects, arbitrary workflow graphs,
durable conversations or memory, autonomous planner stability, provider quality
guarantees, a production Studio contract, or general distributed systems
infrastructure.

## What Should Remain Experimental

- Planner selection, decomposition, generated tests, autonomous loops, and
  model-produced code.
- Investigation session shape, transcripts, findings, and semantic memory. An
  investigation may reference a durable operation without its content model
  becoming stable.
- Provider registries, connector quality, model selection, token/cost accuracy,
  and third-party adapters.
- Studio UI and Studio AI internal endpoints.
- Patch generation/application workflows and automatic mutation approval.
- Generic/OpenAI/third-party tool export adapters outside the MCP contract.
- `DurableStep` and higher-level workflow composition until they use the shared
  lease, attempt, identity, cancellation, and migration semantics.
- Multi-agent coordination and durable autonomous workflows.

Experimental APIs may use the v0.7 substrate. They should not expand its
stable contract or dictate its schema.

## Explicit Non-Goals Through v0.7

- A generic workflow engine, DAG language, scheduler product, or Temporal clone.
- Exactly-once effects across email, payments, providers, or arbitrary HTTP APIs.
- Persistent chat history, vector memory, agent personality, or multi-agent
  collaboration.
- Planner/provider quality parity with dedicated agent frameworks.
- Redis, Kafka, Celery, or another mandatory runtime service.
- A broad public-API cleanup or 1.0 compatibility promise.
- Stabilizing Studio or its internal HTTP APIs.
- Supporting every MCP transport.
- Django feature parity, custom M2M through models, or object-valued lazy
  forward FKs as milestone work.
- A full observability, audit-archive, or human-approval product.
- Replacing the working task queue before an incremental integration proves
  that replacement is necessary.

## Risks

| Risk | Consequence | Control |
| --- | --- | --- |
| “Durable” becomes a workflow-engine wishlist | Scope and compatibility explode | Stabilize only operation/attempt state and explicit executor hooks; keep plans and graphs outside. |
| Old authorization is replayed after delay | Revoked or cross-tenant work mutates data | Persist provenance, resolve current identity, and recheck policy before each mutation boundary. |
| Idempotency is mistaken for exactly-once external effects | Duplicate payments, mail, or provider calls | Guarantee only framework-owned database effects; expose application idempotency adapters and document at-least-once execution. |
| A late worker commits after losing its lease | Two attempts can produce conflicting state | Use fencing tokens and verify ownership inside the completion transaction. |
| Operation records leak prompts, credentials, or business data | Security and retention burden | Store hashes/references and redacted result/error envelopes; never persist raw bearer tokens; keep retention bounded. |
| Operation tables become a database hotspot | Latency and cleanup pressure | Index claim/query paths, bound history, test contention, and add pruning before stability. |
| Task, MCP, and AI APIs are forcibly merged | Regressions and an incoherent abstraction | Share state primitives and identifiers; keep executor-specific payloads and APIs separate. |
| Consolidation breaks broad imports | Pre-1.0 users still incur avoidable migration cost | Preserve stable exports, deprecate shims, and refactor behind compatibility tests. |
| Adoption repair is deferred for architecture | Users cannot trust current docs | Ship verified v0.6.x truth first and let serious production bugs interrupt the planned sequence. |

## Unknowns

- Which experimental AI surfaces, if any, have real external users. The empty
  issue tracker is not evidence of no usage.
- Whether users prefer an asynchronous operation response for all durable MCP
  mutations or an explicit separate dispatch tool/API.
- The correct retention and pruning defaults for results, errors, attempts, and
  input hashes.
- The minimum principal reference applications can resolve across restarts
  without storing credentials or coupling Aksara to one identity provider.
- Whether the stable task table shape is used directly despite being documented
  as internal, and therefore how cautiously it must be migrated.
- Which external-effect adapter contract is small enough to be useful without
  implying exactly-once semantics.
- The throughput and latency at which a PostgreSQL operation ledger would stop
  meeting actual users' requirements. No repository evidence currently shows
  that limit.
- Whether `DurableStep` has external adoption that warrants adaptation rather
  than deprecation.
- What final hosted evidence should replace or supplement the RC2-specific
  evidence file for future release archaeology.

## Final Recommendation

Ship one evidence-backed v0.6.x adoption repair when it is ready. In parallel,
design v0.7 around a minimal PostgreSQL operation/attempt state machine. Reuse
the task queue's proven claim and recovery mechanics, preserve the MCP runtime's
authorization and REST convergence, and add only the state necessary to make
framework-managed work queryable, recoverable, reauthorized, idempotent within
its database boundary, cancellable, and auditable across workers.

Do not promote the current planner, provider, investigation, Studio, or workflow
APIs as the milestone. They can become safer experimental clients of the new
substrate. Stable status should follow multi-process failure evidence and an
installed-wheel production gate, not the presence of a class name or a version
number.

**If v0.6 made Aksara agent execution safe, v0.7 should make Aksara authorized operations durable.**

## Operator summary

### What should we work on immediately?

Correct the installed-package story: executable AI docs, the `/mcp/` endpoint,
the task Principal contract, provider/configuration guidance, package metadata,
and final release evidence. Then write the durable-operation state-machine and
authorization ADR before implementation.

### What should we deliberately NOT work on?

Planner quality, memory, multi-agent workflows, a generic workflow engine,
provider parity, production Studio, broad 1.0 cleanup, relation parity, or new
mandatory infrastructure.

### What should v0.7 mean?

An explicit authorized operation remains identifiable, queryable, bounded,
recoverable, reauthorized, and auditable after a response, process, or worker
is lost.

### What is the smallest credible path to it?

Add a migrated PostgreSQL operation and attempt ledger; link the existing task
worker to it; add leases/fencing, scoped idempotency, principal provenance and
reauthorization, then durable decisions/cancellation/counters and a
policy-filtered status API. Extend selected MCP mutations only after those
invariants pass multi-process failure tests.

### What code evidence most strongly drove that conclusion?

`mcp/server.py` creates strong but ephemeral invocation context; `tasks.py`
already proves PostgreSQL multi-worker recovery; `approval.py`, `audit.py`, and
`ai/limits.py` stop at process lifetime; `session_store.py` is explicitly
in-memory; and `workflows.py` independently persists steps without task-grade
leases or production migrations.

### What assumption from this prompt did the repository disprove, if any?

It disproved the broad phrase “durable agent runtime.” Aksara does not yet have
one coherent agent runtime to make durable: the documented runtime classes do
not match exports, and plan/session/provider abstractions overlap. The evidence
supports a narrower, stronger substrate—durable authorized operations—while
agent behavior remains experimental.
