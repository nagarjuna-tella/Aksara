# Aksara v0.7.2 Security Review

## Assessment

The v0.7.2 audit-closure candidate strengthens seven security-relevant or
trust-boundary findings without adding a new security policy. No finding in
this set requires confidential advisory handling: the v0.7.1 audit already
disclosed the behavior, and the review found no framework-default remote exploit
that bypasses authentication without application-specific prerequisites.

The strongest practical issues were unsafe primitives. ACTION-001 affected an
application that declared a permission on a ViewSet or action and then exposed
the custom HTTP action. STORAGE-001 required an application to pass an
attacker-influenced storage name directly to `FileSystemStorage`. EX-001 existed
in a historical example that the v0.7.1 documentation explicitly marked as
noncanonical. The candidate closes each primitive and fails closed.

| ID | Confidentiality | Integrity | Authorization / tenant isolation | Availability | Execution ownership | Exploit prerequisites and affected surface | v0.7.1 assessment |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ACTION-001` | Indirect read exposure was possible if a custom read action returned protected data. | A custom mutation could run without its declared permission path. | Directly relevant: ViewSet and action permissions, object checks, and tenant context now run before the handler. | Denials are bounded HTTP failures. | Not applicable. | A deployed custom action plus a permission declaration that the application expected Aksara to enforce. Generated custom REST actions; matching MCP calls retain the same application policy. | Exploitable application authorization primitive, not a universal anonymous bypass in every app. |
| `STORAGE-001` | An attacker-influenced name could read a sibling path reachable by the process. | The same primitive could write or delete outside the configured root. | Filesystem trust boundary; unrelated to Principal/RLS. | Deletion or overwrite could disrupt the host application. | Not applicable. | Direct `FileSystemStorage` use with an untrusted path and filesystem permissions permitting the target. FileField retained its independent validation. | Unsafe primitive with application-input and host-permission prerequisites. |
| `SOFTDELETE001` | Discarded predicates could expose rows outside an intended application filter. | Mutating work based on a broadened queryset could affect unintended rows. | Directly relevant: tenant/application predicates are preserved; forced RLS remains defense in depth. | No distinct availability vector. | Not applicable. | Application passes a restricted queryset to a module-level visibility helper. RLS could reduce impact where correctly enabled but was never accepted as the repair. | Security-relevant query-broadening bug; exploitability depended on application use and database role. |
| `EX-001` | A protected example route could execute without tenant resolution. | Work could occur without the intended tenant context. | Direct tenant-routing relevance in the shipped historical multitenant example. Exact and explicit-prefix matching now replaces root-prefix matching. | No distinct availability vector. | Not applicable. | An application copied or deployed the noncanonical historical example middleware. | Real example defect, already documented as unsafe; not the supported RLS reference architecture. |
| `CFG-001` | A corrupted allowlist could cause an operator to enforce a different trust boundary than intended. | Configuration could be silently reinterpreted. | Relevant to origin/host settings. The deterministic grammar preserves complete URLs, host ports, and IPv6 forms or rejects ambiguity. | Invalid configuration now fails at startup instead of degrading silently. | Not applicable. | Security-sensitive list supplied through an environment string containing the POSIX path delimiter. | Unsafe configuration primitive; no standalone allowlist bypass was demonstrated. |
| `MIGRATION-001` | Missing tenant/auth tables could undermine an application's intended access model. | A declared model could silently disappear from generated schema. | Indirect tenant/auth relevance. Qualified identity and explicit ambiguity errors prevent silent selection by import order. | A colliding application now fails loudly until names are qualified. | Not applicable. | Two registered models share a simple class name and migration/discovery code uses that name. | High data-integrity risk; explicit failure is the compatible security posture for ambiguity. |
| `TASK-001` | No direct read exposure. | A stale worker could overwrite a replacement owner's authoritative result or error. | Tenant provenance remains attached to the task; ordinary Tasks do not become Principal-authoritative. | Healthy heartbeats prevent incorrect recovery, while hard-killed workers remain recoverable. | Directly relevant: database-time lease, worker ID, claim token, atomic transfer, and conditional updates fence old owners. | Concurrent or paused workers plus work lasting beyond the former stale-lock threshold. | Reproducible execution-state integrity bug. External effects remain at-least-once and must be application-repeat-safe. |

## Authorization parity

Generated REST CRUD, custom REST actions, generated MCP tools, and Durable
Operation execution were compared at their existing boundaries. Custom actions
now apply ViewSet permissions by default, allow an explicit action-level
override, run request checks before handlers, and run object checks for detail
actions. The installed Support Desk gate proves that REST and MCP calls retain
the same application permission and tenant rules, including authorization
revocation after discovery. Durable Operations continue to re-resolve the
Principal and recheck authorization at execution time. No unified v0.8
capability abstraction was introduced.

## PostgreSQL and RLS

The candidate was exercised with an ephemeral `NOSUPERUSER NOBYPASSRLS` role,
forced RLS, and two tenants. Custom actions, soft-delete visibility, generated
CRUD, task tenant provenance, Durable Operations, and packaged Support Desk
paths remained isolated. Application predicates and RLS both passed; neither is
used to excuse defects in the other.

## Verification

- The security suite passes 430 tests; its generated API fuzz subset passes 165.
- The dedicated RLS/tenancy set passes 22 tests.
- The packaged Support Desk passes 66 production-shaped checks.
- Five installed-candidate task process scenarios prove all ten ownership
  invariants, including zero authoritative writes from stale success/failure.
- Bandit reports no high-severity findings under the repository policy.
- The installed candidate dependency graph has no known vulnerabilities; the
  unpublished candidate package itself is correctly unresolvable on PyPI.
- The final intended tree passes Gitleaks with no leaks. The evidence-specific
  credential scan also confirms that no credential-bearing PostgreSQL URL or
  supplied test credential is recorded in the release evidence.

Detailed evidence is in [`audit-evidence/v072/`](audit-evidence/v072/), and the
complete closure ledger is in
[`AKSARA_V072_AUDIT_CLOSURE.md`](AKSARA_V072_AUDIT_CLOSURE.md).
