# Tutorials

Step-by-step guides for building real applications.

---

## Overview

These tutorials walk you through building complete applications:

| Tutorial | What You'll Build | Time |
|----------|------------------|------|
| [Blog API](blog-api.md) | REST API with posts, comments, tags | 30 min |
| [Multi-Tenant App](multi-tenant.md) | SaaS application with tenant isolation | 45 min |
| [AI Integration](ai-integration.md) | Natural language features | 30 min |
| [Deployment](deployment.md) | Production deployment | 20 min |

---

## Prerequisites

Before starting, ensure you have:

- Python 3.10+
- PostgreSQL (recommended) or SQLite
- Basic Python knowledge
- Familiarity with REST APIs

---

## Getting Started

Each tutorial builds on concepts from the previous one, but can also be followed independently.

### Recommended Order

1. **[Blog API](blog-api.md)** — Learn the fundamentals
   - Models and fields
   - ViewSets and serializers
   - Relationships
   - Authentication

2. **[Multi-Tenant App](multi-tenant.md)** — Advanced patterns
   - Tenant middleware
   - Database isolation
   - Per-tenant configuration

3. **[AI Integration](ai-integration.md)** — AI features
   - Natural language queries
   - Code generation
   - AI-powered debugging

4. **[Deployment](deployment.md)** — Go to production
   - Docker setup
   - Database migrations
   - Environment configuration

---

## Tutorial Format

Each tutorial follows this structure:

1. **Overview** — What you'll build
2. **Setup** — Project initialization
3. **Step-by-step instructions** — Building the feature
4. **Testing** — Verifying it works
5. **Next steps** — Where to go from here

---

## Sample Code

Complete code for each tutorial is available:

```bash
# Clone the examples repository
git clone https://github.com/aksara/examples.git

# Navigate to a tutorial
cd examples/blog-api

# Install dependencies
pip install -e .

# Run
aksara runserver
```

---

## Quick Links

### Blog API Tutorial

Build a complete blog API with:
- User authentication
- Posts, comments, tags
- Search and filtering
- Pagination

→ [Start Blog API Tutorial](blog-api.md)

### Multi-Tenant Tutorial

Build a SaaS application with:
- Tenant isolation
- Subdomain routing
- Per-tenant data
- Admin interface

→ [Start Multi-Tenant Tutorial](multi-tenant.md)

### AI Integration Tutorial

Add AI features to your app:
- Natural language queries
- AI-generated code
- Smart debugging

→ [Start AI Tutorial](ai-integration.md)

### Deployment Tutorial

Deploy to production:
- Docker configuration
- Environment setup
- Database migrations
- Monitoring

→ [Start Deployment Tutorial](deployment.md)

---

## Need Help?

- Check the [documentation](../index.md)
- Read the [API reference](../reference/api-reference.md)
- Ask questions on [GitHub Discussions](https://github.com/aksara/aksara/discussions)

---

## Related Documentation

- [Getting Started](../getting-started/index.md)
- [ORM Guide](../orm/index.md)
- [API Guide](../api/index.md)
