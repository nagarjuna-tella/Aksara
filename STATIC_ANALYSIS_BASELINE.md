# Static-analysis debt baseline

This repository is not Ruff-clean or mypy-clean. The v0.6 policy records the
legacy debt explicitly and prevents any rule or error-code count from growing.
It does not disable a Ruff rule family or silence mypy errors globally.

The reviewed baseline uses Ruff 0.16.6 and mypy 2.3.1:

| Tool | Audit count | Reviewed baseline | Change |
| --- | ---: | ---: | ---: |
| Ruff | 7,290 | 7,230 | -60 |
| mypy | 504 | 501 | -3 |

The audit's Ruff log preceded some v0.5.55 cleanup, so the 34 findings already
removed before this phase are included in the Ruff change above. This phase
then removed 26 correctness-significant findings or tightly justified test-only
findings.

## Classification and action

| Class | Examples | v0.6 action |
| --- | --- | --- |
| Correctness and public-contract defects | broken `tasks.__all__`, loop callback capture, duplicate runtime/type import | Fixed before establishing the baseline |
| Error and observability defects | bare exception, exception logging without the supplied traceback, redundant exception formatting | Fixed before establishing the baseline |
| Stable-surface type resolution | missing forward imports in session, model, router, Admin, debug, and investigation modules | Fixed before establishing the baseline |
| Test-only high-signal rules | callable detection, subprocess result policy, dynamic star-import test | Fixed or justified on the exact line |
| Mechanical modernization | legacy `typing` aliases, quoted annotations, UTC alias, import order | Baseline; reduce incrementally |
| Broad exception patterns | `BLE001`, `S110`, `S112` | Baseline; review per call site because many are intentional boundary handlers |
| Dynamic framework typing | model metaclass, field descriptors, generated serializers, migration autodetection | Baseline; improve with focused typing work |
| Experimental Studio annotations | the remaining Ruff `F821` findings | Baseline and excluded from the stable v0.6 compatibility contract |

## Enforced command

```bash
python scripts/check_static_baseline.py
```

The command runs repository-wide Ruff and mypy, checks the exact tool versions,
and fails if the total or any individual rule/error-code count exceeds
`static-analysis-baseline.json`. Counts may fall without editing the baseline,
which makes cleanup a ratchet. Raising a count requires an explicit review of
this document and the baseline; CI never updates it automatically.
