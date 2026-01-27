# AI Commands

AI-powered CLI commands for development.

---

## Overview

Aksara's AI commands help you:

- **Query data** with natural language
- **Generate code** from descriptions
- **Analyze schemas** for issues
- **Plan complex tasks** automatically

```bash
aksara ai --help
```

---

## ai query

Query your database using natural language.

```bash
aksara ai query "Users who signed up this week"
```

Output:
```
📊 Query: Users who signed up this week
📝 SQL: SELECT * FROM users WHERE created_at >= '2024-01-08'

Found 23 results:

| id       | email              | name     | created_at          |
|----------|-------------------|----------|---------------------|
| abc-123  | john@example.com  | John     | 2024-01-10 10:30:00 |
| def-456  | jane@example.com  | Jane     | 2024-01-09 14:22:00 |
...
```

### Options

| Option | Description |
|--------|-------------|
| `--limit`, `-l` | Max results (default: 20) |
| `--output`, `-o` | Output file (csv, json) |
| `--sql-only` | Show SQL without executing |
| `--dry-run` | Parse query without executing |
| `--no-confirm` | Skip confirmation for updates |

### Examples

```bash
# Export to CSV
aksara ai query "All orders from last month" --output orders.csv

# Just show SQL
aksara ai query "Users with posts" --sql-only

# More results
aksara ai query "All products" --limit 100
```

---

## ai generate

Generate code from natural language descriptions.

### Generate Model

```bash
aksara ai generate model "BlogPost with title, slug, content, author FK, tags M2M"
```

Output:
```python
class BlogPost(Model):
    """A blog post."""
    
    title = fields.StringField(max_length=200)
    slug = fields.StringField(max_length=200, unique=True)
    content = fields.TextField()
    author = fields.ForeignKey("User", on_delete="CASCADE")
    tags = fields.ManyToManyField("Tag", related_name="posts")
    
    class Meta:
        table_name = "blog_posts"
```

### Generate ViewSet

```bash
aksara ai generate viewset BlogPost
```

### Generate Serializer

```bash
aksara ai generate serializer BlogPost
```

### Generate Test

```bash
aksara ai generate test BlogPost --type crud
```

### Generate CRUD

Generate model, serializer, viewset, and tests:

```bash
aksara ai generate crud "Product with name, price, description, category FK"
```

### Options

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Output file |
| `--append` | Append to existing file |
| `--dry-run` | Show without saving |

---

## ai doctor

Analyze your schema for issues and suggest fixes.

```bash
aksara ai doctor
```

Output:
```
🔍 Analyzing schema...

✓ 12 models analyzed
⚠️ 5 issues found

Issues:
  1. [HIGH] Post.author_id has no index (FK without index)
     Fix: Add db_index=True to ForeignKey

  2. [MEDIUM] User.email should be unique
     Fix: Add unique=True to EmailField

  3. [LOW] Comment.created_at missing default
     Fix: Add auto_now_add=True

Run `aksara ai doctor --fix` to auto-fix issues.
```

### Options

| Option | Description |
|--------|-------------|
| `--fix` | Auto-fix issues |
| `--fix-interactive` | Confirm each fix |
| `--min-severity` | Filter by severity |
| `--models` | Check specific models |
| `--output`, `-o` | Save report (json, html) |

### Examples

```bash
# Auto-fix all
aksara ai doctor --fix

# Interactive fixes
aksara ai doctor --fix-interactive

# Only high severity
aksara ai doctor --min-severity high

# Specific models
aksara ai doctor --models User,Post

# Save report
aksara ai doctor --output report.html
```

---

## ai plan

Create a multi-step plan for complex tasks.

```bash
aksara ai plan "Add a commenting system to blog posts"
```

Output:
```
📋 Plan: Add commenting system

Step 1: Create Comment model
  Type: create_model
  File: models.py
  Dependencies: None

Step 2: Create CommentSerializer
  Type: create_serializer
  File: serializers.py
  Dependencies: Step 1

Step 3: Create CommentViewSet
  Type: create_viewset
  File: viewsets.py
  Dependencies: Steps 1, 2

Step 4: Add nested comments to PostSerializer
  Type: modify_file
  File: serializers.py
  Dependencies: Steps 1, 2

Step 5: Generate migration
  Type: create_migration
  Dependencies: Step 1

Step 6: Create tests
  Type: create_test
  File: tests/test_comments.py
  Dependencies: Steps 1-4

Execute plan? [y/N/i(nteractive)]
```

### Options

