"""Tests for the agent runtime loop."""

from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar

import pytest

from conftest import FakeProvider, text_result, tool_result
from nexusagent.agents import Agent
from nexusagent.config import AgentConfig
from nexusagent.exceptions import ProviderAuthError
from nexusagent.memory import InMemoryMemory
from nexusagent.tools import Tool, ToolRegistry
from nexusagent.types import FinishReason, Message, Role, ToolCall, Usage


class ExplodingTool(Tool):
    name = "explode"
    description = "always raises"
    parameters: ClassVar[dict[str, Any]] = {}

    async def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("kaboom")


class SlowOneTool(Tool):
    name = "slow_one"
    description = "sleeps, then records its execution"
    parameters: ClassVar[dict[str, Any]] = {}

    def __init__(self, order: list[str], delay: float) -> None:
        self._order = order
        self._delay = delay

    async def execute(self, **kwargs: Any) -> str:
        await asyncio.sleep(self._delay)
        self._order.append(self.name)
        return "slow_one done"


class SlowTwoTool(SlowOneTool):
    name = "slow_two"
    description = "sleeps, then records its execution"


# --- basic round-trips -----------------------------------------------------------


async def test_simple_roundtrip() -> None:
    provider = FakeProvider([text_result("Hello!")])
    agent = Agent(provider=provider, config=AgentConfig(system_prompt="be nice"))
    result = await agent.run("hi")

    assert result.output == "Hello!"
    assert result.finish_reason is FinishReason.STOP
    assert result.iterations == 1
    assert result.usage == Usage(prompt_tokens=10, completion_tokens=5)
    assert result.usage.total_tokens == 15
    assert [m.role for m in result.messages] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
    ]
    assert result.trace.model_dump()["steps"][0]["type"] == "model_call"


async def test_message_list_input_is_used_verbatim() -> None:
    provider = FakeProvider([text_result("ok")])
    agent = Agent(provider=provider)
    result = await agent.run([Message.user("a"), Message.user("b")])
    assert [m.content for m in result.messages] == ["a", "b", "ok"]


async def test_system_prompt_seeded_once_across_runs() -> None:
    provider = FakeProvider([text_result("one"), text_result("two")])
    memory = InMemoryMemory()
    agent = Agent(
        provider=provider, config=AgentConfig(system_prompt="sys"), memory=memory
    )
    await agent.run("first")
    result = await agent.run("second")
    assert len([m for m in result.messages if m.role is Role.SYSTEM]) == 1


# --- tool flows -------------------------------------------------------------------


async def test_tool_roundtrip(builtin_registry: ToolRegistry) -> None:
    provider = FakeProvider(
        [
            tool_result(
                [ToolCall(id="c1", name="calculator", arguments={"expression": "2+2"})]
            ),
            text_result("The answer is 4."),
        ]
    )
    agent = Agent(provider=provider, tools=builtin_registry)
    result = await agent.run("what is 2+2?")

    assert result.output == "The answer is 4."
    assert [step.type for step in result.trace.steps] == [
        "model_call",
        "tool_call",
        "model_call",
    ]

    tool_messages = [m for m in result.messages if m.role is Role.TOOL]
    assert tool_messages[0].content == "4"
    assert tool_messages[0].tool_call_id == "c1"
    assert tool_messages[0].name == "calculator"

    # the follow-up prompt contains the tool result
    assert any(m.role is Role.TOOL for m in provider.prompts[1])
    # and the registry offered every tool to the model
    assert provider.tools_seen[0] is not None
    assert len(provider.tools_seen[0]) == 3


async def test_parallel_tool_calls(builtin_registry: ToolRegistry) -> None:
    calls = [
        ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"}),
        ToolCall(id="c2", name="generate_uuid", arguments={}),
    ]
    provider = FakeProvider([tool_result(calls), text_result("done")])
    agent = Agent(provider=provider, tools=builtin_registry)
    result = await agent.run("run two tools")

    tool_messages = [m for m in result.messages if m.role is Role.TOOL]
    assert len(tool_messages) == 2
    assert {m.tool_call_id for m in tool_messages} == {"c1", "c2"}
    assert tool_messages[0].content == "2"


async def test_parallel_execution_is_concurrent() -> None:
    order: list[str] = []
    registry = ToolRegistry()
    registry.register_many(SlowOneTool(order, delay=0.1), SlowTwoTool(order, delay=0.1))

    provider = FakeProvider(
        [
            tool_result(
                [
                    ToolCall(id="c1", name="slow_one", arguments={}),
                    ToolCall(id="c2", name="slow_two", arguments={}),
                ]
            ),
            text_result("done"),
        ]
    )
    agent = Agent(provider=provider, tools=registry)
    started = time.perf_counter()
    result = await agent.run("parallel")
    elapsed = time.perf_counter() - started

    assert result.output == "done"
    assert sorted(order) == ["slow_one", "slow_two"]
    assert elapsed < 0.18  # sequential would be ~0.2s


