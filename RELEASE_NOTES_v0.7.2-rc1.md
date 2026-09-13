# Aksara v0.7.2 — Audit Closure

Aksara v0.7.2 closes every functional defect disclosed by the v0.7.1 Public
Truth audit. The `0.7.2rc1` candidate contains one regression-backed repair for
each of the 22 findings and establishes the correctness baseline for the next
architectural phase.

## Authorization and isolation

- Custom HTTP actions now enforce declared ViewSet and action permissions,
  including object and tenant checks.
- Direct filesystem storage operations cannot escape their configured root,
  including through sibling-prefix paths or symlinks.
- Soft-delete visibility transformations preserve existing query restrictions.
- The historical multitenant example no longer exempts every path through a
  root-prefix match.

## Persistence and execution

- Same-named models now cause an explicit registry collision instead of silent
  migration omission.
- Requested foreign-key eager loading is honored by terminal query methods.
- Boolean and timestamp values are encoded correctly in bulk updates.
- JSON and YAML fixtures round-trip primary keys, UUIDs, relations, timestamps,
  nullable values, JSON, and PostgreSQL arrays through safe loading.
- Ordinary tasks now use claim tokens, database-time leases, heartbeats,
  atomic recovery, and conditional terminal writes so a stale worker cannot
  overwrite the current owner.

## Generated interfaces and development workflow

- Cursor-paginated responses retain `next_cursor` and paginator metadata.
- The generated Ticket Desk TypeScript client compiles under strict TypeScript
  and agrees with live list, detail, create, update, filter, and pagination
  responses.
- Basic, Blog, CRM, and multitenant scaffolds declare their package selection
  explicitly and support editable and wheel installation.
- The database test helper now pins application work to a rollback transaction
  and releases all resources after the test.

## Configuration and bounded experimental fixes

- List-valued environment settings use a platform-independent grammar that
  preserves URLs, ports, and IPv6 values.
- Python compatibility checks share the supported 3.11–3.14 policy.
- Provider detection distinguishes explicit configuration from adapter
  defaults and supports keyless custom endpoints.
- Workflow imports are order-independent and diagnostic environment actions
  render one coherent assignment.
- Inspector results label live, synthetic, failed, and unavailable provenance;
  synthetic `ANALYZE` output cannot claim execution.
- Array Admin rendering does not mutate caller-owned values.

## Compatibility boundary

This maintenance release adds no dependency and implements no v0.8 capability.
Durable Operations and stable MCP semantics are unchanged. Correctness and
security tightening may reject unsafe paths, unauthorized custom actions,
ambiguous model collisions, malformed configuration, and stale task writes that
older versions accepted.
