# Tutorial: AI Integration

Add AI-powered features to your Aksara application.

---

## What You'll Build

Enhance your application with AI features:

- Natural language database queries
- AI-generated API endpoints
- Smart code suggestions
- Automated testing

**Time:** ~30 minutes

---

## Prerequisites

- Existing Aksara project (or complete the Blog API tutorial first)
- OpenAI API key or Anthropic API key
- Aksara 0.4.0+

---

## Setup

### Install AI Dependencies

```bash
pip install aksara[ai]
```

### Configure AI Provider

```python
# settings.py
import os

AKSARA = {
    # ... existing settings ...
    
    # AI Mode
    "AI_MODE": True,
    "AI_PROVIDER": "openai",  # or "anthropic"
    "AI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "AI_MODEL": "gpt-4",
}
```

### Set API Key

```bash
export OPENAI_API_KEY=sk-your-key-here
```

---

## Part 1: Natural Language Queries

### CLI Queries

Query your data with natural language:

```bash
# Basic query
aksara ai query "Show all published posts"

# Complex query
aksara ai query "Posts by John that have more than 5 comments"

# Aggregations
aksara ai query "Average number of comments per post"

# Time-based
aksara ai query "Users who signed up this week"
```

### Python API

```python
# app/reports.py
from aksara.ai import QueryEngine

async def generate_report():
    engine = QueryEngine()
    
    # Query data naturally
    active_users = await engine.query(
        "Active users who logged in within the last 30 days"
    )
    
    top_posts = await engine.query(
        "Top 10 posts by view count this month"
    )
    
    engagement = await engine.query(
        "Average comments per post by author"
    )
    
    return {
        "active_users": active_users.data,
        "top_posts": top_posts.data,
        "engagement": engagement.data,
    }
```

### Create a Query Endpoint

```python
# app/viewsets.py
from aksara.api import ViewSet, action
from aksara.api.permissions import IsAuthenticated
from aksara.ai import QueryEngine

class AIViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["post"])
    async def query(self, request):
        """Execute natural language query."""
        query_text = request.data.get("query")
        
        if not query_text:
            return {"error": "Query is required"}, 400
        
        engine = QueryEngine(read_only=True)  # Safe mode
        
        try:
            result = await engine.query(query_text)
            return {
                "data": result.data,
                "count": result.count,
                "sql": result.sql,  # Show generated SQL
            }
        except Exception as e:
            return {"error": str(e)}, 400
```

### Test It

```bash
curl -X POST http://localhost:8000/api/ai/query/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "Posts published this week with at least 3 comments"}'
```

Response:
```json
{
  "data": [
    {"id": "abc-123", "title": "My Post", "comments_count": 5},
    {"id": "def-456", "title": "Another Post", "comments_count": 3}
  ],
  "count": 2,
  "sql": "SELECT * FROM posts WHERE published_at >= '2024-01-08' AND (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) >= 3"
}
```

---

## Part 2: AI-Generated Code

### Generate Models via CLI

```bash
aksara ai generate model "Review with rating (1-5), comment text, user FK, product FK"
```

Output:
```python
class Review(Model):
    """Product review from a user."""
    
    rating = fields.IntegerField(validators=[MinValue(1), MaxValue(5)])
    comment = fields.TextField()
    user = fields.ForeignKey("User", on_delete="CASCADE", related_name="reviews")
    product = fields.ForeignKey("Product", on_delete="CASCADE", related_name="reviews")
    
    class Meta:
        table_name = "reviews"
        unique_together = [("user", "product")]  # One review per user per product
```

### Generate ViewSets

```bash
aksara ai generate viewset Review --features pagination,filtering,search
```

### Generate Tests

```bash
aksara ai generate test Review --type crud,api
```

### Programmatic Generation

