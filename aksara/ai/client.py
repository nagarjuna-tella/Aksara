"""
AI Client Protocol for Aksara.

This module defines the protocol (interface) for LLM clients that can be
used with Aksara's AI features. External packages (e.g., aksara-openai,
aksara-anthropic) can implement this protocol.

Aksara core does NOT implement any concrete client - this is intentionally
provider-agnostic. The protocol ensures type safety and consistent APIs
across different LLM providers.

v0.4.2: Initial release
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class BaseAiClient(Protocol):
    """
    Protocol for LLM clients used in conjunction with Aksara.
    
    External packages can implement this protocol to integrate
    with Aksara's AI features. The protocol defines the minimal
    interface needed for chat-based interactions with tool support.
    
    Example implementation (in external package):
    
        from openai import AsyncOpenAI
        from aksara.ai.client import BaseAiClient
        
        class OpenAIClient:
            def __init__(self, api_key: str):
                self.client = AsyncOpenAI(api_key=api_key)
            
            async def chat(
                self,
                messages: List[Dict[str, Any]],
                tools: Optional[List[Dict[str, Any]]] = None,
                **kwargs: Any,
            ) -> Dict[str, Any]:
                response = await self.client.chat.completions.create(
                    model=kwargs.get("model", "gpt-4"),
                    messages=messages,
                    tools=tools,
                    **kwargs,
                )
                return response.model_dump()
        
        # This passes the protocol check:
        assert isinstance(OpenAIClient("key"), BaseAiClient)
    
    Usage with Aksara:
    
        from aksara.ai import get_ai_tools_for_request, export_tools_as_openai_functions
        from aksara.ai.query import AiQueryPlan, execute_ai_query_plan
        
        # 1. Get tools in provider format
        tools = await get_ai_tools_for_request(request, app)
        openai_tools = export_tools_as_openai_functions(tools)
        
        # 2. Chat with LLM using your client
        client = OpenAIClient(api_key="...")
        response = await client.chat(
            messages=[{"role": "user", "content": "Find all active users"}],
            tools=openai_tools,
        )
        
        # 3. Parse response and execute query plan
        plan = AiQueryPlan.model_validate(response["tool_calls"][0]["arguments"])
        result = await execute_ai_query_plan(plan)
    """
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                Example: [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Find all active users."}
                ]
            tools: Optional list of tool definitions in provider-specific format.
                Aksara provides exporters for OpenAI, MCP, and generic formats.
            **kwargs: Provider-specific arguments (model, temperature, etc.)
        
        Returns:
            Response dict with at minimum:
                - 'content': The text response (may be None if tool call)
                - 'tool_calls': Optional list of tool calls the LLM wants to make
            
            Exact structure depends on provider, but should include
            enough information to extract tool calls and responses.
        
        Raises:
            Any provider-specific exceptions should be caught and
            re-raised or handled by the implementation.
        """
        ...


class AiClientConfig(Protocol):
    """
    Protocol for AI client configuration.
    
    Implementations can use this to standardize configuration
    across different providers.
    """
    
    @property
    def api_key(self) -> Optional[str]:
        """API key for the provider."""
        ...
    
    @property
    def model(self) -> str:
        """Default model to use."""
        ...
    
    @property
    def max_tokens(self) -> int:
        """Maximum tokens for responses."""
        ...
    
    @property
    def temperature(self) -> float:
        """Temperature for response generation."""
        ...


# =============================================================================
# Type Aliases for Common Patterns
# =============================================================================

# Message format used by most providers
ChatMessage = Dict[str, Any]  # {"role": str, "content": str, ...}

# Tool call format
ToolCall = Dict[str, Any]  # {"name": str, "arguments": Dict, ...}

# Full response format
ChatResponse = Dict[str, Any]  # {"content": str, "tool_calls": List[ToolCall], ...}
