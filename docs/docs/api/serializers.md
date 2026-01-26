# Serializers

Transform and validate data for API requests and responses.

---

## Overview

Serializers handle:

- **Request validation** — Validate incoming JSON data
- **Response transformation** — Format model data for output
- **Field selection** — Control which fields are exposed
- **Nested serialization** — Handle related objects

```python
from vidyut.api import ModelSerializer
from myapp.models import Post

class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "author", "created_at"]
    read_only_fields = ["id", "created_at"]
```

---

## ModelSerializer

The most common serializer type, automatically maps to a model:

```python
from vidyut.api import ModelSerializer

class PostSerializer(ModelSerializer):
    model = Post
```

### Specifying Fields

#### All Fields

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = "__all__"
```

#### Specific Fields

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "author_id", "created_at"]
```

#### Exclude Fields

```python
class PostSerializer(ModelSerializer):
    model = Post
    exclude = ["internal_notes", "deleted_at"]
```

### Read-Only Fields

Fields that can be read but not set via API:

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = "__all__"
    read_only_fields = ["id", "created_at", "updated_at", "author_id"]
```

### Write-Only Fields

Fields that can be set but not read (e.g., passwords):

```python
class UserSerializer(ModelSerializer):
    model = User
    fields = ["id", "email", "password", "name"]
    write_only_fields = ["password"]
```

---

## Field Options

### Custom Field Configuration

```python
from vidyut.api import ModelSerializer, Field

class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "summary"]
    
    # Custom field not on model
    summary = Field(read_only=True)
    
    def get_summary(self, obj):
        """Compute summary from content."""
        return obj.content[:200] + "..." if len(obj.content) > 200 else obj.content
```

### Field Validation

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content"]
    
    def validate_title(self, value):
        """Validate title field."""
        if len(value) < 5:
            raise ValidationError("Title must be at least 5 characters")
        return value
    
    def validate_content(self, value):
        """Validate content field."""
        if not value.strip():
            raise ValidationError("Content cannot be empty")
        return value
```

### Object-Level Validation

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "slug", "content"]
    
    def validate(self, data):
        """Validate the entire object."""
        # Ensure slug is unique for this author
        existing = await Post.objects.filter(
            author_id=self.context["user_id"],
            slug=data.get("slug"),
        ).exclude(id=self.instance.id if self.instance else None).first()
        
        if existing:
            raise ValidationError({"slug": "You already have a post with this slug"})
        
        return data
```

---

## Nested Serialization

### Related Objects

```python
class AuthorSerializer(ModelSerializer):
    model = Author
    fields = ["id", "name", "email"]

class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "author", "created_at"]
    
    # Nest the author
    author = AuthorSerializer(read_only=True)
```

Output:
```json
{
    "id": "post-uuid",
    "title": "My Post",
    "content": "...",
    "author": {
        "id": "author-uuid",
        "name": "Jane Doe",
        "email": "jane@example.com"
    },
    "created_at": "2024-01-15T10:30:00Z"
}
```

### Nested Writable

```python
class CommentSerializer(ModelSerializer):
    model = Comment
    fields = ["id", "content", "author_id"]

class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "comments"]
    
    # Writable nested serializer
    comments = CommentSerializer(many=True)
    
    async def create(self, validated_data):
        comments_data = validated_data.pop("comments", [])
        post = await Post.objects.create(**validated_data)
        
        for comment_data in comments_data:
            await Comment.objects.create(post=post, **comment_data)
        
        return post
```

### Many=True for Lists

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "tags"]
    
    # List of nested objects
    tags = TagSerializer(many=True, read_only=True)
```

---

## Computed Fields

### Method Fields

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "summary", "word_count", "is_long"]
    
    summary = Field(read_only=True)
    word_count = Field(read_only=True)
    is_long = Field(read_only=True)
    
    def get_summary(self, obj):
        """First 200 characters."""
        content = obj.content or ""
        return content[:200] + "..." if len(content) > 200 else content
    
    def get_word_count(self, obj):
        """Count words in content."""
        return len((obj.content or "").split())
    
    def get_is_long(self, obj):
        """True if over 1000 words."""
        return self.get_word_count(obj) > 1000
