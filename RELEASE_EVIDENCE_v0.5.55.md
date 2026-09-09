# Aksara v0.5.55 release-candidate evidence

## Candidate

- Revision: `094169ef22bf90b8ae9d7814e62889d557d44f15`
- Branch: `codex/v055-correctness`
- Parent: `bf388ac734070bcad18b895f6f1b3d66877b16d9`
- Status: release candidate only; not published
- Candidate diff: 48 files changed, 1,162 insertions, 241 deletions

The candidate contains Advanced Field Policy corrections, failed-start database cleanup, effective route traversal across the supported web stack, dependency bounds, release-gate matrix coverage, regressions, and public documentation. The benchmark implementation overhaul is excluded.

The separate benchmark change is preserved at `dccef5ddf3b8ad9c5fee1ccdc39cf753bbf9032e` on `codex/benchmark-overhaul`. Relative to the shared field-policy base `bf388ac734070bcad18b895f6f1b3d66877b16d9`, it changes 46 files with 5,128 insertions and 1,852 deletions.

## Environment

- macOS host with local PostgreSQL 18.4
- Database: `aksara_test`
- Extensions exercised: pgvector and pgcrypto
- Database-backed tests were required with `AKSARA_REQUIRE_DATABASE_TESTS=1`; missing connectivity could not become a skip
- asyncpg 0.31.0, Pydantic 2.13.5, pytest 9.1.1
- Python/web matrix:

| Python | FastAPI | Starlette | Result |
| --- | --- | --- | --- |
| 3.11.5 | 0.136.1 | 1.0.1 | 7,929 passed, 3 skipped, 25 warnings |
| 3.11.5 | 0.141.1 | 1.6.0 | 7,929 passed, 3 skipped, 26 warnings |
| 3.14.4 | 0.136.1 | 1.0.1 | 7,929 passed, 3 skipped, 25 warnings |
| 3.14.4 | 0.141.1 | 1.6.0 | 7,929 passed, 3 skipped, 26 warnings |

The three skips are the pre-existing optional OpenAPI-fuzz placeholder and two live OpenAI examples that require `OPENAI_API_KEY`. The OpenAPI placeholder remains a required v0.6 P1 gate and is not treated as v0.6-ready evidence.

## Reproducible commands

The local database URL was supplied through `AKSARA_TEST_DATABASE_URL`; credentials are intentionally absent from this record.

```bash
export DATABASE_URL="$AKSARA_TEST_DATABASE_URL"
export AKSARA_REQUIRE_DATABASE_TESTS=1

python -m pip install -e '.[dev]'
python -m pip install 'fastapi==0.136.1' 'starlette==1.0.1'
python -m pytest --tb=short -q

python -m pip install 'fastapi==0.141.1' 'starlette==1.6.0'
python -m pytest --tb=short -q

python -m pytest -q tests/migrations tests/fields tests/api tests/admin
python -m mkdocs build --strict --site-dir /tmp/aksara-v055-final-site
python -m build --outdir /tmp/aksara-v055-final-dist
python -m twine check /tmp/aksara-v055-final-dist/*
```

The complete test command was repeated in isolated Python 3.11.5 and 3.14.4 environments at both documented web dependency boundaries. Dependency freezes are saved beside the full-suite logs.

The benchmark smoke used the harness from the isolated `codex/benchmark-overhaul` worktree while importing Aksara from this candidate checkout. The wheel smoke created a clean virtual environment, installed only the built wheel, scaffolded a generated app, started it, exercised OpenAPI/health/docs/Studio routing, and terminated it gracefully.

## Results

| Gate | Evidence | Result |
| --- | --- | --- |
| Failed-start and cancellation cleanup | `audit-evidence/v055/repro-cleanup.log`, `tests/db/test_failed_start_cleanup.py` | acquired 1, released 1, no stale session; real one-connection pool restored capacity |
| Advanced fields and migrations | `audit-evidence/v055/field-migration-gate.log` | 612 passed; includes the preserved 452-test migration group |
| Python 3.14 minimum web boundary | `audit-evidence/v055/full-minimum.log` | 7,929 passed, 3 skipped |
| Python 3.14 latest supported boundary | `audit-evidence/v055/full-latest.log` | 7,929 passed, 3 skipped |
| Python 3.11 minimum web boundary | `audit-evidence/v055/full-py311-minimum.log` | 7,929 passed, 3 skipped |
| Python 3.11 latest supported boundary | `audit-evidence/v055/full-py311-latest.log` | 7,929 passed, 3 skipped |
| 52-case benchmark correctness smoke | `audit-evidence/v055/benchmark-smoke.log` | 52 passed, 0 failed, 0 unsupported |
| Strict documentation build | `audit-evidence/v055/docs-final.log` | passed |
| Wheel and source distribution | `audit-evidence/v055/build-final.log` | both built |
| Package metadata | `audit-evidence/v055/twine-final.log` | wheel and sdist passed |
| Clean wheel install and generated app | `audit-evidence/v055/wheel-smoke-final.log` | import 0.5.55; OpenAPI, health, and docs returned 200; Studio returned expected 404; graceful shutdown observed |
| New-code lint | `audit-evidence/v055/new-code-ruff.log` | passed |

## Blockers

There is no known P0 blocker for the v0.5.55 correctness candidate. Publication remains blocked on explicit release authorization.

The broader v0.6 Production Mode claim remains blocked by the unchecked P1 gates in `AKSARA_V06_CHECKLIST.md`, especially restricted-role tenancy, real generated-API abuse invariants, release interpretation of Doctor warnings, a reviewed static-analysis baseline, and the packaged production-shaped reference application.

## Known limitations

- Only FastAPI 0.136.1 through 0.141.1 and Starlette 1.0.1 through 1.6.0 are declared and tested for this candidate.
- PostgreSQL-backed validation used PostgreSQL 18.4 locally; release CI is configured for PostgreSQL 16 with pgvector.
- Studio and AI investigation/planning surfaces remain experimental. Investigation state is process-local and has no restart or multi-worker durability guarantee.
- The optional OpenAPI-fuzz test is still a placeholder and is scheduled for replacement in the v0.6 P1 work.
- Existing repository-wide Ruff and mypy debt is not represented as clean; new candidate modules were checked separately.

## Explicitly deferred from v0.5.55

- Benchmark implementation overhaul and comparative performance claims
- Custom many-to-many through models
- Object-valued lazy forward foreign keys
- Durable investigation sessions and AI memory
- Autonomous durable mutation/approval guarantees
- Studio redesign and broad provider certification
- Repository-wide formatting or type-annotation rewrite
- New ORM field types or major CLI redesign
