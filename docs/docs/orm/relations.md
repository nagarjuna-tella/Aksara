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

`on_delete` accepts the canonical values `CASCADE`, `SET NULL`, `RESTRICT`, and
`PROTECT`. Matching is case-insensitive, `SET_NULL`-style underscore variants
are accepted, and `OnDelete` enum instances may be used.

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
`select_related(...).all()` and then read the loaded object synchronously with
`get_related("author")`. Calling it without preloading raises `ValueError`; it
does not issue a query.

### Reverse Access

Aksara finalizes reverse descriptors after loading models during application
startup. In a standalone script, import all related models and call the public
`aksara.finalize_relations()` before using reverse accessors.

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
await category.delete()  # Reload the post to observe category=None
```

### RESTRICT / PROTECT

Prevent deletion if related objects exist.

```python
class Post(Model):
    author = fields.ForeignKey(Author, on_delete=RESTRICT)

# This raises an error if the author has posts
await author.delete()  # ORM precheck raises RestrictedError
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
    Unlike ForeignKey's reverse which returns a manager (`.all()`, `.filter()`), `await user.profile()` returns one object or `None`. Use
    `await user.profile.get()` when absence should raise `DoesNotExist`.

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
has_tag = tag.id in await post.tags.ids()
```

### Reverse Access

```python
tag = await Tag.objects.get(name="python")

# Get all posts with this tag
posts = await tag.posts.all()

# Filter the returned list; the reverse M2M manager has no filter() method.
recent = [post for post in await tag.posts.all() if post.created_at > last_week]
```

### Junction Table

Generate and apply migrations to create the junction table. Declaring a model
alone does not create it. The default name is `{source_table}_{field_name}`:
`posts_tags` for a `posts` table with a `tags` field. It contains source/target
UUID references, a unique pair, its own ID and a creation timestamp. Inspect
the generated migration rather than copying a separate hand-written schema.

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

Models can reference themselves by their explicit registered class name. The
string `"self"` is not a supported shortcut:

```python
class Category(Model):
    name = fields.String(max_length=100)
    parent = fields.ForeignKey(
        "Category",  # explicit registered model name
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
posts = await Post.objects.filter(author=author).all()

# Posts by author email
posts = await Post.objects.filter(author__email="jane@example.com").all()

# Posts with a specific tag (M2M)
tag = await Tag.objects.get(name="python")
posts = await tag.posts.all()
```

Forward M2M traversal in a filter such as `tags__name` is not supported by
the current query builder. Resolve the tag and use its reverse M2M manager,
as above.

### Select Related (Eager Loading)

Avoid one lookup per parent by batching related-object loads. Aksara first
fetches the parent rows, then loads the requested FK/O2O relations in additional
queries; `select_related()` is not a promise of one SQL JOIN query.

```python
# Without select_related: N+1 queries
posts = await Post.objects.all()
for post in posts:
    author = await Author.objects.get(id=post.author_id)  # Query per post

# With select_related: batched related-object loading
posts = await Post.objects.select_related("author").all()
for post in posts:
    author = post.get_related("author")
    print(author.name)
```

`select_related()` preserves its eager-loading contract with both `all()` and
`first()`. A successful `first()` call populates each requested relation before
returning; nullable relations are marked as loaded and return `None` through
`get_related()`. A query with no matching parent returns `None` without issuing
relation queries. QuerySet has no `get()` method; `Model.objects.get()` remains
a manager method.

### Prefetch Related (For M2M)

```python
# Efficient M2M loading
posts = await Post.objects.prefetch_related("tags").all()
for post in posts:
    for tag in post.get_prefetched_m2m("tags"):
        print(tag.name)
```

---

## Complete relation example

These models use distinct names to avoid collisions with framework models.
In an application, import them for migration discovery and apply migrations,
including the M2M junction table, before calling `demo()` on a connected database.
For a standalone script, call `finalize_relations()` after all declarations and
before using reverse accessors. The example is not a standalone setup script
or an authentication implementation.

```python
from aksara import Model, fields, CASCADE, SET_NULL

class BlogAuthor(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)

class BlogCategory(Model):
    name = fields.String(max_length=50)
    slug = fields.String(max_length=50, unique=True)
    parent = fields.ForeignKey(
        "BlogCategory",
        on_delete=CASCADE,
        nullable=True,
        related_name="children",
    )

class BlogTag(Model):
    name = fields.String(max_length=30, unique=True)
    slug = fields.String(max_length=30, unique=True)

class BlogPost(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)
    
    # Many-to-one: Many posts per author
    author = fields.ForeignKey(
        BlogAuthor,
        on_delete=CASCADE,
        related_name="posts",
    )
    
    # Many-to-one: Many posts per category (optional)
    category = fields.ForeignKey(
        BlogCategory,
        on_delete=SET_NULL,
        nullable=True,
        related_name="posts",
    )
    
    # Many-to-many: Posts have multiple tags
    tags = fields.ManyToMany(
        BlogTag,
        related_name="posts",
    )
    
    created_at = fields.DateTime(auto_now_add=True)

class BlogProfile(Model):
    # One-to-one: Each user has one profile
    user = fields.OneToOne(
        BlogAuthor,
        on_delete=CASCADE,
        related_name="profile",
    )
    bio = fields.Text(nullable=True)
    website = fields.URL(nullable=True)


# Usage examples
async def demo():
    # Create user with profile
    user = await BlogAuthor.objects.create(email="jane@example.com", name="Jane")
    profile = await BlogProfile.objects.create(user=user, bio="Tech writer")
    
    # Create category hierarchy
    tech = await BlogCategory.objects.create(name="Technology", slug="tech")
    python = await BlogCategory.objects.create(name="Python", slug="python", parent=tech)
    
    # Create tags
    tutorial = await BlogTag.objects.create(name="Tutorial", slug="tutorial")
    beginner = await BlogTag.objects.create(name="Beginner", slug="beginner")
    
    # Create post with relations
    post = await BlogPost.objects.create(
        title="Getting Started with Python",
        content="Learn Python basics...",
        author=user,
        category=python,
    )
    
    # Add tags
    await post.tags.add(tutorial, beginner)
    
    # Query examples
    jane_posts = await user.posts.all()
    tech_posts = await tech.posts.all()  # Direct category only; not descendants
    tutorial_posts = await tutorial.posts.all()
    
    # Efficient loading
    posts = await BlogPost.objects.select_related("author", "category").all()
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
# Use when you need these related objects; measure the resulting query
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
