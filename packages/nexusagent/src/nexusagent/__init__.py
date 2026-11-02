"""nexusagent — a lightweight, provider-agnostic AI agent runtime.

Tool calling, conversation memory, streaming and first-class tracing for
agents built on any OpenAI-compatible endpoint.

Quick start::

    from nexusagent import Agent, AgentConfig, OpenAICompatProvider

    agent = Agent(
        provider=OpenAICompatProvider(model="gpt-4o-mini", api_key="sk-..."),
        config=AgentConfig(system_prompt="You are a precise assistant."),
    )
    result = await agent.run("Hello!")
"""

from __future__ import annotations

from .agents import Agent, AgentEvent, AgentRunResult
from .config import AgentConfig
from .exceptions import (
    ConfigurationError,
    NexusAgentError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ToolArgumentError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)
from .memory import BaseMemory, InMemoryMemory
from .providers import (
    DEFAULT_BASE_URL,
    ChatProvider,
    ChatResult,
    OpenAICompatProvider,
    ProviderEvent,
    ProviderRegistry,
)
from .tools import (
    CalculatorTool,
    CurrentDateTimeTool,
    Tool,
    ToolRegistry,
    UuidTool,
    register_builtin_tools,
)
from .types import FinishReason, Message, Role, ToolCall, Usage

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "Agent",
    "AgentConfig",
    "AgentEvent",
    "AgentRunResult",
    "BaseMemory",
    "CalculatorTool",
    "ChatProvider",
    "ChatResult",
    "ConfigurationError",
    "CurrentDateTimeTool",
    "FinishReason",
    "InMemoryMemory",
    "Message",
    "NexusAgentError",
    "OpenAICompatProvider",
    "ProviderAuthError",
    "ProviderError",
    "ProviderEvent",
    "ProviderRateLimitError",
    "ProviderRegistry",
    "ProviderTimeoutError",
    "Role",
    "Tool",
    "ToolArgumentError",
    "ToolCall",
    "ToolError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ToolRegistry",
    "Usage",
    "UuidTool",
    "register_builtin_tools",
]
