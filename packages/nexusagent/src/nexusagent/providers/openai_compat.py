"""OpenAI-compatible chat-completions provider.

One wire format covers OpenAI, OpenRouter, Together, Groq, vLLM, LM Studio
and Ollama (through its OpenAI shim) — exactly the endpoints a self-hosted
deployment wants. Point ``base_url`` at any of them and the rest of the
runtime does not care which one answered.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from ..types import FinishReason, Message, ToolCall, Usage
from .base import ChatResult, ProviderEvent

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_USER_AGENT = "nexusagent (github.com/Abolfazlrwm/NexusHub)"

_FINISH_REASONS = {
    "stop": FinishReason.STOP,
    "tool_calls": FinishReason.TOOL_CALLS,
    "length": FinishReason.LENGTH,
}


def _map_finish_reason(raw: str | None) -> FinishReason:
    return _FINISH_REASONS.get(raw or "", FinishReason.STOP)


def _parse_usage(raw: dict[str, Any] | None) -> Usage:
    if not raw:
        return Usage()
    return Usage(
        prompt_tokens=int(raw.get("prompt_tokens") or 0),
        completion_tokens=int(raw.get("completion_tokens") or 0),
    )


class OpenAICompatProvider:
    """Chat provider for any OpenAI-compatible ``/chat/completions`` endpoint.

    Pass ``http_client`` to inject a pre-configured :class:`httpx.AsyncClient`
    (used by tests and by the platform for connection pooling); otherwise a
    client is created lazily and reused.
    """

    name = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
        default_headers: dict[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model:
            raise ValueError("model must be a non-empty string")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_key = api_key
        self._default_headers = dict(default_headers or {})
        self._client = http_client

    # -- public API ------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> ChatResult:
        """Perform a non-streaming chat completion."""
        payload = self._build_payload(messages, tools, overrides, stream=False)
        response = await self._request(payload)
        return self._parse_response(response)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> AsyncIterator[ProviderEvent]:
        """Stream a chat completion as provider events.

        Yields ``text_delta`` events as content arrives, then a single
        ``done`` event carrying the assembled result.
        """
        payload = self._build_payload(messages, tools, overrides, stream=True)
        payload["stream_options"] = {"include_usage": True}

        client = self._ensure_client()
        request = client.build_request(
            "POST", "/chat/completions", json=payload, headers=self._headers()
        )
        try:
            response = await client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"provider timed out after {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"connection to provider failed: {exc}") from exc

        try:
            if response.status_code >= 400:
                await self._raise_for_status(response)
            async for event in self._parse_stream(response):
                yield event
        finally:
            await response.aclose()

    # -- internals -----------------------------------------------------------

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        """Per-request headers.

        Auth is attached per request rather than baked into the client so
        that injected clients (tests, platform connection pools) send the
        same credentials as provider-owned ones.
        """
        headers = {
            "User-Agent": _USER_AGENT,
            **self._default_headers,
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
        overrides: dict[str, Any],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.to_openai() for message in messages],
            **overrides,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        return payload

    async def _request(self, payload: dict[str, Any]) -> httpx.Response:
        client = self._ensure_client()
        try:
            response = await client.post(
                "/chat/completions", json=payload, headers=self._headers()
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"provider timed out after {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"connection to provider failed: {exc}") from exc
        if response.status_code >= 400:
            await self._raise_for_status(response)
        return response

    async def _raise_for_status(self, response: httpx.Response) -> None:
        body = (await response.aread()).decode("utf-8", errors="replace")
        status = response.status_code
        snippet = body[:2000]
        if status in (401, 403):
            raise ProviderAuthError(
                "provider rejected the API key",
                status_code=status,
                response_body=snippet,
            )
        if status == 429:
            raise ProviderRateLimitError(
                "provider rate limit exceeded",
                status_code=status,
                response_body=snippet,
                retry_after=response.headers.get("retry-after"),
            )
        raise ProviderError(
            f"provider returned HTTP {status}",
            status_code=status,
            response_body=snippet,
        )

    def _parse_response(self, response: httpx.Response) -> ChatResult:
        data = response.json()
        choices = data.get("choices") or [{}]
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        return ChatResult(
            content=message.get("content"),
            tool_calls=[ToolCall.from_openai(call) for call in tool_calls],
            usage=_parse_usage(data.get("usage")),
            finish_reason=_map_finish_reason(choices[0].get("finish_reason")),
            model=data.get("model", self.model),
        )

    async def _parse_stream(self, response: httpx.Response) -> AsyncIterator[ProviderEvent]:
        text_parts: list[str] = []
        tool_calls: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None
        usage = Usage()
        model = self.model

        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            model = chunk.get("model") or model
            choices = chunk.get("choices") or []
            if not choices:
                # Usage-only chunk, sent when stream_options.include_usage is on.
                usage = _parse_usage(chunk.get("usage"))
                continue

            choice = choices[0]
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta") or {}

            content_delta = delta.get("content")
            if content_delta:
                text_parts.append(content_delta)
                yield ProviderEvent(type="text_delta", delta=content_delta)

            for tool_delta in delta.get("tool_calls") or []:
                index = tool_delta.get("index", 0)
                accumulator = tool_calls.setdefault(
                    index, {"id": "", "name": "", "arguments": ""}
                )
                if tool_delta.get("id"):
                    accumulator["id"] = tool_delta["id"]
                function = tool_delta.get("function") or {}
                if function.get("name"):
                    accumulator["name"] = function["name"]
                if function.get("arguments"):
                    accumulator["arguments"] += function["arguments"]

        yield ProviderEvent(
            type="done",
            result=ChatResult(
                content="".join(text_parts) or None,
                tool_calls=[
                    ToolCall.from_openai(
                        {
                            "id": acc["id"],
                            "type": "function",
                            "function": {
                                "name": acc["name"],
                                "arguments": acc["arguments"],
                            },
                        }
                    )
                    for _, acc in sorted(tool_calls.items())
                ],
                usage=usage,
                finish_reason=_map_finish_reason(finish_reason),
                model=model,
            ),
        )
