"""
AI Providers Example - Prompting

v0.5.14: Demonstrates how to build prompts from Aksara's AiRouteHint metadata.

This module shows how to combine:
- AiRouteHint (route metadata from decorators)
- User input data
- AiModelProfile (model configuration)

Into effective prompts for LLM calls.

Copy these patterns to your project and customize the prompt templates.
"""

from __future__ import annotations

import json
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.ai.models import AiRouteHint, AiModelProfile


# =============================================================================
# Prompt Building Functions
# =============================================================================

def build_prompt_for_route(
    hint: "AiRouteHint",
    user_input: dict[str, Any],
    profile: Optional["AiModelProfile"] = None,
    *,
    include_examples: bool = True,
    include_context: bool = True,
) -> str:
    """
    Build a completion prompt from route hint and user input.
    
    Combines the AI hint metadata with user-provided data to create
    an effective prompt for the LLM.
    
    Args:
        hint: AiRouteHint from the route decorator
        user_input: Dict of user-provided data (e.g., post content)
        profile: Optional AiModelProfile for model-specific adjustments
        include_examples: Whether to include example prompt/input/output
        include_context: Whether to include descriptive context
        
    Returns:
        Formatted prompt string
        
    Example:
        hint = get_ai_route_hint(view.ai_suggest_tags)
        prompt = build_prompt_for_route(
            hint=hint,
            user_input={"title": post.title, "content": post.content},
        )
        response = await client.complete(prompt, model=profile)
    """
    parts = []
    
    # System context from hint
    if include_context and hint.description:
        parts.append(f"Task: {hint.description}")
    
    # Add title context
    if hint.title:
        parts.append(f"Action: {hint.title}")
    
    # Risk level context (helps model understand sensitivity)
    if hint.risk_level and hint.risk_level != "low":
        risk_context = {
            "medium": "This operation modifies data. Be careful and precise.",
            "high": "This is a high-risk operation. Double-check all outputs.",
        }
        if context := risk_context.get(hint.risk_level):
            parts.append(f"Note: {context}")
    
    # Usage kind context
    if hint.usage_kind:
        usage_context = {
            "read_only": "This is a read-only operation.",
            "write": "This operation may create or modify data.",
            "admin": "This is an administrative operation requiring elevated privileges.",
        }
        if context := usage_context.get(hint.usage_kind):
            parts.append(f"Mode: {context}")
    
    # Include example if available
    if include_examples:
        if hint.example_prompt:
            parts.append(f"Example request: {hint.example_prompt}")
        
        if hint.example_input:
            parts.append(f"Example input: {json.dumps(hint.example_input, indent=2)}")
        
        if hint.example_output:
            parts.append(f"Expected output format: {json.dumps(hint.example_output, indent=2)}")
    
    # User input data
    if user_input:
        parts.append("--- User Input ---")
        for key, value in user_input.items():
            if isinstance(value, (dict, list)):
                parts.append(f"{key}: {json.dumps(value, indent=2)}")
            else:
                parts.append(f"{key}: {value}")
    
    # Build final prompt
    prompt = "\n\n".join(parts)
    
    return prompt


def build_chat_messages_for_route(
    hint: "AiRouteHint",
    user_input: dict[str, Any],
    profile: Optional["AiModelProfile"] = None,
    *,
    system_message: Optional[str] = None,
    include_examples: bool = True,
) -> list[dict[str, str]]:
    """
    Build chat messages from route hint and user input.
    
    Creates a properly structured message list for chat-style APIs
    (OpenAI, Anthropic, etc.).
    
    Args:
        hint: AiRouteHint from the route decorator
        user_input: Dict of user-provided data
        profile: Optional AiModelProfile for model-specific adjustments
        system_message: Optional override for system message
        include_examples: Whether to include example in user message
        
    Returns:
        List of message dicts with "role" and "content" keys
        
    Example:
        messages = build_chat_messages_for_route(
            hint=hint,
            user_input={"content": post.content},
        )
        response = await client.chat(messages, model=profile)
    """
    messages = []
    
    # Build system message
    if system_message:
        system_content = system_message
    else:
        system_parts = []
        
        if hint.description:
            system_parts.append(hint.description)
        
        if hint.title:
            system_parts.append(f"You are helping with: {hint.title}")
        
        # Add safety context based on risk level
        if hint.risk_level == "high":
            system_parts.append(
                "This is a high-risk operation. "
                "Be very careful and precise with your response. "
                "Ask for clarification if the request is ambiguous."
            )
        elif hint.risk_level == "medium":
            system_parts.append(
                "This operation modifies data. "
                "Ensure your response is accurate and well-formed."
            )
        
        # Add expected output format hint
        if hint.example_output:
            system_parts.append(
                f"Respond in this format: {json.dumps(hint.example_output)}"
            )
        
        system_content = " ".join(system_parts) if system_parts else "You are a helpful assistant."
    
    messages.append({
        "role": "system",
        "content": system_content,
    })
    
    # Build user message
    user_parts = []
    
    # Include example if helpful
    if include_examples and hint.example_prompt:
        user_parts.append(f"Example: {hint.example_prompt}")
        user_parts.append("---")
    
    # Add user input
    user_parts.append("Please process the following:")
    for key, value in user_input.items():
        if isinstance(value, (dict, list)):
            user_parts.append(f"{key}: {json.dumps(value)}")
        else:
            user_parts.append(f"{key}: {value}")
    
    messages.append({
        "role": "user",
        "content": "\n".join(user_parts),
    })
    
    return messages


