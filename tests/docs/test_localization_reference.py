"""Execute the exact locale/timezone guide without a database or catalogs."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / 'docs/docs/advanced/internationalization-and-timezones.md'


def test_localization_examples():
    from starlette.testclient import TestClient

    from aksara.conf import settings
    from aksara.i18n import clear_i18n_cache
    from aksara.middleware import locale_var, timezone_var

    original = vars(settings).copy()
    locale_token = locale_var.set(None)
    timezone_token = timezone_var.set(None)
    snippets = dict(re.findall(r'```python title="([^"]+)"\n(.*?)```', PAGE.read_text(), re.DOTALL))
    try:
        namespace = {'__name__': 'locale_app'}
        exec(compile(snippets['locale_app.py'], 'locale_app.py', 'exec'), namespace)  # noqa: S102 - trusted repository example
        with TestClient(namespace['app']) as client:
            response = client.get('/preferences', headers={
                'Accept-Language': 'fr-CA,fr;q=0.9,en;q=0.5',
                'X-Timezone': 'America/New_York',
            })
            assert response.status_code == 200
            assert response.json() == {
                'locale': 'fr', 'timezone': 'America/New_York',
                'message': 'Welcome back, Ada',
                'local_time': '2026-01-15T09:30:00-05:00',
            }
            response = client.get('/preferences')
            assert response.status_code == 200
            assert response.json()['locale'] == 'en'
            assert response.json()['timezone'] == 'UTC'
            assert response.json()['local_time'] == '2026-01-15T14:30:00+00:00'
            response = client.get('/preferences', headers={
                'Accept-Language': 'es', 'X-Timezone': 'Mars/OlympusMons',
            })
            assert response.status_code == 200
            assert response.json()['locale'] == 'en'
            assert response.json()['timezone'] == 'UTC'
        assert locale_var.get() is None and timezone_var.get() is None
        exec(compile(snippets['timezone_conversion.py'], 'timezone_conversion.py', 'exec'), {})  # noqa: S102 - trusted repository example
        assert timezone_var.get() is None
    finally:
        vars(settings).clear()
        vars(settings).update(original)
        clear_i18n_cache()
        locale_var.reset(locale_token)
        timezone_var.reset(timezone_token)
