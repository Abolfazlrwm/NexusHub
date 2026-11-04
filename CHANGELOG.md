# Changelog

All notable changes to NexusHub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `nexushub-api` gateway: FastAPI app factory with typed `NEXUS_`-prefixed
  settings and SQLModel persistence (agents, api keys, chat sessions,
  messages, runs) on SQLite or Postgres
- Agent, session, message, run and api-key CRUD endpoints with pagination
  and one stable error envelope
- Bearer API-key authentication: SHA-256 hashed keys, plaintext shown once,
  revocation, `last_used_at` tracking and first-key bootstrap rule
- Run execution bridged to the nexusagent runtime: provider resolution per
  agent (`provider_config` overrides, `OPENAI_*` env fallback), built-in
  tools, session history replay and transcript persistence
- SSE streaming endpoint forwarding the engine event protocol verbatim
  (`run_started` ... `run_finished`, plus `run_failed` on upstream errors)
- Per-run observability: status, usage, finish reason and trace JSON; the
  synchronous endpoint stores the engine's full step trace
- `api-ci` workflow (ruff, mypy, pytest on Python 3.10-3.13), Makefile
  tasks, curl walkthrough example and gateway README/architecture docs
- 38 gateway tests (115 total in the monorepo)


## [0.1.0] - 2026-11-03

### Added

- **nexusagent runtime core** (`packages/nexusagent`), the engine NexusHub is built on:
  - Core conversation types with OpenAI wire-format serialization, tolerant of
    malformed tool-call arguments
  - Immutable, validated `AgentConfig`
  - Agent loop: model calls, tool calling (parallel by default), memory
    seeding, iteration budget, soft tool failures, full per-step traces
  - Streaming runs with a typed event protocol (`text_delta`,
    `tool_call_started/finished`, `run_finished`)
  - OpenAI-compatible provider for any `/chat/completions` endpoint
    (OpenAI, OpenRouter, vLLM, LM Studio, Ollama) with SSE streaming,
    incremental tool-call reassembly and typed error mapping
  - In-memory conversation history with sliding-window trimming that pins
    system messages
  - Built-in tools: safe AST-based calculator, current datetime with IANA
    timezones, UUID generator
  - 97 tests, ruff-clean, fully type-checked; GitHub Actions CI on
    Python 3.10–3.13

### Planned

- FastAPI gateway: agent CRUD, chat streaming over SSE, API-key authentication
- Run history with full per-step traces
- RAG pipeline: document ingestion, embeddings, pgvector retrieval
- Async job queue on Redis + arq
- Eval engine: YAML datasets, parallel runs, scoring, comparison reports
- Next.js dashboard: agent builder, chat playground, trace viewer, eval reports
- One-command self-hosting via docker compose
