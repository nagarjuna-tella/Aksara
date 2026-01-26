# Query Engine

Natural language to database queries.

---

## Overview

The Query Engine translates natural language into database queries:

```python
from vidyut.ai import QueryEngine

engine = QueryEngine()
result = await engine.query("Users who signed up this month")

print(result.data)  # Query results
print(result.sql)   # Generated SQL
```

---

## Quick Start

### Basic Queries

```python
from vidyut.ai import QueryEngine

engine = QueryEngine()

# Simple query
users = await engine.query("All active users")

# With conditions
posts = await engine.query("Posts published in the last week")

# With relations
comments = await engine.query("Comments on posts by John")
```

### View Generated SQL

```python
result = await engine.query(
    "Users with more than 10 posts",
    return_sql=True,
)

print(result.sql)
# SELECT users.* FROM users 
# JOIN posts ON posts.author_id = users.id 
# GROUP BY users.id 
# HAVING COUNT(posts.id) > 10
```

---

## Query Syntax

### Filtering

```python
# Equality
"Users named John"
"Posts with status 'published'"

# Comparison
"Orders over $100"
"Users older than 30"
"Posts with less than 5 comments"

# Date ranges
"Posts from last month"
"Users who signed up this week"
"Orders from January 2024"

# Null checks
"Users without a profile picture"
"Posts with no comments"
```

### Sorting

```python
# Ascending
"Users ordered by name"
"Posts sorted by date"

# Descending
"Newest posts first"
"Users by most recent login"
"Top selling products"
```

### Limiting

```python
# Count limits
"First 10 users"
"Top 5 posts by views"
"Last 20 orders"

# Unique
"Unique email domains"
"Distinct categories"
```

### Aggregations

```python
# Count
"Number of active users"
"How many posts per category"

# Sum
"Total revenue this month"
"Sum of all order amounts"

# Average
"Average order value"
"Mean user age"

# Min/Max
"Cheapest product"
"Most expensive order"
"Oldest user"
```

### Relations

```python
# Foreign keys
"Posts by user John"
"Comments on post 'Hello World'"
"Orders for customer 123"

# Many-to-many
"Posts tagged with 'python'"
"Users in the 'admin' group"

# Nested
"Comments on posts by users from New York"
```

---

## Query Options

### Read-Only Mode

```python
# Default: read-only (safe)
engine = QueryEngine(read_only=True)

# Allow modifications (be careful!)
engine = QueryEngine(read_only=False)
result = await engine.query("Delete inactive users")
```

### Result Limits

```python
result = await engine.query(
    "All users",
    limit=100,  # Max results
)
```

### Timeout

```python
result = await engine.query(
    "Complex aggregation",
    timeout=30,  # Seconds
)
```

### Dry Run

```python
# Get SQL without executing
result = await engine.query(
    "Users with posts",
    dry_run=True,
)

print(result.sql)     # The SQL query
print(result.data)    # None (not executed)
print(result.valid)   # True if SQL is valid
```

---

## Result Object

### Properties

```python
result = await engine.query("Active users")

print(result.data)           # List of records
print(result.count)          # Number of results
print(result.sql)            # Generated SQL
print(result.execution_time) # Query time in ms
print(result.model)          # Primary model queried
```

### Iteration

```python
result = await engine.query("All posts")

for post in result:
    print(post.title)
```

### Conversion

```python
# To DataFrame
df = result.to_dataframe()

# To JSON
json_data = result.to_json()

# To dict
records = result.to_dict()
```

---

## Context-Aware Queries

### Using Context Engine

```python
from vidyut.ai import QueryEngine, ContextEngine

context_engine = ContextEngine()
query_engine = QueryEngine()

# Gather schema context
context = await context_engine.gather("User purchases")

# Query with context (better accuracy)
result = await query_engine.query(
    "Users who bought products in Electronics category",
    context=context,
)
```

### Model Hints

