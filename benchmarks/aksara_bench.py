"""
Aksara ORM Benchmark Suite

Performance benchmarks for Aksara ORM operations including:
- Single record operations (create, read, update, delete)
- Bulk operations
- Relation queries (FK, M2M)
- select_related vs N+1 patterns
"""

import asyncio
import os
import sys
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aksara import Model, fields, CASCADE
from aksara.db import Database
from aksara.db.debug import capture_queries
from aksara.registry import ModelRegistry
from aksara.relations import RelationRegistry

from common import (
    DATABASE_URL,
    BENCH_USERS,
    BENCH_POSTS_PER_USER,
    BENCH_TAGS,
    BENCH_TAGS_PER_POST,
    BenchmarkSuite,
    BenchmarkResult,
    Timer,
    async_timer,
    USERS_TABLE,
    POSTS_TABLE,
    TAGS_TABLE,
    POST_TAGS_TABLE,
)


# --- Model Definitions ---

class BenchUser(Model):
    __tablename__ = USERS_TABLE
    name = fields.String(max_length=100)
    email = fields.Email(unique=True)


class BenchTag(Model):
    __tablename__ = TAGS_TABLE
    name = fields.String(max_length=100)


class BenchPost(Model):
    __tablename__ = POSTS_TABLE
    title = fields.String(max_length=200)
    content = fields.Text(nullable=True)
    author = fields.ForeignKey(BenchUser, on_delete=CASCADE, related_name="posts")
    tags = fields.ManyToMany(BenchTag, related_name="posts")


# --- Benchmark Functions ---

async def bench_create_single(db: Database) -> BenchmarkResult:
    """Benchmark single record creation."""
    async with async_timer() as timer:
        for i in range(100):
            user = await BenchUser.objects.create(
                name=f"SingleTest {i}",
                email=f"single{i}@test.com"
            )
    
    return BenchmarkResult(
        name="Create 100 records (single)",
        duration_ms=timer.elapsed_ms,
        operations=100,
    )


async def bench_read_single(db: Database) -> BenchmarkResult:
    """Benchmark single record reads by ID."""
    # First get some IDs
    users = await BenchUser.objects.filter(email__icontains="single").all()
    user_ids = [u.id for u in users[:100]]
    
    async with async_timer() as timer:
        for uid in user_ids:
            user = await BenchUser.objects.get(id=uid)
    
    return BenchmarkResult(
        name="Read 100 records (by ID)",
        duration_ms=timer.elapsed_ms,
        operations=len(user_ids),
    )


async def bench_read_filter(db: Database) -> BenchmarkResult:
    """Benchmark filtered reads."""
    async with async_timer() as timer:
        for i in range(50):
            users = await BenchUser.objects.filter(
                name__icontains="User"
            ).all()
    
    return BenchmarkResult(
        name="Filter 50 times",
        duration_ms=timer.elapsed_ms,
        operations=50,
    )


async def bench_update_single(db: Database) -> BenchmarkResult:
    """Benchmark single record updates."""
    users = await BenchUser.objects.filter(email__icontains="single").all()
    users_to_update = users[:100]
    
    async with async_timer() as timer:
        for user in users_to_update:
            user.name = f"Updated {user.name}"
            await user.save()
    
    return BenchmarkResult(
        name="Update 100 records (single)",
        duration_ms=timer.elapsed_ms,
        operations=len(users_to_update),
    )


async def bench_fk_no_preload(db: Database) -> BenchmarkResult:
    """Benchmark FK access WITHOUT select_related (N+1 pattern)."""
    # Get 100 posts
    all_posts = await BenchPost.objects.all()
    posts = all_posts[:100]
    
    async with async_timer() as timer:
        async with capture_queries() as log:
            for post in posts:
                # This triggers a query for each post
                author = await BenchUser.objects.get(id=post.author_id)
    
    return BenchmarkResult(
        name="FK access NO preload (100 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": log.count},
    )


async def bench_fk_with_select_related(db: Database) -> BenchmarkResult:
    """Benchmark FK access WITH select_related (batched)."""
    async with async_timer() as timer:
        async with capture_queries() as log:
            all_posts = await BenchPost.objects.select_related("author").all()
            posts = all_posts[:100]
            
            for post in posts:
                author = post.get_related("author")
    
    return BenchmarkResult(
        name="FK access WITH select_related (100 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": log.count},
    )


async def bench_m2m_no_preload(db: Database) -> BenchmarkResult:
    """Benchmark M2M access WITHOUT prefetch_related."""
    all_posts = await BenchPost.objects.all()
    posts = all_posts[:50]
    
    async with async_timer() as timer:
        async with capture_queries() as log:
            for post in posts:
                tags = await post.tags.all()
    
    return BenchmarkResult(
        name="M2M access NO preload (50 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": log.count},
    )


