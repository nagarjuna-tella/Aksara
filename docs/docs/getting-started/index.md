# Getting Started

Welcome to Vidyut! This section will guide you through setting up your development environment and creating your first application.

---

## Overview

Vidyut is designed to get you productive quickly while maintaining the flexibility to scale to complex applications. In this guide, you'll learn:

1. **[Installation](installation.md)** — Install Vidyut and its dependencies
2. **[Project Layout](project-layout.md)** — Understand the recommended project structure
3. **[Settings](settings.md)** — Configure your application
4. **[First App](first-app.md)** — Build your first Vidyut application
5. **[Database Setup](database-setup.md)** — Connect to PostgreSQL
6. **[Running Your App](running-your-app.md)** — Development and production deployment

---

## Prerequisites

Before starting with Vidyut, ensure you have:

| Requirement | Minimum Version | Recommended |
|-------------|-----------------|-------------|
| Python | 3.11 | 3.12+ |
| PostgreSQL | 13 | 15+ |
| pip/uv | Latest | Latest |

Vidyut is **PostgreSQL-only** by design. This allows us to leverage PostgreSQL-specific features like:

- UUID primary keys with `gen_random_uuid()`
- JSON/JSONB columns
- Advanced indexing
- Efficient connection pooling via `asyncpg`

---

## Quick Links

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Get Vidyut installed in your environment.

    [:octicons-arrow-right-24: Install Vidyut](installation.md)

-   :material-folder-outline:{ .lg .middle } **Project Layout**

    ---

    Learn the recommended directory structure.

    [:octicons-arrow-right-24: Project Structure](project-layout.md)

-   :material-cog:{ .lg .middle } **Settings**

    ---

    Configure database, debug mode, and more.

    [:octicons-arrow-right-24: Configuration](settings.md)

-   :material-rocket-launch:{ .lg .middle } **First App**

    ---

    Create your first Vidyut application.

    [:octicons-arrow-right-24: Build Your App](first-app.md)

</div>

---

## Architecture Overview

Vidyut applications follow a layered architecture:

```
┌─────────────────────────────────────────────────────┐
│                    HTTP Layer                        │
│              (FastAPI / Starlette)                   │
├─────────────────────────────────────────────────────┤
│                   API Layer                          │
│     (ViewSets, Actions, Serializers, Permissions)    │
├─────────────────────────────────────────────────────┤
│                   ORM Layer                          │
│        (Models, QuerySets, Managers, Relations)      │
├─────────────────────────────────────────────────────┤
│                 Database Layer                       │
│           (asyncpg, Connection Pool)                 │
├─────────────────────────────────────────────────────┤
│                  PostgreSQL                          │
└─────────────────────────────────────────────────────┘
```

**AI Mode** integrates across all layers, providing:

- **Tools** — Auto-discovered from ViewSets
- **Context Engine** — Full app state as structured JSON
- **Query Engine** — Natural language to database queries
- **Patch Engine** — Safe code modifications
- **Agent Runtime** — Coordination for external AI agents

---

## Next Steps

Start with [Installation](installation.md) to get Vidyut set up on your system.
