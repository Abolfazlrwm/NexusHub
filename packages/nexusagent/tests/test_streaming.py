"""Tests for the streaming run API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from conftest import FakeProvider, text_result, tool_result
from nexusagent.agents import Agent, AgentEvent
from nexusagent.tools import ToolRegistry, register_builtin_tools
from nexusagent.types import FinishReason, ToolCall


async def collect(agent: Agent, prompt: str) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    stream: AsyncIterator[AgentEvent] = agent.run_stream(prompt)
    async for event in stream:
        events.append(event)
    return events


async def test_text_run_event_sequence() -> None:
    provider = FakeProvider([text_result("Hello there, friend!")])
    agent = Agent(provider=provider)
    events = await collect(agent, "hi")

    types = [event.type for event in events]
    assert types[0] == "run_started"
    assert types[1] == "iteration_started"
    assert types[-1] == "run_finished"
    assert types.count("text_delta") >= 2

    deltas = "".join(
        event.delta for event in events if event.type == "text_delta" and event.delta
    )
    assert deltas == "Hello there, friend!"

    finished = events[-1]
    assert finished.finish_reason is FinishReason.STOP
    assert finished.output == "Hello there, friend!"
    assert finished.iterations == 1


async def test_tool_run_event_sequence() -> None:
    provider = FakeProvider(
        [
            tool_result(
                [ToolCall(id="c1", name="calculator", arguments={"expression": "2+2"})]
            ),
            text_result("The answer is 4."),
        ]
    )
    agent = Agent(provider=provider, tools=register_builtin_tools(ToolRegistry()))
    events = await collect(agent, "what is 2+2?")

    assert [event.type for event in events] == [
        "run_started",
        "iteration_started",
        "tool_call_started",
        "tool_call_finished",
        "iteration_started",
        "text_delta",
        "text_delta",
        "run_finished",
    ]

    started = events[2]
    assert started.call_id == "c1"
    assert started.name == "calculator"
    assert started.arguments == {"expression": "2+2"}

    finished_tool = events[3]
    assert finished_tool.call_id == "c1"
    assert finished_tool.output == "4"
    assert finished_tool.is_error is False


async def test_events_are_json_serializable() -> None:
    provider = FakeProvider([text_result("hi there")])
    agent = Agent(provider=provider)
    events = await collect(agent, "hello")

    assert events
    for event in events:
        payload = json.loads(event.model_dump_json())
        assert payload["type"] == event.type


async def test_run_finished_carries_the_trace() -> None:
    provider = FakeProvider(
        [
            tool_result(
                [ToolCall(id="c1", name="calculator", arguments={"expression": "7*6"})]
            ),
            text_result("42"),
        ]
    )
    agent = Agent(provider=provider, tools=register_builtin_tools(ToolRegistry()))
    events = await collect(agent, "7*6?")

    finished = events[-1]
    assert [step.type for step in finished.trace.steps] == [
        "model_call",
        "tool_call",
        "model_call",
    ]
    assert finished.trace.tool_calls[0].output == "42"
    assert finished.usage.total_tokens > 0


async def test_streaming_and_run_agree(builtin_registry: ToolRegistry) -> None:
    def fresh_provider() -> FakeProvider:
        return FakeProvider(
            [
                tool_result(
                    [ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"})]
                ),
                text_result("2"),
            ]
        )

    streamed_agent = Agent(provider=fresh_provider(), tools=builtin_registry)
    streamed = await collect(streamed_agent, "1+1?")

    direct_agent = Agent(provider=fresh_provider(), tools=builtin_registry)
    direct = await direct_agent.run("1+1?")

    assert streamed[-1].output == direct.output
    assert streamed[-1].usage == direct.usage
    assert streamed[-1].finish_reason is direct.finish_reason
    assert streamed[-1].iterations == direct.iterations
