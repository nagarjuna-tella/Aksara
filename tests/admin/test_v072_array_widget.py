"""Regression contracts for observational array-widget rendering."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aksara.contrib.admin.widgets import ArrayAdminWidget

FIELD = SimpleNamespace(nullable=True)


@pytest.mark.parametrize(
    "values",
    [
        [],
        ["one"],
        ["one", "two", "three"],
        ["one", "two", "three", "four"],
    ],
)
def test_render_preserves_lists_at_every_minimum_boundary(values):
    before = list(values)
    widget = ArrayAdminWidget(min_rows=3)

    rendered = widget.render("items", values, FIELD)

    assert values == before
    assert rendered.count('class="array-item"') == max(3, len(values))


def test_repeated_render_and_shared_reference_are_observational():
    shared = ["one"]
    alias = shared
    widget = ArrayAdminWidget(min_rows=3)

    first = widget.render("items", shared, FIELD)
    second = widget.render("items", shared, FIELD)

    assert shared is alias
    assert shared == ["one"]
    assert first == second


def test_tuple_is_supported_without_mutation():
    values = ("one", "two")
    rendered = ArrayAdminWidget(min_rows=3).render("items", values, FIELD)

    assert values == ("one", "two")
    assert rendered.count('class="array-item"') == 3


def test_render_preserves_html_escaping_without_mutation():
    values = ['<script>alert("x")</script>', "safe & sound"]
    before = list(values)

    rendered = ArrayAdminWidget(min_rows=1).render("items", values, FIELD)

    assert values == before
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in rendered
    assert "safe &amp; sound" in rendered
