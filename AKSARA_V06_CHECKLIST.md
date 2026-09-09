# Aksara v0.6 executable checklist

Evidence: [current-state audit](AKSARA_CURRENT_STATE.md) and [saved results](audit-evidence/current-state/). Unchecked items are gates, not claims of absent implementation. No production code was changed by the audit.

## ORM

- [x] P0: Make transaction/session acquisition exception-safe; `audit-evidence/v055/repro-cleanup.log` shows releases=1 and no leaked session.
- [x] P0: Real one-connection-pool regressions cover repeated setup/start/reset failures and cancellation (`tests/db/test_failed_start_cleanup.py`).

## migrations

- [ ] Preserve the 452 passing migration cases; validate a fresh bootstrap plus an existing-schema upgrade under the final supported environment. Existing locking/checksum implementation should be reused.

## relations

- [x] Preserve tested relation/on_delete behavior; document ID-valued forward FK and unsupported custom through models without implying implementation.

## API

- [x] P0: Effective route traversal fixes all 15 failures; the full suite passes on Python 3.11/3.14 at both documented web dependency boundaries.

## security

- [x] P1: Replace skipped OpenAPI fuzz placeholders with generated-CRUD invalid-input and forbidden-field mutation invariants; `audit-evidence/v060/generated-api-abuse.md` records the real PostgreSQL run.
- [ ] P1: Set an explicit release policy for Doctor warnings and security-matrix requirements; test both safe and unsafe cases.

## tenancy

- [x] P1: Run cross-tenant ORM/generated-API/task checks with a non-superuser, non-BYPASSRLS application role, including one-connection pool reuse and an MCP-principal call to a catalog-described REST operation; see `audit-evidence/v060/restricted-role-tenancy.md`.

## MCP

- [ ] Verify route-derived tool inventory and schema against a running generated app; discovery survives both supported dependency boundaries, while the end-to-end authorization gate remains open.
- [ ] Keep protocol-level MCP execution outside the v0.6 guarantee unless a real transport is implemented and exercised; this repository currently exposes an MCP-shaped catalog only.

## Agent/AI

- [ ] State that investigation sessions are process-local unless durable storage is implemented and restart/multi-worker behavior tested.
- [ ] Keep autonomous durable mutation/approval guarantees out of the production contract until replay/retry/authorization-at-execution is demonstrated.

## Admin

- [x] Revalidate mounting/discovery with supported dependencies and preserve passing CRUD/permission assertions; both dependency boundaries pass.

## Studio

- [x] Fix the three reproduced route/context failures and launch-check mismatch; generated projects keep Studio disabled by default and docs retain its experimental boundary.

## CLI

- [x] Preserve CLI/scaffolding regressions and run launch checks at both supported web dependency boundaries.

## diagnostics

- [ ] Make production warning handling explicit to release operators; check that route inspection accurately reports a running first app.

## operations

- [x] P0: Validate connection/session cleanup after tenant setup and transaction startup failures, including real-pool cancellation and reset failures.
- [ ] Before claiming restart/shutdown reliability, execute a bounded real deployment failure test; this audit did not certify it.

## observability

- [ ] Ensure the supported operational contract distinguishes successful command exit from a WARN report; retain structured evidence for failed release checks.

## packaging

- [x] P0: Encode the supported dependency compatibility boundary; four full-suite matrix runs agree at 7,929 passed / 3 expected skips.
- [x] Run isolated wheel-install import/runtime validation; the generated app served OpenAPI, health, and docs and shut down cleanly.

## docs

- [x] Update the advanced-policy roadmap for the unpublished candidate without rewriting historical release claims.
- [ ] P1: Publish tested stable surfaces and explicit experimental/unverified limitations.
- [ ] Align CONTRIBUTING lint/type requirements with enforced, reviewed gates.

## performance

- [x] Keep the 52-case smoke as a correctness gate; `codex/benchmark-overhaul` isolates the rewrite and the candidate uses it only as an external validation harness.

## release engineering

- [x] P1: Inspect live PR #15 through the public GitHub API; it is open/mergeable with the original head green, and all eight review comments were independently rechecked.
- [ ] Triage 504 mypy errors and 7290 Ruff findings; fix substantive issues and explicitly baseline legacy debt instead of blanket ignoring it.
- [ ] Replay required release checks on the exact intended revision, including supported Python/PostgreSQL environments.
- [x] Split Advanced Field Policy correctness from the benchmark overhaul: correctness is on `codex/v055-correctness`; the unchanged overhaul head is preserved on `codex/benchmark-overhaul`.
