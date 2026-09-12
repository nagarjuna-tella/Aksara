"""Execute the suggestion example and verify filtered CLI result semantics."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.diagnostics import DiagnosticIssue, DiagnosticReport


def test_diagnostic_suggestion_example():
    page = Path(__file__).resolve().parents[2] / 'docs/docs/debugging/autoremediation.md'
    code = re.search(r'```python title="diagnostic_suggestion.py"\n(.*?)```', page.read_text(), re.DOTALL)[1]
    namespace = {}
    exec(compile(code, 'diagnostic_suggestion.py', 'exec'), namespace)  # noqa: S102
    assert namespace['issue'].actions[0] == namespace['suggestion']
    assert namespace['suggestion'].kind == 'run_command'


def test_filtered_fix_plan_is_not_release_gate():
    report = DiagnosticReport()
    report.add(DiagnosticIssue(kind='general', severity='error', title='No suggestion', message='Error'))
    runner = CliRunner()
    with patch('aksara.diagnostics.run_all_checks', new=AsyncMock(return_value=report)):
        full = runner.invoke(cli, ['doctor', 'fix-plan', '--format', 'json'])
        filtered = runner.invoke(cli, ['doctor', 'fix-plan', '--format', 'json', '--only-with-actions'])
    assert full.exit_code == 1
    assert filtered.exit_code == 0
    data = json.loads(filtered.output)
    assert data['issues'] == []
    assert data['stats']['errors'] == 1
