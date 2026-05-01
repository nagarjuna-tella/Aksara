# Getting Started

Welcome to Aksara! This guide will help you build your first web API from scratch.

---

## What is Aksara?

**Aksara** is a Python framework for building web APIs that talk to databases. Think of it as the "backend" part of a web application — the server that stores and retrieves data.

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Frontend      │ ───► │    Aksara       │ ───► │   PostgreSQL    │
│  (Your app,     │      │  (Your API)     │      │   (Database)    │
│   website)      │ ◄─── │                 │ ◄─── │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        User                  Backend              Where data lives
```

**What Aksara does for you:**

| Problem | How Aksara Solves It |
|---------|---------------------|
| "I need to store data" | **Models** define your database tables |
| "I need to query data" | **QuerySets** let you search without writing SQL |
| "I need an API" | **ViewSets** create REST endpoints automatically |
| "I need to protect data" | **Permissions** control who can access what |
| "I need an admin panel" | **Admin** gives you a dashboard to manage data |
| "I want AI agents to use my API" | **MCP Tools** auto-generated from your models at `/ai/tools/mcp` |
| "I need to debug my app" | **Doctor & Fix Plans** diagnose issues and print the remediation path |

---

## Why Aksara?

Aksara is designed for Python developers who want to:

✅ **Build fast** — Get a working API in minutes, not hours  
✅ **Use modern Python** — Async/await, type hints, Python 3.11+  
✅ **Stay productive** — Less boilerplate, more features  
✅ **Scale confidently** — Built for PostgreSQL's performance  
✅ **Work with AI** — Built-in AI agent integration  

---

## What You'll Learn

This section walks you through building your first Aksara application:

### 1. [Installation](installation.md)

Install Aksara and set up your development environment.

**What you'll do:** Run `pip install aksara` and verify it works.

### 2. [Project Layout](project-layout.md)

Understand how Aksara projects are organized.

**What you'll learn:** Where to put your models, views, and settings.

### 3. [Settings](settings.md)

Configure your application's behavior.

**What you'll learn:** How to connect to your database and enable features.

### 4. [First App](first-app.md)

Build your first complete application from scratch.

**What you'll do:** Create a "Tasks" API with create, read, update, delete.

### 5. [Database Setup](database-setup.md)

Connect Aksara to PostgreSQL.

**What you'll do:** Set up a database and run migrations.

### 6. [Running Your App](running-your-app.md)

Start your development server and test your API.

**What you'll do:** Run your app and make your first API calls.

### After Getting Started

Once your app is running, explore the built-in tooling:

- **[Studio](../studio/index.md)** — Visual dashboard at `/studio/ui` with an AI Console for natural-language queries
- **[AI Mode](../ai-mode/index.md)** — MCP tool export, AI Debugger, Architecture Review, Performance Analyzer
- **[Diagnostics](../diagnostics.md)** — `aksara doctor` checks app health; `aksara doctor fix-plan` prints the fix sequence

---

## Prerequisites

Before starting, you need:

| Requirement | Why You Need It |
|-------------|-----------------|
| **Python 3.11+** | Aksara uses modern Python features |
| **PostgreSQL 13+** | Where your data will be stored |
| **pip or uv** | To install Python packages |

### Check Your Python Version

```bash
python --version
# Should output: Python 3.11.x or higher
```

### Check If PostgreSQL Is Running

```bash
# macOS (if installed via Homebrew)
brew services list | grep postgresql

# Linux
sudo systemctl status postgresql

# Or just try to connect
psql --version
```

**Don't have PostgreSQL?** The [Database Setup](database-setup.md) guide shows you how to install it.

---

## How Aksara Works (The Big Picture)

When a request comes to your Aksara API, here's what happens:

```
1. REQUEST ARRIVES
   ↓
   POST /api/tasks/ {"title": "Buy milk"}
   
2. VIEWSET HANDLES IT
   ↓
   TaskViewSet.create() is called
   
3. SERIALIZER VALIDATES
   ↓
   TaskSerializer checks the data is valid
   
4. MODEL SAVES TO DATABASE
   ↓
   Task.objects.create(title="Buy milk")
   
5. RESPONSE SENT
   ↓
   {"id": "abc123", "title": "Buy milk", "completed": false}
```

Each piece has a specific job:

| Component | Job | File Location |
|-----------|-----|---------------|
| **Model** | Define what data looks like | `app/models.py` |
| **Serializer** | Convert between Python and JSON | `app/serializers.py` |
| **ViewSet** | Handle API requests | `app/views.py` |
| **URL Config** | Register ViewSets with the app | `app/urls.py` |

---

## Ready to Start?

Let's go! Begin with [Installation](installation.md) →

---

## Quick Reference

Already familiar with web frameworks? Here's the quick version:

```bash
# Install
pip install aksara

# Create project
aksara startproject myproject
cd myproject

# Set up the database
aksara dbsetup

# Create migrations
aksara makemigrations

# Run migrations
aksara migrate

# Start development server
aksara dev
```

Then visit `http://localhost:8000/docs` for interactive API documentation.

---

## Getting Help

Stuck? Here's where to find help:

- **Documentation** — You're reading it!
- **API Reference** — Detailed API docs at `/api/`
- **GitHub Issues** — Report bugs or request features
- **Changelog** — See what's new in each version

---

## Next Steps

After completing this guide, explore:

- **[ORM Guide](../orm/index.md)** — Deep dive into models and queries
- **[API Guide](../api/index.md)** — Build advanced REST APIs
- **[Admin Guide](../admin/index.md)** — Customize your admin dashboard
- **[AI Mode](../ai-mode/index.md)** — Enable AI agent integration
