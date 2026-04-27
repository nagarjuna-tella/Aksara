<p align="center">
  <img src="https://raw.githubusercontent.com/nagarjuna-tella/aksara/main/aksara/studio/static/icons/aksara-logo.svg" width="64" alt="Aksara logo"/>
</p>

<h1 align="center">Aksara – Async Postgres-first Web Framework</h1>

<p align="center">
  A modern async web framework that combines a typed ORM for PostgreSQL, a FastAPI-compatible router, a built-in Admin, and an AI-aware Studio & contracts layer.
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/tests-5795%2B%20passing-22c55e?style=flat-square&logo=pytest&logoColor=white" alt="Tests">
  <img src="https://img.shields.io/badge/version-0.5.42-3b82f6?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/async-asyncpg-6366f1?style=flat-square" alt="Async">
</p>

<p align="center">
  Built for teams that want <strong>fast CRUD</strong>, <strong>strong DX</strong>, and <strong>LLM-ready backends</strong>.
</p>

---

## Features at a Glance

<table>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/lightning-bolt.png" alt="async"/></td>
    <td><strong>Async everything</strong> – built on async Postgres drivers (asyncpg)</td>
  </tr>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/database.png" alt="orm"/></td>
    <td><strong>Postgres-first ORM</strong> – models, migrations, typed fields, relations</td>
  </tr>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/settings.png" alt="admin"/></td>
    <td><strong>Admin included</strong> – browse and edit data without extra setup</td>
  </tr>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/monitor.png" alt="studio"/></td>
    <td><strong>Studio</strong> – inspector for models, routes, migrations, runtime, and DB queries</td>
  </tr>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/artificial-intelligence.png" alt="ai"/></td>
    <td><strong>AI contracts</strong> – JSON schemas, provider profiles, and route hints for LLMs</td>
  </tr>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/console.png" alt="cli"/></td>
    <td><strong>CLI & patterns</strong> – start projects with blog, CRM, multitenant, and AI examples</td>
  </tr>
  <tr>
    <td><img src="https://img.icons8.com/fluency/24/stethoscope.png" alt="diagnostics"/></td>
    <td><strong>Doctor mode</strong> – self-diagnostics for DB, migrations, AI, settings, and security; structured fix-plan suggestions via <code>aksara doctor fix-plan</code></td>
  </tr>
  <tr>
    <td>🧠</td>
    <td><strong>Agent mode</strong> – gather project context and build LLM-ready system prompts via Studio UI, CLI (<code>aksara agent</code>), or Python API; <strong>Playbooks</strong> (v0.5.20) – 8 built-in recipes for common tasks (add field, fix migrations, harden permissions, etc.)</td>
  </tr>
  <tr>
    <td>🔍</td>
    <td><strong>Inspectors</strong> (v0.5.21) – deep model introspection and query plan analysis via <code>aksara inspect models</code> / <code>aksara inspect queries</code>, Studio Inspector tab, and agent context sections</td>
  </tr>
  <tr>
    <td>🔎</td>
    <td><strong>Semantic Search</strong> (v0.5.22) – in-memory TF-IDF search index across models, routes, settings, playbooks, and queries; Studio Spotlight (⌘K), CLI <code>aksara search</code>, and agent context integration</td>
  </tr>
  <tr>
    <td>🤖</td>
    <td><strong>Agentic Workflows</strong> (v0.5.23) – structured step-by-step execution plans from free-text goals; combines diagnostics, search, inspectors, and playbooks into ordered timelines with risk/effort badges; Studio Workflow tab, CLI <code>aksara agent workflow</code>, and Python API</td>
  </tr>
  <tr>
    <td>⚡</td>
    <td><strong>Studio AI Flows</strong> (v0.5.29) – in-context AI actions for Models, Routes, Queries, Migrations, and Diagnostics panels; deterministic prompt packs with risk badges, copy buttons, and CLI parity (<code>aksara ai flows</code>)</td>
  </tr>
  <tr>
    <td>🗺️</td>
    <td><strong>AI Console & Project Graph</strong> (v0.5.31–0.5.32) – natural-language console with intent routing across 8 flow types; full project graph mapping models, routes, queries, migrations, diagnostics, gaps, and events</td>
  </tr>
  <tr>
    <td>🐛</td>
    <td><strong>AI Debugger</strong> (v0.5.33) – automated root-cause analysis: issue clustering, 6 heuristic patterns, confidence-ranked causes, and safe fix suggestions; Studio panel, CLI <code>aksara ai flows debug</code></td>
  </tr>
  <tr>
    <td>🏗️</td>
    <td><strong>AI Architecture Review</strong> (v0.5.34) – automated health scoring (A–F), coupling/schema/API/migration/performance findings with categorised suggestions; Studio panel, CLI <code>aksara ai flows review</code></td>
  </tr>
  <tr>
    <td>📊</td>
    <td><strong>AI Performance Analyzer</strong> (v0.5.35) – detects slow queries, N+1 patterns, query explosions, missing indexes, heavy joins, and route hotspots; penalty-based scoring with recommendations; Studio panel, CLI <code>aksara ai flows performance</code></td>
  </tr>