async def test_sequential_execution_preserves_order() -> None:
    order: list[str] = []
    registry = ToolRegistry()
    registry.register_many(SlowOneTool(order, delay=0.0), SlowTwoTool(order, delay=0.0))

    provider = FakeProvider(
        [
            tool_result(
                [
                    ToolCall(id="c1", name="slow_one", arguments={}),
                    ToolCall(id="c2", name="slow_two", arguments={}),
                ]
            ),
            text_result("done"),
        ]
    )
    agent = Agent(
        provider=provider,
        tools=registry,
        config=AgentConfig(parallel_tool_calls=False),
    )
    await agent.run("sequential")
    assert order == ["slow_one", "slow_two"]


async def test_unknown_tool_soft_fails() -> None:
    provider = FakeProvider(
        [
            tool_result(
                [ToolCall(id="c1", name="does_not_exist", arguments={"x": 1})]
            ),
            text_result("recovered"),
        ]
    )
    agent = Agent(provider=provider, tools=ToolRegistry())
    result = await agent.run("try")

    assert result.finish_reason is FinishReason.STOP
    assert result.output == "recovered"

    tool_step = result.trace.steps[1]
    assert tool_step.type == "tool_call"
    assert tool_step.is_error is True
    assert tool_step.error == "tool_not_found"

    tool_message = next(m for m in result.messages if m.role is Role.TOOL)
    assert "not available" in tool_message.content


async def test_tool_exception_soft_fails() -> None:
    registry = ToolRegistry()
    registry.register(ExplodingTool())
    provider = FakeProvider(
        [
            tool_result([ToolCall(id="c1", name="explode", arguments={})]),
            text_result("handled"),
        ]
    )
    agent = Agent(provider=provider, tools=registry)
    result = await agent.run("boom")

    assert result.output == "handled"
    tool_step = result.trace.steps[1]
    assert tool_step.is_error is True
    assert tool_step.error == "tool_execution_failed"
    assert "kaboom" in tool_step.output


async def test_max_iterations_guard(builtin_registry: ToolRegistry) -> None:
    script = [
        tool_result(
            [ToolCall(id=f"c{i}", name="calculator", arguments={"expression": "1+1"})]
        )
        for i in range(5)
    ]
    provider = FakeProvider(script)
    agent = Agent(
        provider=provider,
        tools=builtin_registry,
        config=AgentConfig(max_iterations=3),
    )
    result = await agent.run("loop forever")

    assert result.finish_reason is FinishReason.MAX_ITERATIONS
    assert result.iterations == 3
    assert result.output == ""

    # history stays consistent: every requested call got a tool answer
    assistant_messages = [m for m in result.messages if m.role is Role.ASSISTANT]
    tool_messages = [m for m in result.messages if m.role is Role.TOOL]
    assert len(assistant_messages) == 3
    assert len(tool_messages) == 3
    # exactly three model calls were consumed from the script
    assert len(provider.script) == 2


async def test_usage_accumulates_over_iterations(builtin_registry: ToolRegistry) -> None:
    provider = FakeProvider(
        [
            tool_result(
                [ToolCall(id="c1", name="calculator", arguments={"expression": "2+2"})],
                prompt=10,
                completion=5,
            ),
            text_result("4", prompt=20, completion=7),
        ]
    )
    agent = Agent(provider=provider, tools=builtin_registry)
    result = await agent.run("what is 2+2?")

    assert result.usage == Usage(prompt_tokens=30, completion_tokens=12)
    assert result.usage.total_tokens == 42
    assert result.trace.model_calls[0].usage.prompt_tokens == 10
    assert result.trace.model_calls[1].usage.prompt_tokens == 20


async def test_provider_error_propagates() -> None:
    provider = FakeProvider([ProviderAuthError("bad key")])
    agent = Agent(provider=provider)
    with pytest.raises(ProviderAuthError, match="bad key"):
        await agent.run("hi")


async def test_memory_is_shared_across_runs(builtin_registry: ToolRegistry) -> None:
    memory = InMemoryMemory()
    provider = FakeProvider([text_result("first answer"), text_result("second answer")])
    agent = Agent(provider=provider, memory=memory)
    await agent.run("first question")
    result = await agent.run("second question")

    roles = [m.role for m in result.messages]
    assert roles == [Role.USER, Role.ASSISTANT, Role.USER, Role.ASSISTANT]
    # the second prompt included the prior exchange
    assert len(provider.prompts[1]) == 3
