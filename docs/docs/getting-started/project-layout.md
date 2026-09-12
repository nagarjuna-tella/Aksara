# Project layout

The basic scaffold is a starting shell. Its model, serializer, ViewSet and Admin
examples are commented out; generating files does not create a working domain
API. The [first-project tutorial](first-project.md) replaces those stubs with a
complete protected application.

## Basic project

```bash
aksara startproject myproject
```

This generates the following files:

```text
myproject/
├── main.py
├── settings.py
├── pyproject.toml
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .editorconfig
├── README.md
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── admin.py
├── migrations/
│   └── __init__.py
└── static/
    └── welcome.html
```

| File | Responsibility |
| --- | --- |
| `settings.py` | Loads local environment, configures the installed-app list and exposes the global settings object. |
| `main.py` | Imports application modules, constructs Aksara, registers routes and provides the welcome/health endpoints. |
| `app/models.py` | Declares persistent models; schema changes still require reviewed migrations. |
| `app/serializers.py` | Defines input/output validation and representation where needed. |
| `app/views.py` | Defines ViewSets and their permissions; creation does not supply an identity service. |
| `app/urls.py` | Calls explicit route registration. |
| `app/admin.py` | Registers application models for the Admin interface. |
| `migrations/` | Holds the versioned application schema changes. |
| `.env` | Local configuration and secrets; keep it out of version control. |
| `.env.example` | Configuration template; replace example credentials locally. |
| `static/welcome.html` | Welcome-page content read by the entry point. |

The scaffold does not generate a `tests/` directory. Create application tests
when following the tutorial. A templates directory or a mounted static directory
is also application-owned; the welcome file alone is not a general static mount.

The bundled `blog`, `crm` and `multitenant` templates have flat modules and
different settings. This tree describes **basic only**. See
[template-specific setup](patterns.md) before using a domain copy.

## Add another application module

From the project directory:

```bash
aksara startapp inventory
```

The command creates five files:

```text
inventory/
├── __init__.py
├── models.py
├── views.py
├── serializers.py
└── admin.py
```

It does not create `urls.py`, modify settings or register new routes for you.
Older CLI versions suggest `AksaraSettings(apps=...)`; that is not the current
global configuration API. In a generated basic project, add `"inventory"` to
`INSTALLED_APPS` in `settings.py`; the existing `configure(installed_apps=...)`
call applies that list. In other applications, configure the appropriate full
module path through the [settings API](../reference/settings-reference.md).

After defining models and ViewSets, use explicit
[route registration](../api/routing.md) and review generated migrations. Do not
assume there is an importable `inventory.urls.register_routes` function just
because `startapp` succeeded. Model class names must remain distinct across
loaded modules; see the [model-discovery limitation](../orm/models.md).

## Keep one coherent application structure

Larger projects may organize Python packages under a directory such as `apps/`.
Ensure those packages are importable, configure their full module paths and
register their routes deliberately. A directory convention does not create a
separate migration namespace or configure database routing.

Use one reviewed [migration workflow](../orm/migrations.md) for the application.
For tests, follow the tutorial's fixtures and the
[testing guide](../advanced/testing.md); no generated helper automatically
provides rollback isolation for every HTTP request.

Authentication and tenant membership are application code. Put their adapters
where they can be tested and register them explicitly, as the tutorial does.
Introduce [ordinary tasks](../tutorials/ticket-desk-reports.md),
[durable actions](../tutorials/ticket-desk-durable.md) and
[optional MCP](../tutorials/ticket-desk-mcp.md) when needed. File generation does
not enable or supervise those services.