```python
# scripts/scaffold.py
from aksara.ai import Codegen

async def scaffold_feature(description: str):
    gen = Codegen()
    
    # Generate model
    model_code = await gen.model(description)
    print("Model:\n", model_code)
    
    # Generate serializer
    serializer_code = await gen.serializer(description.split()[0])
    print("\nSerializer:\n", serializer_code)
    
    # Generate viewset
    viewset_code = await gen.viewset(description.split()[0])
    print("\nViewSet:\n", viewset_code)

# Usage
await scaffold_feature("Subscription with plan name, price, features JSON, user FK")
```

---

## Part 3: AI-Powered Admin

### Smart Search

Add natural language search to your admin:

```python
# admin.py
from aksara.contrib.admin import AdminSite, ModelAdmin
from aksara.ai import QueryEngine

class SmartAdminSite(AdminSite):
    async def search(self, query: str):
        """Natural language search across all models."""
        engine = QueryEngine()
        results = {}
        
        for model_admin in self.registered_models:
            model_name = model_admin.model.__name__
            try:
                result = await engine.query(
                    f"{query} in {model_name}",
                    limit=10
                )
                if result.data:
                    results[model_name] = result.data
            except:
                pass
        
        return results

admin = SmartAdminSite(title="Smart Admin")
```

### Auto-Generated Filters

```python
class PostAdmin(ModelAdmin):
    model = Post
    
    async def get_filters(self):
        """AI-suggested filters based on data patterns."""
        from aksara.ai import ContextEngine
        
        context = await ContextEngine().gather(f"Useful filters for {self.model.__name__}")
        
        # Returns suggested filters like:
        # ["is_published", "author", "created_at__gte", "tags"]
        return context.suggestions.get("filters", [])
```

---

## Part 4: Smart Debugging

### AI Debug Tab

When errors occur in debug mode, get AI-powered suggestions:

```python
# Automatically enabled when AI_MODE=True and DEBUG=True
app = Aksara(debug=True)
```

On error, the debug page shows:

```
Error: Post.DoesNotExist

AI Analysis:
  The query Post.objects.get(id="invalid") returned no results.
  
  Possible causes:
  1. The ID doesn't exist in the database
  2. The ID format is invalid (not a valid UUID)
  
  Suggestions:
  1. Use get_or_404() for automatic 404 handling
  2. Use filter().first() with a None check
  3. Validate the ID format before querying
```

### Programmatic Debug Help

```python
from aksara.ai import get_debug_suggestion

try:
    post = await Post.objects.get(id=post_id)
except Post.DoesNotExist as e:
    suggestion = await get_debug_suggestion(e, context={
        "post_id": post_id,
        "model": "Post",
    })
    logger.info(f"Debug suggestion: {suggestion}")
    raise
```

---

## Part 5: Schema Analysis

### Run Schema Doctor

```bash
aksara ai doctor
```

Output:
```
🔍 Analyzing schema...

Issues Found:
  1. [HIGH] Post.author_id has no index
     Suggestion: Add db_index=True to ForeignKey
     
  2. [MEDIUM] User.email should be unique
     Suggestion: Add unique=True to EmailField
     
  3. [LOW] Comment model has no updated_at field
     Suggestion: Add updated_at = fields.DateTimeField(auto_now=True)

Run `aksara ai doctor --fix` to auto-fix issues.
```

### Auto-Fix Issues

```bash
aksara ai doctor --fix --interactive
```

### Programmatic Analysis

```python
from aksara.ai import SchemaDoctor

async def check_schema():
    doctor = SchemaDoctor()
    report = await doctor.analyze()
    
    critical = [i for i in report.issues if i.severity == "critical"]
    if critical:
        raise Exception(f"Critical schema issues: {critical}")
    
    return report
```

---

## Part 6: AI-Powered Tests

### Generate Test Cases

```python
from aksara.ai import Codegen

async def generate_tests_for_model(model_name: str):
    gen = Codegen()
    
    # Generate comprehensive tests
    tests = await gen.test(
        model=model_name,
        test_types=["crud", "validation", "edge_cases", "permissions"]
    )
    
    return tests
```

### AI Test Suggestions

