"""API key lifecycle over HTTP."""

from __future__ import annotations


def create_key(client, headers, name="default"):
    response = client.post("/v1/api-keys", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_first_key_bootstraps_and_returns_plaintext(client):
    body = client.post("/v1/api-keys", json={"name": "ci-key"})
    assert body.status_code == 201
    payload = body.json()
    assert payload["key"].startswith("nx_")
    assert payload["prefix"] == payload["key"][:11]


def test_prefix_visible_in_listing(client, headers):
    body = create_key(client, headers, "visible")
    listed = client.get("/v1/api-keys", headers=headers).json()
    prefixes = {item["prefix"] for item in listed}
    assert body["prefix"] in prefixes
    # the plaintext itself never leaves the creation response
    assert all("key" not in item for item in listed)


def test_revoke_and_conflict(client, headers):
    body = create_key(client, headers)
    first = client.delete(f"/v1/api-keys/{body['id']}", headers=headers)
    assert first.status_code == 204
    listed = client.get("/v1/api-keys", headers=headers).json()
    revoked = [item for item in listed if item["id"] == body["id"]][0]
    assert revoked["revoked_at"] is not None

    again = client.delete(f"/v1/api-keys/{body['id']}", headers=headers)
    assert again.status_code == 409


def test_revoke_unknown_key_404(client, headers):
    response = client.delete("/v1/api-keys/nope", headers=headers)
    assert response.status_code == 404
