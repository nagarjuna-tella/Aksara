# Aksara v0.7.2 Audit Closure

## Decision

All 22 functional findings disclosed by the v0.7.1 Public Truth audit were
independently reproduced against the public `aksara-framework==0.7.1` wheel and
closed in the installed `0.7.2rc1` candidate. The final ledger is 22 `FIXED`,
zero `DISPROVED`, zero `ALREADY_RESOLVED`, and zero unresolved.

The repairs preserve the existing Stable, Evolving, and Experimental boundary.
They introduce no new dependency, database backend, product capability, or
v0.8 architecture. Historical v0.7.1 evidence remains unchanged.

## Closure matrix

| ID | v0.7.1 result | Root cause | v0.7.2 disposition | Compatibility impact | Evidence |
| -- | ------------- | ---------- | ------------------ | -------------------- | -------- |
| `CFG-001` | https://example.com is split into ["https", "//example.com"]. | List parsing reused the platform path delimiter, which conflicts with URI and IPv6 syntax. | **FIXED** | JSON arrays and unambiguous comma-separated values are deterministic; ambiguous legacy input now fails clearly. | [`candidate`](audit-evidence/v072/installed-closure-pytest.log), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `SDK-001` | Generation succeeds but tsc exits 2 with TS2322 because TicketListParams lacks the query helper index signature. | Generated parameter interfaces lacked the indexability required by the query serializer. | **FIXED** | Generated list parameters compile strictly without any/type-error suppression. | [`candidate`](audit-evidence/v072/typescript-sdk-gate.json), [`baseline`](audit-evidence/v072-baseline/SDK-001.json) |
| `STORAGE-001` | save("../media-private/probe.txt") writes to a sibling prefix directory outside the root. | Containment used a raw string prefix rather than resolved path components. | **FIXED** | Traversal, absolute escapes, sibling prefixes, and outward symlinks are rejected across storage operations. | [`candidate`](audit-evidence/v072/installed-closure-pytest.log), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `ACTION-001` | Generated list returns 403 while the declared protected custom action returns 200. | Generated custom-action routes omitted the ViewSet/action permission dispatch used by generated CRUD. | **FIXED** | Previously unauthorized calls now return a structured denial and never invoke the handler. | [`candidate`](audit-evidence/v072/support-desk-gate.json), [`baseline`](audit-evidence/v072-baseline/ACTION-001.json) |
| `TASK-001` | A second worker reclaims active work; the stale first worker later overwrites the newer completed result. | Ordinary tasks had an age-based lock without an owner token, renewable lease, or fenced terminal update. | **FIXED** | Adds an internal migration and lease ownership; stale workers cannot heartbeat or complete after transfer. | [`candidate`](audit-evidence/v072/task-process-gate.json), [`baseline`](audit-evidence/v072-baseline/TASK-001.json) |
| `AIPROVIDER001` | Clean environment reports default Ollama configured; keyless explicit custom endpoint reports not configured. | Compatibility heuristics conflated adapter defaults with explicit provider configuration. | **FIXED** | Configured, reachable, authenticated, and healthy remain separate experimental states. | [`candidate`](audit-evidence/v072/installed-closure-pytest.log), [`baseline`](audit-evidence/v072-baseline/AIPROVIDER001.json) |
| `GAP001` | Python 3.10 is accepted and the diagnostic claims 3.10 is supported. | Gap Analysis carried an obsolete Python 3.10 threshold independent of package policy. | **FIXED** | Python 3.9/3.10 fail, 3.11-3.14 pass, and later versions are explicitly unsupported. | [`candidate`](audit-evidence/v072/installed-closure-pytest.log), [`baseline`](audit-evidence/v072-baseline/GAP001.json) |
| `AIFLOW001` | First import from aksara.ai.workflows exits 1 through a Studio/workflow circular import. | Studio package initialization eagerly re-exported workflow builders while workflows imported Studio models. | **FIXED** | Public import names and signatures remain available through lazy forwarding in every tested order. | [`candidate`](audit-evidence/v072/installed-boundaries.json), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `AIFLOW002` | DATABASE_URL renders as export DATABASE_URL=export DATABASE_URL=.... | Diagnostic actions passed partially rendered shell snippets into a renderer that prepended another export assignment. | **FIXED** | New actions store raw values; one renderer supports raw and legacy values without executing secrets. | [`candidate`](audit-evidence/v072/installed-closure-pytest.log), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `EX-001` | The root exemption matches every path via startswith, so /api/projects/ bypasses the resolver and reaches downstream. | The example treated '/' as a prefix exemption, so every request path matched. | **FIXED** | Root and health exemptions are exact; only explicit subtree prefixes match children. | [`candidate`](audit-evidence/v072/installed-boundaries.json), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `SCAFFOLD-001` | Hatchling cannot infer a package matching the generated distribution name; editable install exits 1. | Generated project distribution names did not tell Hatchling which Python packages/modules to include. | **FIXED** | Basic, Blog, CRM, and multitenant projects explicitly select packages and support editable/wheel installs. | [`candidate`](audit-evidence/v072/scaffold-gate.json), [`baseline`](audit-evidence/v072-baseline/SCAFFOLD-001.json) |
| `SOFTDELETE001` | with_deleted and only_deleted construct a fresh manager queryset and lose an ID restriction. | Visibility helpers replaced the supplied queryset with a new manager queryset. | **FIXED** | Visibility is now a clone transformation that preserves predicates, tenant scope, ordering, slicing, annotations, and loading intent. | [`candidate`](audit-evidence/v072/rls-targeted.log), [`baseline`](audit-evidence/v072-baseline/SOFTDELETE001.json) |
| `FIXTURE001` | Exported primary keys are rejected when the row does not already exist. | The loader treated an explicit missing primary key as an update-only target. | **FIXED** | Dumped explicit identities insert when absent, update when present, and fail strict conflicts explicitly. | [`candidate`](audit-evidence/v072/closure-targeted.log), [`baseline`](audit-evidence/v072-baseline/fixtures.json) |
| `FIXTURE002` | UUID export contains Python-specific tags rejected by safe_load. | YAML export allowed Python-specific UUID tags that safe_load rejects. | **FIXED** | UUID/date/time/datetime and nested values use portable safe YAML scalars. | [`candidate`](audit-evidence/v072/closure-targeted.log), [`baseline`](audit-evidence/v072-baseline/fixtures.json) |
| `FIXTURE003` | Default registry iteration supplies string names where model classes are required. | Default dumping iterated registry keys instead of canonical model classes. | **FIXED** | Default and explicit dumps enumerate canonical models and surface name collisions. | [`candidate`](audit-evidence/v072/closure-targeted.log), [`baseline`](audit-evidence/v072-baseline/fixtures.json) |
| `INSPECTOR001` | Synthetic plan is labeled EXPLAIN ANALYZE with no warning. | The synchronous offline fallback relabeled synthetic estimates as ANALYZE and discarded the warning. | **FIXED** | Every result reports live/synthetic/failed/unavailable provenance and whether ANALYZE executed. | [`candidate`](audit-evidence/v072/installed-doc-imports.json), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `ADMINWIDGET001` | Rendering min_rows=3 mutates ["one"] into ["one", "", ""]. | Array rendering padded the caller's list object in place. | **FIXED** | Rendering defensively copies list and tuple inputs while retaining validation and escaping. | [`candidate`](audit-evidence/v072/installed-doc-imports.json), [`baseline`](audit-evidence/v072-baseline/unit-findings.json) |
| `MIGRATION-001` | Built-in User replaces the multitenant application User by simple name; migration commands exit 0 while tenant_users is missing. | The registry keyed models only by simple class name, allowing later imports to replace earlier models. | **FIXED** | Canonical identity is module-qualified class name; simple names resolve only when unambiguous and collisions raise AmbiguousModelError. | [`candidate`](audit-evidence/v072/closure-targeted.log), [`baseline`](audit-evidence/v072-baseline/MIGRATION-001.json) |
| `RELATION001` | first() creates the parent without relation-loading steps; get_related raises ValueError. | QuerySet.first() materialized a row without running the eager-loading phase used by all(). | **FIXED** | first() honors select_related and prefetch intent with existing signatures. | [`candidate`](audit-evidence/v072/closure-targeted.log), [`baseline`](audit-evidence/v072-baseline/RELATION001.json) |
| `BULK-001` | PostgreSQL infers CASE output as text and asyncpg raises DatatypeMismatchError. | PostgreSQL inferred searched CASE result parameters without the declared field type. | **FIXED** | CASE values are cast through field SQL types across the supported scalar/advanced field matrix. | [`candidate`](audit-evidence/v072/closure-targeted.log), [`baseline`](audit-evidence/v072-baseline/BULK-001.json) |
| `PAGINATION-001` | Direct paginator results contain metadata that generated response models strip. | The router serialized every paginator through one fixed page response model. | **FIXED** | Paginator-specific metadata, including next_cursor, survives HTTP serialization and OpenAPI/SDK generation. | [`candidate`](audit-evidence/v072/typescript-sdk-gate.json), [`baseline`](audit-evidence/v072-baseline/PAGINATION-001.json) |
| `TESTING-001` | Database.execute commits outside the acquired transaction; writes survive and the pool remains usable after exit. | The helper opened a raw transaction while yielded Database calls continued to acquire other pool connections. | **FIXED** | Same-task database/model operations bind to the owned transaction, roll back, and close the pool; HTTP/process boundaries remain explicit. | [`candidate`](audit-evidence/v072/installed-closure-pytest.log), [`baseline`](audit-evidence/v072-baseline/TESTING-001.json) |

## Canonical model identity

After v0.7.2, a model's canonical registry identity is its module-qualified
class name. An unqualified simple class name continues to resolve when exactly
one registered model has that name. A collision raises `AmbiguousModelError`
deterministically, independent of import order. Migration discovery, relation
resolution, fixture enumeration, Admin lookup, and CLI inspection may therefore
never silently choose or discard a colliding model.

## Compatibility boundary

The release intentionally rejects behavior that was unsafe or ambiguous:
unauthorized custom actions, storage-root escapes, ambiguous list syntax,
ambiguous model names, and stale task-owner writes. It adds one versioned
internal migration for ordinary task lease ownership. Normal non-colliding
v0.7.1 applications retain source compatibility, and the public-wheel upgrade
campaign preserves application data, relations, queued tasks, and Durable
Operation state.

The machine-readable authority for this table is
[`audit-evidence/v072/findings-closure.json`](audit-evidence/v072/findings-closure.json).
