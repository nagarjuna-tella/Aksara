"""
Aksara AI Connectors  (v0.5.30)

Pluggable connector layer for executing AI prompt packs through different
LLM providers.  Each connector implements a common interface (``AIConnector``)
and returns normalised output.

Connectors:
    - ``OpenAIConnector``  — OpenAI & Azure OpenAI
    - ``AnthropicConnector`` — Anthropic / Claude
    - ``OllamaConnector``  — local Ollama models
    - ``HttpConnector``    — generic custom HTTP endpoints

Usage::

    from aksara.ai.connectors.registry import get_connector

    connector = get_connector("openai")
    result = await connector.chat(messages, model="gpt-4o")
"""

from aksara.ai.connectors.base import AIConnector
from aksara.ai.connectors.registry import get_connector, CONNECTOR_REGISTRY

__all__ = [
    "AIConnector",
    "get_connector",
    "CONNECTOR_REGISTRY",
]
