# Aksara v0.6 executable checklist

Evidence: [current-state audit](AKSARA_CURRENT_STATE.md) and [saved results](audit-evidence/current-state/). Unchecked items are gates, not claims of absent implementation. No production code was changed by the audit.

## ORM

- [x] P0: Make transaction/session acquisition exception-safe; `audit-evidence/v055/repro-cleanup.log` shows releases=1 and no leaked session.
- [x] P0: Real one-connection-pool regressions cover repeated setup/start/reset failures and cancellation (`tests/db/test_failed_start_cleanup.py`).

## migrations

- [x] Preserve the migration suite and validate fresh bootstrap, existing-schema upgrade, idempotent replay, and unapplied-migration startup failure from the packaged reference app; `audit-evidence/v060/support-desk-gate.json` records the PostgreSQL run.

## relations

- [x] Preserve tested relation/on_delete behavior; document ID-valued forward FK and unsupported custom through models without implying implementation.

## API

- [x] P0: Effective route traversal fixes all 15 failures; the full suite passes on Python 3.11/3.14 at both documented web dependency boundaries.

## security

- [x] P1: Replace skipped OpenAPI fuzz placeholders with generated-CRUD invalid-input and forbidden-field mutation invariants; `audit-evidence/v060/generated-api-abuse.md` records the real PostgreSQL run.
- [x] P1: Set an explicit release policy for Doctor warnings and security-matrix requirements; `production-check --release` requires every check to pass and rejects incomplete matrix coverage, with safe and unsafe CLI regressions.

## tenancy

- [x] P1: Run cross-tenant ORM/generated-API/task checks with a non-superuser, non-BYPASSRLS application role, including one-connection pool reuse and an MCP-principal call to a catalog-described REST operation; see `audit-evidence/v060/restricted-role-tenancy.md`.

## MCP

- [x] Verify route-derived tool inventory and schema against the running packaged support desk app, including an authorized same-tenant mutation and denied cross-tenant mutation.
- [x] Keep protocol-level MCP execution outside the v0.6 guarantee; the reference app and public documentation explicitly identify the supported surface as a catalog-described REST operation.

## Agent/AI

- [x] State that investigation sessions are process-local unless durable storage is implemented and restart/multi-worker behavior tested; the v0.6 contract and AI docs make this limitation prominent.
- [x] Keep autonomous durable mutation/approval guarantees out of the production contract until replay/retry/authorization-at-execution is demonstrated; these guarantees are explicitly experimental/deferred.

## Admin

- [x] Revalidate mounting/discovery with supported dependencies and preserve passing CRUD/permission assertions; both dependency boundaries pass.

## Studio

- [x] Fix the three reproduced route/context failures and launch-check mismatch; generated projects keep Studio disabled by default and docs retain its experimental boundary.

## CLI

- [x] Preserve CLI/scaffolding regressions and run launch checks at both supported web dependency boundaries.

## diagnostics

- [x] Make production warning handling explicit to release operators; deployment warnings remain advisory, while release-candidate warnings fail. Route inspection accurately reports a running first app at both dependency boundaries.

## operations

- [x] P0: Validate connection/session cleanup after tenant setup and transaction startup failures, including real-pool cancellation and reset failures.
- [x] P0: Release database and worker state when custom lifespan startup fails; provision internal runtime tables through migrations so a current schema starts with DML-only service grants.
- [x] Execute a bounded packaged-app deployment gate covering unavailable DB, invalid config, pending migration, task/worker recovery, backend reconnection, two app instances, in-flight graceful shutdown, and connection cleanup; see `audit-evidence/v060/support-desk-gate.json`.

## observability

- [x] Ensure the supported operational contract distinguishes successful deployment-command exit from a WARN report; release mode returns nonzero for WARN and includes `policy`, `release_ready`, and `exit_code` in JSON.

## packaging

- [x] P0: Encode the supported dependency compatibility boundary; four full-suite matrix runs agree at 7,929 passed / 3 expected skips.
- [x] Run isolated wheel-install import/runtime validation; the generated app served OpenAPI, health, and docs and shut down cleanly.

## docs

- [x] Update the advanced-policy roadmap for the unpublished candidate without rewriting historical release claims.
- [x] P1: Publish tested stable surfaces and explicit experimental/unverified limitations in the v0.6 stability and production contract, with matching MCP, Studio, AI, security, runtime, and upgrade documentation.
- [x] Align CONTRIBUTING lint/type requirements with enforced, reviewed gates; CI and pre-commit run the same pinned Ruff/mypy debt ratchet.

## performance

- [x] Keep the 52-case smoke as a correctness gate; `codex/benchmark-overhaul` isolates the rewrite and the candidate uses it only as an external validation harness.

## release engineering

- [x] P1: Inspect live PR #15 through the public GitHub API; it is open/mergeable with the original head green, and all eight review comments were independently rechecked.
- [x] Triage 504 mypy errors and 7,290 Ruff findings; fix high-signal defects and explicitly baseline the remaining 501 mypy / 7,222 Ruff findings by error code without blanket ignores.
- [ ] Replay required release checks on the exact intended revision, including supported Python/PostgreSQL environments.
- [x] Split Advanced Field Policy correctness from the benchmark overhaul: correctness is on `codex/v055-correctness`; the unchanged overhaul head is preserved on `codex/benchmark-overhaul`.
