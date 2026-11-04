"""Run execution over HTTP (with the fake provider)."""

from __future__ import annotations

from nexusagent import ProviderAuthError

from conftest import FakeProvider


def test_run_without_session_completes(fake_provider_client, headers, agent):
    response = fake_provider_client.post(
        f"/v1/agents/{agent['id']}/runs",
        json={"input": "hello"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["output"] == "fake says hi"
    assert body["iterations"] >= 1
    assert body["usage"] == {"prompt_tokens": 2, "completion_tokens": 3}
    assert body["trace"] is not None
    assert body["model"] == "gpt-4o-mini"  # the configured model, from the agent row


def test_run_persists_history_in_session(fake_provider_client, headers, agent):
    chat_session = fake_provider_client.post(
        f"/v1/agents/{agent['id']}/sessions", json={}, headers=headers
    ).json()

    first = fake_provider_client.post(
        f"/v1/agents/{agent['id']}/runs",
        json={"input": "hi", "session_id": chat_session["id"]},
        headers=headers,
    )
    assert first.status_code == 201

    messages = fake_provider_client.get(
        f"/v1/sessions/{chat_session['id']}/messages", headers=headers
    ).json()
    roles = [message["role"] for message in messages]
    # system prompt is seeded by the engine, not stored; storage records the exchange
    assert roles == ["user", "assistant"]

    second = fake_provider_client.post(
        f"/v1/agents/{agent['id']}/runs",
        json={"input": "again", "session_id": chat_session["id"]},
        headers=headers,
    )
    assert second.status_code == 201
    messages = fake_provider_client.get(
        f"/v1/sessions/{chat_session['id']}/messages", headers=headers
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant"]


def test_run_rejects_foreign_session(fake_provider_client, headers, agent, client):
    other = client.post(
        "/v1/agents", json={"name": "other"}, headers=headers
    ).json()
    foreign_session = client.post(
        f"/v1/agents/{other['id']}/sessions", json={}, headers=headers
    ).json()
    response = fake_provider_client.post(
        f"/v1/agents/{agent['id']}/runs",
        json={"input": "hi", "session_id": foreign_session["id"]},
        headers=headers,
    )
    assert response.status_code == 404


def test_provider_failure_marks_run_failed(fake_provider_client, headers, agent):
    def failing_factory(name: str, **kwargs):
        class ExplodingProvider(FakeProvider):
            async def stream(self, messages, tools=None, **overrides):
                raise ProviderAuthError("bad key")
                yield  # pragma: no cover

        return ExplodingProvider(**kwargs)

    from nexushub_api.deps import get_provider_factory

    fake_provider_client.app.dependency_overrides[get_provider_factory] = lambda: failing_factory
    try:
        response = fake_provider_client.post(
            f"/v1/agents/{agent['id']}/runs", json={"input": "hi"}, headers=headers
        )
    finally:
        fake_provider_client.app.dependency_overrides.pop(get_provider_factory, None)

    assert response.status_code == 201  # the request succeeded; the run did not
    body = response.json()
    assert body["status"] == "failed"
    assert "bad key" in body["error"]
    assert body["finished_at"] is not None


def test_list_and_get_runs(fake_provider_client, headers, agent):
    fake_provider_client.post(
        f"/v1/agents/{agent['id']}/runs", json={"input": "one"}, headers=headers
    )
    listed = fake_provider_client.get(
        "/v1/runs", params={"agent_id": agent["id"]}, headers=headers
    ).json()
    assert listed["total"] == 1
    run_id = listed["items"][0]["id"]
    fetched = fake_provider_client.get(f"/v1/runs/{run_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run_id


def test_run_for_unknown_agent_404(fake_provider_client, headers):
    response = fake_provider_client.post(
        "/v1/agents/ghost/runs", json={"input": "hi"}, headers=headers
    )
    assert response.status_code == 404
