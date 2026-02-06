"""
Blog Example - Views (v0.5.8)

ViewSets for Post and Comment with custom actions.
Demonstrates:
- ModelViewSet for CRUD
- API key authentication
- Pagination and ordering
- AI-aware endpoints
- Custom publish action
"""

from datetime import datetime
from typing import Optional
from aksara import ModelViewSet, action, Request
from fastapi import Depends, Query
from .models import Post, Comment
from .serializers import PostSerializer, PostListSerializer, CommentSerializer
from .auth import require_api_key
from .settings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

# =============================================================================
# Stopwords for tag suggestion (simple rule-based)
# =============================================================================
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "it", "its",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they",
    "what", "which", "who", "whom", "how", "when", "where", "why", "all",
    "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
}


def extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
    """
    Extract candidate keywords from text using simple rules.
    
    - Splits by whitespace and punctuation
    - Removes stopwords
    - Filters short words and returns unique lowercase words
    """
    if not text:
        return []
    
    # Basic tokenization: split on non-alphanumeric
    import re
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Remove stopwords and deduplicate
    keywords = []
    seen = set()
    for word in words:
        if word not in STOPWORDS and word not in seen:
            seen.add(word)
            keywords.append(word)
            if len(keywords) >= max_keywords:
                break
    
    return keywords


class PostViewSet(ModelViewSet):
    """
    ViewSet for blog posts.
    
    Authentication:
        All endpoints require X-API-Key header.
    
    Endpoints:
        GET    /api/posts/                      - List posts (paginated)
        POST   /api/posts/                      - Create a post
        GET    /api/posts/{id}/                 - Get a post
        PUT    /api/posts/{id}/                 - Update a post
        DELETE /api/posts/{id}/                 - Delete a post
        POST   /api/posts/{id}/publish/         - Publish a post
        POST   /api/posts/{id}/unpublish/       - Unpublish a post
        POST   /api/posts/{id}/view/            - Increment view count
        GET    /api/posts/{id}/ai-suggest-tags/ - AI: suggest tags
    
    Query Parameters for list:
        ?page=1              - Page number (default: 1)
        ?page_size=10        - Items per page (default: 10, max: 100)
        ?order_by=-created_at - Ordering (default: -created_at)
        ?is_published=true   - Filter by publish status
    """
    
    model = Post
    serializer_class = PostSerializer
    prefix = "/api/posts"
    tags = ["Blog API"]
    ai_exposed = True
    
    # Apply auth to all endpoints in this ViewSet
    dependencies = [Depends(require_api_key)]
    
    async def list(
        self,
        request: Request,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
        order_by: str = Query("-created_at", description="Order by field (prefix with - for descending)"),
        is_published: Optional[bool] = Query(None, description="Filter by publish status"),
    ):
        """
        List posts with pagination and ordering.
        
        Returns paginated response with:
        - results: list of posts
        - page: current page number
        - page_size: items per page
        - total: total count of matching posts
        """
        # Build query
        queryset = self.model.objects
        
        # Apply filter
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published)
        
        # Get total count
        all_posts = await queryset.all()
        total = len(all_posts)
        
        # Apply ordering
        if order_by.startswith("-"):
            field = order_by[1:]
            posts = sorted(all_posts, key=lambda p: getattr(p, field, None) or "", reverse=True)
        else:
            posts = sorted(all_posts, key=lambda p: getattr(p, order_by, None) or "")
        
        # Apply pagination
        offset = (page - 1) * page_size
        paginated = posts[offset:offset + page_size]
        
        return {
            "results": [PostListSerializer.from_model(p).model_dump() for p in paginated],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    
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
        return [PostListSerializer.from_model(p).model_dump() for p in posts]
    
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
        return [PostListSerializer.from_model(p).model_dump() for p in filtered]
    
    # =========================================================================
    # AI-Aware Endpoint (v0.5.8)
    # =========================================================================
    
    @action(
        detail=True,
        methods=["GET"],
        path="ai-suggest-tags",
        name="suggest_tags_for_post",
        description="Analyze a blog post and suggest candidate tags based on content keywords. Returns structured data for LLM consumption.",
        ai_exposed=True,
    )
    async def ai_suggest_tags(self, pk: str, request: Request):
        """
        AI Tool: Suggest tags for a blog post.
        
        Analyzes the post's title and content to extract candidate tags
        using simple keyword extraction (no external AI/ML required).
        
        This endpoint is designed to be called by LLM agents via /ai/tools.
        The response provides structured data that an LLM can use to
        recommend tags to the user.
        
        Returns:
            post_id: The post's UUID
            title: Post title
            content_preview: First 200 chars of content
            existing_tags: Currently assigned tags
            candidate_tags: Suggested tags based on content analysis
        """
        post = await self.model.objects.get(id=pk)
        
        # Extract keywords from title and content
        title_keywords = extract_keywords(post.title, max_keywords=5)
        content_keywords = extract_keywords(post.content or "", max_keywords=10)
        
        # Combine and deduplicate, preferring title keywords
        seen = set(title_keywords)
        candidates = title_keywords.copy()
        for kw in content_keywords:
            if kw not in seen:
                seen.add(kw)
                candidates.append(kw)
        
        # Remove existing tags from suggestions
        existing = set(post.tags or [])
        candidates = [c for c in candidates if c.lower() not in {t.lower() for t in existing}]
        
        return {
            "post_id": str(post.id),
            "title": post.title,
            "content_preview": (post.content or "")[:200] + ("..." if len(post.content or "") > 200 else ""),
            "existing_tags": post.tags or [],
            "candidate_tags": candidates[:10],  # Limit to 10 suggestions
        }


class CommentViewSet(ModelViewSet):
    """
    ViewSet for comments.
    
    Authentication:
        All endpoints require X-API-Key header.
    
    Endpoints:
        GET    /api/comments/           - List all comments
        POST   /api/comments/           - Create a comment
        GET    /api/comments/{id}/      - Get a comment
        PUT    /api/comments/{id}/      - Update a comment
        DELETE /api/comments/{id}/      - Delete a comment
        POST   /api/comments/{id}/approve/ - Approve a comment
        POST   /api/comments/{id}/reject/  - Reject a comment
    
    Query Parameters:
        ?post_id=<uuid>          - Filter by post
        ?is_approved=true        - Filter by approval status
    """
    
    model = Comment
    serializer_class = CommentSerializer
    prefix = "/api/comments"
    tags = ["Blog API"]
    ai_exposed = True
    
    # Apply auth to all endpoints in this ViewSet
    dependencies = [Depends(require_api_key)]
    
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
