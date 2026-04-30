"""
Blog Example - Models

Demonstrates:
- Post model with slug, tags (JSON array), publish workflow
- Comment model with FK relationship to Post
- AI metadata for Studio integration
"""

from aksara import Model, fields


class Post(Model):
    """
    Blog post with rich content support.
    
    Features:
    - Slugified URLs for SEO
    - Tags as JSON array for flexible categorization
    - Publish workflow with published_at timestamp
    - View counter for analytics
    """
    
    title = fields.String(
        max_length=200,
        ai_description="Post title displayed to readers",
    )
    slug = fields.String(
        max_length=200,
        unique=True,
        ai_description="URL-friendly version of title (e.g., my-first-post)",
    )
    content = fields.Text(
        ai_description="Full post content in Markdown or HTML",
    )
    excerpt = fields.String(
        max_length=500,
        nullable=True,
        ai_description="Short summary for listings and SEO",
    )
    tags = fields.JSON(
        default=[],
        ai_description="List of tags for categorization (e.g., ['python', 'tutorial'])",
    )
    is_published = fields.Boolean(
        default=False,
        ai_description="Whether the post is visible to readers",
    )
    published_at = fields.DateTime(
        nullable=True,
        ai_description="When the post was published",
    )
    view_count = fields.Integer(
        default=0,
        ai_description="Number of times the post has been viewed",
        ai_agent_writable=False,  # AI agents should not modify view counts
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the post was created",
    )
    updated_at = fields.DateTime(
        auto_now=True,
        ai_description="When the post was last modified",
    )
    
    class Meta:
        table_name = "posts"
        ai_name = "Post"
        ai_description = "Blog post with title, content, tags, and publish status"
        ai_agent_exposed = True


class Comment(Model):
    """
    Comment on a blog post.
    
    Features:
    - Linked to Post via ForeignKey
    - Supports anonymous comments (author_name)
    - Moderation via is_approved flag
    """
    
    post = fields.ForeignKey(
        "Post",
        on_delete="CASCADE",
        ai_description="The post this comment belongs to",
    )
    author_name = fields.String(
        max_length=100,
        ai_description="Display name of the commenter",
    )
    author_email = fields.String(
        max_length=255,
        nullable=True,
        ai_description="Optional email for notifications",
        ai_sensitive=True,  # PII — excluded from AI context and MCP exports
    )
    text = fields.Text(
        ai_description="Comment content",
    )
    is_approved = fields.Boolean(
        default=True,
        ai_description="Whether the comment is visible (for moderation)",
        ai_agent_writable=False,  # Moderation decisions should be made by humans, not AI agents
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the comment was posted",
    )
    
    class Meta:
        table_name = "comments"
        ai_name = "Comment"
        ai_description = "Comment on a blog post"
        ai_agent_exposed = True
