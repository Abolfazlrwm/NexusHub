"""Shared fixtures and fakes for engine tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from nexusagent.providers.base import ChatResult, ProviderEvent
from nexusagent.tools import ToolRegistry, register_builtin_tools
from nexusagent.types import FinishReason, Message, ToolCall, Usage


class FakeProvider:
    """In-memory ChatProvider double.

    Replays a script of :class:`ChatResult` objects (or exceptions to raise)
    one per model call, splitting text content into small deltas so
    streaming behaviour is genuinely exercised. Records every prompt and
    tool manifest it receives for assertions.
    """

    name = "fake"
    model = "fake-model"

    def __init__(self, script: list[ChatResult | Exception]) -> None:
        self.script = list(script)
        self.prompts: list[list[Message]] = []
        self.tools_seen: list[list[dict[str, Any]] | None] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> ChatResult:
        self.prompts.append(list(messages))
        self.tools_seen.append(tools)
        return self._next()

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> AsyncIterator[ProviderEvent]:
        self.prompts.append(list(messages))
        self.tools_seen.append(tools)
        result = self._next()
        content = result.content or ""
        for index in range(0, len(content), 8):
            yield ProviderEvent(type="text_delta", delta=content[index : index + 8])
        yield ProviderEvent(type="done", result=result)

    def _next(self) -> ChatResult:
        if not self.script:
            raise AssertionError("FakeProvider script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def text_result(text: str, *, prompt: int = 10, completion: int = 5) -> ChatResult:
    """A ChatResult containing plain text."""
    return ChatResult(
        content=text,
        usage=Usage(prompt_tokens=prompt, completion_tokens=completion),
        finish_reason=FinishReason.STOP,
        model="fake-model",
    )


def tool_result(
    calls: list[ToolCall], *, prompt: int = 10, completion: int = 5
) -> ChatResult:
    """A ChatResult requesting tool calls."""
    return ChatResult(
        content=None,
        tool_calls=calls,
        usage=Usage(prompt_tokens=prompt, completion_tokens=completion),
        finish_reason=FinishReason.TOOL_CALLS,
        model="fake-model",
    )


@pytest.fixture
def builtin_registry() -> ToolRegistry:
    return register_builtin_tools(ToolRegistry())
