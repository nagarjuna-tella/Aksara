"""
Aksara Example App - Models

All models for the basic_app example.
Demonstrates v0.2+ features: AI metadata, ForeignKey relationships.
"""

from aksara import Model, fields


class User(Model):
    """
    User model with email, name, and active status.
    
    Demonstrates v0.2 AI metadata for field-level documentation.
    """
    
    email = fields.String(
        max_length=255, 
        unique=True,
        ai_description="User's email address for authentication",
        ai_sensitive=True,  # Won't be exposed to AI by default
    )
    name = fields.String(
        max_length=100, 
        nullable=True,
        ai_description="User's display name",
    )
    is_active = fields.Boolean(
        default=True,
        ai_description="Whether the user account is active",
    )
    metadata = fields.JSON(
        nullable=True,
        ai_description="Arbitrary user metadata as JSON",
    )
    
    class Meta:
        table_name = "users"
        # v0.2: AI metadata for the model
        ai_name = "User"
        ai_description = "System user accounts for authentication and authorization"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]


class Post(Model):
    """
    Blog post model with ForeignKey to User.
    
    Demonstrates v0.2 ForeignKey relationships.
    """
    
    title = fields.String(
        max_length=200,
        ai_description="Post title",
    )
    content = fields.String(
        max_length=10000, 
        nullable=True,
        ai_description="Post body content",
    )
    is_published = fields.Boolean(
        default=False,
        ai_description="Whether the post is publicly visible",
    )
    view_count = fields.Integer(
        default=0,
        ai_description="Number of times the post has been viewed",
        ai_agent_writable=False,  # AI shouldn't modify view counts
    )
    
    # v0.2: ForeignKey relationship to User
    author = fields.ForeignKey(
        User,
        on_delete="CASCADE",  # Delete posts when user is deleted
        nullable=True,  # Allow posts without authors for now
        ai_description="The user who authored this post",
    )
    
    class Meta:
        table_name = "posts"
        ai_name = "Post"
        ai_description = "Blog posts created by users"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]


class Article(Model):
    """
    Article model with tags.
    
    Demonstrates array fields via JSON.
    """
    
    title = fields.String(
        max_length=255,
        ai_description="Article title",
    )
    body = fields.String(
        max_length=50000, 
        nullable=True,
        ai_description="Full article body content",
    )
    tags = fields.JSON(
        nullable=True,
        ai_description="List of tags for categorization",
    )
    
    class Meta:
        table_name = "articles"
        ai_name = "Article"
        ai_description = "Long-form articles with rich content"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]
