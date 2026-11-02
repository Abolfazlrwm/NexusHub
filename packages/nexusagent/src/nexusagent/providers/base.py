"""Provider-agnostic chat interface.

The runtime depends only on this protocol; concrete providers translate it
to a wire format. This keeps the agent loop testable with in-memory fakes
and portable across vendors.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from ..types import FinishReason, Message, ToolCall, Usage


class ChatResult(BaseModel):
    """The outcome of one completed model call."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    finish_reason: FinishReason = FinishReason.STOP
    model: str | None = None


class ProviderEvent(BaseModel):
    """One incremental event from a streaming model call.

    ``text_delta`` carries a fragment of the answer as it arrives; ``done``
    carries the fully assembled :class:`ChatResult`, including tool calls
    reassembled from their streamed argument fragments.
    """

    type: Literal["text_delta", "done"]
    delta: str | None = None
    result: ChatResult | None = None


class ChatProvider(Protocol):
    """Anything that can drive the agent loop.

    ``stream`` is the primary path used by the runtime; ``complete`` is a
    convenience for one-shot calls and provider verification.
    """

    name: str
    model: str

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> ChatResult: ...

    def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> AsyncIterator[ProviderEvent]: ...
