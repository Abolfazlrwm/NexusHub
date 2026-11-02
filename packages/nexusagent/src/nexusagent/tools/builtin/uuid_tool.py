"""UUID generator tool."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from ..exceptions import ToolExecutionError
from .base import Tool

_MAX_COUNT = 32


class UuidTool(Tool):
    """Generate one or more random UUID4 strings."""

    name = "generate_uuid"
    description = (
        "Generate one or more random UUID4 strings, useful for unique "
        "identifiers. Returns one UUID per line."
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": f"How many UUIDs to generate (1-{_MAX_COUNT}). Defaults to 1.",
                "minimum": 1,
                "maximum": _MAX_COUNT,
            },
        },
    }

    async def execute(self, **kwargs: Any) -> str:
        raw_count = kwargs.get("count", 1)
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "'count' must be an integer", tool=self.name
            ) from exc
        if not 1 <= count <= _MAX_COUNT:
            raise ToolExecutionError(
                f"'count' must be between 1 and {_MAX_COUNT}", tool=self.name
            )
        return "\n".join(str(uuid.uuid4()) for _ in range(count))
