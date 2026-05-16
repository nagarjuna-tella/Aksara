# Tutorials

Step-by-step guides for building real applications with Aksara.

---

## What Are These Tutorials?

These tutorials walk you through building complete, working applications. Each tutorial teaches you new concepts while building something useful.

**What you'll learn:**

- How to structure an Aksara project
- How to define data models
- How to create API endpoints
- How to add authentication
- How to deploy to production

---

## Available Tutorials

| Tutorial | What You'll Build | Time | Difficulty |
|----------|------------------|------|------------|
| [Blog API](blog-api.md) | REST API with posts, comments, tags | 30 min | Beginner |
| [Multi-Tenant App](multi-tenant.md) | SaaS application with tenant isolation | 45 min | Intermediate |
| [AI Integration](ai-integration.md) | Natural language features | 30 min | Intermediate |
| [Deployment](deployment.md) | Production deployment | 20 min | Beginner |

---

## Before You Start

### Prerequisites

| Requirement | Minimum | How to Check |
|-------------|---------|--------------|
| Python | 3.11+ | `python --version` |
| PostgreSQL | 13+ | `psql --version` |
| Aksara | Latest | `aksara --version` |

### Basic Knowledge

You should be comfortable with:

- **Python basics** — variables, functions, classes
- **Command line** — running commands in a terminal
- **APIs** — what REST APIs are (we'll teach the rest!)

**Don't worry if you haven't used Django or similar frameworks** — these tutorials explain everything from scratch.

---

## Recommended Path

### For Beginners

Start with the **Blog API** tutorial. It covers all the fundamentals:

1. **[Blog API](blog-api.md)** — Learn core concepts
   - Creating models (your data structure)
   - Creating ViewSets (your API endpoints)
   - Adding authentication (user login)
   - Testing your API

### For Experienced Developers

If you're familiar with web frameworks, you can jump to:

- **[Deployment](deployment.md)** — Get your app running in production
- **[AI Integration](ai-integration.md)** — Add AI-powered features

### For SaaS Builders

If you're building a multi-tenant SaaS:

- **[Multi-Tenant App](multi-tenant.md)** — Tenant isolation and subdomain routing

---

## Tutorial Format

Each tutorial follows this structure:

### 1. Overview
What you'll build and why it's useful.

### 2. Setup
Creating the project and installing dependencies.

### 3. Step-by-Step Instructions
Building the feature with code examples and explanations.

### 4. Testing
Verifying everything works.

### 5. Next Steps
Ideas for extending what you built.

---

## Quick Start

Want to dive right in? Here's how to start the Blog API tutorial:

```bash
# Install Aksara
pip install aksara-framework

# Create a new project
aksara startproject blog_api
cd blog_api

# Now follow the Blog API tutorial →
```

[Start the Blog API Tutorial →](blog-api.md)

---

## Getting Help

**Stuck on a tutorial?** Here's what to do:

1. **Check your code** — Typos are the #1 cause of errors
2. **Check your database** — Is PostgreSQL running?
3. **Check the error message** — Aksara provides helpful error details
4. **Check the docs** — The [ORM](../orm/index.md) and [API](../api/index.md) docs have more details

---

## Sample Code

Complete code for each tutorial is available on GitHub:

```bash
# Clone the examples repository
git clone https://github.com/aksara/examples.git

# Navigate to a tutorial
cd examples/blog-api

# Install and run
pip install -e .
aksara migrate
aksara dev
```
