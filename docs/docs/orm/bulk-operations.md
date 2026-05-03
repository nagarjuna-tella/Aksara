# Bulk Operations

Aksara's ORM provides high-performance bulk operations for efficiently managing large datasets. These operations minimize database roundtrips and utilize PostgreSQL-native features for atomicity and speed.

---

## Bulk Create

Insert thousands of records efficiently with automatic batching.

```python
# Create 10,000 user instances in memory
users_to_create = [
    User(email=f"user{i}@example.com", name=f"User {i}")
    for i in range(10000)
]

# Batch insert (1000 per batch by default)
created_users = await User.objects.bulk_create(
    users_to_create,
    batch_size=1000
)

# ✅ This performs 10 queries (batching 1000 items each)
# ❌ Instead of 10,000 individual INSERT queries
```

### Ignoring Conflicts

If you want to skip records that violate unique constraints instead of raising exceptions, use `ignore_conflicts=True`. This utilizes PostgreSQL's `ON CONFLICT DO NOTHING`.

```python
# If email is unique and some duplicates exist, skip them silently
created = await User.objects.bulk_create(
    users,
    ignore_conflicts=True
)

# Returns only successfully inserted records
```

---

## Bulk Update

Update thousands of records efficiently using PostgreSQL `CASE` statements.

```python
# Mark all unpublished posts as published
posts = await Post.objects.filter(status="draft").all()

# Modify instances in memory
for post in posts:
    post.status = "published"
    post.updated_at = datetime.now()

# Batch update all at once
updated_count = await Post.objects.bulk_update(
    posts,
    fields=['status', 'updated_at'],
    batch_size=1000
)

print(f"Updated {updated_count} posts")
```

---

## Upsert (Insert or Update)

Perform an insert if a record is new, or update it if it already exists based on unique constraints. 

**Uses PostgreSQL's native `ON CONFLICT DO UPDATE`** for atomicity and performance.

```python
# Upsert: Insert if new, update if exists (by email)
user, created = await User.objects.upsert(
    email="john@example.com",  # Unique key for conflict detection
    defaults={'name': 'John Doe', 'is_active': True},  # Values for creation
    update_fields=['name', 'updated_at']  # Fields to update on conflict
)

if created:
    print(f"Created new user: {user.email}")
else:
    print(f"Updated existing user: {user.email}")
```

If `update_fields` is omitted, all fields specified in `defaults` will be updated on conflict.
