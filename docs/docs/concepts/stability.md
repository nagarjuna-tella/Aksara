# Stable, evolving, experimental, and internal

Aksara is pre-1.0. Stability describes a bounded contract, not every symbol in
a module or every deployment configuration.

| Label | Meaning | Examples |
| --- | --- | --- |
| Stable | Documented behavior covered by the published stability contracts | ORM/migrations, generated REST, Principal/permissions, restricted-role tenancy, synchronous MCP, core tasks, opt-in Durable Operations |
| Evolving | Usable surface whose detailed API may change | Storage integrations, SDK generation, Admin details, `DurableStep` |
| Experimental | Evaluate with explicit application ownership; outside production guarantees | Studio AI, planners, provider workflows, investigation sessions, code/patch generation |
| Internal | Implementation detail, not an application compatibility promise | Durable repository commands, physical table layouts, raw fence/worker values |
| Deprecated | Compatibility behavior retained while a replacement is preferred | Legacy provider configuration fields identified in the settings reference |

The [v0.6 contract](../roadmap/v0-6-stability-contract.md) and
[v0.7 contract](../roadmap/v0-7-stability-contract.md) are authoritative.
Production guarantees require their migration, database role, RLS, and runtime
profiles. A documented export alone does not broaden either contract.

Synchronous generated MCP execution is stable. An experimental planner calling
that tool does not make the planner stable. Durable Operations are stable
within their execution constraints. A workflow using `DurableStep` does not
inherit Operation ownership, current reauthorization, or atomic-completion
guarantees.

Use [application boundaries](application-boundaries.md) to choose the smallest
execution surface that meets the application's needs.
