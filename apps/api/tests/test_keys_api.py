"""API key lifecycle over HTTP."""

from __future__ import annotations


def create_key(client, name="default"):
    response = client.post("/v1/api-keys", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_created_key_is_returned_once(client):
    body = create_key(client, "ci-key")
    assert body["key"].startswith("nx_")
    assert body["prefix"] == body["key"][:11]

    listed = client.get("/v1/api-keys").json()
    assert listed[0]["prefix"] == body["prefix"]
    # the plaintext never appears again
    assert all("key" not in item or item.get("key") is None for item in listed)
    assert "key" not in listed[0]


def test_revoke_and_conflict(client):
    body = create_key(client)
    first = client.delete(f"/v1/api-keys/{body['id']}")
    assert first.status_code == 204
    listed = client.get("/v1/api-keys").json()
    assert listed[0]["revoked_at"] is not None

    again = client.delete(f"/v1/api-keys/{body['id']}")
    assert again.status_code == 409


def test_revoke_unknown_key_404(client):
    response = client.delete("/v1/api-keys/nope")
    assert response.status_code == 404
