"""Agent CRUD over HTTP."""

from __future__ import annotations


def test_create_and_get_agent(client, headers):
    response = client.post(
        "/v1/agents",
        json={"name": "writer", "system_prompt": "You write well.", "temperature": 0.3},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "writer"
    assert body["provider"] == "openai-compat"
    assert body["temperature"] == 0.3

    fetched = client.get(f"/v1/agents/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_duplicate_agent_name_conflicts(client, headers):
    client.post("/v1/agents", json={"name": "dup"}, headers=headers)
    second = client.post("/v1/agents", json={"name": "dup"}, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_validation_rejects_bad_temperature(client, headers):
    response = client.post("/v1/agents", json={"name": "hot", "temperature": 9.0}, headers=headers)
    assert response.status_code == 422


def test_list_agents_paginates(client, headers):
    for index in range(5):
        client.post("/v1/agents", json={"name": f"agent-{index}"}, headers=headers)
    page = client.get("/v1/agents", params={"limit": 2, "offset": 1}, headers=headers)
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["limit"] == 2


def test_update_agent_partial(client, headers):
    created = client.post("/v1/agents", json={"name": "before"}, headers=headers).json()
    updated = client.patch(
        f"/v1/agents/{created['id']}",
        json={"description": "now with a description"},
        headers=headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["description"] == "now with a description"
    assert body["name"] == "before"


def test_delete_agent(client, headers):
    created = client.post("/v1/agents", json={"name": "gone"}, headers=headers).json()
    deleted = client.delete(f"/v1/agents/{created['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/v1/agents/{created['id']}", headers=headers).status_code == 404


def test_unknown_agent_is_404(client, headers):
    response = client.get("/v1/agents/does-not-exist", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
