# Aksara after v0.7: market and roadmap review

Research date: **2026-09-11**. Framework baseline: released **v0.7.0**,
`b7ac75f4b1bd4b262824e828601168336b4ecf7f`.

This is a strategy recommendation, not an implementation authorization, release
approval, or claim of customer demand. The v0.7.1 documentation and installed
application journeys are still being validated. Source and test anchors below
describe the released implementation; they do not substitute for candidate
regression results.

## Executive Summary

Aksara fits the **Python application backend framework** category. Its strongest
technical proposition is bringing generated APIs, tenant-aware persistence, and
delayed authorized application mutations into one supported contract. It is
more opinionated than an API framework, less operationally complete than a
hosted backend platform, and narrower than a general durable workflow engine.

Lead with the backend. Present AI agents as one kind of client. The original
claim that every human, service, job, tool, and agent automatically shares the
same boundary is too broad: ordinary tasks retain tenant context, not a complete
Principal; custom code must use the supported permission and execution paths.
Durable actions require application-owned current identity resolution and action
authorization. These qualifications should be visible in the first explanation.

Recommend **v0.8: operating authorized application work in production**. The
single problem is making the existing execution contract deployable, inspectable,
and recoverable by someone other than its author. Start with one reference
deployment, worker lifecycle guidance, identity-provider integration, and
correlated operational evidence. Add framework APIs only where real deployments
show that existing public seams are insufficient. Do not implement this thesis
in v0.7.1.

The main adoption blocker currently demonstrated is public usability, followed
by the amount of integration and operating knowledge users must supply.
Independent production demand remains unproven. A technically unusual boundary
is not yet a commercial moat.

## What Aksara Actually Is Today

The released package includes an async PostgreSQL ORM, migration engine,
generated REST/ViewSets, serializers, identity and policy primitives, tenant/RLS
support, Admin, tasks, storage, CLI/Doctor, TypeScript generation, synchronous
MCP tools, and opt-in Durable Authorized Operations. The
[public-truth audit](AKSARA_V071_PUBLIC_TRUTH_AUDIT.md) records the broader
capability inventory and candidate verification gaps.

The distinguishing durable unit is an application **Operation**, not a workflow
graph or a persisted conversation. A physical execution is an Attempt. For
`postgres_atomic`, the supported application mutation and authoritative success
state commit on the same guarded PostgreSQL transaction. External calls have a
different contract and may end in `external_outcome_unknown`.

The [v0.7 contract](docs/docs/roadmap/v0-7-stability-contract.md) requires restricted
roles, tenant enforcement, correct action classification, retained registrations,
and operated workers/export/retention. It does not promise safety for arbitrary
Python code, direct database connections, or a provider's external effects.

## Capability Inventory

These source/test pairs are the evidence for the strategic argument. The
candidate audit owns the full stability matrix and installed-wheel results.

| Capability | Source evidence | Executable contract evidence | Strategic implication |
| --- | --- | --- | --- |
| Models, fields, queries, relations | `aksara/model/`, `aksara/manager.py`, `aksara/fields.py` | `tests/fields/`, `tests/test_relations.py` | Useful backend foundation; declared relation exclusions matter |
| Migrations | `aksara/migrations/`, `aksara/core/migrations/` | `tests/migrations/` | Upgrade confidence is essential, not optional polish |
| Generated APIs and serialization | `aksara/api/viewsets.py`, `serializers.py`, `router.py` | `tests/api/`, `tests/security/fuzz/` | Reduces repeated CRUD wiring; OpenAPI itself is table stakes |
| Principal, permission, field policy | `aksara/security/`, `aksara/permissions.py` | `tests/security/`, `tests/mcp/` | Shared enforcement is useful only where each entry point participates |
| Tenancy and RLS | `aksara/tenancy.py`, `aksara/db/tenant_context.py` | `tests/security/test_tenant_isolation.py` | PostgreSQL is part of the semantics, not a replaceable URL |
| Ordinary tasks | `aksara/tasks.py` | `tests/test_tasks.py` | Queueing does not automatically preserve requester authority |
| Durable admission and current authority | `aksara/durable/service.py`, `registry.py` | `tests/durable/test_service.py`, `test_authorization.py` | Addresses authority changes between submission and execution |
| Atomic effects and ownership | `aksara/durable/execution.py`, `aksara/db/durable_guard.py` | `tests/durable/test_atomic_execution.py`, `test_multiprocess.py` | Avoids split commits within the supported same-database boundary |
| External effects | `aksara/durable/external.py` | `tests/durable/test_external_effects.py` | Honest uncertainty and reconciliation are part of the product |
| Outbox, retention, diagnostics | `aksara/durable/outbox.py`, `diagnostics.py`, service pruning | `tests/durable/test_outbox.py`, `test_retention.py`, `test_diagnostics.py` | Primitives exist; an operator still needs a complete runbook |
| API and query diagnostics | `aksara/middleware/tracing.py`, `aksara/db/tracing.py` | `tests/db/test_tracing.py`, `tests/diagnostics/` | Do not describe observability as absent; integration and correlation need evaluation |
| MCP | `aksara/mcp/` | `tests/mcp/`, installed-wheel reference checks | An application access surface, not a reason to build another agent planner |
| Client generation | `aksara/sdk/typescript.py` | SDK and CLI tests | Useful convenience; generated-client usability needs its own journey |
| AI, Studio, DurableStep | `aksara/ai/`, `aksara/studio/`, `aksara/workflows.py` | Component tests, separate stability exclusions | Existence and component tests do not make these v0.7 durable guarantees |

