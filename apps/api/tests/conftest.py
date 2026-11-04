"""Shared fixtures for the API test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nexusagent import ChatResult, ProviderEvent, Usage
from nexusagent.providers.base import ChatProvider

from nexushub_api.deps import get_provider_factory
from nexushub_api.main import create_app
from nexushub_api.settings import Settings


class FakeProvider(ChatProvider):
    """Deterministic provider for tests: echoes a fixed answer."""

    name = "fake"

    def __init__(self, *, model: str = "fake-mini", **kwargs: object) -> None:
        self.model = model

    async def complete(self, messages, tools=None, **overrides):
        return ChatResult(
            content="fake says hi",
            usage=Usage(prompt_tokens=2, completion_tokens=3),
            model=self.model,
        )

    async def stream(self, messages, tools=None, **overrides):
        yield ProviderEvent(type="text_delta", delta="fake ")
        yield ProviderEvent(type="text_delta", delta="says hi")
        yield ProviderEvent(
            type="done",
            result=ChatResult(
                content="fake says hi",
                usage=Usage(prompt_tokens=2, completion_tokens=3),
                model=self.model,
            ),
        )


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path}/test.db", _env_file=None)


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        yield http


@pytest.fixture
def fake_provider_client(client):
    """Client whose runs execute against FakeProvider instead of HTTP."""

    def factory(name: str, **kwargs):
        return FakeProvider(**kwargs)

    client.app.dependency_overrides[get_provider_factory] = lambda: factory
    yield client
    client.app.dependency_overrides.pop(get_provider_factory, None)


@pytest.fixture
def headers(client):
    """Authenticate via the bootstrap rule (no active keys yet)."""
    response = client.post("/v1/api-keys", json={"name": "tests"})
    assert response.status_code == 201
    key = response.json()["key"]
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture
def agent(client, headers):
    """One created agent, ready for sessions and runs."""
    response = client.post(
        "/v1/agents",
        json={"name": "helper", "system_prompt": "You are helpful."},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()
