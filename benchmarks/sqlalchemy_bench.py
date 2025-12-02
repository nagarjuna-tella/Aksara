"""
SQLAlchemy 2.0 Async Benchmark

Performance benchmarks comparing SQLAlchemy 2.0 async API.
"""

import asyncio
import os
import sys
import uuid

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Column, String, Text, ForeignKey, Table, select, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship, selectinload

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


# Convert postgresql:// to postgresql+asyncpg://
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


# --- SQLAlchemy Models ---

class Base(DeclarativeBase):
    pass


# M2M association table
post_tags_table = Table(
    POST_TAGS_TABLE,
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("post_id", UUID(as_uuid=True), ForeignKey(f"{POSTS_TABLE}.id", ondelete="CASCADE"), nullable=False),
    Column("tag_id", UUID(as_uuid=True), ForeignKey(f"{TAGS_TABLE}.id", ondelete="CASCADE"), nullable=False),
)


class SAUser(Base):
    __tablename__ = USERS_TABLE
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    
    posts = relationship("SAPost", back_populates="author")


class SATag(Base):
    __tablename__ = TAGS_TABLE
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)


class SAPost(Base):
    __tablename__ = POSTS_TABLE
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey(f"{USERS_TABLE}.id", ondelete="CASCADE"), nullable=False)
    
    author = relationship("SAUser", back_populates="posts")
    tags = relationship("SATag", secondary=post_tags_table)


# --- Benchmark Functions ---

async def bench_create_single(session_maker) -> BenchmarkResult:
    """Benchmark single record creation."""
    async with async_timer() as timer:
        for i in range(100):
            async with session_maker() as session:
                user = SAUser(name=f"SingleTest {i}", email=f"sa_single{i}@test.com")
                session.add(user)
                await session.commit()
    
    return BenchmarkResult(
        name="Create 100 records (single)",
        duration_ms=timer.elapsed_ms,
        operations=100,
    )


async def bench_read_single(session_maker) -> BenchmarkResult:
    """Benchmark single record reads by ID."""
    # First get some IDs
    async with session_maker() as session:
        result = await session.execute(
            select(SAUser).where(SAUser.email.contains("sa_single"))
        )
        users = result.scalars().all()
        user_ids = [u.id for u in users[:100]]
    
    async with async_timer() as timer:
        for uid in user_ids:
            async with session_maker() as session:
                result = await session.execute(select(SAUser).where(SAUser.id == uid))
                user = result.scalar_one()
    
    return BenchmarkResult(
        name="Read 100 records (by ID)",
        duration_ms=timer.elapsed_ms,
        operations=len(user_ids),
    )


async def bench_read_filter(session_maker) -> BenchmarkResult:
    """Benchmark filtered reads."""
    async with async_timer() as timer:
        for i in range(50):
            async with session_maker() as session:
                result = await session.execute(
                    select(SAUser).where(SAUser.name.contains("User"))
                )
                users = result.scalars().all()
    
    return BenchmarkResult(
        name="Filter 50 times",
        duration_ms=timer.elapsed_ms,
        operations=50,
    )


async def bench_update_single(session_maker) -> BenchmarkResult:
    """Benchmark single record updates."""
    # Get users to update
    async with session_maker() as session:
        result = await session.execute(
            select(SAUser).where(SAUser.email.contains("sa_single"))
        )
        users = result.scalars().all()
        user_ids = [u.id for u in users[:100]]
    
    async with async_timer() as timer:
        for uid in user_ids:
            async with session_maker() as session:
                result = await session.execute(select(SAUser).where(SAUser.id == uid))
                user = result.scalar_one()
                user.name = f"Updated {user.name}"
                await session.commit()
    
    return BenchmarkResult(
        name="Update 100 records (single)",
        duration_ms=timer.elapsed_ms,
        operations=len(user_ids),
    )


async def bench_fk_no_preload(session_maker) -> BenchmarkResult:
    """Benchmark FK access WITHOUT eager loading (N+1 pattern)."""
    # Get 100 posts
    async with session_maker() as session:
        result = await session.execute(select(SAPost))
        all_posts = result.scalars().all()
        post_author_ids = [(p.id, p.author_id) for p in all_posts[:100]]
    
    query_count = 0
    async with async_timer() as timer:
        for post_id, author_id in post_author_ids:
            async with session_maker() as session:
                # This is the N+1 pattern - separate query for each author
                result = await session.execute(select(SAUser).where(SAUser.id == author_id))
                author = result.scalar_one()
                query_count += 1
    
    return BenchmarkResult(
        name="FK access NO preload (100 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(post_author_ids),
        extra_info={"query_count": query_count},
    )


async def bench_fk_with_eager_load(session_maker) -> BenchmarkResult:
    """Benchmark FK access WITH selectinload (batched)."""
    async with async_timer() as timer:
        async with session_maker() as session:
            result = await session.execute(
                select(SAPost).options(selectinload(SAPost.author))
            )
            posts = result.scalars().all()[:100]
            
            for post in posts:
                author = post.author  # Already loaded
    
    return BenchmarkResult(
        name="FK access WITH selectinload (100 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": 2},  # 1 for posts, 1 for authors
    )


