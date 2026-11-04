"""SSE streaming of agent runs."""

from __future__ import annotations


def test_stream_emits_engine_events(fake_provider_client, headers, agent):
    with fake_provider_client.stream(
        "POST",
        f"/v1/agents/{agent['id']}/runs/stream",
        json={"input": "hello"},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: run_started" in body
    assert "event: text_delta" in body
    assert "event: run_finished" in body
    assert "fake says hi" in body


def test_stream_persists_the_run(fake_provider_client, headers, agent):
    with fake_provider_client.stream(
        "POST",
        f"/v1/agents/{agent['id']}/runs/stream",
        json={"input": "hello"},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        "".join(response.iter_text())

    listed = fake_provider_client.get(
        "/v1/runs", params={"agent_id": agent["id"]}, headers=headers
    ).json()
    assert listed["total"] == 1
    run = listed["items"][0]
    assert run["status"] == "completed"
    assert run["output"] == "fake says hi"
    # streamed runs record tool steps; here there were none
    assert run["trace"]["steps"] == []


def test_stream_persists_session_messages(fake_provider_client, headers, agent):
    chat_session = fake_provider_client.post(
        f"/v1/agents/{agent['id']}/sessions", json={}, headers=headers
    ).json()
    with fake_provider_client.stream(
        "POST",
        f"/v1/agents/{agent['id']}/runs/stream",
        json={"input": "hello", "session_id": chat_session["id"]},
        headers=headers,
    ) as response:
        "".join(response.iter_text())

    messages = fake_provider_client.get(
        f"/v1/sessions/{chat_session['id']}/messages", headers=headers
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
