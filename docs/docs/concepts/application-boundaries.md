# How an application request becomes an authorized effect

**Stable:** the documented v0.6 request boundary and opt-in v0.7 durable
execution contract. Individual integrations must still apply their application
policy; importing a Principal does not secure arbitrary Python code.

Aksara combines PostgreSQL models and migrations with generated REST APIs,
permissions, and optional MCP tools. A human, service, or agent may request the
same business action. The application verifies who is asking, then Aksara's
covered execution paths enforce the relevant policy and database boundaries.

## Start with identity

Authentication verifies a credential. Your authentication integration turns
that verification into a server-owned `Principal`: the current actor, tenant,
roles, scopes, and related authority. A tenant is the data boundary in which
that actor operates. A tenant ID supplied by a caller is not proof that they
belong to it.

Permissions answer whether that actor may perform an action. Object policy
adds conditions about a particular record. Field policy constrains which data
may be read or changed. `PolicyEngine` provides shared decisions for covered
paths, while application permission classes and action authorizers express
business rules. PostgreSQL RLS adds a database isolation boundary when the
restricted-role production profile is in place.

See [authentication](../api/authentication.md),
[permissions](../api/permissions.md), and
[tenant isolation](../security/multi-tenancy.md).

## Models, serializers, and ViewSets have different jobs

A Model describes persisted data and its validation. Migrations apply deliberate
schema changes; starting a web process is not the deployment migration step.
Queries and transaction contexts operate on the configured PostgreSQL database.
The declared relation and field contracts apply; custom many-to-many through
models and object-valued lazy forward foreign keys remain unsupported.

A serializer shapes input and output. A ViewSet provides generated HTTP actions
around the model and exposes customization points. Hiding a field in a schema
or UI is not authorization: write restrictions must be enforced on execution.
Custom handlers remain responsible for the business validation and policy they
perform outside the generated path.

See [models](../orm/models.md), [serializers](../api/serializers.md),
[ViewSets](../api/viewsets.md), and
[transactions](../orm/expressions-and-transactions.md).

## Select an execution path

| Need | Start with | Boundary to understand |
| --- | --- | --- |
| Return a result while the caller waits | Synchronous REST | Current request authority; explicit transaction scope for multi-write atomicity |
| Let an MCP client invoke exposed application actions | Synchronous `/mcp/` tools | Authentication plus execution-time tool authorization |
| Queue an ordinary application job | Background task | Application code owns authorization beyond persisted tenant context |
| Retain an accepted action across worker loss or approval delay | Durable Operation | Persisted identity reference, current reauthorization, bounded retry and ownership |
| Cache successful workflow steps | `DurableStep` | Evolving helper; not the Operation contract |

An HTTP request does not automatically make all application writes one atomic
unit. Use `transaction.atomic()` when related PostgreSQL writes must commit or
roll back together; see the [transaction guide](../orm/expressions-and-transactions.md).

MCP is an optional client interface. It does not require an AI provider.
`/mcp/` is the Streamable HTTP protocol endpoint; `/ai/tools/mcp` is the
inspection catalog. The current synchronous MCP approval grant and a durable
Operation decision have different persistence and consumption boundaries.
Neither approval restores revoked permission.

See the [MCP quickstart](../getting-started/mcp.md) and
[background tasks](../advanced/background-tasks.md).

## Understand delayed work without a distributed-systems glossary

An **Operation** is the accepted request: “resolve this ticket.” An **Attempt**
is one worker's effort to execute it. Several Attempts may belong to one
Operation after failures. A **lease** is temporary ownership; a **fence** is an
increasing ownership number that makes an older worker's covered writes invalid
after another worker takes over.

**Idempotency** gives repeated submissions the same logical identity within a
bounded window. It does not deduplicate arbitrary provider calls forever.
**Reauthorization** rebuilds current authority before delayed effects, because
permission may have changed since admission. **Cancellation** prevents work
when it wins the supported race; it does not undo completed work.

For `postgres_atomic`, supported application mutation and Operation completion
share the same guarded PostgreSQL transaction. The handler must use the
supplied context on the owning task and database. Independent connections,
threads, subprocesses, other databases, and external network effects cannot be
included in that guarantee.

An external provider may accept a request and lose the response. If neither
idempotency nor reconciliation establishes its outcome, Aksara reports
`external_outcome_unknown`. That uncertainty is information an operator needs,
not an invitation to retry blindly.

See the [durable operations guide](../advanced/durable-operations.md) for
registration, dispatch, workers, decisions, recovery, and retention.

## Know what is outside the contract

The application owns credential verification, business policy, handler code,
worker supervision, provider reconciliation, backups, and long-term audit
retention. The application database role and registered code are trusted.

Planner quality, persistent AI conversations and memory, multi-agent autonomy,
provider quality, and Studio AI internals remain experimental. Protocol-level
MCP Tasks and generic workflow/DAG orchestration are deferred. See
[stability labels](stability.md) before choosing an integration.
