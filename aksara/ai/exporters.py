"""
Aksara AI Exporters

Convert AiTool instances to various agent framework formats.

Supported formats:
- Generic: Simple JSON structure any framework can adapt
- MCP: Model Context Protocol compatible format
- Future: OpenAI function calling, LangChain tools
"""

from typing import Any, Dict, List

from aksara.ai.models import AiTool


def export_tools_as_generic(tools: List[AiTool]) -> List[Dict[str, Any]]:
    """
    Export tools as a simple, stable JSON structure.
    
    This is the "base API" that any agent framework can adapt from.
    Uses Pydantic's model_dump() for consistent serialization.
    
    Args:
        tools: List of AiTool instances
        
    Returns:
        List of tool dictionaries
        
    Example:
        tools = await get_ai_tools_for_request(request, app)
        generic_tools = export_tools_as_generic(tools)
        # Returns:
        # [
        #     {
        #         "name": "users_list",
        #         "title": "List Users",
        #         "description": "Get a paginated list of users",
        #         "http_method": "GET",
        #         "path": "/api/users/",
        #         "kind": "query",
        #         ...
        #     }
        # ]
    """
    return [tool.model_dump() for tool in tools]


def export_tools_as_mcp(tools: List[AiTool]) -> List[Dict[str, Any]]:
    """
    Export tools in MCP (Model Context Protocol) compatible format.
    
    MCP tools have a specific schema structure that LLMs can use
    to understand how to invoke HTTP endpoints.
    
    The format closely matches the MCP tool schema:
    - name: Tool identifier
    - description: What the tool does
    - inputSchema: JSON Schema for parameters
    - metadata: Additional info (HTTP method, path, etc.)
    
    Args:
        tools: List of AiTool instances
        
    Returns:
        List of MCP-formatted tool dictionaries
        
    Example:
        mcp_tools = export_tools_as_mcp(tools)
        # Returns:
        # [
        #     {
        #         "name": "users_list",
        #         "description": "Get a paginated list of users",
        #         "inputSchema": {
        #             "type": "object",
        #             "properties": {...},
        #             "required": [...]
        #         },
        #         "metadata": {
        #             "http_method": "GET",
        #             "path": "/api/users/",
        #             ...
        #         }
        #     }
        # ]
    """
    mcp_tools = []
    
    for tool in tools:
        mcp_tool = {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": tool.input_schema.get("properties", {}),
                "required": tool.input_schema.get("required", []),
            },
            "metadata": {
                "http_method": tool.http_method,
                "path": tool.path,
                "kind": tool.kind,
                "model": tool.model,
                "requires_auth": tool.requires_auth,
                "requires_admin": tool.requires_admin,
                "permissions": tool.permissions,
                "tags": tool.ai_tags,
            },
        }
        
        # Add output schema if available
        if tool.output_schema:
            mcp_tool["outputSchema"] = tool.output_schema
        
        mcp_tools.append(mcp_tool)
    
    return mcp_tools


def export_tools_as_openai_functions(tools: List[AiTool]) -> List[Dict[str, Any]]:
    """
    Export tools as OpenAI function calling format.
    
    Compatible with OpenAI's function calling API and Assistants API.
    
    Args:
        tools: List of AiTool instances
        
    Returns:
        List of OpenAI function definitions
        
    Example:
        functions = export_tools_as_openai_functions(tools)
        # Use with OpenAI:
        # response = client.chat.completions.create(
        #     model="gpt-4",
        #     messages=[...],
        #     functions=functions
        # )
    """
    functions = []
    
    for tool in tools:
        function = {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": tool.input_schema.get("properties", {}),
                "required": tool.input_schema.get("required", []),
            },
        }
        functions.append(function)
    
    return functions


def export_tools_as_langchain(tools: List[AiTool]) -> List[Dict[str, Any]]:
    """
    Export tools in a format suitable for LangChain tool creation.
    
    This provides the metadata needed to create LangChain Tool or
    StructuredTool instances.
    
    Args:
        tools: List of AiTool instances
        
    Returns:
        List of tool specifications for LangChain
        
    Example:
        tool_specs = export_tools_as_langchain(tools)
        # Create LangChain tools:
        # from langchain.tools import StructuredTool
        # for spec in tool_specs:
        #     tool = StructuredTool(
        #         name=spec["name"],
        #         description=spec["description"],
        #         args_schema=spec["args_schema"],
        #         func=create_api_caller(spec["metadata"])
        #     )
    """
    langchain_tools = []
    
    for tool in tools:
        lc_tool = {
            "name": tool.name,
            "description": tool.description,
            "args_schema": tool.input_schema,
            "return_direct": False,
            "metadata": {
                "http_method": tool.http_method,
                "path": tool.path,
                "kind": tool.kind,
                "model": tool.model,
                "requires_auth": tool.requires_auth,
                "requires_admin": tool.requires_admin,
                "permissions": tool.permissions,
                "tags": tool.ai_tags,
            },
        }
        langchain_tools.append(lc_tool)
    
    return langchain_tools
