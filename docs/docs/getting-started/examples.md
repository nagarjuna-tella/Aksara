# Golden-Path Examples

Aksara ships example apps for the first ten minutes and for common backend shapes.

Validate them:

```bash
aksara examples validate
aksara examples validate --format json
```

## Examples

| Example | Demonstrates |
|---|---|
| `basic_app` | Smallest working Aksara app |
| `blog` | Models, relations, APIs, Studio, MCP |
| `crm` | Business data model and reporting queries |
| `multitenant` | Tenant-aware app structure |
| `ai_providers` | Local and remote AI setup |

## Run an Example

```bash
cd examples/blog
python -m venv .venv
source .venv/bin/activate
pip install -e ../..
aksara doctor launch-check
aksara migrate
aksara dev
```

Open:

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* Tool inspection catalog: http://127.0.0.1:8000/ai/tools/mcp (HTTP JSON; protocol clients use `/mcp/` when enabled)

## AI Provider Note

Examples do not require paid providers. Configure AI only when you want AI Console, AI Debugger, Architecture Review, Performance Analyzer, Investigation Sessions, or Daily Briefing to call a model.
