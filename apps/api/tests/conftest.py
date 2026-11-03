"""Shared fixtures for the API test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexushub_api.main import create_app
from nexushub_api.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path}/test.db", _env_file=None)


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        yield http


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
