"""
Tests for v0.5.45 ORM expressions and annotations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from aksara import Model, fields
from aksara.db.engine import Database
from aksara.db.expressions import CosineDistance, Count, EuclideanDistance, F, Q, Sum
from aksara.manager import QuerySet
from aksara.model.base import finalize_relations
from aksara.relations import RelationRegistry
from aksara.registry import ModelRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear model registry state before and after each test."""
    ModelRegistry.clear()
    RelationRegistry.clear()
    yield
    ModelRegistry.clear()
    RelationRegistry.clear()


class MetricRecord(Model):
    """Simple model used for ORM expression tests."""

    title = fields.String(max_length=200)
    views = fields.Integer(default=0)
    likes = fields.Integer(default=0)
    metadata = fields.JSON(default=dict)

    class Meta:
        table_name = "metric_records"


class TestQObjects:
    """Tests for recursive Q object compilation."""

    def test_q_object_compiles_nested_boolean_logic(self):
        qs = QuerySet(MetricRecord).filter(
            Q(title__icontains="admin") | ~Q(likes__lt=5),
            views__gte=10,
        )

        where_clause, values = qs._build_where_clause()

        assert 'WHERE' in where_clause
        assert 'OR' in where_clause
        assert 'NOT' in where_clause
        assert '"title" ILIKE $1' in where_clause
        assert '"likes" < $2' in where_clause
        assert '"views" >= $3' in where_clause
        assert values == ["%admin%", 5, 10]

    def test_f_expression_compiles_in_filter(self):
        qs = QuerySet(MetricRecord).filter(views__gt=F("likes"))

        where_clause, values = qs._build_where_clause()

        assert where_clause == 'WHERE "views" > "likes"'
        assert values == []

    def test_json_path_exact_compiles(self):
        qs = QuerySet(MetricRecord).filter(metadata__preferences__theme="dark")

        where_clause, values = qs._build_where_clause()

        assert where_clause == 'WHERE "metadata" -> $1 ->> $2 = $3'
        assert values == ["preferences", "theme", "dark"]

    def test_json_path_icontains_compiles(self):
        qs = QuerySet(MetricRecord).filter(metadata__profile__display_name__icontains="ada")

        where_clause, values = qs._build_where_clause()

        assert where_clause == 'WHERE "metadata" -> $1 ->> $2 ILIKE $3'
        assert values == ["profile", "display_name", "%ada%"]

    def test_json_path_numeric_lookup_compiles(self):
        qs = QuerySet(MetricRecord).filter(metadata__stats__score__gte=9)

        where_clause, values = qs._build_where_clause()

        assert where_clause == 'WHERE ("metadata" -> $1 ->> $2)::double precision >= $3'
        assert values == ["stats", "score", 9]


