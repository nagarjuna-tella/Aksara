# Aksara v0.8 Architectural Inputs from Audit Closure

This note records bounded observations produced while closing the v0.7.1 audit.
It is input to a future design process. v0.7.2 implements none of these ideas
and does not change the existing roadmap or stability classifications.

## Declared authorization across interfaces

ACTION-001 showed that callers should not lose a declared application policy
because a framework operation is reached through a different generated route.
The patch repair applies existing ViewSet/action permission semantics to custom
REST actions and verifies that MCP and Durable Operations retain their existing
checks. A future capability design can consider one declarative authorization
description that each transport consumes, while preserving execution-time
Principal and PolicyEngine rechecks. That design must not collapse request
admission, durable execution authority, or approval into one boolean.

## Stable identity before richer abstraction

MIGRATION-001 established module-qualified class identity as canonical and kept
simple names only as an unambiguous convenience. Any future schema, generated
client, agent-tool, or Admin abstraction should use canonical identity in stored
or cross-process references. Display names can remain short, but persistent
identity must not depend on import order.

## Tasks and Durable Operations remain distinct

TASK-001 adds the minimum ownership protocol required for an ordinary worker to
avoid stale authoritative writes. It does not make ordinary Tasks
Principal-authoritative, approval-aware, or exactly-once. A future abstraction
should preserve the choice between lightweight at-least-once background work
and Durable Authorized Operations with admission, execution reauthorization,
fencing, approval, audit, and explicit external-effect classes.

## Generated schema must close the client loop

SDK-001 and PAGINATION-001 were one contract failure spanning server schema,
HTTP serialization, OpenAPI, generated TypeScript, and runtime query encoding.
Future generated abstractions should treat this complete chain as one evidence
unit:

```text
model and ViewSet declaration
→ HTTP payload and OpenAPI
→ generated client types
→ strict compilation
→ live client request and response
```

## Provenance is part of tool output

INSPECTOR001 showed that a useful-looking synthetic result can be more harmful
than an explicit unavailable result when provenance is lost. Future AI-native
inspection tools should carry source, execution state, uncertainty, and failure
mode as structured fields rather than relying on prose warnings.

## Configuration is a trust-boundary language

CFG-001 showed that generic platform parsing is unsuitable for security-sensitive
configuration. Any future configuration abstraction should define portable,
unambiguous wire grammars and validate them before application startup. Defaults,
explicit configuration, reachability, authentication, and health should remain
separate concepts, as reinforced by AIPROVIDER001.

These are observations only. No unified Capability abstraction, Action runtime,
workflow engine, provider family, database backend, or v0.8 implementation was
added during audit closure.
