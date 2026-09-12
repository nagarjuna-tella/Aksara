"""Verify gap scanner orchestration with controlled checks, not deployment claims."""

import asyncio
from unittest.mock import patch

from pydantic import ValidationError

from aksara import gapanalysis


def test_gap_analysis_selection_and_failure_handling():
    expected = {'imports', 'db', 'migrations', 'routers', 'providers', 'studio',
                'environment', 'ai_pipeline', 'ai_hub'}
    assert set(gapanalysis._CATEGORY_CHECKERS) == expected
    calls = []

    async def first():
        calls.append('first-start')
        await asyncio.sleep(0)
        calls.append('first-end')
        return []

    async def failing():
        calls.append('second')
        raise ValueError('controlled checker failure')

    with patch.dict(gapanalysis._CATEGORY_CHECKERS, {'db': first, 'imports': failing}, clear=True), \
         patch('aksara.ai.graph_events.emit_graph_event'):
        report = asyncio.run(gapanalysis.run_gap_analysis(categories=[]))
        assert calls == ['first-start', 'first-end', 'second']
        assert report.categories_checked == ['db', 'imports']
        assert report.stats.warning == 1
        assert report.issues[0].code == 'IMPORTS_CHECKER_FAILED'
        assert not report.has_errors
        calls.clear()
        try:
            asyncio.run(gapanalysis.run_gap_analysis(categories=['unknown']))
        except ValidationError as error:
            assert error.errors()[0]['type'] == 'literal_error'
        else:
            raise AssertionError('Unknown category must fail before scanning')
        assert calls == []

        assert asyncio.run(gapanalysis.run_gap_analysis_for_category('unknown')) == []
        assert asyncio.run(gapanalysis.run_gap_analysis_for_category('imports')) == []
        assert calls == ['second']
