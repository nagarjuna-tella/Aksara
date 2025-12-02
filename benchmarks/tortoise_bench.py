"""
Tortoise ORM Benchmark

Performance benchmarks comparing Tortoise ORM async API.
"""

import asyncio
import os
import sys
import uuid

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tortoise import Tortoise, fields
from tortoise.models import Model

from common import (
    DATABASE_URL,
    BenchmarkSuite,
    BenchmarkResult,
    async_timer,
    BENCH_USERS,
    BENCH_POSTS_PER_USER,
    BENCH_TAGS,
    BENCH_TAGS_PER_POST,
    USERS_TABLE,
    POSTS_TABLE,
    TAGS_TABLE,
    POST_TAGS_TABLE,
)


# --- Tortoise Models ---

class TortUser(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    name = fields.CharField(max_length=100)
    email = fields.CharField(max_length=255, unique=True)
    
    class Meta:
        table = USERS_TABLE


class TortTag(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    name = fields.CharField(max_length=100)
    
    class Meta:
        table = TAGS_TABLE


class TortPost(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    title = fields.CharField(max_length=200)
    content = fields.TextField(null=True)
    author = fields.ForeignKeyField("models.TortUser", related_name="posts", on_delete=fields.CASCADE)
    tags = fields.ManyToManyField("models.TortTag", related_name="posts", through=POST_TAGS_TABLE)
    
    class Meta:
        table = POSTS_TABLE


# --- Benchmark Functions ---

async def bench_create_single() -> BenchmarkResult:
    """Benchmark single record creation."""
    async with async_timer() as timer:
        for i in range(100):
            await TortUser.create(name=f"SingleTest {i}", email=f"tort_single{i}@test.com")
    
    return BenchmarkResult(
        name="Create 100 records (single)",
        duration_ms=timer.elapsed_ms,
        operations=100,
    )


async def bench_read_single() -> BenchmarkResult:
    """Benchmark single record reads by ID."""
    # First get some IDs
    users = await TortUser.filter(email__icontains="tort_single").limit(100)
    user_ids = [u.id for u in users]
    
    async with async_timer() as timer:
        for uid in user_ids:
            user = await TortUser.get(id=uid)
    
    return BenchmarkResult(
        name="Read 100 records (by ID)",
        duration_ms=timer.elapsed_ms,
        operations=len(user_ids),
    )


async def bench_read_filter() -> BenchmarkResult:
    """Benchmark filtered reads."""
    async with async_timer() as timer:
        for i in range(50):
            users = await TortUser.filter(name__icontains="User").all()
    
    return BenchmarkResult(
        name="Filter 50 times",
        duration_ms=timer.elapsed_ms,
        operations=50,
    )


async def bench_update_single() -> BenchmarkResult:
    """Benchmark single record updates."""
    users = await TortUser.filter(email__icontains="tort_single").limit(100)
    
    async with async_timer() as timer:
        for user in users:
            user.name = f"Updated {user.name}"
            await user.save()
    
    return BenchmarkResult(
        name="Update 100 records (single)",
        duration_ms=timer.elapsed_ms,
        operations=len(users),
    )


async def bench_fk_no_preload() -> BenchmarkResult:
    """Benchmark FK access WITHOUT prefetch (N+1 pattern)."""
    # Get 100 posts
    all_posts = await TortPost.all().limit(100)
    
    query_count = 0
    async with async_timer() as timer:
        for post in all_posts:
            # This triggers a query for each post (N+1)
            author = await post.author
            query_count += 1
    
    return BenchmarkResult(
        name="FK access NO preload (100 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(all_posts),
        extra_info={"query_count": query_count},
    )


async def bench_fk_with_prefetch() -> BenchmarkResult:
    """Benchmark FK access WITH prefetch_related."""
    async with async_timer() as timer:
        posts = await TortPost.all().prefetch_related("author").limit(100)
        
        for post in posts:
            author = post.author  # Already loaded
    
    return BenchmarkResult(
        name="FK access WITH prefetch (100 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": 2},
    )


async def bench_m2m_no_preload() -> BenchmarkResult:
    """Benchmark M2M access WITHOUT prefetch."""
    all_posts = await TortPost.all().limit(50)
    
    query_count = 0
    async with async_timer() as timer:
        for post in all_posts:
            tags = await post.tags.all()
            query_count += 1
    
    return BenchmarkResult(
        name="M2M access NO preload (50 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(all_posts),
        extra_info={"query_count": query_count},
    )


async def bench_m2m_with_prefetch() -> BenchmarkResult:
    """Benchmark M2M access WITH prefetch_related."""
    async with async_timer() as timer:
        posts = await TortPost.all().prefetch_related("tags").limit(50)
        
        for post in posts:
            tags = post.tags  # Already loaded
    
    return BenchmarkResult(
        name="M2M access WITH prefetch (50 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": 2},
    )


async def bench_complex_query() -> BenchmarkResult:
    """Benchmark complex query with multiple conditions."""
    async with async_timer() as timer:
        for i in range(20):
            posts = await TortPost.filter(
                title__icontains="Post",
                content__not_isnull=True
            ).all()
    
    return BenchmarkResult(
        name="Complex query 20 times",
        duration_ms=timer.elapsed_ms,
        operations=20,
    )


async def bench_count() -> BenchmarkResult:
    """Benchmark count operations."""
    async with async_timer() as timer:
        for i in range(50):
            count = await TortPost.filter(title__icontains="Post").count()
    
    return BenchmarkResult(
        name="Count with filter 50 times",
        duration_ms=timer.elapsed_ms,
        operations=50,
    )


# --- Main Runner ---

async def setup_database():
    """Set up database and create tables."""
    import random
    
    # Initialize Tortoise with explicit model paths
    await Tortoise.init(
        db_url=DATABASE_URL.replace("postgresql://", "asyncpg://"),
        modules={"models": ["tortoise_bench"]}
    )
    
    # Get connection and drop existing tables
    conn = Tortoise.get_connection("default")
    await conn.execute_script(f"""
        DROP TABLE IF EXISTS "{POST_TAGS_TABLE}" CASCADE;
        DROP TABLE IF EXISTS "{POSTS_TABLE}" CASCADE;
        DROP TABLE IF EXISTS "{TAGS_TABLE}" CASCADE;
        DROP TABLE IF EXISTS "{USERS_TABLE}" CASCADE;
    """)
    
    # Recreate schema
    await Tortoise.generate_schemas(safe=False)
    
    print("Seeding benchmark data...")
    
    # Create users
    users = []
    for i in range(BENCH_USERS):
        user = await TortUser.create(name=f"User {i}", email=f"tort_user{i}@benchmark.com")
        users.append(user)
    
    # Create tags
    tags = []
    for i in range(BENCH_TAGS):
        tag = await TortTag.create(name=f"Tag {i}")
        tags.append(tag)
    
    # Create posts with tags
    for user in users:
        for j in range(BENCH_POSTS_PER_USER):
            post = await TortPost.create(
                title=f"Post {j} by {user.name}",
                content=f"Content for post {j}",
                author=user
            )
            # Add random tags
            selected_tags = random.sample(tags, min(BENCH_TAGS_PER_POST, len(tags)))
            await post.tags.add(*selected_tags)
    
    print(f"  Created {len(users)} users")
    print(f"  Created {len(tags)} tags")
    print(f"  Created {len(users) * BENCH_POSTS_PER_USER} posts")


async def run_benchmarks():
    """Run all Tortoise benchmarks."""
    print("\n" + "=" * 60)
    print("  Tortoise ORM Benchmarks")
    print("=" * 60)
    
    await setup_database()
    
    suite = BenchmarkSuite(name="Tortoise")
    
    # Run benchmarks
    benchmarks = [
        bench_create_single,
        bench_read_single,
        bench_read_filter,
        bench_update_single,
        bench_fk_no_preload,
        bench_fk_with_prefetch,
        bench_m2m_no_preload,
        bench_m2m_with_prefetch,
        bench_complex_query,
        bench_count,
    ]
    
    for bench_fn in benchmarks:
        try:
            result = await bench_fn()
            suite.add(result)
            print(f"  ✓ {result}")
        except Exception as e:
            print(f"  ✗ {bench_fn.__name__}: {e}")
    
    # Cleanup
    await Tortoise.close_connections()
    
    suite.print_results()
    return suite


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