async def bench_m2m_with_prefetch(db: Database) -> BenchmarkResult:
    """Benchmark M2M access WITH prefetch_related."""
    async with async_timer() as timer:
        async with capture_queries() as log:
            all_posts = await BenchPost.objects.prefetch_related("tags").all()
            posts = all_posts[:50]
            
            for post in posts:
                tags = post.get_prefetched_m2m("tags")
    
    return BenchmarkResult(
        name="M2M access WITH prefetch_related (50 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": log.count},
    )


async def bench_complex_query(db: Database) -> BenchmarkResult:
    """Benchmark complex query with multiple conditions."""
    async with async_timer() as timer:
        for i in range(20):
            posts = await (
                BenchPost.objects
                .filter(title__icontains="Post")
                .filter(content__isnull=False)
                .all()
            )
    
    return BenchmarkResult(
        name="Complex query 20 times",
        duration_ms=timer.elapsed_ms,
        operations=20,
    )


async def bench_count(db: Database) -> BenchmarkResult:
    """Benchmark count operations."""
    async with async_timer() as timer:
        for i in range(50):
            count = await BenchPost.objects.filter(title__icontains="Post").count()
    
    return BenchmarkResult(
        name="Count with filter 50 times",
        duration_ms=timer.elapsed_ms,
        operations=50,
    )


# --- Main Runner ---

async def setup_database() -> Database:
    """Set up database and create tables."""
    db = Database(DATABASE_URL)
    await db.connect()
    
    # Drop and recreate tables
    await db.execute(f"DROP TABLE IF EXISTS {POST_TAGS_TABLE} CASCADE")
    await db.execute(f"DROP TABLE IF EXISTS {POSTS_TABLE} CASCADE")
    await db.execute(f"DROP TABLE IF EXISTS {TAGS_TABLE} CASCADE")
    await db.execute(f"DROP TABLE IF EXISTS {USERS_TABLE} CASCADE")
    
    # Create tables
    await db.execute(BenchUser.get_create_table_sql())
    await db.execute(BenchTag.get_create_table_sql())
    await db.execute(BenchPost.get_create_table_sql())
    
    # Create M2M join table
    m2m_field = BenchPost._m2m_fields['tags']
    await db.execute(m2m_field.get_join_table_sql())
    
    return db


async def seed_data():
    """Seed benchmark data."""
    import random
    
    print("Seeding benchmark data...")
    
    # Create users
    users = []
    for i in range(BENCH_USERS):
        user = await BenchUser.objects.create(
            name=f"User {i}",
            email=f"user{i}@benchmark.com"
        )
        users.append(user)
    
    # Create tags
    tags = []
    for i in range(BENCH_TAGS):
        tag = await BenchTag.objects.create(name=f"Tag {i}")
        tags.append(tag)
    
    # Create posts
    posts = []
    for user in users:
        for j in range(BENCH_POSTS_PER_USER):
            post = await BenchPost.objects.create(
                title=f"Post {j} by {user.name}",
                content=f"Content for post {j}",
                author_id=user.id
            )
            posts.append(post)
            
            # Add random tags
            selected_tags = random.sample(tags, min(BENCH_TAGS_PER_POST, len(tags)))
            await post.tags.add(*selected_tags)
    
    print(f"  Created {len(users)} users")
    print(f"  Created {len(tags)} tags")
    print(f"  Created {len(posts)} posts")


async def run_benchmarks():
    """Run all Aksara benchmarks."""
    print("\n" + "=" * 60)
    print("  Aksara ORM Benchmarks")
    print("=" * 60)
    
    # Clear registries
    ModelRegistry.clear()
    RelationRegistry.clear()
    
    # Setup
    db = await setup_database()
    await seed_data()
    
    suite = BenchmarkSuite(name="Aksara")
    
    # Run benchmarks
    benchmarks = [
        bench_create_single,
        bench_read_single,
        bench_read_filter,
        bench_update_single,
        bench_fk_no_preload,
        bench_fk_with_select_related,
        bench_m2m_no_preload,
        bench_m2m_with_prefetch,
        bench_complex_query,
        bench_count,
    ]
    
    for bench_fn in benchmarks:
        try:
            result = await bench_fn(db)
            suite.add(result)
            print(f"  ✓ {result}")
        except Exception as e:
            print(f"  ✗ {bench_fn.__name__}: {e}")
    
    # Cleanup
    await db.disconnect()
    
    suite.print_results()
    return suite


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
