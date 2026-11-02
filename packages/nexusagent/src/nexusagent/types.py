"""Core conversation types shared across the nexusagent runtime.

The message model follows the OpenAI chat format closely enough that
serialization to any OpenAI-compatible provider is a single method call,
while staying provider-agnostic: no provider-specific fields live here.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Who authored a conversation message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(str, Enum):
    """Why the agent loop (or a single model call) stopped."""

    STOP = "stop"                      # model produced a final answer
    TOOL_CALLS = "tool_calls"          # model requested tool calls
    LENGTH = "length"                  # the response hit the token limit
    MAX_ITERATIONS = "max_iterations"  # the agent exhausted its iteration budget


class ToolCall(BaseModel):
    """A single function call requested by the model."""

    id: str = Field(description="Provider-issued call id, echoed in the tool result message.")
    name: str = Field(description="Name of the tool to invoke.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed JSON arguments for the call.",
    )
    raw_arguments: str = Field(
        default="",
        description="Original JSON arguments exactly as the model produced them (kept for traces).",
    )

    @classmethod
    def from_openai(cls, payload: dict[str, Any]) -> ToolCall:
        """Build a :class:`ToolCall` from an OpenAI-format ``tool_calls`` entry.

        Malformed JSON in ``arguments`` is tolerated on purpose: models do
        emit broken JSON occasionally. ``raw_arguments`` keeps the original
        string and ``arguments`` falls back to an empty dict, so tool
        execution surfaces a helpful error to the model instead of crashing
        the run.
        """
        function = payload.get("function") or {}
        raw = function.get("arguments")

        if isinstance(raw, dict):
            parsed, raw_text = raw, json.dumps(raw)
        elif isinstance(raw, str):
            raw_text = raw
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError:
                loaded = {}
            parsed = loaded if isinstance(loaded, dict) else {}
        else:
            parsed, raw_text = {}, ""

        return cls(
            id=str(payload.get("id") or ""),
            name=str(function.get("name") or ""),
            arguments=parsed,
            raw_arguments=raw_text,
        )

    def to_openai(self) -> dict[str, Any]:
        """Serialize back to the OpenAI wire format."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.raw_arguments or json.dumps(self.arguments),
            },
        }


class Usage(BaseModel):
    """Token accounting for one or more model calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens across prompt and completion."""
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: object) -> Usage:
        if not isinstance(other, Usage):
            return NotImplemented
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


class Message(BaseModel):
    """One message in a conversation.

    Assistant messages may carry ``tool_calls``; tool results reference them
    back via ``tool_call_id``, mirroring the OpenAI chat message shape.
    """

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    # -- convenience constructors -------------------------------------------

    @classmethod
    def system(cls, content: str) -> Message:
        """Create a system message."""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        """Create a user message."""
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(
        cls, content: str | None, tool_calls: list[ToolCall] | None = None
    ) -> Message:
        """Create an assistant message, optionally with requested tool calls."""
        return cls(role=Role.ASSISTANT, content=content, tool_calls=tool_calls or [])

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str | None = None) -> Message:
        """Create a tool-result message answering ``tool_call_id``."""
        return cls(role=Role.TOOL, content=content, tool_call_id=tool_call_id, name=name)

    # -- serialization ------------------------------------------------------

    def to_openai(self) -> dict[str, Any]:
        """Serialize to the OpenAI chat-completions wire format."""
        payload: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            payload["content"] = self.content
        if self.tool_calls:
            payload["tool_calls"] = [call.to_openai() for call in self.tool_calls]
        if self.role is Role.TOOL:
            payload["content"] = self.content or ""
            payload["tool_call_id"] = self.tool_call_id or ""
            if self.name:
                payload["name"] = self.name
        return payload
