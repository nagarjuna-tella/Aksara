# Relations

Define relationships between models using ForeignKey, ManyToMany, and OneToOne fields.

---

## Overview

Aksara supports three types of relationships:

| Type | Relationship | Example |
|------|--------------|---------|
| **ForeignKey** | Many-to-One | Posts have one Author |
| **OneToOne** | One-to-One | User has one Profile |
| **ManyToMany** | Many-to-Many | Posts have many Tags |

All relationships support:

- **Forward access** — Access stored FK values or relation managers from the defining model
- **Reverse access** — Access back from the related model
- **AI metadata** — Relationship descriptions for LLMs

---

## ForeignKey (Many-to-One)

A ForeignKey creates a many-to-one relationship where multiple objects can reference a single related object.

### Definition

```python
from aksara import Model, fields, CASCADE

class Author(Model):
    name = fields.String(max_length=100)
    email = fields.Email(unique=True)

class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    author = fields.ForeignKey(
        Author,                    # or "Author" as string
        on_delete=CASCADE,
        related_name="posts",      # Reverse accessor name
    )
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `to` | `str` or `type` | Required | Target model |
| `on_delete` | `str` | `CASCADE` | Delete behavior |
| `related_name` | `str` | `{model}_set` | Name for reverse relation |
| `nullable` | `bool` | `False` | Allow NULL values |

### Forward Access

Access the stored foreign-key value from the child:

```python
# Get a post
post = await Post.objects.get(id=post_id)

# Forward FK fields currently expose the stored FK value/id.
author_id = post.author_id
# post.author currently exposes the same stored FK value/id.
same_author_id = post.author

# Load the related object explicitly.
author = await Author.objects.get(id=author_id)
```

Today, `post.author` and `post.author_id` expose the same stored FK value/id;
`post.author` is not a lazy-loaded related object. For eager loading, use
`select_related()` and then read the loaded object with `get_related("author")`.

### Reverse Access

Access related objects from the parent:

```python
# Get an author
author = await Author.objects.get(id=author_id)

# Access all posts by this author
posts = await author.posts.all()

# Filter posts
recent_posts = await author.posts.filter(created_at__gt=last_week)

# Count posts
post_count = await author.posts.count()
```

### Creating with ForeignKey

```python
# Method 1: Pass the related object
author = await Author.objects.get(email="jane@example.com")
post = await Post.objects.create(
    title="My Post",
    content="Content here",
    author=author,
)

# Method 2: Pass the ID directly
post = await Post.objects.create(
    title="My Post",
    content="Content here",
    author_id=author.id,
)
```

---

## on_delete Options

When the referenced object is deleted, what happens to objects that reference it?

### CASCADE

Delete the referencing objects too.

```python
class Post(Model):
    author = fields.ForeignKey(Author, on_delete=CASCADE)

# When author is deleted, all their posts are deleted
await author.delete()  # Posts automatically deleted
```

### SET_NULL

Set the foreign key to NULL (requires `nullable=True`).

```python
class Post(Model):
    category = fields.ForeignKey(
        Category,
        on_delete=SET_NULL,
        nullable=True,
    )

# When category is deleted, posts remain but category becomes NULL
await category.delete()  # post.category becomes None
```

### RESTRICT / PROTECT

Prevent deletion if related objects exist.

```python
class Post(Model):
    author = fields.ForeignKey(Author, on_delete=RESTRICT)

# This raises an error if the author has posts
await author.delete()  # Raises ForeignKeyConstraintError
```

### Import on_delete Constants

```python
from aksara import CASCADE, SET_NULL, RESTRICT, PROTECT
# or
from aksara.fields import CASCADE, SET_NULL, RESTRICT, PROTECT
# or use the enum
from aksara.relations import OnDelete
author = fields.ForeignKey(User, on_delete=OnDelete.CASCADE)
```

---

## OneToOne

A OneToOne relationship is like a ForeignKey but enforces uniqueness — each object can only be related to one other object.

### Definition

```python
class User(Model):
    email = fields.Email(unique=True)

