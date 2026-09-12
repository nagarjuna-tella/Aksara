"""Ensure instructional-text normalization cannot conceal execution changes."""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / 'scripts/check_v071_runtime_scope.py'))


def test_cli_normalizer_rejects_generation_and_help_argument_execution_changes():
    normalize = MODULE['normalized_cli']
    source = '''
def startproject(template):
    """Original help."""
    files = copy_template_project(template)
    ui.text("Original text")
    ui.next_steps(["Original step"])
    write_scaffold_files(files)
'''
    changed_help = source.replace('Original', 'Updated')
    assert normalize(source) == normalize(changed_help)
    changed_generation = source.replace('copy_template_project(template)', 'copy_template_project("different")')
    assert normalize(source) != normalize(changed_generation)
    executable_help_argument = source.replace('"Original text"', 'run_something()')
    assert normalize(source) != normalize(executable_help_argument)
    extra_call = source + '\n    another_action()\n'
    assert normalize(source) != normalize(extra_call)


def test_template_normalizer_rejects_source_and_name_changes():
    normalize = MODULE['normalized_templates']
    templates = {name: {'name': name, 'description': 'Original', 'source': None if name == 'basic' else name}
                 for name in ('basic', 'blog', 'crm', 'multitenant')}
    source = 'TEMPLATES = ' + repr(templates)
    assert normalize(source) == normalize(source.replace('Original', 'Updated'))
    assert normalize(source) != normalize(source.replace("'source': 'blog'", "'source': 'crm'"))
    assert normalize(source) != normalize(source.replace("'name': 'blog'", "'name': 'crm'"))
