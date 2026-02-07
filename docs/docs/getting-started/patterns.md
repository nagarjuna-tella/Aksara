# Choosing a Pattern

Aksara offers several ways to start a project. This guide helps you pick the right one.

---

## Quick Decision Guide

| If you want to... | Start with... |
|-------------------|---------------|
| Learn Aksara from scratch | **Blank Project** |
| Build a content-based app | **Blog Pattern** |
| Build internal tools or CRM | **CRM Pattern** |
| Build a SaaS with tenants | **Multitenant Pattern** |
| See AI/LLM wiring examples | **AI Providers Example** |

---

## 1. Blank Project

**Command:**

```bash
aksara startproject myapp
```

**Use when:**

- You know exactly what you're building
- You want full control over the structure
- You're following a tutorial or learning

**What you get:**

- A minimal app with one example model
- Pre-configured Admin and Studio
- Ready-to-use project structure

**Next steps:**

- Follow [Your First 10 Minutes](ten-minutes.md)
- Or jump to [Quickstart](../quickstart.md)

---

## 2. Blog Pattern

**Command:**

```bash
aksara startproject myblog --template blog
```

**Use when:**

- You're building content-focused apps
- You want to see CRUD, list/detail views, and workflows
- You need posts, comments, tags, and publish states

**What you get:**

- `Post` model with title, content, slug, published state
- `Comment` model linked to posts
- Full ViewSets for both
- Admin registrations
- Sample queries and workflows

**Key concepts demonstrated:**

- ForeignKey relationships
- Query filtering and ordering
- Boolean workflow fields (draft → published)
- Slug generation

**Docs:** [Blog Pattern](../patterns/blog.md)

---

## 3. CRM Pattern

**Command:**

```bash
aksara startproject mycrm --template crm
```

**Use when:**

- You're building internal tools or dashboards
- You need customers, deals, and pipeline stages
- You want to see reporting patterns

**What you get:**

- `Customer` model
- `Deal` model with stage tracking
- `Pipeline` and `Stage` models
- ViewSets with custom actions
- Admin with list filters

**Key concepts demonstrated:**

- Multiple related models
- Enum-like stage fields
- Custom ViewSet actions (e.g., close deal)
- Aggregation queries

**Docs:** [CRM Pattern](../patterns/crm.md)

---

## 4. Multitenant Pattern

**Command:**

```bash
aksara startproject saas --template multitenant
```

**Use when:**

- You're building a SaaS application
- Each customer (tenant) needs isolated data
- You need tenant-aware middleware and queries

**What you get:**

- `Tenant` model
- `TenantUser` model
- Tenant middleware for request scoping
- Base model class with tenant FK
- Example tenant-aware ViewSets

**Key concepts demonstrated:**

- Middleware for tenant resolution
- Automatic query scoping by tenant
- Tenant-aware model base class
- User-tenant relationships

**Docs:** [Multitenant Pattern](../patterns/multitenant.md)

---

## 5. AI Providers Example

**Location:** `examples/ai_providers/`

**Note:** This is not a `--template` option. It's an example package you can copy.

**Use when:**

- You want to wire Aksara's AI contracts to real providers
- You're integrating OpenAI, Azure, or Anthropic
- You need to see the adapter pattern in action

**What you get:**

- Protocol-based LLM client adapters
- Environment-based configuration
- Prompt building from route hints
- Example AI-powered ViewSet actions

**How to use:**

```bash
# Copy examples to your project
aksara ai examples -o ./ai_adapters

# Or browse them directly
ls examples/ai_providers/
```

**Key concepts demonstrated:**

- Soft SDK imports (no hard dependencies)
- Protocol-based adapter pattern
- Environment variable configuration
- Using AI route hints in prompts

**Docs:** [Bring Your Own LLM](../ai-mode/bring-your-own-llm.md)

---

## Comparison Table

| Feature | Blank | Blog | CRM | Multitenant |
|---------|-------|------|-----|-------------|
| Models included | 1 example | 2+ | 4+ | 3+ |
| Relationships | None | ForeignKey | Multiple FKs | FK + Middleware |
| Admin setup | Basic | Full | Full | Full |
| Middleware | None | None | None | Tenant resolution |
| Best for | Learning | Content apps | Internal tools | SaaS |

---

## Next Steps

After creating your project:

1. **Configure your database** – Edit `.env` with your DATABASE_URL
2. **Run migrations** – `aksara migrate`
3. **Start the server** – `aksara dev`
4. **Explore** – Visit `/admin/` and `/studio/ui`

Need more guidance? Start with [Your First 10 Minutes](ten-minutes.md).
