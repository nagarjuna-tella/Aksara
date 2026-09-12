# AI Debug tab

**Experimental — local diagnostic assistance.** The built-in advisor is
rule-based: it matches error categories and messages to suggestions and prepares
a prompt you can copy to an assistant. It does not automatically call an LLM
provider. A suggestion is a starting point for investigation, not a verified fix.

## Show the local advisor

The debug HTML response requires `Aksara(debug=True)`. The advisor additionally
checks the configured `Settings.debug` and `Settings.ai_debug_enabled` values.
Set these explicitly for a local debugging application:

```python title="ai_debug_example.py"
from aksara import Aksara
from aksara.conf import Settings, configure


def create_debug_ai_example(*, show_advisor=True):
    configure(Settings(debug=True, ai_debug_enabled=show_advisor))
    app = Aksara(
        debug=True,
        database_url=None,
        auto_discover=False,
        enable_admin=False,
    )

    @app.get("/diagnostic-example")
    async def diagnostic_example():
        raise ValueError("deliberate diagnostic example")

    return app
```

Request `/diagnostic-example` with `Accept: text/html` to inspect the development
error page. With `show_advisor=True`, it includes the AI Debug tab and copyable
prompt. `show_advisor=False` disables the advisor while preserving the ordinary
debug page. Merge these settings into your existing startup configuration;
do not reconfigure global settings while serving requests.

The advisor setting defaults to `True`, but global debug defaults to `False`.
Do not assume that the constructor's debug flag sets global configuration.
JSON error responses do not include this tab. If advisor construction fails,
the handler can still render the ordinary debug page without it.

## What the page provides

The default advisor uses exception classifications and message patterns. It can
show explanations, suggestions, and references to related tools. Those
references do not execute tools or apply patches. The copyable prompt is text
for you to review and use deliberately.

It is not an interactive debugger, automatic query optimizer, provider-quality
guarantee, or production incident diagnosis service. For measured database
behavior, use [query profiling](query-profiling.md). For a lookup or response
problem, use the [exception reference](../reference/exceptions.md) and
[relationship guide](../orm/relations.md). In particular, Aksara's lookup failure
is `aksara.manager.DoesNotExist`, not `User.DoesNotExist`, and a forward foreign
key is not an awaitable object accessor.

## Inspect context before sharing it

The default local advisor needs no provider key and makes no provider request.
Copying its prompt or context into an external assistant is a separate action;
review the content before doing so.

The context can contain exception text, traceback filenames and function names,
request URL and query parameters, selected request headers, application names,
and correlation identifiers. A cached request body can contribute a preview.
The default context builder does not populate frame-local variable previews.
A few sensitive header names and the password portion of a conventional
database URL are masked, but this is not comprehensive redaction. Sensitive
values embedded in exception messages, query strings, source context, or bodies
can remain visible.

The old constructor options `debug_ai_privacy`, `debug_ai_provider`,
`debug_ai_model`, `debug_ai_endpoint`, and `debug_ai_enabled` are not implemented
controls for this feature. Use `Settings.ai_debug_enabled` for the supported
switch; do not rely on extra constructor keywords to configure privacy or route
data to a local provider. The default page uses its built-in advisor; this guide
does not promise a provider or custom-advisor integration.

Keep debug mode disabled on production-facing applications. The AI tab inherits
the debug page's exposure; it does not add authentication or a staff-only access
check. See [error-page access and masking limits](error-pages.md) and
[AI stability boundaries](../ai-mode/index.md).
