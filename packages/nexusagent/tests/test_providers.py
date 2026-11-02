"""Tests for the OpenAI-compatible provider, driven by a mocked HTTP transport."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from nexusagent.exceptions import (
    ConfigurationError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
)
from nexusagent.providers import (
    DEFAULT_BASE_URL,
    OpenAICompatProvider,
    ProviderRegistry,
)
from nexusagent.types import FinishReason, Message, ToolCall, Usage

BASE_URL = "https://provider.test/v1"


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=BASE_URL)


def sse_body(chunks: list[dict[str, Any]]) -> str:
    lines = [json.dumps(chunk) for chunk in chunks]
    return "".join(f"data: {line}\n\n" for line in lines) + "data: [DONE]\n\n"


def completion_response(content: str | None = "Hello there", **overrides: Any) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    message.update(overrides.pop("message", {}))
    payload: dict[str, Any] = {
        "id": "chatcmpl-test",
        "model": "test-model",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 6},
    }
    payload.update(overrides)
    return payload


# --- non-streaming -------------------------------------------------------------


async def test_complete_parses_plain_response() -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "payload": json.loads(request.content),
                "authorization": request.headers.get("authorization"),
            }
        )
        return httpx.Response(200, json=completion_response())

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(
            model="test-model", api_key="sk-test", http_client=client
        )
        result = await provider.complete([Message.user("hi")])

    assert result.content == "Hello there"
    assert result.tool_calls == []
    assert result.finish_reason is FinishReason.STOP
    assert result.usage == Usage(prompt_tokens=12, completion_tokens=6)
    assert result.model == "test-model"

    request = captured[0]
    assert request["authorization"] == "Bearer sk-test"
    assert request["payload"]["model"] == "test-model"
    assert request["payload"]["stream"] is False
    assert request["payload"]["messages"] == [{"role": "user", "content": "hi"}]
    assert "tools" not in request["payload"]


async def test_complete_parses_tool_calls_and_forwards_tools() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tools"] == [{"type": "function", "function": {"name": "calc"}}]
        return httpx.Response(
            200,
            json=completion_response(
                content=None,
                message={
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "calculator",
                                "arguments": '{"expression": "2+2"}',
                            },
                        }
                    ],
                },
            ),
        )

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        result = await provider.complete(
            [Message.user("what is 2+2?")],
            tools=[{"type": "function", "function": {"name": "calc"}}],
        )

    assert result.content is None
    assert result.tool_calls == [
        ToolCall(
            id="call_1",
            name="calculator",
            arguments={"expression": "2+2"},
            raw_arguments='{"expression": "2+2"}',
        )
    ]


async def test_overrides_are_forwarded() -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=completion_response())

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        await provider.complete([Message.user("hi")], temperature=0.2, max_tokens=64)

    assert captured[0]["temperature"] == 0.2
    assert captured[0]["max_tokens"] == 64


# --- error mapping ---------------------------------------------------------------


async def test_auth_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        with pytest.raises(ProviderAuthError, match="rejected the API key"):
            await provider.complete([Message.user("hi")])


async def test_rate_limit_error_mapped_with_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "slow down"}},
            headers={"retry-after": "30"},
        )

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        with pytest.raises(ProviderRateLimitError) as excinfo:
            await provider.complete([Message.user("hi")])
    assert excinfo.value.retry_after == "30"
    assert excinfo.value.status_code == 429


async def test_server_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        with pytest.raises(ProviderError, match="HTTP 500") as excinfo:
            await provider.complete([Message.user("hi")])
    assert excinfo.value.status_code == 500
    assert excinfo.value.response_body == "boom"


# --- streaming -------------------------------------------------------------------


async def test_stream_yields_text_deltas_then_done() -> None:
    chunks = [
        {"model": "test-model", "choices": [{"index": 0, "delta": {"content": "Hel"}}]},
        {"model": "test-model", "choices": [{"index": 0, "delta": {"content": "lo"}}]},
        {"model": "test-model", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        {
            "model": "test-model",
            "choices": [],
            "usage": {"prompt_tokens": 15, "completion_tokens": 4},
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body(chunks).encode())

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        events = [event async for event in provider.stream([Message.user("hi")])]

    assert [event.type for event in events] == ["text_delta", "text_delta", "done"]
    assert events[0].delta == "Hel"
    assert events[1].delta == "lo"
    done = events[2].result
    assert done is not None
    assert done.content == "Hello"
    assert done.finish_reason is FinishReason.STOP
    assert done.usage.prompt_tokens == 15
    assert done.usage.completion_tokens == 4
    assert done.tool_calls == []


async def test_stream_assembles_split_tool_call_arguments() -> None:
    chunks = [
        {
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "calculator", "arguments": ""},
                            }
                        ]
                    },
                }
            ],
        },
        {
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '{"expr'}}
                        ]
                    },
                }
            ],
        },
        {
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": 'ession": "2+2"}'}}
                        ]
                    },
                }
            ],
        },
        {
            "model": "test-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body(chunks).encode())

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        events = [event async for event in provider.stream([Message.user("hi")])]

    done = events[-1].result
    assert events[-1].type == "done"
    assert done is not None
    assert done.content is None
    assert done.finish_reason is FinishReason.TOOL_CALLS
    assert done.tool_calls == [
        ToolCall(
            id="call_1",
            name="calculator",
            arguments={"expression": "2+2"},
            raw_arguments='{"expression": "2+2"}',
        )
    ]


async def test_stream_assembles_parallel_tool_calls_by_index() -> None:
    chunks = [
        {
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 1,
                                "id": "call_b",
                                "function": {"name": "current_datetime", "arguments": "{}"},
                            },
                            {
                                "index": 0,
                                "id": "call_a",
                                "function": {"name": "calculator", "arguments": "{}"},
                            },
                        ]
                    },
                }
            ],
        },
        {
            "model": "test-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body(chunks).encode())

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        events = [event async for event in provider.stream([Message.user("hi")])]

    done = events[-1].result
    assert done is not None
    assert [call.id for call in done.tool_calls] == ["call_a", "call_b"]
    assert [call.name for call in done.tool_calls] == ["calculator", "current_datetime"]


async def test_stream_sends_stream_options_and_tools() -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, content=sse_body([]).encode())

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        _ = [
            event
            async for event in provider.stream(
                [Message.user("hi")],
                tools=[{"type": "function", "function": {"name": "calc"}}],
            )
        ]

    payload = captured[0]
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["tools"] == [{"type": "function", "function": {"name": "calc"}}]


async def test_stream_auth_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    async with make_client(handler) as client:
        provider = OpenAICompatProvider(model="test-model", http_client=client)
        with pytest.raises(ProviderAuthError):
            async for _ in provider.stream([Message.user("hi")]):
                pass


# --- construction and registry ----------------------------------------------------


def test_empty_model_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        OpenAICompatProvider(model="")


def test_default_base_url() -> None:
    assert DEFAULT_BASE_URL == "https://api.openai.com/v1"
    provider = OpenAICompatProvider(model="m", base_url="https://x.test/v1/")
    assert provider.base_url == "https://x.test/v1"


def test_registry_creates_openai_provider() -> None:
    provider = ProviderRegistry.create("openai-compat", model="gpt-4o-mini", api_key="k")
    assert isinstance(provider, OpenAICompatProvider)
    assert provider.model == "gpt-4o-mini"


def test_registry_unknown_provider_raises() -> None:
    with pytest.raises(ConfigurationError, match="unknown provider"):
        ProviderRegistry.create("does-not-exist", model="m")


def test_registry_lists_providers() -> None:
    assert "openai" in ProviderRegistry.available()
    assert "openai-compat" in ProviderRegistry.available()


def test_registry_duplicate_registration_raises() -> None:
    with pytest.raises(ValueError, match="already registered"):
        ProviderRegistry.register("openai", OpenAICompatProvider)
