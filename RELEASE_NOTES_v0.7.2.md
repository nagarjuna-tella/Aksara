# Aksara v0.7.2 — Audit Closure

v0.7.1 established public truth. v0.7.2 closes the complete functional defect
ledger exposed by that audit: all 22 disclosed findings are fixed, covered by
permanent regressions, and verified against the installed final wheel.

## Authorization, isolation, and ownership

- Custom HTTP actions enforce declared ViewSet, action, object, tenant, and
  shared REST/MCP authorization boundaries.
- Filesystem storage rejects traversal, absolute-path, sibling-prefix, and
  outward-symlink escapes.
- Portable configuration parsing preserves URLs, ports, and IPv6 values while
  rejecting ambiguous legacy list syntax.
- Soft-delete visibility preserves existing query and tenant predicates, and
  the historical multitenant example applies exact route exemptions.
- Ordinary Tasks use claim tokens, database-time leases, heartbeats, atomic
  recovery, and stale-owner fencing. The additive internal migration is
  `aksara/core/migrations/0003_task_claim_ownership.py`.

## Persistence and generated interfaces

- Module-qualified model identity prevents silent migration loss when class
  names collide.
- Terminal relation queries honor requested eager loading.
- Typed bulk updates correctly encode booleans, timestamps, and the supported
  field matrix.
- JSON and safe YAML fixtures round-trip identities, relations, dates, UUIDs,
  nullable values, JSON, and PostgreSQL arrays.
- Paginator-specific metadata and cursor continuation survive REST, OpenAPI,
  and SDK generation.
- The generated TypeScript SDK compiles in strict mode and agrees with live
  list, detail, mutation, filtering, and pagination behavior.

## Developer and bounded experimental surfaces

- All generated scaffolds support editable and wheel installation.
- The database testing helper provides real same-task rollback isolation and
  releases its resources.
- Python compatibility diagnostics enforce the supported 3.11–3.14 range.
- Experimental provider configured-state detection, workflow import ordering,
  and diagnostic environment rendering are corrected without promoting those
  surfaces to Stable.
- Inspector results distinguish live, synthetic, failed, and unavailable
  provenance, and Array Admin rendering no longer mutates caller-owned values.

## Scope

This release closes 22 of 22 audit findings, with zero unresolved. It adds no
product capability, dependency, database engine, or v0.8 work. Durable
Operations semantics and the Stable MCP contract are unchanged. Experimental
AI surfaces remain Experimental.