async def bench_m2m_no_preload(session_maker) -> BenchmarkResult:
    """Benchmark M2M access WITHOUT eager loading."""
    # Get 50 posts
    async with session_maker() as session:
        result = await session.execute(select(SAPost))
        all_posts = result.scalars().all()
        post_ids = [p.id for p in all_posts[:50]]
    
    query_count = 0
    async with async_timer() as timer:
        for post_id in post_ids:
            async with session_maker() as session:
                result = await session.execute(
                    select(SAPost).options(selectinload(SAPost.tags)).where(SAPost.id == post_id)
                )
                post = result.scalar_one()
                tags = post.tags
                query_count += 1
    
    return BenchmarkResult(
        name="M2M access NO preload (50 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(post_ids),
        extra_info={"query_count": query_count},
    )


async def bench_m2m_with_eager_load(session_maker) -> BenchmarkResult:
    """Benchmark M2M access WITH selectinload."""
    async with async_timer() as timer:
        async with session_maker() as session:
            result = await session.execute(
                select(SAPost).options(selectinload(SAPost.tags))
            )
            posts = result.scalars().all()[:50]
            
            for post in posts:
                tags = post.tags  # Already loaded
    
    return BenchmarkResult(
        name="M2M access WITH selectinload (50 posts)",
        duration_ms=timer.elapsed_ms,
        operations=len(posts),
        extra_info={"query_count": 2},
    )


async def bench_complex_query(session_maker) -> BenchmarkResult:
    """Benchmark complex query with multiple conditions."""
    async with async_timer() as timer:
        for i in range(20):
            async with session_maker() as session:
                result = await session.execute(
                    select(SAPost)
                    .where(SAPost.title.contains("Post"))
                    .where(SAPost.content.isnot(None))
                )
                posts = result.scalars().all()
    
    return BenchmarkResult(
        name="Complex query 20 times",
        duration_ms=timer.elapsed_ms,
        operations=20,
    )


async def bench_count(session_maker) -> BenchmarkResult:
    """Benchmark count operations."""
    async with async_timer() as timer:
        for i in range(50):
            async with session_maker() as session:
                result = await session.execute(
                    select(func.count()).select_from(SAPost).where(SAPost.title.contains("Post"))
                )
                count = result.scalar()
    
    return BenchmarkResult(
        name="Count with filter 50 times",
        duration_ms=timer.elapsed_ms,
        operations=50,
    )


# --- Main Runner ---

async def setup_database():
    """Set up database and create tables."""
    import random
    
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    
    # Drop and recreate tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    print("Seeding benchmark data...")
    
    # Create users
    users = []
    async with session_maker() as session:
        for i in range(BENCH_USERS):
            user = SAUser(name=f"User {i}", email=f"sa_user{i}@benchmark.com")
            session.add(user)
            users.append(user)
        await session.commit()
        # Refresh to get IDs
        for user in users:
            await session.refresh(user)
    
    # Create tags
    tags = []
    async with session_maker() as session:
        for i in range(BENCH_TAGS):
            tag = SATag(name=f"Tag {i}")
            session.add(tag)
            tags.append(tag)
        await session.commit()
        for tag in tags:
            await session.refresh(tag)
    
    # Create posts with tags
    async with session_maker() as session:
        for user in users:
            for j in range(BENCH_POSTS_PER_USER):
                post = SAPost(
                    title=f"Post {j} by {user.name}",
                    content=f"Content for post {j}",
                    author_id=user.id
                )
                # Add random tags
                selected_tags = random.sample(tags, min(BENCH_TAGS_PER_POST, len(tags)))
                post.tags = selected_tags
                session.add(post)
        await session.commit()
    
    print(f"  Created {len(users)} users")
    print(f"  Created {len(tags)} tags")
    print(f"  Created {len(users) * BENCH_POSTS_PER_USER} posts")
    
    return engine, session_maker


async def run_benchmarks():
    """Run all SQLAlchemy benchmarks."""
    print("\n" + "=" * 60)
    print("  SQLAlchemy 2.0 Async Benchmarks")
    print("=" * 60)
    
    engine, session_maker = await setup_database()
    
    suite = BenchmarkSuite(name="SQLAlchemy")
    
    # Run benchmarks
    benchmarks = [
        bench_create_single,
        bench_read_single,
        bench_read_filter,
        bench_update_single,
        bench_fk_no_preload,
        bench_fk_with_eager_load,
        bench_m2m_no_preload,
        bench_m2m_with_eager_load,
        bench_complex_query,
        bench_count,
    ]
    
    for bench_fn in benchmarks:
        try:
            result = await bench_fn(session_maker)
            suite.add(result)
            print(f"  ✓ {result}")
        except Exception as e:
            print(f"  ✗ {bench_fn.__name__}: {e}")
    
    # Cleanup
    await engine.dispose()
    
    suite.print_results()
    return suite


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
