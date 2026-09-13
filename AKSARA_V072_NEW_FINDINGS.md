# Aksara v0.7.2 New Findings Register

## Release decision

No newly discovered unresolved release blocker, security flaw, data-integrity
defect, or v0.7.2 regression remains. The campaign produced two bounded
release-process findings; both were corrected and regression-checked before the
candidate evidence was finalized.

| ID | Classification | Observation | Disposition | Evidence |
| --- | --- | --- | --- | --- |
| `V072-NF-001` | Regression caused by v0.7.2 | Correct provider configured-state semantics allowed `base_url=None`, exposing a Studio status serializer that assumed a string. One first full-source run failed that assertion. | Fixed within the AIPROVIDER001 wave by rendering an absent URL as an empty display value without changing provider semantics. The repeated full suite and all four matrix cells pass. | `audit-evidence/v072/matrix-py314-latest.log` and the provider/Studio regression tests |
| `V072-NF-002` | Test-harness drift | The installed documentation runner still invoked the v0.7.1 negative-control names for synthetic Inspector provenance and Array widget mutation after those contracts became positive. | Updated only the runner assertions and evidence fields to require explicit synthetic provenance and caller-input preservation. The installed candidate now passes 348 Python and 15 JSON fence checks. | `audit-evidence/v072/installed-doc-imports.json` |

Two local execution incidents were investigated and classified as harness or
environment setup, not framework defects: the development virtual environment
did not contain the `build` command, so the established isolated `uvx` build
path was used; and an early upgrade-gate parser assumed asyncpg decoded JSONB to
a mapping rather than a string. Neither affected package source or candidate
behavior, and neither remains in the finalized gate.

No ordinary maintenance item or feature request was promoted into v0.7.2
scope. The finite 22-item ledger remains the entire product-change boundary.
