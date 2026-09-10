# Static-analysis debt evidence

Date: 2026-09-09

The v0.6 audit began with 7,290 Ruff findings and 504 mypy errors. After
correctness-focused cleanup, the reviewed repository-wide baseline was 7,230
Ruff findings and 501 mypy errors. `static-analysis-baseline.json` records both
totals and every individual rule or error-code count; it does not disable rule
families or add a repository-wide ignore.

The cleanup fixed a broken `tasks` star export, loop callback capture, runtime
type-name resolution, exception handling and traceback logging, and several
high-signal test defects. Mechanical modernization, broad boundary exception
patterns, dynamic framework typing, and experimental Studio annotation debt
remain classified in `STATIC_ANALYSIS_BASELINE.md`.

Enforced command:

```console
PYTHONPYCACHEPREFIX=/tmp/aksara-v060-pycache /tmp/aksara-v055-py311/bin/python scripts/check_static_baseline.py
```

The production reference-app phase removed twelve more Ruff findings without
adding mypy debt and tightened the committed baseline accordingly.

Result: exit **0**; Ruff **7,218 / 7,218**, mypy **501 / 501**.

The same command using a deliberately lower temporary baseline exited **1**
and reported total and per-code overages for both tools. This proves the gate
rejects growth. Ruff 0.16.6 and mypy 2.3.1 are pinned in the development
dependencies, and CI and pre-commit invoke the same script.

An affected regression suite ran against the local PostgreSQL `aksara_test`
database:

```console
DATABASE_URL="$AKSARA_TEST_DATABASE_URL" AKSARA_REQUIRE_DATABASE_TESTS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/aksara-v060-pycache PYTHONPATH="$PWD" /tmp/aksara-v055-py311/bin/python -m pytest -p pytest_asyncio.plugin -q tests/test_tasks.py tests/test_v048_examples_validate.py tests/migrations tests/admin tests/test_security_round2.py tests/api/test_router.py tests/test_v039_investigation_engine.py tests/test_v040_investigation_continuation.py tests/test_debug_error_pages.py tests/ai/test_ai_debug.py tests/test_bug_hunt_phase3_fixes.py tests/test_testing.py tests/test_v049_global_invariants.py tests/test_media_mounting.py
```

Result: **1,050 passed, 3 dependency deprecation warnings in 11.28s**.

That suite exposed an order-dependent production-mode defect: bundled example
imports configured the process-wide debug setting, and a later application
constructed with `debug=False` inherited it for Admin, media, and Studio mount
decisions. Application debug mode is now authoritative for those boundaries,
example import validation restores caller settings, and direct regressions
cover the mismatch. The Studio and affected boundary suite passed **1,234 tests
with 2 dependency deprecation warnings in 7.58s**.

The edited documentation passed the strict MkDocs build in 3.11s.