class UserProfile(Model):
    user = fields.OneToOne(
        User,
        on_delete=CASCADE,
        related_name="profile",
    )
    bio = fields.Text(nullable=True)
    avatar_url = fields.URL(nullable=True)
```

### Forward Access

```python
profile = await UserProfile.objects.get(id=profile_id)
user_id = profile.user_id
# profile.user currently exposes the same stored FK value/id.
user = await User.objects.get(id=user_id)
print(user.email)
```

### Reverse Access

```python
user = await User.objects.get(id=user_id)
profile = await user.profile()  # Note: callable, not manager
print(profile.bio)
```

!!! note "OneToOne Reverse is a Single Object"
    Unlike ForeignKey's reverse which returns a manager (`.all()`, `.filter()`), OneToOne reverse returns a single object (or raises `DoesNotExist`).

### When to Use OneToOne

- **User profiles** — Separate profile data from auth data
- **Optional extensions** — Data that doesn't apply to all records
- **Large fields** — Separate rarely-accessed large fields

---

## ManyToMany

A ManyToMany relationship allows multiple objects on both sides of the relationship.

### Definition

```python
class Tag(Model):
    name = fields.String(max_length=50, unique=True)

class Post(Model):
    title = fields.String(max_length=200)
    tags = fields.ManyToMany(
        Tag,
        related_name="posts",
    )
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `to` | `str` or `type` | Required | Target model |
| `related_name` | `str` | `{model}_set` | Name for reverse relation |
| `through` | `str` | Unsupported | Custom through models are not supported yet |

### Forward Access

```python
post = await Post.objects.get(id=post_id)

# Get all tags
tags = await post.tags.all()

# Add tags
await post.tags.add(tag1, tag2)

# Remove tags
await post.tags.remove(tag1)

# Clear all tags
await post.tags.clear()

# Set tags (replaces existing)
await post.tags.set([tag1, tag2, tag3])

# Check membership
has_tag = await post.tags.contains(tag)
```

### Reverse Access

```python
tag = await Tag.objects.get(name="python")

# Get all posts with this tag
posts = await tag.posts.all()

# Filter
recent = await tag.posts.filter(created_at__gt=last_week)
```

### Junction Table

Aksara automatically creates a junction table:

```sql
-- Auto-generated for Post.tags -> Tag
CREATE TABLE post_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE (post_id, tag_id)
);
```

### Custom Through Model

Custom through models are not supported yet. Passing `through=` raises a clear
configuration error instead of silently creating a join table that cannot store
the custom model's extra fields.

---

## String References

Use string references for:

- **Forward references** — Model defined later in the file
- **Circular references** — Models that reference each other

```python
class Author(Model):
    name = fields.String(max_length=100)
    # Reference Post that's defined below
    favorite_post = fields.ForeignKey("Post", nullable=True, on_delete=SET_NULL)

class Post(Model):
    title = fields.String(max_length=200)
    author = fields.ForeignKey("Author", on_delete=CASCADE)
```

---

## Self-Referential Relations

Models can reference themselves:

```python
class Category(Model):
    name = fields.String(max_length=100)
    parent = fields.ForeignKey(
        "self",  # or "Category"
        on_delete=CASCADE,
        nullable=True,
        related_name="children",
    )

# Usage
parent = await Category.objects.create(name="Electronics")
child = await Category.objects.create(name="Phones", parent=parent)

# Access children
phones = await parent.children.all()

# Access parent
electronics_id = child.parent_id
electronics = await Category.objects.get(id=electronics_id)
```

---

## Querying Relations

### Filtering by Related Objects

```python
# Posts by a specific author
posts = await Post.objects.filter(author=author)

# Posts by author email
posts = await Post.objects.filter(author__email="jane@example.com")

# Posts with a specific tag (M2M)
posts = await Post.objects.filter(tags__name="python")
```

### Select Related (Eager Loading)

Avoid N+1 queries by loading related objects in one query:

