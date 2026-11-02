"""Tool abstraction: capabilities a model can invoke during a run."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class Tool(ABC):
    """Base class every nexusagent tool inherits from.

    Subclasses declare their manifest as class attributes — ``name``,
    ``description`` and a JSON-Schema ``parameters`` object — and implement
    :meth:`execute`, which receives the model's parsed arguments and returns
    a plain string for the model to read.

    Implementations should raise :class:`~nexusagent.exceptions.ToolExecutionError`
    (or :class:`~nexusagent.exceptions.ToolArgumentError`) with a helpful
    message instead of letting raw exceptions escape: the runtime converts
    those into tool-result messages the model can react to.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Run the tool with model-provided arguments and return its output."""

    @classmethod
    def spec(cls) -> dict[str, Any]:
        """Return the tool manifest in OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters
                or {"type": "object", "properties": {}},
            },
        }
