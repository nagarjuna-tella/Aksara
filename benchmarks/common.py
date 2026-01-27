"""
Benchmarks Common Utilities

Shared schema, timing helpers, and test data generation
for ORM performance benchmarks.
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, List, Dict, Optional
from functools import wraps

# Number of records to create for benchmarks
BENCH_USERS = 100
BENCH_POSTS_PER_USER = 10
BENCH_TAGS = 20
BENCH_TAGS_PER_POST = 3


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    duration_ms: float
    operations: int = 1
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def ops_per_sec(self) -> float:
        """Operations per second."""
        return (self.operations / self.duration_ms) * 1000
    
    def __str__(self) -> str:
        return (
            f"{self.name}: {self.duration_ms:.2f}ms "
            f"({self.ops_per_sec:.0f} ops/sec)"
        )


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""
    name: str
    results: List[BenchmarkResult] = field(default_factory=list)
    
    def add(self, result: BenchmarkResult) -> None:
        """Add a result to the suite."""
        self.results.append(result)
    
    def print_results(self) -> None:
        """Print formatted benchmark results."""
        print(f"\n{'=' * 60}")
        print(f"  {self.name} Benchmark Results")
        print(f"{'=' * 60}")
        
        for result in self.results:
            print(f"  {result}")
        
        print(f"{'=' * 60}\n")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "suite": self.name,
            "results": [
                {
                    "name": r.name,
                    "duration_ms": r.duration_ms,
                    "operations": r.operations,
                    "ops_per_sec": r.ops_per_sec,
                    **r.extra_info,
                }
                for r in self.results
            ],
        }


class Timer:
    """Simple timer context manager."""
    
    def __init__(self):
        self.start: float = 0
        self.end: float = 0
    
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.end = time.perf_counter()
    
    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds."""
        return (self.end - self.start) * 1000


@asynccontextmanager
async def async_timer():
    """Async timer context manager."""
    timer = Timer()
    timer.start = time.perf_counter()
    try:
        yield timer
    finally:
        timer.end = time.perf_counter()


def benchmark(name: str, operations: int = 1):
    """Decorator to benchmark an async function."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> BenchmarkResult:
            async with async_timer() as timer:
                result = await func(*args, **kwargs)
            
            return BenchmarkResult(
                name=name,
                duration_ms=timer.elapsed_ms,
                operations=operations,
                extra_info={"result": result} if result else {},
            )
        return wrapper
    return decorator


# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/aksara_bench")


# Common table names used by all benchmarks
USERS_TABLE = "bench_users"
POSTS_TABLE = "bench_posts"
TAGS_TABLE = "bench_tags"
POST_TAGS_TABLE = "bench_post_tags"


# Schema SQL for raw SQL benchmarks
CREATE_TABLES_SQL = f"""
-- Users
CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tags
CREATE TABLE IF NOT EXISTS {TAGS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL
);

-- Posts
CREATE TABLE IF NOT EXISTS {POSTS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    content TEXT,
    author_id UUID NOT NULL REFERENCES {USERS_TABLE}(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Post-Tags M2M
CREATE TABLE IF NOT EXISTS {POST_TAGS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES {POSTS_TABLE}(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES {TAGS_TABLE}(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (post_id, tag_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_{POSTS_TABLE}_author_id ON {POSTS_TABLE}(author_id);
CREATE INDEX IF NOT EXISTS idx_{POST_TAGS_TABLE}_post_id ON {POST_TAGS_TABLE}(post_id);
CREATE INDEX IF NOT EXISTS idx_{POST_TAGS_TABLE}_tag_id ON {POST_TAGS_TABLE}(tag_id);
"""


DROP_TABLES_SQL = f"""
DROP TABLE IF EXISTS {POST_TAGS_TABLE} CASCADE;
DROP TABLE IF EXISTS {POSTS_TABLE} CASCADE;
DROP TABLE IF EXISTS {TAGS_TABLE} CASCADE;
DROP TABLE IF EXISTS {USERS_TABLE} CASCADE;
"""


async def seed_data_raw(execute_fn: Callable, fetch_fn: Callable):
    """
    Seed benchmark data using raw SQL.
    
    Args:
        execute_fn: Function to execute SQL (async)
        fetch_fn: Function to fetch results (async)
    
    Returns:
        Dict with user_ids, post_ids, tag_ids
    """
    import random
    
    # Create users
    user_ids = []
    for i in range(BENCH_USERS):
        result = await fetch_fn(
            f"INSERT INTO {USERS_TABLE} (name, email) VALUES ($1, $2) RETURNING id",
            f"User {i}",
            f"user{i}@example.com"
        )
        user_ids.append(result['id'])
    
    # Create tags
    tag_ids = []
    for i in range(BENCH_TAGS):
        result = await fetch_fn(
            f"INSERT INTO {TAGS_TABLE} (name) VALUES ($1) RETURNING id",
            f"Tag {i}"
        )
        tag_ids.append(result['id'])
    
    # Create posts for each user
    post_ids = []
    for user_id in user_ids:
        for j in range(BENCH_POSTS_PER_USER):
            result = await fetch_fn(
                f"INSERT INTO {POSTS_TABLE} (title, content, author_id) VALUES ($1, $2, $3) RETURNING id",
                f"Post {j} by {user_id}",
                f"Content for post {j}",
                user_id
            )
            post_ids.append(result['id'])
    
    # Add random tags to posts
    for post_id in post_ids:
        selected_tags = random.sample(tag_ids, min(BENCH_TAGS_PER_POST, len(tag_ids)))
        for tag_id in selected_tags:
            await execute_fn(
                f"INSERT INTO {POST_TAGS_TABLE} (post_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                post_id,
                tag_id
            )
    
    return {
        "user_ids": user_ids,
        "post_ids": post_ids,
        "tag_ids": tag_ids,
    }


def print_comparison(results: Dict[str, BenchmarkSuite]):
    """Print comparison table of benchmark suites."""
    if not results:
        return
    
    # Get all benchmark names from first suite
    first_suite = list(results.values())[0]
    bench_names = [r.name for r in first_suite.results]
    
    print(f"\n{'=' * 80}")
    print("  Benchmark Comparison")
    print(f"{'=' * 80}")
    
    # Header
    header = f"{'Benchmark':<30}"
    for suite_name in results.keys():
        header += f" {suite_name:>14}"
    print(header)
    print("-" * 80)
    
    # Results
    for bench_name in bench_names:
        row = f"{bench_name:<30}"
        for suite in results.values():
            for r in suite.results:
                if r.name == bench_name:
                    row += f" {r.duration_ms:>12.2f}ms"
                    break
            else:
                row += " " * 14 + "N/A"
        print(row)
    
    print(f"{'=' * 80}\n")
