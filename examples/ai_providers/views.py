"""
AI Providers Example - Views

v0.5.14: Example views demonstrating end-to-end AI wiring.

Shows how to:
1. Define routes with @ai_route_hint
2. Get hint metadata at runtime
3. Build prompts from hints + user input
4. Call LLM adapters
5. Return structured responses

Copy these patterns to your project.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from aksara import Model, fields
from aksara.api import ModelViewSet, action

# Import AI hints (from core Aksara)
try:
    from aksara.ai import ai_route_hint
    from aksara.ai.hints import get_ai_route_hint
except ImportError:
    # Fallback for testing without full Aksara
    def ai_route_hint(**kwargs):
        def decorator(fn):
            fn._aksara_ai_hint = kwargs
            return fn
        return decorator
    
    def get_ai_route_hint(fn):
        return getattr(fn, '_aksara_ai_hint', None)

# Local imports
from .adapters import get_llm_client_from_settings, LlmClient
from .prompting import (
    build_prompt_for_route,
    build_chat_messages_for_route,
    get_tag_suggestion_prompt,
    extract_tags_from_response,
    parse_json_response,
)
from .settings import settings

logger = logging.getLogger("ai_providers.views")


# =============================================================================
# Demo Model (for this example)
# =============================================================================

class DemoPost(Model):
    """
    Demo blog post model for AI examples.
    
    In a real app, you'd use your actual models.
    
    This model demonstrates all three AI metadata attributes:
    - ai_description: Tells AI Console and MCP what each field means
    - ai_sensitive: Excludes PII from AI context and MCP tool exports
    - ai_agent_writable: Controls whether AI agents can modify the field
    
    These attributes flow through to:
    - /ai/tools (AI tools discovery)
    - /ai/tools/mcp (MCP tool catalog for AI agents)
    - Studio AI Console context
    """
    
    title = fields.String(
        max_length=200,
        ai_description="Post title — used by AI for content analysis and search",
    )
    content = fields.Text(
        ai_description="Full post body (Markdown supported) — AI uses this for summarization and tag suggestion",
    )
    tags = fields.JSON(
        default=[],
        ai_description="List of categorization tags (e.g., ['python', 'tutorial'])",
    )
    summary = fields.Text(
        nullable=True,
        ai_description="AI-generated summary of the post content",
    )
    author_email = fields.String(
        max_length=255,
        nullable=True,
        ai_description="Author's contact email",
        ai_sensitive=True,  # PII — this field is excluded from AI context and MCP exports
    )
    is_featured = fields.Boolean(
        default=False,
        ai_description="Whether this post is editorially featured",
        ai_agent_writable=False,  # Editorial decisions should be made by humans, not AI agents
    )
    
    class Meta:
        table_name = "demo_posts"
        ai_name = "DemoPost"
        ai_description = "Blog posts for AI analysis, summarization, and tag suggestion demos"
        ai_agent_exposed = True  # This model appears in /ai/tools and /ai/tools/mcp
        ai_permissions = ["read", "write"]


# =============================================================================
# Example ViewSet with AI Actions
# =============================================================================

class DemoPostViewSet(ModelViewSet):
    """
    Example ViewSet demonstrating AI-powered actions.
    
    This shows the complete pattern:
    1. Use @ai_route_hint to document AI behavior
    2. Access hint metadata at runtime with get_ai_route_hint()
    3. Build prompts using hint info + user input
    4. Call LLM via adapter
    5. Return structured response
    """
    
    model = DemoPost
    prefix = "/api/demo-posts"
    tags = ["Demo AI"]
    
    # -------------------------------------------------------------------------
    # Action: AI Suggest Tags
    # -------------------------------------------------------------------------
    
    @action(detail=True, methods=["post"])
    @ai_route_hint(
        title="Suggest tags for a blog post",
        description=(
            "Analyzes the blog post content and suggests relevant tags. "
            "Uses the post title and content to generate appropriate "
            "categorization tags."
        ),
        usage_kind="read_only",
        risk_level="low",
        example_prompt="Suggest tags for my post about Python async programming",
        example_input={"title": "Understanding Python Async", "content": "..."},
        example_output={"tags": ["python", "async", "programming", "tutorial"]},
    )
    async def ai_suggest_tags(self, request, id: int):
        """
        Suggest tags for a blog post using AI.
        
        This demonstrates the complete AI wiring pattern:
        1. Get the post data
        2. Build prompt from hint + content
        3. Call LLM adapter
        4. Parse and return structured response
        """
        # 1. Get the post (in real app, use self.get_object(id))
        # For demo, we use dummy data
        post = DemoPost(
            id=id,
            title=request.get("title", "Demo Post"),
            content=request.get("content", "Demo content about programming."),
        )
        
        # 2. Get AI hint metadata
        hint = get_ai_route_hint(self.ai_suggest_tags)
        
        # 3. Build the prompt
        if hint:
            # Use structured prompt building
            from aksara.ai.models import AiRouteHint
            hint_obj = AiRouteHint(
                view_name="DemoPostViewSet",
                route_name="ai_suggest_tags",
                path=f"/api/demo-posts/{id}/ai_suggest_tags",
                methods=["POST"],
                **hint,
            )
            prompt = build_prompt_for_route(
                hint=hint_obj,
                user_input={"title": post.title, "content": post.content},
            )
        else:
            # Fallback to simple prompt
            prompt = get_tag_suggestion_prompt(post.title, post.content)
        
        # 4. Call LLM (in real app - here we show the pattern)
        try:
            client = get_llm_client_from_settings(settings)
            
            # For demo, use simple model profile
            from aksara.ai.providers import AiModelProfile
            profile = AiModelProfile(
                model_name=getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-4o-mini"),
                model_kind="chat",
                provider="openai",
            )
            
            response = await client.complete(prompt, model=profile)
            
            # 5. Parse response
            tags = extract_tags_from_response(response)
            
            return {
                "id": id,
                "suggested_tags": tags,
                "model_used": profile.model_name,
            }
            
        except RuntimeError as e:
            # SDK not installed - return helpful error
            logger.warning(f"AI SDK not available: {e}")
            return {
                "error": "AI provider SDK not installed",
                "message": str(e),
                "suggestion": "Install the provider SDK: pip install openai",
            }
    
    # -------------------------------------------------------------------------
    # Action: AI Generate Summary
    # -------------------------------------------------------------------------
    
    @action(detail=True, methods=["post"])
    @ai_route_hint(
        title="Generate summary for a blog post",
        description=(
            "Creates a concise summary of the blog post content. "
            "The summary is suitable for previews, excerpts, or SEO descriptions."
        ),
        usage_kind="read_only",
        risk_level="low",
        example_prompt="Generate a summary for my tutorial post",
        example_input={"content": "...full post content..."},
        example_output={"summary": "A brief overview of the post in 1-2 sentences."},
    )
    async def ai_generate_summary(self, request, id: int):
        """
        Generate a summary for a blog post using AI.
        """
        content = request.get("content", "")
        max_length = request.get("max_length", 200)
        
        # Get hint for prompt building
        hint = get_ai_route_hint(self.ai_generate_summary)
        
        try:
            client = get_llm_client_from_settings(settings)
            
            from aksara.ai.providers import AiModelProfile
            profile = AiModelProfile(
                model_name=getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-4o-mini"),
                model_kind="chat",
                provider="openai",
            )
            
            prompt = f"""Summarize the following content in {max_length} characters or fewer:

{content[:3000]}

Provide only the summary, no additional formatting."""
            
            summary = await client.complete(prompt, model=profile)
            
            return {
                "id": id,
                "summary": summary.strip(),
                "length": len(summary.strip()),
            }
            
        except RuntimeError as e:
            return {
                "error": "AI provider SDK not installed",
                "message": str(e),
            }
    
    # -------------------------------------------------------------------------
    # Action: AI Analyze Content
    # -------------------------------------------------------------------------
    
    @action(detail=True, methods=["post"])
    @ai_route_hint(
        title="Analyze blog post content",
        description=(
            "Performs comprehensive analysis of the blog post including "
            "readability assessment, key topics, and improvement suggestions."
        ),
        usage_kind="read_only",
        risk_level="low",
        example_prompt="Analyze my blog post for quality and topics",
        example_input={"content": "...post content..."},
        example_output={
            "topics": ["python", "programming"],
            "readability": "intermediate",
            "word_count": 500,
            "suggestions": ["Add more examples", "Include code snippets"],
        },
    )
    async def ai_analyze(self, request, id: int):
        """
        Analyze blog post content using AI.
        
        Demonstrates structured output parsing.
        """
        content = request.get("content", "")
        
        try:
            client = get_llm_client_from_settings(settings)
            
            from aksara.ai.providers import AiModelProfile
            profile = AiModelProfile(
                model_name=getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-4o-mini"),
                model_kind="chat",
                provider="openai",
            )
            
            prompt = f"""Analyze the following blog post and provide a JSON response with:
- topics: list of main topics covered
- readability: "beginner", "intermediate", or "advanced"
- word_count: approximate word count
- suggestions: list of improvement suggestions

Content:
{content[:3000]}

Respond with ONLY valid JSON, no other text."""
            
            response = await client.complete(prompt, model=profile)
            
            try:
                analysis = parse_json_response(response)
            except ValueError:
                # If JSON parsing fails, return raw analysis
                analysis = {"raw_analysis": response}
            
            return {
                "id": id,
                "analysis": analysis,
            }
            
        except RuntimeError as e:
            return {
                "error": "AI provider SDK not installed",
                "message": str(e),
            }


# =============================================================================
# Utility Functions
# =============================================================================

def get_ai_client_status(settings: Any) -> dict[str, Any]:
    """
    Get status of AI provider configuration.
    
    Useful for debugging and health checks.
    """
    from .adapters import check_sdk_availability
    
    sdks = check_sdk_availability()
    configured = getattr(settings, "get_configured_providers", lambda: [])()
    
    return {
        "default_provider": getattr(settings, "AI_DEFAULT_PROVIDER", "openai"),
        "sdk_availability": sdks,
        "configured_providers": configured,
        "ready": any(
            sdks.get(p, False) and p in configured
            for p in ["openai", "azure", "anthropic"]
        ),
    }
