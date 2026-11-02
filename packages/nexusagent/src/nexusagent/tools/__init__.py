"""Built-in tools shipped with nexusagent.

The built-ins are intentionally small and safe: they demonstrate the Tool
contract and cover the most common "model needs a fact or a function"
cases. Platform-specific tools (web search, RAG retrieval, database query)
live in the platform, not the engine.
"""

from __future__ import annotations

from .base import Tool
from .builtin import CalculatorTool, CurrentDateTimeTool, UuidTool
from .registry import ToolRegistry

__all__ = [
    "CalculatorTool",
    "CurrentDateTimeTool",
    "Tool",
    "ToolRegistry",
    "UuidTool",
    "register_builtin_tools",
]


def register_builtin_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register all built-in tools into ``registry`` and return it."""
    registry.register_many(
        CalculatorTool(),
        CurrentDateTimeTool(),
        UuidTool(),
    )
    return registry