## Product Hypotheses Considered

| Hypothesis | What supports it | What challenges it | Decision |
| --- | --- | --- | --- |
| General Python web framework | HTTP, ORM, Admin, CLI | Broad framework competition requires ecosystem breadth; few users need every Aksara subsystem | Valid parent category, insufficient positioning |
| Application backend with authorized durable actions | Persistence, APIs, policy and guarded effects share a contract | Requires adoption of Aksara's data/identity model and careful operation | Best primary description |
| AI-native backend | Generated MCP, agent Principal, budgets and approvals | Ordinary backend work is primary; planners and Studio are experimental | Use only as a qualified capability description |
| Agent framework | Provider/runtime-adjacent modules exist | Would compete on memory, planning, models and orchestration rather than the strongest stable work | Reject as primary category |
| General durable runtime | Attempts, retry, fencing, cancellation | No claim of arbitrary replayable workflow composition | Supporting capability, not Temporal replacement |
| Backend-as-a-service | Many backend functions exist | A package does not supply managed hosting, provisioning, identity service or operational SLAs | Reject |
| MCP backend for existing applications | A stable MCP boundary is available | Same-transaction guarantee requires the supported Aksara database path; retrofitting any ORM is not demonstrated | Secondary integration hypothesis, not a universal retrofit claim |

## Market Categories

The comparison uses primary documentation, not popularity rankings. It answers
which layer each project asks a developer to adopt. Product pages establish
documented capability, not actual reliability, customer satisfaction, or demand
for Aksara. No performance comparison was run.

## Adjacent Systems

### Python application frameworks

