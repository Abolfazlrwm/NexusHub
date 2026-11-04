# nexushub-api — the NexusHub API gateway

A FastAPI gateway in front of the [`nexusagent`](../../packages/nexusagent) runtime:
agents, chat sessions, runs and API keys, persisted with SQLModel and streamed
over SSE.

The gateway owns **persistence and transport**; the engine owns **agent
behaviour**. Everything the gateway knows about running agents comes from the
`nexusagent` public API — the runtime is never re-implemented here.

## Install

```bash
pip install -e "packages/nexusagent[dev]" -e "apps/api[dev]"
```

## Run

```bash
uvicorn nexushub_api.main:app --reload --port 8000
# or: make run-api
```

Interactive docs: <http://127.0.0.1:8000/docs>

## Configuration

All settings are `NEXUS_`-prefixed environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXUS_DATABASE_URL` | `sqlite:///./nexushub.db` | Any SQLAlchemy URL (Postgres works unchanged) |
| `NEXUS_DEBUG` | `false` | Verbose errors |
| `NEXUS_CORS_ORIGINS` | localhost:3000 | Dashboard origins (JSON list) |

Provider secrets stay out of the database by default: runs read
`OPENAI_API_KEY` / `OPENAI_BASE_URL` from the environment unless an agent's
`provider_config` overrides them.

## Authentication

Bearer API keys: `Authorization: Bearer nx_...`.

- `POST /v1/api-keys` returns the plaintext **exactly once**; only a SHA-256
  hash is stored.
- The **first active key** can be created without credentials (bootstrap);
  afterwards, creating more keys requires an authenticated caller.
- Revoked keys answer `403`; unknown or missing keys answer `401`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz`, `/version` | Liveness and version (no auth) |
| `POST` | `/v1/api-keys` | Create a key (bootstrap rule above) |
| `GET` / `DELETE` | `/v1/api-keys[/{id}]` | List / revoke keys |
| `POST` / `GET` | `/v1/agents` | Create / page agents |
| `GET` / `PATCH` / `DELETE` | `/v1/agents/{id}` | Read / update / delete an agent |
| `POST` / `GET` | `/v1/agents/{id}/sessions` | Open / list chat sessions |
| `GET` | `/v1/sessions/{id}` | Session detail |
| `GET` | `/v1/sessions/{id}/messages` | Stored transcript |
| `DELETE` | `/v1/sessions/{id}` | Delete a session and its messages |
| `POST` | `/v1/agents/{id}/runs` | Execute a run synchronously |
| `POST` | `/v1/agents/{id}/runs/stream` | Execute a run, streaming SSE events |
| `GET` | `/v1/runs[?agent_id=]` | Page runs |
| `GET` | `/v1/runs/{id}` | Run detail with usage and trace |

### The run contract

Creating a run always succeeds (201) as long as the agent and session exist —
the **outcome lives on the run resource**. A provider outage produces a run
with `status="failed"` and an `error` string, not a 5xx, so clients get a
durable record of what happened instead of a transient HTTP error.

SSE streams emit the engine's event protocol verbatim:
`run_started`, `iteration_started`, `text_delta`, `tool_call_started`,
`tool_call_finished`, `run_finished` (plus `run_failed` on upstream errors).

### Sessions and history

Sessions are the persistence side of conversations. The engine re-seeds its
system prompt every run; the database stores only the actual exchange
(`user`, `assistant`, `tool` messages), and each run in the same session
replays that transcript before executing.

## Design notes

- **Error envelope**: every error is
  `{"error": {"code": "...", "message": "..."}}` — clients read `code`.
- **Engine failures are upstream**: `NexusAgentError` maps to `502`;
  configuration mistakes map to `500` (deployment problem, not client's).
- **Dependency seams**: settings come from `app.state`, the provider factory
  is a dependency — tests override both without monkey-patching.

See `examples/api_flow.sh` for a complete scripted walkthrough.
