"""
Migration: v033_initial
Generated: 2025-11-29T23:02:54.409467
"""

from vidyut.migrations import Migration
from vidyut.migrations import operations as op


class Migration(Migration):
    """
    Auto-generated migration for models: User, Post, Article
    """
    
    dependencies = []
    
    operations = [
        op.CreateTable(
            name="users",
            fields=[
            ("email", op.StringField(255, unique=True)),
            ("name", op.StringField(100, nullable=True)),
            ("is_active", op.BooleanField(default=True)),
            ("metadata", op.JSONField(nullable=True)),
            ("id", op.UUIDField(primary_key=True)),
            ("created_at", op.DateTimeField(auto_now_add=True)),
            ("updated_at", op.DateTimeField(auto_now=True)),
            ],
        ),
        op.CreateTable(
            name="posts",
            fields=[
            ("title", op.StringField(200)),
            ("content", op.StringField(10000, nullable=True)),
            ("is_published", op.BooleanField(default=False)),
            ("view_count", op.IntegerField(default=0)),
            ("author_id", op.ForeignKeyField('users', on_delete='CASCADE', nullable=True)),
            ("id", op.UUIDField(primary_key=True)),
            ("created_at", op.DateTimeField(auto_now_add=True)),
            ("updated_at", op.DateTimeField(auto_now=True)),
            ],
        ),
        op.CreateTable(
            name="articles",
            fields=[
            ("title", op.StringField(255)),
            ("body", op.StringField(50000, nullable=True)),
            ("tags", op.JSONField(nullable=True)),
            ("id", op.UUIDField(primary_key=True)),
            ("created_at", op.DateTimeField(auto_now_add=True)),
            ("updated_at", op.DateTimeField(auto_now=True)),
            ],
        ),
    ]