| Option | Description |
|--------|-------------|
| `--execute` | Execute immediately |
| `--interactive` | Confirm each step |
| `--dry-run` | Preview changes only |
| `--save` | Save plan to file |
| `--load` | Load plan from file |

### Examples

```bash
# Execute immediately
aksara ai plan "Add user profiles" --execute

# Step by step
aksara ai plan "Add ratings" --interactive

# Save for later
aksara ai plan "Add search" --save search-plan.json

# Load and execute
aksara ai plan --load search-plan.json --execute
```

---

## ai agent

Run an AI agent for complex autonomous tasks.

```bash
aksara ai agent "Review the codebase and suggest improvements"
```

Output:
```
🤖 Starting AI agent...

[Thinking] Analyzing codebase structure...
[Action] Reading models.py
[Action] Reading viewsets.py
[Thinking] Found potential issues...

Agent Report:
=============

1. N+1 Query in PostViewSet.list()
   File: viewsets.py:25
   Fix: Add select_related("author")

2. Missing index on Post.created_at
   File: models.py:15
   Fix: Add db_index=True

3. Duplicate code in serializers
   Files: serializers.py:10, serializers.py:45
   Fix: Extract common fields to base class

Would you like me to fix these issues? [y/N]
```

### Options

| Option | Description |
|--------|-------------|
| `--interactive` | Confirm each action |
| `--tools` | Restrict available tools |
| `--timeout` | Max execution time |
| `--max-iterations` | Max think-act cycles |

### Examples

```bash
# Interactive mode
aksara ai agent "Improve test coverage" --interactive

# Read-only analysis
aksara ai agent "Review code" --tools query_records,list_models,read_file

# With timeout
aksara ai agent "Refactor models" --timeout 300
```

---

## ai patch

Modify existing files with AI assistance.

```bash
aksara ai patch models.py "Add phone field to User model"
```

Output:
```
📝 Patch: Add phone field to User model

Preview:
--- models.py (original)
+++ models.py (modified)
@@ -10,6 +10,7 @@
 class User(Model):
     email = fields.EmailField(unique=True)
+    phone = fields.StringField(max_length=20, null=True)
     name = fields.StringField(max_length=100)

Apply patch? [y/N]
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview only |
| `--no-backup` | Don't create backup |
| `--force` | Skip confirmation |

---

## ai ask

Ask questions about your codebase.

```bash
aksara ai ask "How do I add pagination to a ViewSet?"
```

Output:
```
To add pagination to a ViewSet, set the pagination_class:

```python
from aksara.api import ModelViewSet, PageNumberPagination

class PostViewSet(ModelViewSet):
    model = Post
    pagination_class = PageNumberPagination
    page_size = 20
```

Based on your codebase, I see you're already using PageNumberPagination
in UserViewSet (viewsets.py:15). You can follow the same pattern.

Related files:
- viewsets.py:15 (existing pagination example)
- settings.py:23 (default pagination settings)
```

---

## ai config

Configure AI settings.

```bash
aksara ai config --show
```

Output:
```
AI Configuration:
  Provider: openai
  Model: gpt-4
  API Key: sk-**** (configured)
  
Settings:
  Require confirmation: true
  Read-only mode: false
  Audit logging: true
```

### Set Configuration

```bash
aksara ai config set AI_PROVIDER anthropic
aksara ai config set AI_MODEL claude-3-opus
```

---

## Common Patterns

### Generate and Apply

```bash
# Generate model
aksara ai generate model "Comment with text, author, post" > comment.py

# Review and add to models.py
cat comment.py >> models.py

# Generate migration
aksara makemigrations
```

### Analyze and Fix

```bash
# Check for issues
aksara ai doctor

# Fix interactively
aksara ai doctor --fix-interactive

# Verify fixes
aksara test
```

### Query and Export

```bash
# Query data
aksara ai query "Orders over $100 this month" --output big_orders.csv

# Analyze
aksara ai query "Average order value by customer" --output customer_value.json
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AKSARA_AI_API_KEY` | API key for AI provider |
| `AKSARA_AI_PROVIDER` | AI provider (openai, anthropic) |
| `AKSARA_AI_MODEL` | Model to use |

---

## Related Documentation

- [AI Mode Overview](../ai-mode/index.md)
- [Query Engine](../ai-mode/query-engine.md)
- [Codegen](../ai-mode/codegen.md)
- [Schema Doctor](../ai-mode/schema-doctor.md)
- [Safety](../ai-mode/safety.md)