```python
# Specify models explicitly
result = await engine.query(
    "Items over $50",
    models=["Product", "Order"],  # Hint which models to use
)
```

---

## Safety Features

### SQL Injection Prevention

All queries are parameterized:

```python
result = await engine.query("User named 'Robert'; DROP TABLE users;--'")
# Safely handled as: WHERE name = %s
# Parameter: "Robert'; DROP TABLE users;--'"
```

### Query Validation

```python
try:
    result = await engine.query("Invalid gibberish query")
except QueryParseError as e:
    print(f"Could not understand: {e}")
```

### Dangerous Query Detection

```python
result = await engine.query(
    "Delete all users",
    allow_destructive=False,  # Default
)
# Raises: DestructiveQueryError
```

### Confirmation for Modifications

```python
result = await engine.query(
    "Update all posts to published",
    require_confirmation=True,
)

if result.requires_confirmation:
    print(f"This will affect {result.affected_count} rows")
    if confirm():
        result = await result.execute()
```

---

## Error Handling

### Query Parse Errors

```python
from vidyut.ai.exceptions import QueryParseError

try:
    result = await engine.query("@#$%^&*")
except QueryParseError as e:
    print(f"Could not parse: {e.message}")
    print(f"Suggestions: {e.suggestions}")
```

### Ambiguous Queries

```python
from vidyut.ai.exceptions import AmbiguousQueryError

try:
    result = await engine.query("Items")  # Could be Product, Order, etc.
except AmbiguousQueryError as e:
    print(f"Ambiguous: {e.message}")
    print(f"Did you mean: {e.candidates}")
```

### Execution Errors

```python
from vidyut.ai.exceptions import QueryExecutionError

try:
    result = await engine.query("Posts with invalid_field")
except QueryExecutionError as e:
    print(f"Execution failed: {e.message}")
    print(f"SQL: {e.sql}")
```

---

## CLI Usage

### Interactive Query

```bash
vidyut ai query "Active users"
```

Output:
```
📊 Query: Active users
📝 SQL: SELECT * FROM users WHERE is_active = true

Found 150 results:

| id  | email              | name     | is_active |
|-----|-------------------|----------|-----------|
| 1   | john@example.com  | John     | true      |
| 2   | jane@example.com  | Jane     | true      |
...
```

### Export Results

```bash
# To CSV
vidyut ai query "All orders" --output orders.csv

# To JSON
vidyut ai query "All orders" --output orders.json
```

### SQL Only

```bash
vidyut ai query "Users with posts" --sql-only

# Output: SELECT * FROM users WHERE EXISTS (SELECT 1 FROM posts WHERE ...)
```

---

## Examples

### E-commerce Queries

```python
# Revenue analysis
"Total revenue by month this year"
"Top 10 selling products"
"Average order value per customer"
"Orders with shipping delays"

# Customer insights
"Customers who haven't ordered in 6 months"
"Most valuable customers by lifetime spend"
"New customers this quarter"
```

### Blog Queries

```python
# Content analysis
"Most commented posts"
"Posts with no views"
"Authors ranked by total views"
"Tags used more than 10 times"

# Engagement
"Comments per post average"
"Posts published by day of week"
"User engagement trend over time"
```

### SaaS Queries

```python
# User activity
"Daily active users last 30 days"
"Users who logged in but took no action"
"Feature usage by plan type"

# Subscription
"MRR by month"
"Churn rate this quarter"
"Trials that converted to paid"
```

---

## Configuration

```python
# settings.py
VIDYUT = {
    "AI_QUERY_ENGINE": {
        # Safety
        "read_only": True,
        "allow_destructive": False,
        "require_confirmation_for_updates": True,
        
        # Limits
        "default_limit": 100,
        "max_limit": 1000,
        "timeout_seconds": 30,
        
        # Logging
        "log_queries": True,
        "log_sql": True,
    },
}
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Context Engine](context-engine.md)
- [Tools](tools.md)
- [Querying](../orm/querying.md) — ORM query reference
