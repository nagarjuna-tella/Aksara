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

def startapp(app_name):
    """Original help."""
    files = create_app_scaffold(app_name)
    click.echo("Original instructions")
    write_scaffold_files(files)

def ai_provider_detect():
    """Original help."""
    click.echo("Original provider instructions")
'''
    changed_help = source.replace('Original', 'Updated')
    assert normalize(source) == normalize(changed_help)
    changed_generation = source.replace('copy_template_project(template)', 'copy_template_project("different")')
    assert normalize(source) != normalize(changed_generation)
    executable_help_argument = source.replace('"Original text"', 'run_something()')
    assert normalize(source) != normalize(executable_help_argument)
    interpolated = source.replace('"Original text"', 'f"Original {lookup(\'first\')}"')
    assert normalize(interpolated) != normalize(interpolated.replace("'first'", "'second'"))
    rendered = source.replace('"Original text"', 'render("first")')
    assert normalize(rendered) != normalize(rendered.replace('"first"', '"second"'))
    extra_call = source + '\n    another_action()\n'
    assert normalize(source) != normalize(extra_call)
    assert normalize(source) != normalize(source.replace('create_app_scaffold(app_name)', 'create_app_scaffold("different")'))
    assert normalize(source) != normalize(source.replace('click.echo("Original instructions")', 'click.echo(run_something())'))
    assert normalize(source) != normalize(source.replace('click.echo("Original provider instructions")', 'click.echo(run_something())'))


def test_template_normalizer_rejects_source_and_name_changes():
    normalize = MODULE['normalized_templates']
    templates = {name: {'name': name, 'description': 'Original', 'source': None if name == 'basic' else name}
                 for name in ('basic', 'blog', 'crm', 'multitenant')}
    source = 'TEMPLATES = ' + repr(templates)
    assert normalize(source) == normalize(source.replace('Original', 'Updated'))
    assert normalize(source) != normalize(source.replace("'source': 'blog'", "'source': 'crm'"))
    assert normalize(source) != normalize(source.replace("'name': 'blog'", "'name': 'crm'"))


def test_readme_normalizer_preserves_executable_interpolations():
    normalize = MODULE['normalized']
    source = 'def get_readme_template(project_name):\n    return f"Original {project_name}"\n'
    assert normalize(source) == normalize(source.replace('Original', 'Updated instructions'))
    for expression in (
        'other_name',
        'run_something(project_name)',
        'project_name!r',
        'project_name:>20',
        'project_name:{width()}',
    ):
        changed = source.replace('{project_name}', '{' + expression + '}')
        assert normalize(source) != normalize(changed), expression
    assert normalize(source) != normalize(source.replace('{project_name}', '{project_name}{project_name}'))
    assert normalize(source) != normalize(source.replace('{project_name}', 'literal project name'))
