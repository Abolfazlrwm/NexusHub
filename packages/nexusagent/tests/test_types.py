"""Tests for the core conversation types."""

from __future__ import annotations

import json

import pytest

from nexusagent.types import FinishReason, Message, Role, ToolCall, Usage


class TestToolCall:
    def test_from_openai_parses_valid_arguments(self) -> None:
        call = ToolCall.from_openai(
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "calculator", "arguments": '{"expression": "2+2"}'},
            }
        )
        assert call.id == "call_1"
        assert call.name == "calculator"
        assert call.arguments == {"expression": "2+2"}
        assert call.raw_arguments == '{"expression": "2+2"}'

    def test_from_openai_tolerates_malformed_json(self) -> None:
        call = ToolCall.from_openai(
            {"id": "call_2", "function": {"name": "broken", "arguments": "{not json"}}
        )
        assert call.arguments == {}
        assert call.raw_arguments == "{not json"

    def test_from_openai_tolerates_non_dict_json(self) -> None:
        call = ToolCall.from_openai(
            {"id": "call_3", "function": {"name": "t", "arguments": "[1, 2]"}}
        )
        assert call.arguments == {}

    def test_from_openai_accepts_pre_parsed_arguments(self) -> None:
        call = ToolCall.from_openai(
            {"id": "call_4", "function": {"name": "t", "arguments": {"a": 1}}}
        )
        assert call.arguments == {"a": 1}
        assert json.loads(call.raw_arguments) == {"a": 1}

    def test_from_openai_without_function_block(self) -> None:
        call = ToolCall.from_openai({"id": "call_5"})
        assert call.name == ""
        assert call.arguments == {}

    def test_to_openai_roundtrip(self) -> None:
        call = ToolCall(id="call_6", name="search", arguments={"q": "agents"})
        payload = call.to_openai()
        assert payload["type"] == "function"
        assert payload["function"]["name"] == "search"
        assert json.loads(payload["function"]["arguments"]) == {"q": "agents"}


class TestUsage:
    def test_total_tokens(self) -> None:
        assert Usage(prompt_tokens=10, completion_tokens=5).total_tokens == 15

    def test_addition(self) -> None:
        total = Usage(prompt_tokens=10, completion_tokens=5) + Usage(
            prompt_tokens=20, completion_tokens=7
        )
        assert total == Usage(prompt_tokens=30, completion_tokens=12)

    def test_addition_with_non_usage_raises(self) -> None:
        with pytest.raises(TypeError):
            _ = Usage() + 42


class TestMessageSerialization:
    def test_user_message(self) -> None:
        assert Message.user("hi").to_openai() == {"role": "user", "content": "hi"}

    def test_system_message(self) -> None:
        assert Message.system("be brief").to_openai() == {
            "role": "system",
            "content": "be brief",
        }

    def test_assistant_plain_text(self) -> None:
        assert Message.assistant("hello").to_openai() == {
            "role": "assistant",
            "content": "hello",
        }

    def test_assistant_with_tool_calls(self) -> None:
        call = ToolCall(id="c1", name="calc", arguments={"expression": "1+1"})
        payload = Message.assistant(None, [call]).to_openai()
        assert payload["role"] == "assistant"
        assert "content" not in payload
        assert payload["tool_calls"][0]["id"] == "c1"
        assert payload["tool_calls"][0]["function"]["name"] == "calc"

    def test_tool_result_message(self) -> None:
        payload = Message.tool("4", tool_call_id="c1", name="calc").to_openai()
        assert payload == {
            "role": "tool",
            "content": "4",
            "tool_call_id": "c1",
            "name": "calc",
        }


def test_finish_reason_values() -> None:
    assert FinishReason.STOP.value == "stop"
    assert FinishReason.MAX_ITERATIONS.value == "max_iterations"


def test_roles() -> None:
    assert [role.value for role in Role] == ["system", "user", "assistant", "tool"]
