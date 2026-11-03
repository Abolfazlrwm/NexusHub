"""Bearer api key authentication."""

from __future__ import annotations


def test_missing_key_is_401(client):
    response = client.get("/v1/agents")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_invalid_key_is_401(client):
    response = client.get("/v1/agents", headers={"Authorization": "Bearer nx_wrong"})
    assert response.status_code == 401


def test_revoked_key_is_403(client, headers):
    keys = client.get("/v1/api-keys", headers=headers).json()
    key_id = keys[0]["id"]
    assert client.delete(f"/v1/api-keys/{key_id}", headers=headers).status_code == 204
    response = client.get("/v1/agents", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_first_key_bootstraps_without_auth(client):
    response = client.post("/v1/api-keys", json={"name": "bootstrap"})
    assert response.status_code == 201


def test_second_key_requires_auth(client):
    client.post("/v1/api-keys", json={"name": "bootstrap"})
    response = client.post("/v1/api-keys", json={"name": "sneaky"})
    assert response.status_code == 401


def test_second_key_with_auth_succeeds(client, headers):
    response = client.post("/v1/api-keys", json={"name": "second"}, headers=headers)
    assert response.status_code == 201
    keys = client.get("/v1/api-keys", headers=headers).json()
    assert len(keys) == 2


def test_revoked_keys_do_not_count_for_bootstrap(client, headers):
    keys = client.get("/v1/api-keys", headers=headers).json()
    client.delete(f"/v1/api-keys/{keys[0]['id']}", headers=headers)
    response = client.post("/v1/api-keys", json={"name": "fresh"})
    assert response.status_code == 201


def test_last_used_at_is_tracked(client, headers):
    client.get("/v1/agents", headers=headers)
    keys = client.get("/v1/api-keys", headers=headers).json()
    assert keys[0]["last_used_at"] is not None
