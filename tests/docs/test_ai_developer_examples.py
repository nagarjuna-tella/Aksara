"""Run deterministic AI developer examples in a disposable project; never apply patches."""

import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ai_codegen_planner_and_patch_previews():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='aksara-ai-doc-preview-') as directory:
        project = Path(directory)
        (project / 'app').mkdir()
        model = project / 'app/models.py'
        original = '"""Temporary documentation fixture."""\n'
        model.write_text(original)
        try:
            os.chdir(project)
            for name in ('planner', 'codegen', 'patch-engine', 'safety'):
                page = ROOT / f'docs/docs/ai-mode/{name}.md'
                code = re.search(r'```python\n(.*?)```', page.read_text(), re.DOTALL)[1]
                namespace = {}
                exec(compile(code, str(page), 'exec'), namespace)  # noqa: S102
                if name == 'planner':
                    assert namespace['validate_plan'](namespace['plan']) == []
                elif name == 'codegen':
                    assert namespace['result'].files
                    for filename, content in namespace['result'].files.items():
                        if filename.endswith('.py'):
                            compile(content, filename, 'exec')
                else:
                    preview = namespace['preview']
                    assert preview.preview_only
                    assert not preview.applied
                    assert preview.files_changed
                assert model.read_text() == original
        finally:
            os.chdir(previous)
