"""Check widget data handling without executing injected markup."""

from types import SimpleNamespace

from aksara.contrib.admin.widgets import ArrayAdminWidget, JSONAdminWidget


def test_array_render_mutates_input_list():
    values = []
    widget = ArrayAdminWidget(min_rows=2)
    widget.render('tags', values, SimpleNamespace(nullable=True))
    assert values == ['', '']


def test_json_render_escapes_textarea_closure():
    marker = '</textarea><b data-widget-probe="inert">marker</b>'
    widget = JSONAdminWidget()
    rendered = widget.render('metadata', marker, SimpleNamespace(nullable=True))
    assert marker not in rendered
    assert "&lt;/textarea&gt;" in rendered
    assert rendered.count('</textarea>') == 1
