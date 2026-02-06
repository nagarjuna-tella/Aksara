# Tutorial: AI Integration

Add AI-powered features to your Aksara application, letting users query data using natural language.

---

## What You'll Build

By the end of this tutorial, you'll add:

- ✅ Natural language database queries ("Show me all posts from last week")
- ✅ AI-powered API endpoints
- ✅ Safe query execution with read-only mode
- ✅ AI-generated insights

**Time:** ~30 minutes

**Difficulty:** Intermediate

---

## What is AI Mode?

AI Mode lets you interact with your application using natural language instead of code.

**Without AI Mode:**
```python
posts = await Post.objects.filter(
    is_published=True,
    created_at__gte=last_week
).order_by("-view_count")[:10]
```

**With AI Mode:**
```
"Show me the top 10 published posts from this week"
```

Aksara converts natural language to database queries automatically.

---

## Prerequisites

- An existing Aksara project (or complete the [Blog API tutorial](blog-api.md) first)
- An API key from OpenAI or Anthropic
- Aksara 0.4.0 or higher

---

## Step 1: Install AI Dependencies

```bash
pip install aksara[ai]
```

This installs the AI module and required dependencies.

---

## Step 2: Configure AI Provider

### Get an API Key

You need an API key from one of these providers:

| Provider | Get Key | Model |
|----------|---------|-------|
| OpenAI | [platform.openai.com](https://platform.openai.com) | GPT-4 |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | Claude |

### Add to Settings

```python
# settings.py
import os

AKSARA = {
    # ... your existing settings ...
    
    # Enable AI features
    "AI_MODE": True,
    
    # Choose your provider
    "AI_PROVIDER": "openai",  # or "anthropic"
    
    # API key from environment variable
    "AI_API_KEY": os.getenv("OPENAI_API_KEY"),
    
    # Which model to use
    "AI_MODEL": "gpt-4",  # or "claude-3-opus" for Anthropic
}
```

### Set Your API Key

```bash
# Add to your .env file
OPENAI_API_KEY=sk-your-key-here

# Or set in terminal
export OPENAI_API_KEY=sk-your-key-here
```

---

## Step 3: Use the CLI for Queries

The simplest way to use AI Mode is through the command line.

### Basic Queries

```bash
# Simple query
aksara ai query "Show all published posts"

# With conditions
aksara ai query "Posts by user alice@example.com"

# Complex queries
aksara ai query "Top 5 posts with the most comments this month"
```

### What Happens

```
┌─────────────────────────────────────────────────────────────┐
│  Your Query: "Posts by Alice from this week"                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  AI understands:                                             │
│  - Model: Post                                               │
│  - Filter: author.name = "Alice"                            │
│  - Filter: created_at >= 7 days ago                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Generated Query:                                            │
│  Post.objects.filter(                                        │
│      author__name="Alice",                                   │
│      created_at__gte=seven_days_ago                          │
│  )                                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Results: [Post 1, Post 2, Post 3]                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 4: Add AI Query Endpoint

Let your users query data through the API.

### Create the ViewSet

```python
# myapp/views.py
from aksara.api import ViewSet, action
from aksara.permissions import IsAuthenticated
from aksara.ai import QueryEngine

class AIQueryViewSet(ViewSet):
    """
    AI-powered query endpoint.
    
    Lets users ask questions in natural language.
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["POST"])
    async def query(self, request):
        """
        Execute a natural language query.
        
        POST /api/ai/query/
        Body: {"query": "Show me all posts from this week"}
        
        Returns: The query results and the generated SQL
        """
        query_text = request.data.get("query")
        
        if not query_text:
            return {"error": "Query is required"}, 400
        
        # Create query engine in read-only mode (safe!)
        engine = QueryEngine(read_only=True)
        
        try:
            result = await engine.query(query_text)
            
            return {
                "data": result.data,      # The actual results
                "count": result.count,     # How many results
                "sql": result.sql,         # The generated SQL (for transparency)
            }
        except Exception as e:
            return {"error": str(e)}, 400
```

### Register the Route

```python
# myapp/urls.py
from aksara.api import Router
from .views import AIQueryViewSet

router = Router()
router.register("ai", AIQueryViewSet, basename="ai")
```

### Test It

```bash
curl -X POST http://localhost:8000/api/ai/query/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "Posts published this week with at least 3 comments"}'
```

**Response:**
```json
{
  "data": [
    {"id": "...", "title": "My Post", "comment_count": 5},
    {"id": "...", "title": "Another Post", "comment_count": 3}
  ],
  "count": 2,
  "sql": "SELECT * FROM posts WHERE published_at >= '2024-01-08' AND comment_count >= 3"
}
```

---

## Step 5: Use QueryEngine in Python

### Basic Usage

```python
from aksara.ai import QueryEngine

async def get_report():
    engine = QueryEngine()
    
    # Query data naturally
    result = await engine.query("Active users who logged in this week")
    
    return result.data
```

### Multiple Queries

```python
async def generate_dashboard():
    engine = QueryEngine()
    
    # Run multiple queries
    active_users = await engine.query(
        "Users who logged in within the last 30 days"
    )
    
    top_posts = await engine.query(
        "Top 10 posts by view count this month"
    )
    
    engagement = await engine.query(
        "Average comments per post by author"
    )
    
    return {
        "active_users": len(active_users.data),
        "top_posts": top_posts.data,
        "engagement": engagement.data,
    }
```

### With Context

Provide additional context for better results:

```python
result = await engine.query(
    "Posts by this user",
    context={
        "user_id": request.user.id,
        "tenant_id": request.tenant.id,
    }
)
```

---

## Step 6: AI Safety Features

### Read-Only Mode

Prevent AI from modifying data:

```python
# Safe mode - can only read, not write
engine = QueryEngine(read_only=True)

# This will fail:
await engine.query("Delete all posts")  # Error!
```

### Audit Logging

Track all AI queries:

```python
# settings.py
AKSARA = {
    # ... other settings ...
    
    "AI_SAFETY": {
        "read_only_mode": True,      # Only allow reads
        "audit_log": True,           # Log all queries
        "max_results": 1000,         # Limit result size
        "timeout_seconds": 30,       # Query timeout
    }
}
```

### Model Restrictions

Limit which models AI can access:

```python
engine = QueryEngine(
    allowed_models=["Post", "Comment"],  # Only these models
    denied_models=["User", "Payment"],   # Never these models
)
```

---

## Step 7: AI-Powered Insights

Generate automatic insights from your data.

### Create Insights Endpoint

```python
# myapp/views.py
from aksara.ai import QueryEngine, InsightGenerator

class InsightsViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["GET"])
    async def dashboard(self, request):
        """
        Generate AI-powered dashboard insights.
        
        GET /api/insights/dashboard/
        """
        engine = QueryEngine(read_only=True)
        
        # Gather data
        total_users = await engine.query("Count of all users")
        active_users = await engine.query("Count of users active this week")
        total_posts = await engine.query("Count of published posts")
        top_authors = await engine.query("Top 5 authors by post count")
        
        # Generate insights
        insights = InsightGenerator()
        summary = await insights.generate(
            data={
                "total_users": total_users.data,
                "active_users": active_users.data,
                "total_posts": total_posts.data,
                "top_authors": top_authors.data,
            },
            prompt="Generate a brief summary of the blog's performance"
        )
        
        return {
            "metrics": {
                "total_users": total_users.data,
                "active_users": active_users.data,
                "total_posts": total_posts.data,
            },
            "top_authors": top_authors.data,
            "ai_summary": summary,
        }
```

---

## Step 8: Export App Context for AI

Make your entire app understandable to external AI systems.

```python
from aksara.ai import build_full_ai_context

# Export structured context
context = await build_full_ai_context(app)

# This includes:
# - All models and their fields
# - All API endpoints
# - Field descriptions and types
# - Relationships between models
```

This is useful for:

- Connecting to external AI agents
- Generating documentation
- Building AI assistants that understand your app

---

## Query Examples

Here are example queries that work with the Blog API:

| Natural Language | What It Does |
|-----------------|--------------|
| "All posts" | List all posts |
| "Published posts" | Posts where is_published=True |
| "Posts by Alice" | Posts where author.name="Alice" |
| "Posts from this week" | Posts created in last 7 days |
| "Top 10 posts by views" | Order by view_count DESC, limit 10 |
| "Posts with no comments" | Posts where comment_count=0 |
| "Authors with most posts" | Group by author, count posts |
| "Average views per post" | Aggregate average of view_count |

---

## Troubleshooting

### "API key not found"

**Problem:** AI features won't work without an API key.

**Solution:** Set the environment variable:
```bash
export OPENAI_API_KEY=sk-your-key-here
```

### "Query too complex"

**Problem:** AI can't understand the query.

**Solution:** Simplify the query or break it into parts:
```bash
# Instead of:
"Posts by verified authors in tech category with 5+ comments from last month"

# Try:
"Posts in tech category from last month"
```

### "Model not found"

**Problem:** AI doesn't know about a model.

**Solution:** Make sure the model is registered and has `ai_description`:
```python
class Post(Model):
    """A blog post."""  # This docstring helps AI understand
    
    title = fields.String(
        max_length=200,
        ai_description="The title of the blog post"  # Field description
    )
```

---

## Best Practices

### 1. Always Use Read-Only Mode in Production

```python
engine = QueryEngine(read_only=True)  # Safe!
```

### 2. Add Descriptions to Models

```python
class Post(Model):
    """
    A blog post that can be published.
    
    Posts belong to an author and can have multiple tags.
    """
    title = fields.String(
        max_length=200,
        ai_description="The post's headline"
    )
```

### 3. Limit Result Sizes

```python
engine = QueryEngine(max_results=100)
```

### 4. Log All AI Queries

For debugging and audit trails:

```python
AKSARA = {
    "AI_SAFETY": {
        "audit_log": True,
    }
}
```

---

## Next Steps

- Explore the [AI Mode documentation](../ai-mode/index.md) for advanced features
- Learn about [AI schema descriptions](../ai-mode/schema.md)
- Set up [AI safety guardrails](../ai-mode/safety.md)

---

## Related Documentation

- [AI Mode Overview](../ai-mode/index.md)
- [Query Engine](../ai-mode/query-engine.md)
- [AI Safety](../ai-mode/safety.md)
- [Models](../orm/models.md) — Adding AI descriptions to models