```

### Context-Aware Fields

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "is_mine", "can_edit"]
    
    is_mine = Field(read_only=True)
    can_edit = Field(read_only=True)
    
    def get_is_mine(self, obj):
        """Check if current user owns this post."""
        user = self.context.get("request").user
        return str(obj.author_id) == str(user.id)
    
    def get_can_edit(self, obj):
        """Check if current user can edit."""
        user = self.context.get("request").user
        return (
            str(obj.author_id) == str(user.id) or
            user.is_staff
        )
```

---

## Serialization Context

Pass context to serializers for dynamic behavior:

```python
# In ViewSet
def serialize(self, obj):
    serializer = self.get_serializer_class()(
        obj,
        context={
            "request": self.request,
            "view": self,
            "user": self.request.user,
        }
    )
    return serializer.data

# In Serializer
class PostSerializer(ModelSerializer):
    model = Post
    
    def get_edit_url(self, obj):
        request = self.context.get("request")
        return request.url_for("post-edit", id=obj.id)
```

---

## Different Serializers per Action

### List vs Detail

```python
class PostListSerializer(ModelSerializer):
    """Minimal data for lists."""
    model = Post
    fields = ["id", "title", "author_id", "created_at"]

class PostDetailSerializer(ModelSerializer):
    """Full data for detail view."""
    model = Post
    fields = "__all__"
    
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments_count = Field(read_only=True)
    
    def get_comments_count(self, obj):
        return len(obj.comments) if hasattr(obj, "comments") else 0

# In ViewSet
class PostViewSet(ModelViewSet):
    model = Post
    serializer_class = PostDetailSerializer
    
    def get_serializer_class(self):
        if self.action == "list":
            return PostListSerializer
        return PostDetailSerializer
```

### Create vs Update

```python
class PostCreateSerializer(ModelSerializer):
    """Fields for creation."""
    model = Post
    fields = ["title", "content", "category_id", "tags"]
    
class PostUpdateSerializer(ModelSerializer):
    """Fields for update."""
    model = Post
    fields = ["title", "content", "category_id"]
    # Cannot change tags during update

class PostViewSet(ModelViewSet):
    model = Post
    
    def get_serializer_class(self):
        if self.action == "create":
            return PostCreateSerializer
        if self.action in ["update", "partial_update"]:
            return PostUpdateSerializer
        return PostDetailSerializer
```

---

## Validation

### Field-Level Validation

```python
class UserSerializer(ModelSerializer):
    model = User
    fields = ["email", "password", "name"]
    
    def validate_email(self, value):
        """Validate email field."""
        if not value.endswith("@company.com"):
            raise ValidationError("Must use company email")
        return value.lower()  # Normalize
    
    def validate_password(self, value):
        """Validate password field."""
        if len(value) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain a digit")
        return value
```

### Cross-Field Validation

```python
class EventSerializer(ModelSerializer):
    model = Event
    fields = ["title", "start_date", "end_date"]
    
    def validate(self, data):
        """Validate across fields."""
        if data.get("end_date") and data.get("start_date"):
            if data["end_date"] < data["start_date"]:
                raise ValidationError({
                    "end_date": "End date must be after start date"
                })
        return data
```

### Async Validation

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["title", "slug"]
    
    async def validate_slug(self, value):
        """Check slug uniqueness."""
        exists = await Post.objects.filter(slug=value).exists()
        if exists:
            raise ValidationError("This slug is already taken")
        return value
```

---

## Response Formatting

### Transform Output

```python
class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "created_at"]
    
    def to_representation(self, obj):
        """Customize output format."""
        data = super().to_representation(obj)
        
        # Format datetime
        if data.get("created_at"):
            data["created_at_human"] = humanize_datetime(data["created_at"])
        
        # Add computed fields
        data["url"] = f"/posts/{data['id']}"
        
        return data
```

### Transform Input

```python
class PostSerializer(ModelSerializer):
    model = Post
    
    def to_internal_value(self, data):
        """Transform input before validation."""
        # Normalize title
        if "title" in data:
            data["title"] = data["title"].strip()
        
        # Auto-generate slug
        if "title" in data and "slug" not in data:
            data["slug"] = slugify(data["title"])
        
        return super().to_internal_value(data)
```

---

## Complete Example

```python
from vidyut.api import ModelSerializer, Field, ValidationError
from myapp.models import Post, Author, Tag, Comment


