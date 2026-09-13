# Aksara v0.7.2 Audit Closure Baseline

## Baseline decision

The immutable starting point is the released Aksara v0.7.1 tree. The current
`main` merge commit is `a0422cf8fa004b41a2ccdaa9aa91c8036357159d`.
The annotated `v0.7.1` tag peels to
`ab9243a765188a8ed50b28994e536f72329a818d`. Both commits have tree
`c37635addace9762dc6ed0d38f4df3281a809652`, so the published tag and merged
source are content-equivalent despite their different commit identities.

The audit-closure branch is `codex/v072-audit-closure`, created directly from
the released `main` merge. No production source, dependency, migration, or
version change was made before this baseline was recorded. The package remains
`0.7.1`; it will not move to `0.7.2rc1` until the implementation campaign and
source regression meet the release-candidate gate.

## Publication verification

- PyPI serves `aksara-framework==0.7.1`.
- A clean Python 3.11 environment installs and imports `0.7.1`; its CLI reports
  `aksara, version 0.7.1`.
- The downloaded public wheel is
  `aksara_framework-0.7.1-py3-none-any.whl`, SHA-256
  `42a3a42be08ee5be1075d4f6da3b22fea6acaa5bf678a57db7ecc00ce4fdd197`.
- That digest matches PyPI and the final v0.7.1 release evidence.
- GitHub publishes the non-draft, non-prerelease `v0.7.1` release.

The isolated public environment is
`/private/tmp/aksara-v072-public-071`. Reproduction subprocesses use isolated
mode from disposable working directories and verify that Aksara is imported
outside this repository.

## Environment

| Item | Baseline |
| --- | --- |
| Local PostgreSQL | 18.4 (`180004`) |
| Database | `aksara_test` |
| Baseline Python | 3.11.15 |
| Additional supported Python | 3.14.4 |
| Minimum web boundary | FastAPI 0.136.1 / Starlette 1.0.1 |
| Latest web boundary | FastAPI 0.141.1 / Starlette 1.6.0 |
| Public-wheel probe web stack | FastAPI 0.141.1 / Starlette 1.6.0 |
| Public-wheel asyncpg | 0.31.0 |

Database credentials and complete connection URLs are excluded from committed
evidence.

## Protected untracked state

Before baseline files were created, the working tree contained only these
intentionally preserved untracked directories:

| Directory | Files | Content-tree SHA-256 |
| --- | ---: | --- |
| `audit-evidence/current-state/` | 26 | `e018f9cdbcfc933cf3769fb0f3cb8ce7bdb7b09c0b717e336af5d2e3f7dfef5f` |
| `audit-evidence/v055/` | 50 | `8f65c3605d3a0ffa139df6053348c1bebc480d2a28028f6601f748b9ff205008` |
| `benchmarks/results/` | 51 | `1777e5606c4754c089b82bf61dba318e3c549520d8b2798aaa3e138b460068e3` |

They are not part of v0.7.2 and must remain unchanged and uncommitted.

## Finding reconciliation

All 22 audit findings were independently reconciled against the public v0.7.1
wheel before production implementation began. The exact released repository
example is paired with that wheel for EX-001 because examples are repository
source rather than installed package modules.

| ID | Baseline result | Evidence |
| --- | --- | --- |
| CFG-001 | Reproduced: URL split at `:` | `unit-findings.json` |
| SDK-001 | Reproduced: TypeScript 5.9.3 exits 2 with TS2322 | `SDK-001.json` |
| STORAGE-001 | Reproduced: sibling-prefix write escapes root | `unit-findings.json` |
| ACTION-001 | Reproduced: generated route 403, custom action 200 | `ACTION-001.json` |
| TASK-001 | Reproduced: stale completion overwrites replacement | `TASK-001.json` |
| AIPROVIDER001 | Reproduced: default false positive and keyless false negative | `AIPROVIDER001.json` |
| GAP001 | Reproduced: Python 3.10 accepted | `GAP001.json` |
| AIFLOW001 | Reproduced: direct clean import exits 1 | `unit-findings.json` |
| AIFLOW002 | Reproduced: duplicated `export DATABASE_URL=` prefix | `unit-findings.json` |
| EX-001 | Reproduced: `/api/projects/` bypasses tenant resolution | `unit-findings.json` |
| SCAFFOLD-001 | Reproduced: editable install exits 1 | `SCAFFOLD-001.json` |
| SOFTDELETE001 | Reproduced: supplied query restrictions are lost | `SOFTDELETE001.json` |
| FIXTURE001 | Reproduced: exported primary key cannot restore missing row | `fixtures.json` |
| FIXTURE002 | Reproduced: UUID YAML output fails safe loading | `fixtures.json` |
| FIXTURE003 | Reproduced: default dump iterates registry names | `fixtures.json` |
| INSPECTOR001 | Reproduced: synthetic ANALYZE lacks provenance | `unit-findings.json` |
| ADMINWIDGET001 | Reproduced: render mutates caller list | `unit-findings.json` |
| MIGRATION-001 | Reproduced: User collision silently omits `tenant_users` | `MIGRATION-001.json` |
| RELATION001 | Reproduced: `select_related(...).first()` loses eager relation | `RELATION001.json` |
| BULK-001 | Reproduced: Boolean/timestamp CASE inferred as text | `BULK-001.json` |
| PAGINATION-001 | Reproduced: HTTP response loses paginator metadata | `PAGINATION-001.json` |
| TESTING-001 | Reproduced: writes survive cleanup and pool remains usable | `TESTING-001.json` |

Totals: 22 reproduced, zero disproved, zero already resolved, zero test-harness
mistakes, and zero unreconciled at baseline. These are baseline dispositions,
not closure dispositions. Every defect remains open until a sensitive
regression, implementation repair, installed-candidate result, and final
evidence establish closure.

## Evidence index

Machine-readable environment, publication, public-wheel, protected-state, and
finding records are in `audit-evidence/v072-baseline/`. The authoritative
finding ledger is `findings.json`; every row records the reproduction command,
environment, expected behavior, observed v0.7.1 behavior, PostgreSQL/network
requirements, security and data-integrity impact, compatibility implications,
evidence artifact, and likely source locations.

The baseline does not authorize a broad redesign. Every future production
change must map to one or more of these 22 IDs.
