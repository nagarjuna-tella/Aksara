<p align="center">
  <img src="aksara/studio/static/icons/aksara-logo.svg" width="64" alt="Aksara logo"/>
</p>

<h1 align="center">Aksara</h1>

<p align="center">
  One model definition → REST API, MCP tools for AI agents, interactive AI Console, built-in Studio UI, admin dashboard, and PostgreSQL migrations. Python. No glue code.
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/tests-5795%2B%20passing-22c55e?style=flat-square&logo=pytest&logoColor=white" alt="Tests">
  <img src="https://img.shields.io/badge/version-0.5.43-3b82f6?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/async-asyncpg-6366f1?style=flat-square" alt="Async">
</p>

---

## What Aksara Does

You define a model once. Aksara generates everything else from it:

```python
from aksara import Aksara, Model, fields
from aksara.api import ModelViewSet

class Incident(Model):
    title = fields.String(
        max_length=200,
        ai_description="Short summary of the incident",
    )
    severity = fields.String(
        choices=["low", "medium", "high", "critical"],
        ai_description="Impact level for triage priority",
    )
    resolved = fields.Boolean(
        default=False,
        ai_agent_writable=False,  # AI agents can read this but not flip it
    )
    notes = fields.Text(
        ai_description="Internal investigation notes",
        ai_sensitive=True,        # Excluded from AI context by default
    )

class IncidentViewSet(ModelViewSet):
    model = Incident

app = Aksara(database_url="postgresql://localhost/myapp")
app.include_viewset(IncidentViewSet, prefix="/incidents")
```

**From this single definition, you get:**

| What             | Where                                                                               |
| ---------------- | ----------------------------------------------------------------------------------- |
| REST API         | `GET/POST/PATCH/DELETE /incidents/`                                                 |
| MCP tool catalog | `/ai/tools/mcp` — any MCP-compatible agent (Claude, Cursor, etc.) can call your API |
| AI Console       | `/studio/ui` → natural-language queries against your live backend                   |
| Studio dashboard | `/studio/ui` — models, routes, queries, migrations, diagnostics                     |
| Admin UI         | `/admin/`                                                                           |
| Database table   | `aksara migrate`                                                                    |

The `ai_description`, `ai_sensitive`, and `ai_agent_writable` metadata you wrote on those fields flows through to the AI Console context and the MCP tool catalog automatically. No second schema. No adapter layer. Write it once.

---

## Quickstart

```bash
pip install aksara
aksara startproject myapp && cd myapp
aksara migrate
aksara dev
```

Now open three things:

| What to try             | URL / Command                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| **Studio + AI Console** | [http://localhost:8000/studio/ui](http://localhost:8000/studio/ui) — ask "explain the Incident model" |
| **MCP tool catalog**    | [http://localhost:8000/ai/tools/mcp](http://localhost:8000/ai/tools/mcp) — point any MCP client here  |
| **Health check**        | `aksara doctor fix-plan` — diagnose and print the remediation path                                    |

That's what makes Aksara different from `pip install fastapi && pip install sqlalchemy && ...`. The AI and diagnostic surfaces exist from the first `aksara dev`.

---

## Features

|     | Feature                  | What it does                                                                                     |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------ |
| 🔌  | **MCP tool export**      | Auto-generated tool catalog at `/ai/tools/mcp` from your model definitions                       |
| 💬  | **AI Console**           | Natural-language queries against your live backend in Studio                                     |
| 🩺  | **Doctor & Fix Plans**   | `aksara doctor fix-plan` diagnoses DB, migrations, AI config, security — prints the fix sequence |
| 🐛  | **AI Debugger**          | Root-cause analysis: issue clustering, heuristic patterns, confidence-ranked causes              |
| 🏗️  | **Architecture Review**  | Automated health scoring (A–F), coupling/schema/API findings                                     |
| 📊  | **Performance Analyzer** | Detects slow queries, N+1, missing indexes, heavy joins                                          |
| ⚡  | **AI Flows**             | In-context AI actions for models, routes, queries, migrations with risk badges                   |
| 🗄️  | **Async ORM**            | Postgres-first: models, typed fields, relations, migrations, asyncpg                             |
| 🔁  | **Auto-REST**            | `ModelViewSet` → full CRUD endpoints, serializers, pagination                                    |
| 🖥️  | **Studio**               | Built-in web UI at `/studio/ui` — inspect models, routes, queries, migrations                    |
| 🛡️  | **Admin**                | Browse and edit data without extra setup                                                         |
| 🔎  | **Semantic Search**      | ⌘K spotlight across models, routes, settings, playbooks                                          |

---

## The Aksara Difference

Most frameworks stop at the database and the HTTP layer. You define a model, you get a table and an endpoint. Aksara keeps going.

The same `ai_description="Short summary of the incident"` you put on a field:

1. **Describes the column** for any developer reading the code
2. **Appears in the MCP tool catalog** at `/ai/tools/mcp` so Claude, Cursor, or any MCP-compatible agent knows what that field means before calling your API
3. **Populates the AI Console context** so you can type "show me all critical unresolved incidents" in Studio and the AI knows which fields to query
4. **Drives the Schema Doctor** which checks that your AI metadata is complete and consistent

`ai_agent_writable=False` on `resolved` means the MCP catalog marks that field read-only — an AI agent can see it but can't change it. `ai_sensitive=True` on `notes` excludes it from AI context entirely.

You write this metadata once, next to the field definition, and it propagates everywhere. No second schema, no separate MCP adapter, no context-building glue code.

---

## Patterns & Examples

| Pattern          | Use Case                          | Command                                           |
| ---------------- | --------------------------------- | ------------------------------------------------- |
| **Blog**         | Posts, comments, publish workflow | `aksara startproject myblog --template blog`      |
| **CRM**          | Customers, deals, pipeline stages | `aksara startproject mycrm --template crm`        |
| **Multitenant**  | Tenant-aware SaaS apps            | `aksara startproject saas --template multitenant` |
| **AI Providers** | BYO LLM wiring examples           | See `examples/ai_providers/`                      |

Browse: [`examples/`](https://github.com/nagarjuna-tella/aksara/tree/main/examples/) | Docs: [Patterns](https://github.com/nagarjuna-tella/aksara/blob/main/docs/docs/patterns/index.md)

---

## Documentation

| Section                                   | Description                                    |
| ----------------------------------------- | ---------------------------------------------- |
| [Quickstart](docs/docs/quickstart.md)     | Build and deploy in 5 minutes                  |
| [ORM Guide](docs/docs/orm/index.md)       | Models, fields, relations, queries             |
| [API Guide](docs/docs/api/index.md)       | ViewSets, actions, serializers                 |
| [AI Mode](docs/docs/ai-mode/index.md)     | MCP, AI Console, Debugger, Architecture Review |
| [Studio Guide](docs/docs/studio/index.md) | Visual inspector & debugging                   |
| [Admin Guide](docs/docs/admin/index.md)   | Admin site customization                       |
| [CLI Reference](docs/docs/cli/index.md)   | All CLI commands                               |

---

## Status

Aksara is **pre-1.0** and actively evolving. Current version: **0.5.43**.

**Stable:** ORM, migrations, ViewSets, serializers, permissions, Admin, Studio, CLI, MCP export, AI Console, Doctor.

**Evolving:** AI Debugger, Architecture Review, Performance Analyzer, Agent Workflows.

See the [Roadmap](https://github.com/nagarjuna-tella/aksara/blob/main/docs/docs/roadmap.md) for what's next.

---

## Contributing

1. Check existing issues or open a new one
2. Fork the repo and create a feature branch
3. Run tests: `pytest`
4. Submit a pull request

---

## Community

<p>
  <a href="https://pypi.org/project/aksara/"><img src="https://img.shields.io/badge/PyPI-aksara-3775A9?style=flat-square&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://github.com/nagarjuna-tella/aksara"><img src="https://img.shields.io/badge/GitHub-aksara-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
</p>

Aksara is designed and built by [Nagarjuna Tella](https://github.com/nagarjuna-tella), with a focus on developer experience for AI-native Python backends.

---

## License

[MIT License](https://github.com/nagarjuna-tella/aksara/blob/main/LICENSE)

---

Built with ❤️ by Nagarjuna Tella.
