"""Settings, key security and metadata endpoints."""

from __future__ import annotations

from nexushub_api.security import generate_api_key, hash_api_key, key_prefix
from nexushub_api.settings import Settings


def test_generate_api_key_shape():
    key = generate_api_key()
    assert key.startswith("nx_")
    assert len(key) > 20
    assert key_prefix(key) == key[:11]


def test_hash_is_deterministic_and_irreversible():
    key = generate_api_key()
    assert hash_api_key(key) == hash_api_key(key)
    assert hash_api_key(key) != key
    assert len(hash_api_key(key)) == 64


def test_settings_env_prefix(monkeypatch):
    monkeypatch.setenv("NEXUS_DATABASE_URL", "sqlite:///./env-test.db")
    monkeypatch.setenv("NEXUS_DEBUG", "true")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///./env-test.db"
    assert settings.debug is True


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version(client):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["service"] == "nexushub-api"
