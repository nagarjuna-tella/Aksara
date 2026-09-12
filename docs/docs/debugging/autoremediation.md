# Diagnostic fix suggestions

Doctor can attach structured suggestions to diagnostic issues. A fix plan helps
you review what to change; it does not execute commands, edit files, or grant an
agent permission to apply a repair. Individual issues may have an empty action
list. Studio or experimental AI consumers do not turn these suggestions into a
validated production repair workflow.

## Read a fix plan

Run diagnostics in your configured application environment:

```bash
aksara doctor fix-plan
aksara doctor fix-plan --format json
aksara doctor fix-plan --only-errors
aksara doctor fix-plan --only-with-actions
```

The command runs diagnostic checks before filtering their results. Those checks
may inspect configured services and filesystem access; filtering is not a way to
avoid running particular checks.

An exit status of 1 means the **filtered issue list** contains errors; otherwise
the status is 0. Consequently `--only-with-actions` can hide an error that has no
suggested action and return 0. JSON `stats` still describe the unfiltered report,
whereas `issues` contains the selected subset. An empty filtered plan is not proof
that the application is healthy.

For the production release policy, use
[Doctor's production checks](../diagnostics.md), including
`aksara doctor production-check --release --format json`. Do not substitute a
filtered fix plan for that gate.

## Represent a suggestion

`DiagnosticAction` is a data model. `build_action()` constructs and validates its
shape; it does not verify that the example is suitable for your environment.
This complete example performs no diagnostics and executes no command:

```python title="diagnostic_suggestion.py"
from aksara.diagnostics import DiagnosticIssue, build_action

suggestion = build_action(
    kind="run_command",
    target="aksara doctor production-check",
    title="Inspect production readiness",
    example="aksara doctor production-check --release --format json",
    description="Review the report before changing deployment settings.",
)
issue = DiagnosticIssue(
    kind="application_review",
    severity="info",
    title="Review deployment configuration",
    message="This application requires an operator review.",
    actions=[suggestion],
)
```

| Field | Meaning |
| --- | --- |
| `kind` | One of `set_env`, `edit_file`, `run_command`, `open_doc`, `add_setting` |
| `target` | Environment name, file, command, URL, or setting |
| `title` | Display label |
| `example` | Optional suggested text; may require adaptation |
| `description` | Optional explanation |

For programmatic diagnosis, `await run_all_checks()` returns a `DiagnosticReport`;
iterate `report.issues` and each issue's `actions`. Checkers that fail are reported
as warning issues. The result includes system metadata and elapsed time, so it is
not a byte-stable artifact across runs.

Review suggested commands and URLs before using them. A command can affect
schema, configuration, or files; diagnostic metadata is not authorization for
those changes. Keep reports private when they reveal deployment details, and
preserve exit codes when collecting them in CI.
