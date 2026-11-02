"""Registry that manages the tools available to an agent."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..exceptions import ToolNotFoundError
from .base import Tool


class ToolRegistry:
    """A named collection of tools with OpenAI schema export.

    The registry is the single source of truth for what an agent *can* do:
    the runtime asks it for schemas when calling the model and looks tools up
    by name when the model requests a call.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        """Register a tool; returns the tool for call chaining."""
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        return tool

    def register_many(self, *tools: Tool) -> None:
        """Register several tools at once."""
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Tool | None:
        """Return the tool with ``name``, or ``None`` if not registered."""
        return self._tools.get(name)

    def require(self, name: str) -> Tool:
        """Return the tool with ``name`` or raise :class:`ToolNotFoundError`."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"tool '{name}' is not registered")
        return tool

    def unregister(self, name: str) -> None:
        """Remove a tool if present; unknown names are ignored."""
        self._tools.pop(name, None)

    def names(self) -> list[str]:
        """Sorted names of all registered tools."""
        return sorted(self._tools)

    def openai_schemas(self) -> list[dict[str, Any]]:
        """All tool manifests in OpenAI format, sorted by name."""
        return [self._tools[name].spec() for name in sorted(self._tools)]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def __repr__(self) -> str:
        return f"ToolRegistry({self.names()})"
