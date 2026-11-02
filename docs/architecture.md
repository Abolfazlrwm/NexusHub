# NexusHub Architecture

This document describes the target architecture of NexusHub, the boundaries
between its components, and the reasoning behind the key decisions. It is
written up-front and evolves with the codebase: when a component lands, its
section is updated to reflect what was actually built.

## Goals

1. **Self-hosted, one command.** `docker compose up` starts the full stack —
   no cloud account, no data leaving the machine.
2. **Eval-first.** An agent is only shippable if you can measure it. Datasets,
   parallel eval runs, scoring and version comparison are core features, not
   extras.
3. **Full observability.** Every run is recorded: every model call, tool call,
   token count, latency and error. Debugging an agent without a trace is
   guesswork.
4. **Small core, thin platform.** The runtime (`nexusagent`) is a standalone
   package with zero platform dependencies; the platform is a service layer
   around it.

## Non-goals

- Re-implementing LangChain-scale abstractions: the runtime stays small and
  focused on the agentic loop.
- Multi-tenant SaaS concerns (billing, orgs, quotas beyond basic rate limits).
- Training or fine-tuning of models.

## Components

| Component | Tech | Responsibility |
| --- | --- | --- |
| Dashboard | Next.js | Agent builder, chat playground, run/trace viewer, eval reports, API keys |
| API Gateway | FastAPI | REST + SSE, validation, API-key auth, auto OpenAPI docs |
| Agent Runtime | `nexusagent` | The agentic loop: model calls, tool calling, memory, streaming, tracing |
| RAG Pipeline | FastAPI service + pgvector | upload → chunk → embed → store → retrieve as a tool |
| Job Queue | Redis + arq | Async execution of long agent runs and eval jobs |
| Eval Engine | worker-side service | YAML datasets → parallel runs → scoring → comparison report |
| Storage | PostgreSQL + pgvector | agents, runs (with traces), documents/chunks, eval results, API keys |

## Data flows

### 1. Streaming chat run

```text
Dashboard ──POST /agents/{id}/chat──► Gateway ──► nexusagent Agent
       ◄────────────SSE events──────────────┘
events: run_started · text_delta · tool_call_started ·
        tool_call_finished · run_finished
```

Each run is persisted with its full trace: per-step model calls (usage,
latency, finish reason) and tool calls (arguments, output, errors).

### 2. Document ingestion (RAG)

```text
upload ─► extract text ─► chunk (size + overlap) ─► embedding
       ─► pgvector ─► retrieval tool exposed to agents
```

Retrieval is just another tool from the runtime's point of view — the agent
decides when to consult the knowledge base.

### 3. Eval run

```text
YAML dataset (cases: input + expected) 
   ─► enqueue on Redis ─► arq worker: run agent per case in parallel
   ─► score (exact/contains + LLM-as-judge)
   ─► aggregate: accuracy · latency p50/p95 · token cost
   ─► compare report vs. a previous eval run (e.g. prompt A vs. prompt B)
```

## Storage model (sketch)

- `agents` — name, model, system prompt, temperature, tool config, version
- `runs` — agent id, input, output, finish reason, usage totals, full trace
  JSON, latency, status
- `documents` / `chunks` — source file metadata; chunks with embedding vectors
- `eval_datasets` / `eval_runs` / `eval_case_results` — dataset YAML, run
  parameters, per-case scores and aggregates
- `api_keys` — hashed keys, scopes, last-seen timestamps

## Key decisions

- **A custom runtime instead of an existing framework.** The platform's value
  is the product layer (eval, traces, UX). Owning a small runtime keeps the
  loop debuggable, dependency-light, and makes tracing a first-class citizen
  rather than a patched-in callback.
- **OpenAI-compatible providers only (for now).** One wire format covers
  OpenAI, OpenRouter, vLLM, LM Studio and Ollama — which is exactly the
  self-hosted audience. A provider abstraction exists, so multi-vendor
  support is additive work.
- **Postgres + pgvector instead of a separate vector DB.** One storage engine
  for relational data and vectors; fewer moving parts; `docker compose` stays
  simple.
- **Redis + arq for async jobs.** Eval runs and long agent runs must not block
  HTTP workers. arq is async-native, small, and has no codegen ceremony.
- **Soft tool failures.** A failing tool returns an error message *to the
  model* instead of crashing the run — the agent can apologize, retry, or
  route around the failure. Crashes are reserved for infrastructure errors
  (auth, connectivity, budget).

## Security notes

- API keys are stored hashed; the plaintext key is shown exactly once at
  creation.
- Provider credentials live in environment variables, never in the database.
- The gateway is the only component exposed to end users; the worker and
  database are internal to the compose network.