```python
# In your test file
from aksara.ai import suggest_tests

class TestPost(AksaraTestCase):
    async def test_create_post(self):
        ...
    
    # Get AI suggestions for missing tests
    @classmethod
    async def suggest_missing_tests(cls):
        suggestions = await suggest_tests(
            model="Post",
            existing_tests=["test_create_post"]
        )
        print("Suggested tests:", suggestions)
        # ["test_update_post", "test_delete_post", "test_publish_unpublished_post", ...]
```

---

## Part 7: Building a Chatbot Interface

### Create Chat Endpoint

```python
# app/chat.py
from aksara.api import ViewSet, action
from aksara.ai import AgentRuntime

class ChatViewSet(ViewSet):
    @action(detail=False, methods=["post"])
    async def message(self, request):
        """Process a chat message."""
        message = request.data.get("message")
        session_id = request.data.get("session_id")
        
        runtime = AgentRuntime(
            tools=["query_records", "list_models", "describe_model"],
            read_only=True,
        )
        
        result = await runtime.execute(
            message,
            session_id=session_id,
        )
        
        return {
            "response": result.output,
            "session_id": result.session_id,
        }
```

### Frontend Integration

```javascript
// chat.js
async function sendMessage(message) {
    const response = await fetch('/api/chat/message/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
            message,
            session_id: currentSessionId,
        }),
    });
    
    const data = await response.json();
    displayMessage(data.response);
}

// Example conversation:
// User: "How many users signed up this week?"
// AI: "There were 23 new users who signed up this week. Would you like to see the details?"
// User: "Yes, show me the top 5 by activity"
// AI: "Here are the top 5 most active new users: ..."
```

---

## Safety Considerations

### Read-Only Queries

Always use read-only mode for user-facing queries:

```python
engine = QueryEngine(read_only=True)
```

### Audit Logging

Enable audit logging for all AI operations:

```python
AKSARA = {
    "AI_SAFETY": {
        "audit_log": True,
        "audit_log_file": "logs/ai_audit.log",
    },
}
```

### Rate Limiting

Limit AI API usage:

```python
AKSARA = {
    "AI_SAFETY": {
        "rate_limit_requests": 100,
        "rate_limit_window": 3600,  # per hour
    },
}
```

---

## Complete Example

Here's a complete AI-enhanced ViewSet:

```python
# app/ai_viewsets.py
from aksara.api import ViewSet, action
from aksara.api.permissions import IsAuthenticated
from aksara.ai import QueryEngine, Codegen, SchemaDoctor

class AIAssistantViewSet(ViewSet):
    """AI-powered assistant endpoints."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["post"])
    async def query(self, request):
        """Natural language data query."""
        engine = QueryEngine(read_only=True)
        result = await engine.query(request.data.get("query"))
        return {
            "data": result.data,
            "sql": result.sql,
            "count": result.count,
        }
    
    @action(detail=False, methods=["post"])
    async def generate(self, request):
        """Generate code from description."""
        gen = Codegen()
        code_type = request.data.get("type", "model")
        description = request.data.get("description")
        
        if code_type == "model":
            code = await gen.model(description)
        elif code_type == "viewset":
            code = await gen.viewset(description)
        elif code_type == "test":
            code = await gen.test(description)
        else:
            return {"error": "Unknown type"}, 400
        
        return {"code": code}
    
    @action(detail=False, methods=["get"])
    async def schema_check(self, request):
        """Check schema for issues."""
        doctor = SchemaDoctor()
        report = await doctor.analyze()
        
        return {
            "issues": [
                {
                    "severity": i.severity,
                    "message": i.message,
                    "suggestion": i.fix_hint,
                }
                for i in report.issues
            ],
            "summary": report.summary,
        }
```

---

## Next Steps

1. **Custom AI tools** — Create domain-specific tools
2. **Fine-tuned models** — Use custom models for better results
3. **Caching** — Cache common AI responses
4. **Webhooks** — Trigger AI actions on events

---

## Related Documentation

- [AI Mode Overview](../ai-mode/index.md)
- [Query Engine](../ai-mode/query-engine.md)
- [Codegen](../ai-mode/codegen.md)
- [Safety](../ai-mode/safety.md)