</table>

---

## Quickstart

Get a running app in 30 seconds:

```bash
pip install aksara

aksara startproject myapp
cd myapp

# Apply migrations & run dev server
aksara migrate
aksara dev
```

Then visit:

| What | URL |
|------|-----|
| **App** | http://127.0.0.1:8000/ |
| **Admin** | http://127.0.0.1:8000/admin/ |
| **Studio** | http://127.0.0.1:8000/studio/ui |
| **API Docs** | http://127.0.0.1:8000/docs |

---

## Your First 10 Minutes with Aksara

New to Aksara? Start here:

**[Your First 10 Minutes with Aksara](https://github.com/nagarjuna-tella/aksara/blob/main/docs/docs/getting-started/ten-minutes.md)**

This hands-on guide walks you from zero to a running app with a model, API, Admin, and Studio.

---

## Patterns & Examples

Aksara ships with real-world patterns and examples:

| Pattern | Use Case | Command |
|---------|----------|---------|
| **Blog** | Posts, comments, publish workflow | `aksara startproject myblog --template blog` |
| **CRM** | Customers, deals, pipeline stages | `aksara startproject mycrm --template crm` |
| **Multitenant** | Tenant-aware SaaS apps | `aksara startproject saas --template multitenant` |
| **AI Providers** | BYO LLM wiring examples | See `examples/ai_providers/` |

Browse: [`examples/`](https://github.com/nagarjuna-tella/aksara/tree/main/examples/) | Docs: [Patterns](https://github.com/nagarjuna-tella/aksara/blob/main/docs/docs/patterns/index.md)

---

## The Aksara Difference

```python
# models.py
from aksara import Model, fields

class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)

# views.py
from aksara.api import ModelViewSet

class PostViewSet(ModelViewSet):
    model = Post
```

**That's it.** You now have:

- `GET /api/posts/` – List all posts (paginated)
- `POST /api/posts/` – Create a post
- `GET /api/posts/{id}/` – Get one post
- `PATCH /api/posts/{id}/` – Update a post
- `DELETE /api/posts/{id}/` – Delete a post
- Plus: Admin UI, Studio inspector, AI tool exposure

---

## Documentation

| Section | Description |
|---------|-------------|
| [Quickstart](docs/docs/quickstart.md) | Build a task manager in 5 minutes |
| [ORM Guide](docs/docs/orm/index.md) | Models, fields, relations, queries |
| [API Guide](docs/docs/api/index.md) | ViewSets, actions, serializers |
| [Admin Guide](docs/docs/admin/index.md) | Admin site customization |
| [Studio Guide](docs/docs/studio/index.md) | Visual inspector & debugging |
| [AI Mode](docs/docs/ai-mode/index.md) | AI tools, context, and provider wiring |
| [CLI Reference](docs/docs/cli/index.md) | All CLI commands |
| [Patterns](docs/docs/patterns/index.md) | Blog, CRM, Multitenant patterns |

---

## Status & Roadmap

Aksara is **pre-1.0** and actively evolving. Current version: **0.5.42**.

See the [Roadmap](https://github.com/nagarjuna-tella/aksara/blob/main/docs/docs/roadmap.md) for what's coming.

**What's stable:**
- ORM, migrations, queries
- ViewSets, serializers, permissions
- Admin, Studio
- CLI commands

**What's evolving:**
- AI Mode APIs and contracts
- Enhanced debugging tools

---

## License

[MIT License](https://github.com/nagarjuna-tella/aksara/blob/main/LICENSE)

---

## Contributing

Contributions welcome! Please:

1. Check existing issues or open a new one
2. Fork the repo and create a feature branch
3. Run tests: `pytest`
4. Submit a pull request

See the codebase for style conventions.

---

## Community

<p>
  <a href="https://pypi.org/project/aksara/"><img src="https://img.shields.io/badge/PyPI-aksara-3775A9?style=flat-square&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://github.com/nagarjuna-tella/aksara"><img src="https://img.shields.io/badge/GitHub-aksara-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
</p>

---

Built with ❤️ by Nagarjuna Tella.
