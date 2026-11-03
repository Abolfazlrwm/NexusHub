"""Chat sessions and stored messages over HTTP."""

from __future__ import annotations


def test_create_and_list_sessions(client, headers, agent):
    response = client.post(
        f"/v1/agents/{agent['id']}/sessions", json={"title": "support"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "support"
    assert body["agent_id"] == agent["id"]

    listed = client.get(f"/v1/agents/{agent['id']}/sessions", headers=headers).json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == body["id"]


def test_default_title(client, headers, agent):
    body = client.post(f"/v1/agents/{agent['id']}/sessions", json={}, headers=headers).json()
    assert body["title"] == "New session"


def test_session_messages_start_empty(client, headers, agent):
    chat_session = client.post(
        f"/v1/agents/{agent['id']}/sessions", json={}, headers=headers
    ).json()
    response = client.get(f"/v1/sessions/{chat_session['id']}/messages", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_delete_session(client, headers, agent):
    chat_session = client.post(
        f"/v1/agents/{agent['id']}/sessions", json={}, headers=headers
    ).json()
    assert client.delete(f"/v1/sessions/{chat_session['id']}", headers=headers).status_code == 204
    assert client.get(f"/v1/sessions/{chat_session['id']}", headers=headers).status_code == 404


def test_session_for_unknown_agent_404(client, headers):
    response = client.post("/v1/agents/ghost/sessions", json={}, headers=headers)
    assert response.status_code == 404
