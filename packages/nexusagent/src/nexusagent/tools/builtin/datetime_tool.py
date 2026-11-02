"""Current date/time tool with IANA timezone support."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..exceptions import ToolExecutionError
from .base import Tool


class CurrentDateTimeTool(Tool):
    """Return the current date and time in a given IANA timezone."""

    name = "current_datetime"
    description = (
        "Return the current date and time as an ISO-8601 string (e.g. "
        "'2026-11-03T14:22:31+00:00') for a given IANA timezone. "
        "Defaults to UTC."
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name, e.g. 'Asia/Tehran'. Defaults to 'UTC'.",
                "default": "UTC",
            },
        },
    }

    async def execute(self, **kwargs: Any) -> str:
        timezone_name = str(kwargs.get("timezone") or "UTC")
        try:
            timezone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise ToolExecutionError(
                f"unknown timezone: '{timezone_name}'", tool=self.name
            ) from exc
        return datetime.now(timezone).isoformat(timespec="seconds")
