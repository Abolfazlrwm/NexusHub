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
def agent(client):
    """One created agent, ready for sessions and runs."""
    response = client.post(
        "/v1/agents",
        json={"name": "helper", "system_prompt": "You are helpful."},
    )
    assert response.status_code == 201
    return response.json()
