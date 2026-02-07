# ⚡ Aksara – Async Postgres-first Web Framework

Aksara is a modern async web framework that combines:

- 🗄️ A typed ORM for PostgreSQL
- 🧩 A FastAPI-compatible router
- 🕹️ A built-in Admin
- 🧠 An AI-aware Studio & contracts layer

Built for teams that want **fast CRUD**, **strong DX**, and **LLM-ready backends**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-2500%2B%20passing-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-0.5.15-blue.svg)]()

---

## ✨ Features at a Glance

- 🚀 **Async everything** – built on async Postgres drivers (asyncpg)
- 🗄️ **Postgres-first ORM** – models, migrations, typed fields, relations
- 🧱 **Admin included** – browse and edit data without extra setup
- 🧪 **Studio** – inspector for models, routes, migrations, runtime, and DB queries
- 🧠 **AI contracts** – JSON schemas, provider profiles, and route hints for LLMs
- 🧰 **CLI & patterns** – start projects with blog, CRM, multitenant, and AI examples

---

## ⚡ Quickstart

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

## 🧭 Your First 10 Minutes with Aksara

New to Aksara? Start here:

👉 **[Your First 10 Minutes with Aksara](docs/docs/getting-started/ten-minutes.md)**

This hands-on guide walks you from zero to a running app with a model, API, Admin, and Studio.

---

## 🧱 Patterns & Examples

Aksara ships with real-world patterns and examples:

| Pattern | Use Case | Command |
|---------|----------|---------|
| **Blog** | Posts, comments, publish workflow | `aksara startproject myblog --template blog` |
| **CRM** | Customers, deals, pipeline stages | `aksara startproject mycrm --template crm` |
| **Multitenant** | Tenant-aware SaaS apps | `aksara startproject saas --template multitenant` |
| **AI Providers** | BYO LLM wiring examples | See `examples/ai_providers/` |

📂 Browse: [`examples/`](examples/) | 📖 Docs: [Patterns](docs/docs/patterns/index.md)

---

## 🎯 The Aksara Difference

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

## 📚 Documentation

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

## 🛠️ Status & Roadmap

Aksara is **pre-1.0** and actively evolving. Current version: **0.5.15**.

See the [Roadmap](docs/docs/roadmap.md) for what's coming.

**What's stable:**
- ORM, migrations, queries
- ViewSets, serializers, permissions
- Admin, Studio
- CLI commands

**What's evolving:**
- AI Mode APIs and contracts
- Enhanced debugging tools

---

## 📄 License

[MIT License](LICENSE)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Check existing issues or open a new one
2. Fork the repo and create a feature branch
3. Run tests: `pytest`
4. Submit a pull request

See the codebase for style conventions.

---

## 💬 Community

- 📦 [PyPI](https://pypi.org/project/aksara/)
- 🐙 [GitHub](https://github.com/aksara-framework/aksara)

---

Built with ❤️ by the Aksara team.
