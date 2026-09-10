# Your first 10 minutes

Use the [First project](first-project.md) guide for the canonical installed-wheel
path. It covers exactly one model, generated REST routes, PostgreSQL migrations,
Doctor, and startup.

The sequence is:

```bash
python -m venv .venv
source .venv/bin/activate
pip install "aksara-framework==0.7.0rc1"
aksara startproject hello_aksara
cd hello_aksara
aksara dbsetup
# Define the Task model and TaskViewSet from the guide.
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

Open `http://127.0.0.1:8000/docs` for REST OpenAPI. The generated project keeps
MCP, provider-backed AI, and Studio disabled by default.

When the REST path works, follow the [MCP quickstart](mcp.md) to add trusted
server-side Principal resolution and connect an official MCP client to
`http://127.0.0.1:8000/mcp/`. The JSON at `/ai/tools/mcp` is an inspection
catalog and is not the MCP protocol transport.