| System | Primary abstraction and data choice | Relevant capability | Relationship to Aksara |
| --- | --- | --- | --- |
| [Django](https://docs.djangoproject.com/en/6.0/intro/overview/) | Models, views and reusable applications | Integrated ORM and model-driven Admin; [migration workflow](https://docs.djangoproject.com/en/6.0/topics/migrations/) | Competes for new Python applications; benchmark the completeness of its learning and upgrade paths, not feature count |
| [FastAPI](https://fastapi.tiangolo.com/features/) | Typed path operations and dependencies | Validation, OpenAPI, security building blocks, generated-client compatibility | Aksara adds an opinionated application model and execution contract on this ecosystem; do not claim FastAPI lacks authentication or validation |
| [Litestar](https://docs.litestar.dev/latest/) | ASGI handlers, DI, DTOs and integrations | SQLAlchemy/Piccolo integration, security, OpenAPI, metrics and plugins | Direct DX comparator; typed APIs, integrations and telemetry are not unique Aksara advantages |
| [Flask](https://flask.palletsprojects.com/en/stable/extensions/) | Small web core extended by packages | Database, email and other integrations through extensions | Competes on simplicity and composability; Aksara trades choice for a shared contract |

Django's integrated application path is a stronger comparison than saying
"FastAPI plus an ORM." However, promising Django equivalence would be misleading:
Aksara declares unsupported relation forms and has not established equivalent
third-party application compatibility. Existing Django teams should not migrate
merely to obtain CRUD or Admin. Existing FastAPI teams should adopt Aksara only
when its chosen persistence and authorization contract saves more work than the
integration costs it introduces.

### Backend platforms

| System | Documented unit / convenience | Architectural boundary | Lesson |
| --- | --- | --- | --- |
| [Supabase](https://supabase.com/docs) | PostgreSQL, Auth, Storage, Realtime, APIs and client libraries | Backend platform with hosted and self-hosted paths | PostgreSQL plus API generation is not enough differentiation; identity and client onboarding matter |
| [Appwrite](https://appwrite.io/docs) | Auth, databases, files, functions, messaging and SDKs | Integrated backend services | Users expect a connected journey through common app needs, not disconnected capability pages |
| [PocketBase](https://pocketbase.io/docs/) | Embedded SQLite, auth, dashboard and REST-like API | Small standalone backend / Go framework; docs explicitly warn about pre-1.0 compatibility | Low-friction evaluation is valuable; do not borrow its deployment simplicity while promising different database guarantees |
| [Convex](https://docs.convex.dev/understanding/overview) | Reactive queries, transactional mutations, actions and clients | Backend/database execution model with explicit separation of network actions | Automatic consistency and coherent abstractions compete with framework assembly; durable scheduling is not uniquely Aksara's |

These systems establish convenience expectations even for developers who choose
to operate Python themselves. They are not interchangeable databases underneath
Aksara. A verified managed-PostgreSQL deployment could complement a platform;
support for a hosted product's pooling, roles and RLS profile must be tested
before claiming compatibility.

### Background and durable execution

| System | Work unit and operational model | Relevant documented behavior | Aksara boundary |
| --- | --- | --- | --- |
| [Celery](https://docs.celeryq.dev/en/stable/userguide/tasks.html) | Named task delivered to a worker through a broker | Acknowledgement, retry and worker-loss behavior depend on configuration; idempotent tasks recommended | Do not equate all queues with exactly-once execution or automatic application authorization |
| [Dramatiq](https://dramatiq.io/guide.html) | Actor/message and worker | Automatic retry with configurable backoff and retry limits | Useful task execution comparator; Aksara should not rebuild a broker ecosystem |
| [RQ](https://python-rq.org/) | Python function/job with Redis connection and workers | Delayed/repeated jobs, retries and scheduler-enabled workers | Simplicity benchmark; ordinary jobs remain a valid choice |
| [Temporal](https://docs.temporal.io/workflow-execution) | Workflow execution, activities, service and workers | Event history and replay, waits, child workflows and cancellation | Complement through an application API when appropriate; do not promise equivalent workflow semantics |
| [Inngest](https://www.inngest.com/docs/learn/inngest-steps) | Functions composed of persisted steps | Step result memoization, independent retries, sleeps and waits | Competes on developer-friendly durable composition; a persisted step is not proof of atomicity with arbitrary application SQL |
| [Trigger.dev](https://trigger.dev/docs/introduction) | Tasks/runs, deployment and operational dashboard | Queuing, retries, schedules and realtime run status; cloud or self-hosted | Operator and client status experience is a relevant adoption benchmark |
| [Hatchet](https://docs.hatchet.run/v1) | Tasks, workers and durable workflows | Persisted execution, retries, checkpointing, monitoring and logs | Broad execution platform; durable Python work alone is not Aksara's differentiator |

The reviewed execution documents do not establish a universal absence of
authorization hooks. A developer can put fresh authorization into a task or
activity. Aksara's proposition is making a specific application contract
available and tested together, not inventing reauthorization or preventing
other frameworks from implementing it.

### Agent and AI application infrastructure

| System | Documented focus | Intended Aksara relationship |
| --- | --- | --- |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence) | Graph state checkpoints, persistent memory and interrupted-run recovery | Agent chooses work; application backend authorizes and performs mutations |
| [Pydantic AI](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/) | Typed agents and durable execution integrations, including Temporal, DBOS and Prefect | Prefer consumer integration over another planner or persistence layer |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | Tools, handoffs, guardrails, MCP integration and tracing | Use supported REST/MCP as an application boundary; SDK guardrails do not replace database permissions |
| [Google ADK](https://google.github.io/adk-docs/) | Agent construction, tools, orchestration, evaluation and deployment | Complementary consumer; do not compete on the full agent lifecycle |
| [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/) | Agents, state, telemetry and explicit workflows | Integrate at authenticated application interfaces rather than duplicate orchestration |
| [CrewAI](https://docs.crewai.com/) | Agents, crews and persisted/resumable flows | Similar consumer opportunity; its workflows are not an Aksara stable surface |

This market already includes persistence, human participation and recovery.
"Agents that survive failure" would underspecify Aksara's distinction. The
useful application question is whether an actor still has permission to change
this tenant's record when execution resumes. No official integration with these
frameworks is claimed by this review; MCP compatibility is not proof that every
framework/version has been tested.

### Authorization and policy

[OpenFGA](https://openfga.dev/docs/concepts) models access through authorization
models and relationship tuples. [Oso](https://www.osohq.com/docs) provides policy
and authorization APIs, including RBAC, ReBAC and ABAC.
[Casbin](https://v3.casbin.org/docs/supported-models) supports several access
control models, including tenant-scoped RBAC and ABAC.

These are reasons to investigate an integration seam, not reasons to build a
new relationship graph service. Aksara still owns enforcement at the request or
effect boundary. Any remote-policy adapter must specify failure handling,
freshness, object/query filtering, field policy and tenant binding. A boolean
"allowed" response does not by itself prove safe list queries or database writes.

## Competitive and Complementary Positioning

Compete for a **new PostgreSQL-backed Python application** whose engineers would
otherwise assemble models, generated APIs, policy checks and durable action
state. Complement external identity, observability, storage and agent systems.
Use orchestrators through explicit APIs when a product needs long-lived
composition beyond a single application Operation.

Do not recommend replacing a functioning Django application, an established
Temporal deployment, or a hosted backend merely to consolidate dependencies.
Switching cost includes models, migrations, identity mapping, operation history,
testing, deployment and team knowledge. A sidecar is not automatically cheap:
remote mutations cannot inherit Aksara's same-database atomic guarantee.

## Table Stakes

These are qualitative assessments for the proposed primary user, not universal
framework ratings. "Weak" concerns the adoption path unless a concrete missing
implementation is identified. Component existence is not certification.

| Area | Assessment | Evidence / work needed |
| --- | --- | --- |
| PostgreSQL, ORM and migration safety | Already strong within declared scope | Source, regression suites and release evidence; retain explicit relation exclusions |
| Generated REST, validation, OpenAPI | Adequate | Existing implementation; prove common customization and error handling from docs |
| Principals, permissions, RLS | Already strong bounded contract | Security and durable authorization tests; operator configuration remains essential |
| Authentication integration | Weak adoption path | Auth/session primitives exist; this audit has not verified a turnkey external OIDC lifecycle |
| OAuth/social-provider breadth | Missing verified integration evidence | Do not claim the package contains none based only on a text search; select a provider from actual user need |
| Admin | Adequate foundation | Avoid promising Django plugin parity or stable Studio internals |
| Tasks and durable actions | Already strong semantics; weak discoverability | Separate Task from Operation and demonstrate both from installed wheel |
| Scheduling | Adequate for documented task paths | No reason yet for a new universal workflow/scheduling service |
| WebSockets/SSE | Existing underlying/specific surfaces | `aksara/api/streaming.py` exists; no hosted realtime-sync platform claim |
| Storage and email | Existing integrations | `aksara/storage.py` and media/email docs; independently execute the recommended configuration |
| Cache | No generalized cache contract verified here | Application/library integration before a framework-wide cache abstraction |
| Testing | Already strong release campaign; weak beginner bridge | Turn tests into public workflows, without presenting test counts as user success |
| Observability | Adequate primitives; weak end-to-end operational story | Query tracing, Doctor and outbox exist; correlate API → Operation → Attempt → effect |
| Deployment and upgrades | Weak reader journey | Reference app exists; independent reproducible rollout/rollback and restore instructions needed |
| Configuration/secrets | Adequate implementation; weak consistency | Global settings and environment precedence must have one authoritative reference |
| SDKs | Adequate narrow TypeScript generation | Test generated client against real documented endpoints; other languages can start with HTTP |
| CLI/scaffold | Adequate commands; instructional gaps | Fresh public install works; starter must explain auth, migrations and tests |
| Docs and integrations | Weak | Measured audit contradictions and pending complete learning path |
| Plugin ecosystem | Not established by this review | Prefer a few versioned integration contracts over promising an ecosystem |
| Managed hosting, generic identity service | Intentionally out of scope | Use existing services; no need to operate a cloud platform to reach 1.0 |

## Current Differentiators

The strongest combination is current identity resolution, tenant-aware policy,
fenced execution and a same-database commit boundary. Each component is familiar;
maintaining their behavior together during retries, cancellation, worker loss
and upgrades is less trivial than connecting a few packages on a happy path.
The source and failure campaigns support that integration claim.

Generated REST/MCP access, bounded approval intent, scoped idempotency and
explicit external uncertainty make that boundary usable by several kinds of
client. They are supporting features. PostgreSQL queues, approval screens,
OpenAPI, typed Python and MCP discovery individually are not defensible moats.

Durable authorization should be the **lead differentiating use case**, after a
plain backend category description. Its value must be demonstrated through a
ticket action submitted today, permission revoked before a delayed attempt, and
the mutation safely denied tomorrow. An ordinary CRUD demonstration does not
show why this framework should exist.

## Adoption Blockers

Technical: integration of real identity sources, action/resolver registration
through deployments, worker supervision, operational correlation, and explicit
modeling limitations. A specific P1 example defect is already recorded as
EX-001 in the public-truth audit; it requires a separately scoped patch rather
than an in-scope middleware change.

Trust/adoption: released failure tests are valuable but not evidence that an
independent team can operate the package. Compatibility support, upgrade
rehearsals, issue response expectations and externally followed examples need
to be visible. No claim of production customer count is made.

Discoverability: too many entry points obscure which feature to choose.
"AI-native" can conceal ordinary application value; this is a positioning risk
to test with readers, not a measured survey result.

## Technical Debt Relevant to Adoption

Installed-package checks during this review also exposed ACTION-001 (custom
HTTP action permission metadata does not automatically enforce authorization),
STORAGE-001 (filesystem sibling-prefix containment), CFG-001 (origin/host list
parsing), SDK-001 (generated TypeScript strict-compilation failure), and
SCAFFOLD-001 (fresh generated projects cannot install editable because Hatch
file selection is missing). The local dependency-install path is now documented
and tested, but application packaging still needs a separate scoped patch. The
public-truth audit contains the reproductions and scoped evidence. These findings
raise the priority of separately reviewed correctness/security maintenance
before broader adoption claims. In particular, shared generated CRUD/MCP checks
must not be generalized into automatic authorization of arbitrary custom HTTP
action bodies. The proposed operating-experience direction depends on closing
these gaps, not merely polishing their documentation.

The subsequent reference audit also reproduced BULK-001 (Boolean/timestamp
`bulk_update` CASE type inference) and PAGINATION-001 (generated HTTP responses
strip page/cursor metadata). TESTING-001 is source-confirmed only: the database
test helper does not bind application queries to its rollback transaction and
its cleanup branch omits pool disconnection. A negative runtime probe is still
pending; do not describe a measured leak. EX-001 remains the historical
multitenant example's exemption-matching defect. The domain-template audit
additionally reproduces MIGRATION-001: discovery of
the built-in auth `User` replaces a same-named application model, omitting its
declared table despite successful migration commands. Together these are ten
separately tracked findings, with different proof scopes, rather than evidence
that the entire backend is unusable. Their reproductions and alternatives are
in the public-truth audit. Closing the relevant functional defects needs a
separate maintenance scope before stronger production/adoption claims.

Prioritize debt by user-visible failure and change risk. Static-analysis ratchets
contain accepted debt; they are not a claim of a clean type/lint baseline.
Documented unsupported custom M2M through models and object-valued lazy forward
foreign keys may block particular applications. Resolve only against concrete
modeling examples and migration compatibility requirements.

There are several related abstractions: ordinary Task, durable Operation,
experimental DurableStep and AI runtime state. Clarify them before consolidating
implementation. A cleanup that merges their names without preserving identity,
retention and retry semantics could be worse than explicit separation.

## Trust and Ecosystem

Publish reproducible installed-wheel journeys and a bounded support policy.
Keep test environment, exact package/version and excluded guarantees attached
to results. Prefer a small number of maintained integrations with explicit
version and error behavior over a logo wall.

The strongest missing non-code evidence is observation of independent developers
building and operating an app. Do not infer trust from GitHub stars, assume
downloads represent production use, or infer market size from AI funding.

## Strategic Distractions

A workflow DAG engine and agent-memory platform would pull Aksara toward
capabilities already central to Temporal, LangGraph, Pydantic AI, ADK and others.
A frontend builder or managed BaaS would add product and service obligations
unrelated to the current strongest guarantee. A vector database or model gateway
would compete in a different layer. Broad SQL portability would multiply the
semantic test matrix before demand has been established.

These ideas are not inherently bad. Reconsider only with a named user problem,
evidence that integration cannot solve it, a maintainer, and a bounded support
contract. The most dangerous temptation is turning an Operation into a general
workflow engine while still describing it as a small backend primitive.

## Primary and Secondary Users

**Primary:** a Python backend engineer building a new tenant-aware internal or
SaaS application on PostgreSQL, with consequential actions that may execute
later or be initiated by tools. They can own deployment and identity integration
and want less bespoke authorization/recovery wiring.

**Secondary:** a platform engineer exposing controlled application actions to
agents; a technical founder who accepts the persistence choices; an existing
Aksara user needing safe delayed work. An established application on a different
ORM is an integration research persona, not the easiest first adopter.

Not the initial target: someone seeking a no-operations mobile backend, a generic
multi-agent lab, or a replacement for an existing enterprise workflow platform.

## Jobs to Be Done

| Job | Fit today | What would prove adoption value |
| --- | --- | --- |
| Build tenant-aware CRUD without assembling each layer | Good bounded technical fit | Beginner independently installs, migrates, authenticates and tests |
| Give a tool the same allowed application action | Good through supported REST/MCP enforcement | Paired allow/deny tests through both entry points, including fields/tenant |
| Resume delayed work under current permission | Strongest differentiating fit | Revoke authority during delay; worker denies without mutation |
| Recover a database mutation after worker loss | Strong under `postgres_atomic` constraints | One committed effect, inspectable status and restart runbook |
| Guarantee an external refund/email happened exactly once | Not an unconditional fit | Provider idempotency and reconciliation; unknown outcome remains explicit |
| Build a general multi-agent process | Outside stable product scope | Integrate another runtime rather than promise planner quality |

## Positioning

Primary category: **Python application backend framework**.

Primary problem: keeping permissions, tenant boundaries and database effects
consistent when the same application action is invoked through different
interfaces or delayed across failures.

Use "AI-native" only after explaining supported agent access. "Agent-safe" alone
is also too absolute: arbitrary tools and callbacks do not become safe simply
because they are registered. Prefer an explicit statement about enforced paths.

## One-Sentence Description

**Aksara is a PostgreSQL-backed Python application framework with generated APIs,
shared authorization boundaries, and durable actions that recheck authority
before supported effects.**

## Primary Wedge

Demonstrate a support-desk or internal-operations action with real consequences:
an authenticated actor schedules a tenant-scoped change, an approval records
intent, permission changes while it waits, and a replacement worker checks
current authority before touching the record. Show the corresponding authorized
success path and its atomic status record. Add MCP as an optional caller.

This is a technical wedge, not proof of a large market. If target users rarely
need delayed delegated mutations, ordinary application usability may be the
better reason to adopt, and the roadmap must narrow accordingly.

## Ecosystem and Integration Strategy

Start with authenticated HTTP/MCP, ordinary ASGI deployment, PostgreSQL and
external identity services. Evaluate an OIDC provider recipe, an operational
telemetry/export recipe and one agent-client example before designing a plugin
system. Existing resolver/authorizer seams should be used first.

Keep a single authority for each concern: an identity provider verifies identity;
Aksara maps a server-owned Principal and enforces the application boundary;
an orchestrator coordinates wider work; an external provider owns its effect
receipt. No adapter may turn cached approval into permanent permission.

## Database Strategy

**Retain PostgreSQL-first and PostgreSQL-only for the current stable contract.**
The implementation directly uses session tenant settings/RLS, row locks and
`SKIP LOCKED`, PostgreSQL time and JSONB in claims, outbox export and execution.
See `aksara/db/tenant_context.py`, `aksara/durable/repository.py`,
`aksara/durable/service.py` and `aksara/durable/execution.py`.

SQLite could make the first five minutes easier, as the
[Flask tutorial](https://flask.palletsprojects.com/en/stable/tutorial/database/)
illustrates. It would not exercise Aksara's actual RLS and multi-worker ownership
contract. A development-only adapter would create a second set of answers for
locking, roles, concurrency and migrations and risk promoting invalid test
confidence. Improve disposable local PostgreSQL setup before adding that split.

MySQL or another production backend would require a deliberately redesigned and
independently tested contract, not SQL spelling substitutions. Record requests
by application, blocked workflow and required guarantee. There is no verified
user-demand evidence in this review that justifies this maintenance burden.
Multi-database support is not table stakes for the chosen PostgreSQL-oriented
persona; it would be essential for a different target audience. Revisit if
qualified users consistently reject the framework solely for this reason.

## Capability Gaps

H/M/L below are qualitative judgments, not computed scores. High risk, dependency
or burden is a cost. High ecosystem availability favors integration. "Gap" can
mean missing supported experience rather than nonexistent code.

| Gap | Adoption impact | Alignment | Implementation risk | Architectural dependency | Maintenance burden | Ecosystem availability | Differentiation | Urgency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Executable progressive docs and upgrade path | High | High | Low | Low | Medium | High | Medium | High |
| Reference worker deployment and recovery workflow | High | High | Medium | Medium | Medium | High | High | High |
| Real identity-provider/resolver integration | High | High | Medium | Medium | Medium | High | Medium | High |
| Correlated operational telemetry/export recipe | High | High | Medium | Medium | Medium | High | Medium | High |
| Specific unsupported relation forms | Medium | Medium | High | High | High | High | Low | Medium |
| Generated-client integration journey | Medium | High | Low | Low | Medium | High | Low | Medium |
| External policy-engine adapter | Medium | High | High | High | Medium | High | Medium | Low |
| SQLite evaluation path | Medium | Low | High | High | High | High | Low | Low |
| Broad production database support | Low | Low | High | High | High | High | Low | Low |
| Generic workflow graphs / agent memory | Low | Low | High | High | High | High | Low | Low |
| Managed cloud / Kubernetes operator | Low | Low | High | High | High | High | Low | Low |

## Prioritization

First eliminate documented setup contradictions and prove a complete app journey.
Then use that app to find the smallest missing operational integration. Separate
functional defects from documentation fixes. Reserve modeling work for users
whose actual schema is blocked. Explore external policy integration only when
the in-process policy model cannot express a real access requirement.

Do not add up the qualitative columns. A high-impact feature with a high
semantic dependency may need design evidence before implementation; a short
integration recipe may remove the same blocker more cheaply.

## Roadmap Principles

1. Improve the supported application path before expanding framework surface.
2. Keep current authority separate from stored intent and scheduling.
3. Prefer integrations with explicit failure behavior over new infrastructure.
4. Preserve PostgreSQL guarantees; do not hide weaker semantics behind one API.
5. Require executable public examples and upgrade evidence for stable surfaces.
6. Let real operating and modeling failures interrupt speculative sequencing.
7. Keep experimental agent/workflow systems outside the backend stability claim.
8. Allocate versions to coherent outcomes, not a list of attractive features.

## Now

Complete v0.7.1 public truth: executable onboarding, one progressive tutorial,
concepts/configuration/operations/upgrade references, example audit, scaffold
equivalence, stability labels, installed-wheel gates and full regression.
Publish this researched roadmap without implying that the next features exist.
Track the eleven audit findings for separately scoped functional maintenance; do
not certify the affected multitenant example as an isolation reference or treat
a passing defect-reproduction probe as proof that the runtime boundary works.

## Next

Validate the proposed v0.8 operating experience against a real application.
Inventory what existing worker, resolver, diagnostics and outbox APIs can already
support. Implement only demonstrated gaps under separate design/review. The
application should be deployable and recoverable without source archaeology.

## Later

Address supported-modeling gaps and selected integrations that independent apps
actually need. Stabilize the chosen supported surface, compatibility/deprecation
policy and upgrades. Do not preassign these to v0.9; their order depends on the
next deployment and user evidence.

## Explore

One external identity provider, one agent-client integration and one telemetry
backend are useful experiments. Evaluate external authorization integration and
hosted-PostgreSQL compatibility with explicit fail-closed and RLS tests. Collect
database-portability demand before changing the architecture. These are
experiments, not support promises.

## Not Planned

A general workflow/DAG engine, autonomous multi-agent platform, vector database,
model gateway, frontend builder, managed BaaS, broad SQL portability, new
mandatory Redis/Kafka service, or a Kubernetes operator are not planned in this
sequence. Protocol-level MCP Tasks are not promised by this roadmap; protocol
and SDK capability must be verified before any separate adoption proposal.

## v0.7.x Maintenance Strategy

v0.7.1 is documentation and developer experience with no intentional production
semantic changes. Subsequent patch releases may address verified correctness,
security, compatibility, packaging and narrow adoption defects. Changes to
authorization, migrations or execution guarantees require explicit functional
review and regression evidence; they must not be hidden in a docs patch.
No patch number beyond v0.7.1 is reserved here.

## v0.8 Thesis

**Make authorized application work operable by an independent backend team.**

The proposed acceptance scenario is one production reference deployment whose
operator can map real identity, register/version actions and resolvers, start
workers with restricted roles, inspect blocked/failed work, correlate exported
events, handle permission revocation, retain idempotency identity correctly,
and recover after worker/database interruption and an application upgrade.

Require a documented supported configuration, executable deployment/recovery
tests, and review by someone who did not write the implementation. Prefer
recipes and standard integrations where existing APIs suffice. Only separately
approved functional gaps belong in v0.8. Exclude new planner, graph, database and
frontend abstractions. Reconsider the thesis if user trials show that modeling
or identity integration prevents adoption before operations become relevant.

## Possible Later Release Sequence

v0.7.1 truth/DX → v0.7.x verified maintenance → evidence-gated v0.8 operating
experience → bounded stabilization toward 1.0. A v0.9 theme is deliberately
unassigned. No dates or automatic release triggers are committed.

## v1.0 Readiness Criteria

1. One explicit public support contract identifies stable imports, defaults,
   errors and exclusions; experimental APIs remain visibly separate.
2. Supported ORM/relations and migrations have fresh-install and real upgrade
   coverage, including restricted-role deployment and a documented rollback or
   forward-recovery decision for schema changes.
3. Authentication, tenant/field policy and synchronous REST/MCP share the
   documented enforcement behavior, with denial and failure tests.
4. Task and durable contracts distinguish scheduling, current authority,
   ownership, idempotency, cancellation and external uncertainty; upgrades retain
   required registrations and state compatibility.
5. A new developer completes the published app journey from a wheel; an operator
   rehearses deployment, failure recovery, retention/export and backup restore.
6. Supported Python/web/PostgreSQL combinations, compatibility/deprecation
   policy, security reporting and release gates are published and exercised.
7. Integration ownership and support limits are explicit for the selected
   identity, storage and operational examples. No unsupported production claim
   depends on Studio or a planner.
8. No unresolved release-blocking correctness/security defect remains within
   that declared surface; limitations have usable alternatives and are visible.

This cutoff does not require every database, social provider, workflow engine,
AI feature or plugin. It requires dependable promises for the chosen backend.
Passing repository tests alone does not satisfy the independent usability and
operator criteria.

## Top 5 Adoption Blockers

1. **Incomplete public learning path:** demonstrated by the audit and unresolved
   clean-room journeys; prevents evaluating existing capabilities.
2. **Integration and operational assembly:** real identity, workers, export and
   recovery still require application knowledge across multiple modules.
3. **Unproven independent trust:** release evidence is not a replacement for
   another team following deployment and upgrade instructions.
4. **Modeling and compatibility boundaries:** declared relation exclusions and
   PostgreSQL requirements can disqualify particular applications.
5. **Category ambiguity:** backend, tool boundary and experimental agent runtime
   compete for attention; reader testing must confirm a clearer introduction.

## Top 5 Opportunities

1. Demonstrate delayed authorization revocation with a real tenant application.
2. Make that same application straightforward to operate and recover.
3. Provide maintained identity and telemetry recipes instead of new services.
4. Let different agent clients use the same tested application API/MCP boundary.
5. Earn a bounded 1.0 through installed behavior and upgrades, not feature breadth.

## Top 5 Distractions

1. General workflow graph/replay engine before the single Operation is easy to use.
2. Agent memory, multi-agent orchestration and provider-quality competition.
3. Broad database portability without qualified user demand and semantic design.
4. Hosted backend/frontend builder that adds a separate service business.
5. New brokers, operators or plugin frameworks before existing seams are tested.

## Highest-Leverage Technical Investment

One executable production reference path that connects real identity, current
authorization, durable worker lifecycle, diagnostics/export and recovery. This
both tests the product distinction and reveals the minimum necessary APIs.

## Highest-Leverage Nontechnical Investment

Observe independent target developers using the published docs. Recruit a small
initial cohort and record setup failures, time spent, source-code detours and
reasons to reject the framework. This is a proposed research activity, not work
already performed or evidence of demand.

## Most Important User Assumption to Validate

**Do enough Python/PostgreSQL application teams have delayed or delegated
mutations whose current authorization they find costly to enforce correctly?**

Ask for a recent concrete incident or implementation, then compare the
developer's current solution with an Aksara trial. Record negative results:
"our ordinary jobs already solve this," "we cannot adopt your ORM," and
"identity integration costs more than it saves" should change prioritization.
Do not validate by asking whether developers like the phrase "AI-native."

## Risks

The wedge may be narrow; operational improvements may expose deeper API gaps;
the ORM adoption cost may exceed execution savings; maintained integrations may
outgrow available capacity. Current vendor documentation can change, and this
review does not establish comparative reliability or a performance advantage.
The proposed persona and buying motivation are hypotheses, not interview results.

## Final Recommendation

Finish public truth before adding capabilities. Describe a PostgreSQL application
backend, show delayed authorized mutations as its distinctive example, and make
that example deployable and recoverable. Use the resulting user evidence to
decide the exact v0.8 scope. Preserve the bounded 1.0 path and decline adjacent
platform work until integration demonstrably cannot meet a real need.

### Additional ORM adoption defect (2026-09-11)

SOFTDELETE001 / P1: the module-level soft-delete visibility helpers discard
existing queryset restrictions. Installed-wheel PostgreSQL execution returned
both rows after an identifier-filtered queryset was passed to either helper.
This can drop application tenant filters; no RLS bypass was demonstrated.
The public guide now starts visibility selection from the manager and applies
filters afterwards. Recommend a separate narrowly scoped runtime patch.
Evidence: `audit-evidence/v071/soft-delete-execution.json`. This reinforces the
existing correctness/adoption priority without changing the roadmap thesis.
