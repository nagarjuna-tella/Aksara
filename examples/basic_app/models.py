"""
Example Models for CLI Testing

These models are used to test the CLI migration commands.
"""

from vidyut import Model, fields


class User(Model):
    """User model with common user fields."""
    
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100, nullable=True)
    is_active = fields.Boolean(default=True)
    metadata = fields.JSON(nullable=True)


class Post(Model):
    """Blog post model."""
    
    title = fields.String(max_length=200)
    content = fields.String(max_length=10000, nullable=True)
    is_published = fields.Boolean(default=False)
    view_count = fields.Integer(default=0)


class Article(Model):
    """Article model with more fields."""
    
    slug = fields.String(max_length=100, unique=True)
    headline = fields.String(max_length=300)
    body = fields.String(max_length=50000, nullable=True)
    author_name = fields.String(max_length=100, nullable=True)
    is_featured = fields.Boolean(default=False)
    tags = fields.JSON(nullable=True, default=list)