class TestAnnotations:
    """Tests for annotate() and aggregate() SQL generation."""

    def test_annotate_builds_reverse_fk_join_clause(self):
        class Post(Model):
            title = fields.String(max_length=200)

            class Meta:
                table_name = "posts"

        class Comment(Model):
            post = fields.ForeignKey(Post, related_name="comments")
            views = fields.Integer(default=0)

            class Meta:
                table_name = "comments"

        finalize_relations()

        qs = QuerySet(Post).annotate(
            comment_count=Count("comments"),
            total_comment_views=Sum("comments__views"),
        )

        join_state = qs._new_join_state()
        select_clause, values = qs._build_select_clause(join_state=join_state)
        join_clause = qs._build_join_clause(join_state)
        group_by_clause = qs._build_group_by_clause(join_state)

        assert values == []
        assert 'COUNT("comments__rel"."id") AS "comment_count"' in select_clause
        assert 'SUM("comments__rel"."views") AS "total_comment_views"' in select_clause
        assert (
            'LEFT JOIN "comments" AS "comments__rel" '
            'ON "comments__rel"."post_id" = "posts"."id"'
        ) in join_clause
        assert '"posts"."id"' in group_by_clause

    def test_annotate_builds_forward_m2m_join_clause(self):
        class Tag(Model):
            name = fields.String(max_length=100)

            class Meta:
                table_name = "tags"

        class Post(Model):
            title = fields.String(max_length=200)
            tags = fields.ManyToMany(Tag, related_name="posts")

            class Meta:
                table_name = "posts"

        finalize_relations()

        qs = QuerySet(Post).annotate(tag_count=Count("tags"))

        join_state = qs._new_join_state()
        select_clause, values = qs._build_select_clause(join_state=join_state)
        join_clause = qs._build_join_clause(join_state)

        assert values == []
        assert 'COUNT("tags__rel"."id") AS "tag_count"' in select_clause
        assert (
            'LEFT JOIN "posts_tags" AS "tags__through" '
            'ON "tags__through"."post_id" = "posts"."id"'
        ) in join_clause
        assert (
            'LEFT JOIN "tags" AS "tags__rel" '
            'ON "tags__rel"."id" = "tags__through"."tag_id"'
        ) in join_clause

    def test_annotate_builds_select_clause(self):
        qs = QuerySet(MetricRecord).annotate(
            total_views=Sum("views"),
            boosted_likes=F("likes") + 1,
        )

        select_clause, values = qs._build_select_clause()
        group_by_clause = qs._build_group_by_clause()

        assert select_clause.startswith('"metric_records".*')
        assert 'SUM("views") AS "total_views"' in select_clause
        assert '("likes" + $1) AS "boosted_likes"' in select_clause
        assert values == [1]
        assert group_by_clause.startswith('GROUP BY')
        assert '"views"' in group_by_clause

    def test_vector_distance_annotations_compile(self):
        class EmbeddingRecord(Model):
            title = fields.String(max_length=200)
            embedding = fields.Vector(dimensions=3)

            class Meta:
                table_name = "embedding_records"

        qs = QuerySet(EmbeddingRecord).annotate(
            cosine_distance=CosineDistance("embedding", [1, 2, 3]),
            euclidean_distance=EuclideanDistance("embedding", [3, 1, 2]),
        )

        select_clause, values = qs._build_select_clause()

        assert '"embedding" <=> CAST($1 AS vector)' in select_clause
        assert '"embedding" <-> CAST($2 AS vector)' in select_clause
        # v0.5.55: vector literals use high-precision repr(float) serialization,
        # so integers render as floats. Compare parsed numeric values.
        parsed = [
            [float(part) for part in literal.strip("[]").split(",")]
            for literal in values
        ]
        assert parsed == [[1.0, 2.0, 3.0], [3.0, 1.0, 2.0]]

    @pytest.mark.asyncio
    async def test_aggregate_returns_summary_dict(self, monkeypatch):
        fake_db = Mock()
        fake_db.fetchrow = AsyncMock(return_value={"total_views": 42, "row_count": 3})
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: fake_db))

        result = await QuerySet(MetricRecord).filter(likes__gte=1).aggregate(
            total_views=Sum("views"),
            row_count=Count("*"),
        )

        assert result == {"total_views": 42, "row_count": 3}
        query = fake_db.fetchrow.await_args.args[0]
        params = fake_db.fetchrow.await_args.args[1:]
        assert 'SELECT SUM("views") AS "total_views", COUNT(*) AS "row_count"' in query
        assert 'FROM "metric_records" WHERE "likes" >= $1' in query
        assert params == (1,)

    @pytest.mark.asyncio
    async def test_aggregate_builds_reverse_m2m_query(self, monkeypatch):
        class Tag(Model):
            name = fields.String(max_length=100)

            class Meta:
                table_name = "tags"

        class Post(Model):
            title = fields.String(max_length=200)
            tags = fields.ManyToMany(Tag, related_name="posts")

            class Meta:
                table_name = "posts"

        finalize_relations()

        fake_db = Mock()
        fake_db.fetchrow = AsyncMock(return_value={"post_count": 2})
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: fake_db))

        result = await QuerySet(Tag).aggregate(post_count=Count("posts"))

        assert result == {"post_count": 2}
        query = fake_db.fetchrow.await_args.args[0]
        assert 'COUNT("posts__rel"."id") AS "post_count"' in query
        assert (
            'LEFT JOIN "posts_tags" AS "posts__through" '
            'ON "posts__through"."tag_id" = "tags"."id"'
        ) in query
        assert (
            'LEFT JOIN "posts" AS "posts__rel" '
            'ON "posts__rel"."id" = "posts__through"."post_id"'
        ) in query


class TestUpdateExpressions:
    """Tests for F-expression updates and record hydration."""

    @pytest.mark.asyncio
    async def test_queryset_update_compiles_f_expression(self, monkeypatch):
        fake_db = Mock()
        fake_db.execute = AsyncMock(return_value="UPDATE 3")
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: fake_db))

        updated = await QuerySet(MetricRecord).filter(likes__gte=10).update(
            views=F("views") + 1,
            title="popular",
        )

        assert updated == 3
        query = fake_db.execute.await_args.args[0]
        params = fake_db.execute.await_args.args[1:]
        assert (
            'UPDATE "metric_records" SET "views" = ("views" + $1), '
            '"title" = $2, "updated_at" = $3'
        ) in query
        assert 'WHERE "likes" >= $4' in query
        assert params[0] == 1
        assert params[1] == "popular"
        assert isinstance(params[2], datetime)
        assert params[3] == 10

    def test_from_record_handles_iterator_keys_and_assigns_annotation_attributes(self):
        class FakeAsyncpgRecord:
            def __init__(self, values):
                self._values = values

            def keys(self):
                return iter(self._values.keys())

            def __getitem__(self, key):
                return self._values[key]

        record = FakeAsyncpgRecord({
            "id": uuid4(),
            "title": "Post",
            "views": 10,
            "likes": 4,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "score_delta": 6,
        })

        instance = MetricRecord._from_record(record)

        assert instance.score_delta == 6
        assert instance.views == 10

    @pytest.mark.asyncio
    async def test_model_insert_rejects_expression_values(self):
        instance = MetricRecord(title="Post", views=F("views") + 1, likes=1)

        with pytest.raises(ValueError, match="Expressions are only supported in update operations"):
            await instance._insert(Mock())