def format_structured_output_prompt(
    task_description: str,
    output_schema: dict[str, Any],
    user_input: dict[str, Any],
    *,
    strict_json: bool = True,
) -> str:
    """
    Build a prompt that requests structured JSON output.
    
    Useful for function-calling style interactions or when you need
    the model to return data in a specific format.
    
    Args:
        task_description: What the model should do
        output_schema: JSON schema or example of expected output
        user_input: User-provided data to process
        strict_json: Whether to emphasize JSON-only response
        
    Returns:
        Formatted prompt requesting structured output
        
    Example:
        prompt = format_structured_output_prompt(
            task_description="Extract tags from the blog post",
            output_schema={"tags": ["python", "tutorial"]},
            user_input={"title": post.title, "content": post.content},
        )
    """
    parts = [
        f"Task: {task_description}",
        "",
        "Expected output format (JSON):",
        json.dumps(output_schema, indent=2),
        "",
        "Input data:",
        json.dumps(user_input, indent=2),
    ]
    
    if strict_json:
        parts.extend([
            "",
            "IMPORTANT: Respond ONLY with valid JSON matching the schema above.",
            "Do not include any explanations or text outside the JSON.",
        ])
    
    return "\n".join(parts)


# =============================================================================
# Response Parsing Helpers
# =============================================================================

def parse_json_response(response: str) -> Any:
    """
    Parse a JSON response from the LLM.
    
    Handles common issues like markdown code blocks and extra whitespace.
    
    Args:
        response: Raw response string from LLM
        
    Returns:
        Parsed JSON data
        
    Raises:
        ValueError: If response is not valid JSON
    """
    # Clean up response
    text = response.strip()
    
    # Handle markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON response: {e}") from e


def extract_tags_from_response(response: str) -> list[str]:
    """
    Extract a list of tags from an LLM response.
    
    Handles various response formats (JSON, comma-separated, etc.).
    
    Args:
        response: Raw response string from LLM
        
    Returns:
        List of extracted tags
    """
    # Try JSON first
    try:
        data = parse_json_response(response)
        if isinstance(data, list):
            return [str(t).strip() for t in data]
        elif isinstance(data, dict) and "tags" in data:
            return [str(t).strip() for t in data["tags"]]
    except (ValueError, KeyError):
        pass
    
    # Fall back to comma/newline separated
    text = response.strip()
    
    # Remove common prefixes
    for prefix in ["Tags:", "Suggested tags:", "Here are the tags:"]:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    
    # Split by comma or newline
    if "," in text:
        tags = [t.strip() for t in text.split(",")]
    else:
        tags = [t.strip() for t in text.split("\n")]
    
    # Clean up tags
    tags = [t.strip("- ").strip() for t in tags if t.strip()]
    
    return tags


# =============================================================================
# Template Helpers
# =============================================================================

def get_tag_suggestion_prompt(title: str, content: str, max_tags: int = 5) -> str:
    """
    Get a pre-built prompt for tag suggestion.
    
    Example prompt template for a common use case.
    
    Args:
        title: Blog post title
        content: Blog post content
        max_tags: Maximum number of tags to suggest
        
    Returns:
        Formatted prompt
    """
    return f"""Analyze the following blog post and suggest up to {max_tags} relevant tags.

Title: {title}

Content:
{content[:2000]}{"..." if len(content) > 2000 else ""}

Respond with a JSON array of tags, like: ["python", "tutorial", "web-development"]
Only include the JSON array, no other text."""


def get_content_summary_prompt(content: str, max_length: int = 200) -> str:
    """
    Get a pre-built prompt for content summarization.
    
    Args:
        content: Content to summarize
        max_length: Target summary length in characters
        
    Returns:
        Formatted prompt
    """
    return f"""Summarize the following content in approximately {max_length} characters or fewer.
The summary should capture the main points and be suitable for a preview or excerpt.

Content:
{content}

Provide only the summary, no additional text or formatting."""
