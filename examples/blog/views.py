"""
Blog Example - Views

ViewSets for Post and Comment with custom actions.
Demonstrates:
- ModelViewSet for CRUD
- Custom publish action
- Tag filtering
"""

from datetime import datetime
from aksara import ModelViewSet, action, Request
from .models import Post, Comment
from .serializers import PostSerializer, PostListSerializer, CommentSerializer


class PostViewSet(ModelViewSet):
    """
    ViewSet for blog posts.
    
    Endpoints:
        GET    /api/posts/              - List all posts
        POST   /api/posts/              - Create a post
        GET    /api/posts/{id}/         - Get a post
        PUT    /api/posts/{id}/         - Update a post
        DELETE /api/posts/{id}/         - Delete a post
        POST   /api/posts/{id}/publish/ - Publish a post
        POST   /api/posts/{id}/view/    - Increment view count
    
    Query Parameters:
        ?is_published=true       - Filter by publish status
        ?tags__contains=python   - Filter by tag
    """
    
    model = Post
    serializer_class = PostSerializer
    prefix = "/api/posts"
    tags = ["Posts"]
    ai_exposed = True
    
    @action(detail=True, methods=["POST"])
    async def publish(self, pk: str, request: Request):
        """
        Publish a post.
        
        Sets is_published=True and records published_at timestamp.
        """
        post = await self.model.objects.get(id=pk)
        post.is_published = True
        post.published_at = datetime.utcnow()
        await post.save()
        return {
            "status": "published",
            "id": str(post.id),
            "published_at": post.published_at.isoformat()
        }
    
    @action(detail=True, methods=["POST"])
    async def unpublish(self, pk: str, request: Request):
        """Unpublish a post."""
        post = await self.model.objects.get(id=pk)
        post.is_published = False
        await post.save()
        return {"status": "unpublished", "id": str(post.id)}
    
    @action(detail=True, methods=["POST"])
    async def view(self, pk: str, request: Request):
        """Increment view count for a post."""
        post = await self.model.objects.get(id=pk)
        post.view_count += 1
        await post.save()
        return {"view_count": post.view_count}
    
    @action(detail=False, methods=["GET"])
    async def published(self, request: Request):
        """List only published posts."""
        posts = await self.model.objects.filter(is_published=True).all()
        return [PostListSerializer.from_model(p) for p in posts]
    
    @action(detail=False, methods=["GET"])
    async def by_tag(self, request: Request):
        """
        List posts by tag.
        
        Usage: GET /api/posts/by_tag/?tag=python
        """
        tag = request.query_params.get("tag")
        if not tag:
            return {"error": "tag parameter required"}
        
        # Note: JSON contains filtering - implementation depends on DB
        posts = await self.model.objects.all()
        filtered = [p for p in posts if tag in (p.tags or [])]
        return [PostListSerializer.from_model(p) for p in filtered]


class CommentViewSet(ModelViewSet):
    """
    ViewSet for comments.
    
    Endpoints:
        GET    /api/comments/           - List all comments
        POST   /api/comments/           - Create a comment
        GET    /api/comments/{id}/      - Get a comment
        PUT    /api/comments/{id}/      - Update a comment
        DELETE /api/comments/{id}/      - Delete a comment
    
    Query Parameters:
        ?post_id=<uuid>          - Filter by post
        ?is_approved=true        - Filter by approval status
    """
    
    model = Comment
    serializer_class = CommentSerializer
    prefix = "/api/comments"
    tags = ["Comments"]
    ai_exposed = True
    
    @action(detail=True, methods=["POST"])
    async def approve(self, pk: str, request: Request):
        """Approve a comment."""
        comment = await self.model.objects.get(id=pk)
        comment.is_approved = True
        await comment.save()
        return {"status": "approved", "id": str(comment.id)}
    
    @action(detail=True, methods=["POST"])
    async def reject(self, pk: str, request: Request):
        """Reject (hide) a comment."""
        comment = await self.model.objects.get(id=pk)
        comment.is_approved = False
        await comment.save()
        return {"status": "rejected", "id": str(comment.id)}
