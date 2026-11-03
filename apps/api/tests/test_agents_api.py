"""Agent CRUD over HTTP."""

from __future__ import annotations


def test_create_and_get_agent(client):
    response = client.post(
        "/v1/agents",
        json={"name": "writer", "system_prompt": "You write well.", "temperature": 0.3},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "writer"
    assert body["provider"] == "openai-compat"
    assert body["temperature"] == 0.3

    fetched = client.get(f"/v1/agents/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_duplicate_agent_name_conflicts(client):
    client.post("/v1/agents", json={"name": "dup"})
    second = client.post("/v1/agents", json={"name": "dup"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_validation_rejects_bad_temperature(client):
    response = client.post("/v1/agents", json={"name": "hot", "temperature": 9.0})
    assert response.status_code == 422


def test_list_agents_paginates(client):
    for index in range(5):
        client.post("/v1/agents", json={"name": f"agent-{index}"})
    page = client.get("/v1/agents", params={"limit": 2, "offset": 1})
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["limit"] == 2


def test_update_agent_partial(client):
    created = client.post("/v1/agents", json={"name": "before"}).json()
    updated = client.patch(
        f"/v1/agents/{created['id']}", json={"description": "now with a description"}
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["description"] == "now with a description"
    assert body["name"] == "before"


def test_delete_agent(client):
    created = client.post("/v1/agents", json={"name": "gone"}).json()
    deleted = client.delete(f"/v1/agents/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/v1/agents/{created['id']}").status_code == 404


def test_unknown_agent_is_404(client):
    response = client.get("/v1/agents/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