```python
# Without select_related: N+1 queries
posts = await Post.objects.all()
for post in posts:
    author = await Author.objects.get(id=post.author_id)  # Query per post

# With select_related: Single query
posts = await Post.objects.select_related("author").all()
for post in posts:
    author = post.get_related("author")
    print(author.name)
```

### Prefetch Related (For M2M)

```python
# Efficient M2M loading
posts = await Post.objects.prefetch_related("tags").all()
for post in posts:
    for tag in post.get_prefetched_m2m("tags"):
        print(tag.name)
```

---

## Complete Example

```python
from aksara import Model, fields, CASCADE, SET_NULL

class User(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)

class Category(Model):
    name = fields.String(max_length=50)
    slug = fields.String(max_length=50, unique=True)
    parent = fields.ForeignKey(
        "self",
        on_delete=CASCADE,
        nullable=True,
        related_name="children",
    )

class Tag(Model):
    name = fields.String(max_length=30, unique=True)
    slug = fields.String(max_length=30, unique=True)

class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)
    
    # Many-to-one: Many posts per author
    author = fields.ForeignKey(
        User,
        on_delete=CASCADE,
        related_name="posts",
    )
    
    # Many-to-one: Many posts per category (optional)
    category = fields.ForeignKey(
        Category,
        on_delete=SET_NULL,
        nullable=True,
        related_name="posts",
    )
    
    # Many-to-many: Posts have multiple tags
    tags = fields.ManyToMany(
        Tag,
        related_name="posts",
    )
    
    created_at = fields.DateTime(auto_now_add=True)

class UserProfile(Model):
    # One-to-one: Each user has one profile
    user = fields.OneToOne(
        User,
        on_delete=CASCADE,
        related_name="profile",
    )
    bio = fields.Text(nullable=True)
    website = fields.URL(nullable=True)


# Usage examples
async def demo():
    # Create user with profile
    user = await User.objects.create(email="jane@example.com", name="Jane")
    profile = await UserProfile.objects.create(user=user, bio="Tech writer")
    
    # Create category hierarchy
    tech = await Category.objects.create(name="Technology", slug="tech")
    python = await Category.objects.create(name="Python", slug="python", parent=tech)
    
    # Create tags
    tutorial = await Tag.objects.create(name="Tutorial", slug="tutorial")
    beginner = await Tag.objects.create(name="Beginner", slug="beginner")
    
    # Create post with relations
    post = await Post.objects.create(
        title="Getting Started with Python",
        content="Learn Python basics...",
        author=user,
        category=python,
    )
    
    # Add tags
    await post.tags.add(tutorial, beginner)
    
    # Query examples
    jane_posts = await user.posts.all()
    tech_posts = await tech.posts.all()  # Including child categories
    tutorial_posts = await Post.objects.filter(tags__name="Tutorial")
    
    # Efficient loading
    posts = await Post.objects.select_related("author", "category").all()
```

---

## Best Practices

### Use Descriptive related_name

```python
# Good
author = fields.ForeignKey(User, related_name="authored_posts")
editor = fields.ForeignKey(User, related_name="edited_posts")

# Confusing
author = fields.ForeignKey(User, related_name="posts")
editor = fields.ForeignKey(User, related_name="posts2")  # ❌
```

### Choose on_delete Carefully

| Scenario | Recommendation |
|----------|----------------|
| Comments on a Post | `CASCADE` — Delete comments with post |
| Posts in a Category | `SET_NULL` — Keep posts, clear category |
| User's Auth Tokens | `CASCADE` — Delete tokens with user |
| Order's Customer | `PROTECT` — Don't delete customers with orders |

### Use select_related for Performance

```python
# Always use when accessing related objects
posts = await Post.objects.select_related("author").all()
```

### Consider Nullable for Optional Relations

```python
# Optional category
category = fields.ForeignKey(
    Category,
    on_delete=SET_NULL,
    nullable=True,  # Posts can exist without a category
)
```

---

## Related Documentation

- [Fields](fields.md) — All field types
- [Querying](querying.md) — Query and filter data
- [Models](models.md) — Model basics
