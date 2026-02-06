# Patterns & Example Packs

Aksara provides real-world example applications demonstrating common patterns for building async APIs. These patterns serve as starting points for your own projects.

## Available Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| [Blog](blog.md) | Post + Comment with moderation | Content platforms, blogs |
| [CRM](crm.md) | Customer + Deal pipeline | Sales apps, lead tracking |
| [Multitenant](multitenant.md) | Tenant-scoped SaaS | B2B SaaS, white-label apps |

## Quick Start with Templates

Use templates to scaffold a project with your chosen pattern:

```bash
# Blog pattern
aksara startproject myblog --template blog

# CRM pattern
aksara startproject mycrm --template crm

# Multitenant pattern
aksara startproject mysaas --template multitenant
```

## List Available Templates

```bash
aksara templates list
```

Output:
```
  ⚡ Aksara v0.5.7
  Available project templates

  basic        Default minimal project (Post model) (default)
  blog         Full blog with Post, Comment, moderation
  crm          Customer & Deal pipeline with forecasting
  multitenant  Tenant-scoped SaaS backend
```

## Pattern Structure

Each pattern includes:

```
pattern/
├── models.py        # Domain models
├── serializers.py   # Validation & response shaping
├── views.py         # ViewSets with actions
├── admin.py         # Admin registrations
├── urls.py          # Route configuration
├── settings.py      # App configuration
├── main.py          # Entry point
├── README.md        # Documentation
└── migrations/      # Database migrations
```

## Key Concepts

### 1. Models with AI Metadata

All patterns use Aksara's AI-enhanced models:

```python
class Post(Model):
    title = fields.String(
        max_length=200,
        ai_description="Post title",
    )
    
    class Meta:
        table_name = "posts"
        ai_name = "Post"
        ai_description = "Blog posts"
        ai_agent_exposed = True
```

### 2. ViewSets with Custom Actions

Patterns demonstrate custom actions:

```python
class PostViewSet(ModelViewSet):
    model = Post
    serializer_class = PostSerializer
    prefix = "/api/posts"
    
    @action(detail=True, methods=["POST"])
    async def publish(self, pk: str, request: Request):
        """Publish a post."""
        post = await self.model.objects.get(id=pk)
        post.is_published = True
        await post.save()
        return {"status": "published"}
```

### 3. Serializers with Computed Fields

Patterns include computed fields:

```python
class DealSerializer(ModelSerializer):
    expected_revenue: Optional[float] = None
    
    class Meta:
        model = Deal
        fields = ["id", "title", "value", "probability", "expected_revenue"]
    
    @classmethod
    def from_model(cls, deal: Deal) -> "DealSerializer":
        instance = super().from_model(deal)
        instance.expected_revenue = deal.value * (deal.probability / 100)
        return instance
```

## Learning Path

1. **Start with Blog** if you're new to Aksara
   - Simple Post + Comment models
   - Basic CRUD with custom actions
   - Moderation workflow

2. **Move to CRM** for business logic
   - Deal stages and probability
   - Forecasting endpoints
   - Pipeline aggregations

3. **Study Multitenant** for SaaS patterns
   - Tenant middleware
   - Scoped queries
   - Domain-based routing

## Next Steps

- [Blog Pattern](blog.md) - Content management
- [CRM Pattern](crm.md) - Sales pipeline
- [Multitenant Pattern](multitenant.md) - SaaS backend
- [CLI Reference](../cli/index.md) - Command reference