class AuthorSerializer(ModelSerializer):
    """Serializer for Author model."""
    model = Author
    fields = ["id", "name", "email", "avatar_url"]


class TagSerializer(ModelSerializer):
    """Serializer for Tag model."""
    model = Tag
    fields = ["id", "name", "slug"]


class CommentSerializer(ModelSerializer):
    """Serializer for Comment model."""
    model = Comment
    fields = ["id", "content", "author_id", "created_at"]
    read_only_fields = ["id", "created_at"]


class PostListSerializer(ModelSerializer):
    """Minimal serializer for post lists."""
    model = Post
    fields = ["id", "title", "is_published", "author_id", "created_at"]


class PostDetailSerializer(ModelSerializer):
    """Full serializer for post detail."""
    model = Post
    fields = [
        "id", "title", "slug", "content", "is_published",
        "author", "tags", "comments_count", "view_count",
        "created_at", "updated_at", "published_at",
        "reading_time", "is_editable",
    ]
    read_only_fields = [
        "id", "created_at", "updated_at", "published_at",
        "view_count", "comments_count",
    ]
    
    # Nested serializers
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    
    # Computed fields
    comments_count = Field(read_only=True)
    reading_time = Field(read_only=True)
    is_editable = Field(read_only=True)
    
    def get_comments_count(self, obj):
        """Get number of comments."""
        if hasattr(obj, "_comments_count"):
            return obj._comments_count
        return 0
    
    def get_reading_time(self, obj):
        """Estimate reading time in minutes."""
        words = len((obj.content or "").split())
        return max(1, words // 200)
    
    def get_is_editable(self, obj):
        """Check if current user can edit."""
        user = self.context.get("request").user
        if not user or user.is_anonymous:
            return False
        return str(obj.author_id) == str(user.id) or user.is_staff


class PostCreateSerializer(ModelSerializer):
    """Serializer for creating posts."""
    model = Post
    fields = ["title", "slug", "content", "category_id", "tag_ids"]
    
    tag_ids = Field(write_only=True, required=False)
    
    def validate_title(self, value):
        """Validate title."""
        value = value.strip()
        if len(value) < 5:
            raise ValidationError("Title must be at least 5 characters")
        if len(value) > 200:
            raise ValidationError("Title must be at most 200 characters")
        return value
    
    def validate_slug(self, value):
        """Validate slug format."""
        import re
        if not re.match(r"^[a-z0-9-]+$", value):
            raise ValidationError("Slug must be lowercase letters, numbers, and hyphens")
        return value
    
    async def validate(self, data):
        """Cross-field validation."""
        # Auto-generate slug if not provided
        if not data.get("slug") and data.get("title"):
            from slugify import slugify
            data["slug"] = slugify(data["title"])
        
        # Check slug uniqueness
        author_id = self.context.get("author_id")
        exists = await Post.objects.filter(
            author_id=author_id,
            slug=data["slug"],
        ).exists()
        
        if exists:
            raise ValidationError({"slug": "You already have a post with this slug"})
        
        return data
    
    async def create(self, validated_data):
        """Create post with tags."""
        tag_ids = validated_data.pop("tag_ids", [])
        
        # Set author from context
        validated_data["author_id"] = self.context.get("author_id")
        
        post = await Post.objects.create(**validated_data)
        
        # Add tags
        if tag_ids:
            tags = await Tag.objects.filter(id__in=tag_ids).all()
            await post.tags.add(*tags)
        
        return post


class PostUpdateSerializer(ModelSerializer):
    """Serializer for updating posts."""
    model = Post
    fields = ["title", "slug", "content", "category_id", "is_published"]
    
    def validate_title(self, value):
        """Validate title."""
        if value and len(value) < 5:
            raise ValidationError("Title must be at least 5 characters")
        return value
    
    async def update(self, instance, validated_data):
        """Update post."""
        # If publishing, set published_at
        if validated_data.get("is_published") and not instance.is_published:
            from datetime import datetime
            validated_data["published_at"] = datetime.now()
        
        for key, value in validated_data.items():
            setattr(instance, key, value)
        
        await instance.save()
        return instance
```

---

## Related Documentation

- [ViewSets](viewsets.md) — Using serializers in ViewSets
- [Fields](../orm/fields.md) — Model field types
- [Validation](../advanced/validation.md) — Advanced validation
