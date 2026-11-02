"""The agent runtime loop.

This is the heart of nexusagent: it drives the conversation between the
model, the tools and the caller — streaming every observable moment as an
event, recording every step as a trace, and keeping tool failures soft so
the model can recover from its own mistakes.

Design rules the loop follows:

- Tool failures are soft: an error becomes a tool-result message the model
  can read and route around. Only infrastructure failures (auth, network,
  budget) raise.
- The iteration budget is respected even when the model keeps asking for
  tools; when it is exhausted, the history stays consistent (every
  requested tool call has an answer) so the same memory can be reused.
- Everything the loop does is recorded in the trace, in order.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from ..config import AgentConfig
from ..exceptions import ProviderError
from ..memory import BaseMemory, InMemoryMemory
from ..providers.base import ChatProvider, ChatResult
from ..tools import ToolRegistry
from ..types import FinishReason, Message, Role, ToolCall, Usage
from .events import (
    AgentEvent,
    IterationStartedEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextDeltaEvent,
    ToolCallFinishedEvent,
    ToolCallStartedEvent,
)
from .trace import ModelCallStep, RunTrace, ToolCallStep


class AgentRunResult(BaseModel):
    """Everything known about one completed agent run."""

    run_id: str
    output: str
    finish_reason: FinishReason
    usage: Usage
    iterations: int
    total_latency_ms: float
    trace: RunTrace
    messages: list[Message]


class Agent:
    """An agent: configuration + provider + tools + memory, run as a loop."""

    def __init__(
        self,
        *,
        provider: ChatProvider,
        config: AgentConfig | None = None,
        tools: ToolRegistry | None = None,
        memory: BaseMemory | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.provider = provider
        self.tools = tools or ToolRegistry()
        self.memory = memory or InMemoryMemory()

    # -- public API ------------------------------------------------------------

    async def run(self, input: str | list[Message]) -> AgentRunResult:
        """Run the agent to completion and return the full result."""
        results: dict[str, AgentRunResult] = {}
        async for _event in self._execute(input, results):
            pass  # events are consumed by run_stream instead
        return results["result"]

    def run_stream(self, input: str | list[Message]) -> AsyncIterator[AgentEvent]:
        """Run the agent, yielding every event as it happens."""
        return self._execute(input, None)

    # -- the loop ----------------------------------------------------------------

    async def _execute(
        self,
        input: str | list[Message],
        result_out: dict[str, AgentRunResult] | None,
    ) -> AsyncIterator[AgentEvent]:
        config = self.config
        run_id = uuid.uuid4().hex
        started = time.perf_counter()
        total_usage = Usage()
        trace = RunTrace()

        await self._seed_history(input)

        yield RunStartedEvent(run_id=run_id, model=self.provider.model)

        finish_reason = FinishReason.STOP
        output = ""
        iterations = 0

        for iteration in range(1, config.max_iterations + 1):
            iterations = iteration
            yield IterationStartedEvent(iteration=iteration)

            step_started = time.perf_counter()
            chat: ChatResult | None = None
            async for event in self.provider.stream(
                await self.memory.messages(),
                tools=self.tools.openai_schemas() or None,
                **self._model_overrides(),
            ):
                if event.type == "text_delta" and event.delta:
                    yield TextDeltaEvent(delta=event.delta)
                elif event.type == "done" and event.result is not None:
                    chat = event.result
            if chat is None:
                raise ProviderError("provider stream ended without a result")

            latency_ms = round((time.perf_counter() - step_started) * 1000, 2)
            total_usage = total_usage + chat.usage
            trace.steps.append(
                ModelCallStep(
                    model=chat.model or self.provider.model,
                    prompt_messages=len(await self.memory.messages()),
                    completion=chat.content or "",
                    tool_call_count=len(chat.tool_calls),
                    usage=chat.usage,
                    finish_reason=chat.finish_reason,
                    latency_ms=latency_ms,
                )
            )
            await self.memory.add(
                Message(
                    role=Role.ASSISTANT,
                    content=chat.content,
                    tool_calls=list(chat.tool_calls),
                )
            )

            if not chat.tool_calls:
                finish_reason = FinishReason.STOP
                output = chat.content or ""
                break

            # Execute every requested tool call, then let the model continue.
            for call in chat.tool_calls:
                yield ToolCallStartedEvent(
                    call_id=call.id, name=call.name, arguments=call.arguments
                )
            steps = await self._execute_tool_calls(chat.tool_calls)
            for call, step in zip(chat.tool_calls, steps, strict=True):
                await self.memory.add(
                    Message.tool(
                        content=step.output, tool_call_id=call.id, name=call.name
                    )
                )
                trace.steps.append(step)
                yield ToolCallFinishedEvent(
                    call_id=call.id,
                    name=call.name,
                    output=step.output,
                    is_error=step.is_error,
                    latency_ms=step.latency_ms,
                )

            if iteration == config.max_iterations:
                # Budget exhausted: history stays consistent (every requested
                # tool call has an answer), but the model never got to speak.
                finish_reason = FinishReason.MAX_ITERATIONS
                output = ""
                break

        total_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        trace.iterations = iterations
        trace.total_latency_ms = total_latency_ms

        result = AgentRunResult(
            run_id=run_id,
            output=output,
            finish_reason=finish_reason,
            usage=total_usage,
            iterations=iterations,
            total_latency_ms=total_latency_ms,
            trace=trace,
            messages=await self.memory.messages(),
        )
        if result_out is not None:
            result_out["result"] = result

        yield RunFinishedEvent(
            run_id=run_id,
            finish_reason=finish_reason,
            output=output,
            usage=total_usage,
            iterations=iterations,
            total_latency_ms=total_latency_ms,
            trace=trace,
        )

    # -- helpers ------------------------------------------------------------------

    async def _seed_history(self, input: str | list[Message]) -> None:
        """Seed memory with the system prompt (once) and the run input."""
        history = await self.memory.messages()
        if self.config.system_prompt and not any(
            message.role is Role.SYSTEM for message in history
        ):
            await self.memory.add(Message.system(self.config.system_prompt))
        if isinstance(input, str):
            await self.memory.add(Message.user(input))
        else:
            await self.memory.extend(input)

    def _model_overrides(self) -> dict[str, Any]:
        overrides: dict[str, Any] = {"temperature": self.config.temperature}
        if self.config.max_tokens is not None:
            overrides["max_tokens"] = self.config.max_tokens
        return overrides

    async def _execute_tool_calls(self, calls: list[ToolCall]) -> list[ToolCallStep]:
        """Run tool calls in parallel (default) or strictly in order."""
        if self.config.parallel_tool_calls and len(calls) > 1:
            return list(
                await asyncio.gather(*(self._invoke_tool(call) for call in calls))
            )
        return [await self._invoke_tool(call) for call in calls]

    async def _invoke_tool(self, call: ToolCall) -> ToolCallStep:
        """Invoke one tool, converting any failure into a soft error step."""
        started = time.perf_counter()
        tool = self.tools.get(call.name)
        if tool is None:
            available = ", ".join(self.tools.names()) or "none"
            return self._tool_step(
                call,
                output=f"Error: tool '{call.name}' is not available. "
                f"Available tools: {available}.",
                is_error=True,
                error="tool_not_found",
                started=started,
            )
        try:
            output = await tool.execute(**call.arguments)
        except Exception as exc:
            return self._tool_step(
                call,
                output=f"Error from tool '{call.name}': {exc}",
                is_error=True,
                error="tool_execution_failed",
                started=started,
            )
        return self._tool_step(call, output=output, is_error=False, started=started)

    def _tool_step(
        self,
        call: ToolCall,
        *,
        output: str,
        is_error: bool,
        started: float,
        error: str | None = None,
    ) -> ToolCallStep:
        return ToolCallStep(
            tool=call.name,
            arguments=call.arguments,
            output=output,
            is_error=is_error,
            error=error,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
