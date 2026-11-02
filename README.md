<div align="center">

# NexusHub

**Self-hosted AI agent platform — build, run, evaluate.**

FastAPI · Next.js · PostgreSQL + pgvector · Redis — powered by the [nexusagent](packages/nexusagent) runtime

[![engine-ci](https://github.com/Abolfazlrwm/NexusHub/actions/workflows/engine-ci.yml/badge.svg)](https://github.com/Abolfazlrwm/NexusHub/actions/workflows/engine-ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](packages/nexusagent/pyproject.toml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

English · [فارسی](README.fa.md)

</div>

---

## What is NexusHub?

NexusHub is an open-source, **self-hosted platform for building, running, evaluating and managing AI agents** — think Dify or LangSmith, but lighter, simpler, and entirely on your own infrastructure.

It is built on one core idea: **you cannot ship an agent you cannot measure.** Evaluation, tracing and observability are not bolted on top — they are part of the runtime from day one.

| Common pain | NexusHub answer |
| --- | --- |
| Cloud agent platforms send your data outside the company | Everything runs on your own server — `docker compose up` and you are done |
| Most open-source agent tools have no eval story | An eval engine in the core: YAML datasets, parallel runs, LLM-as-judge scoring, side-by-side version comparison |
| One tool for RAG, another for eval, another for tracing | One platform: agent builder, chat playground, RAG, traces and evals side by side |

## Architecture

```text
                    ┌─────────────────────────┐
                    │   Dashboard (Next.js)   │
                    │ builder · chat · traces │
                    └────────────┬────────────┘
                                 │ REST + SSE
                    ┌────────────▼────────────┐
                    │   API Gateway (FastAPI) │
                    │  API-key auth · OpenAPI │
                    └──┬─────────┬─────────┬──┘
                       │         │         │
        ┌──────────────▼──┐  ┌───▼─────────┴───┐
        │  Agent Runtime  │  │    Job Queue    │
        │  (nexusagent)   │  │  (Redis + arq)  │
        │  tool calling · │  └───┬─────────────┘
        │  memory · stream│      │
        └──────┬──────────┘      │
               │                 │
        ┌──────▼─────────────────▼───────┐
        │ RAG pipeline: upload → chunk → │
        │ embed → pgvector → retrieval   │
        └──────────────┬─────────────────┘
        ┌──────────────▼─────────────────┐
        │ Eval engine: YAML datasets →   │
        │ parallel runs → scoring →      │
        │ comparison reports             │
        └──────────────┬─────────────────┘
        ┌──────────────▼─────────────────┐
        │ PostgreSQL + pgvector          │
        │ agents · runs · documents ·    │
        │ evals · api keys               │
        └────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the full component and data-flow design.

## Repository layout

```text
NexusHub/
├── packages/
│   └── nexusagent/      # The agent runtime engine (standalone Python package)
├── apps/
│   ├── api/             # FastAPI gateway   (upcoming milestone)
│   └── dashboard/       # Next.js dashboard  (upcoming milestone)
├── docs/                # Architecture and design documents
├── docker-compose.yml   # One-command self-hosting (upcoming milestone)
└── Makefile             # Dev tasks (lint / typecheck / test)
```

The engine is a standalone, publishable package that the platform consumes: the runtime works on its own, and the platform turns it into a product.

## Status & roadmap

NexusHub is under active development. Work lands on feature branches and is merged into `main` milestone by milestone.

- [ ] **nexusagent runtime** — types, tool calling, memory, streaming, tracing
- [ ] **Built-in tools** — calculator, datetime, uuid
- [ ] **FastAPI gateway** — agent CRUD, chat with SSE streaming, API-key auth
- [ ] **Runs & traces** — full run history with per-step traces
- [ ] **RAG pipeline** — document ingestion, embeddings, pgvector retrieval
- [ ] **Job queue** — Redis + arq async workers
- [ ] **Eval engine** — YAML datasets, parallel runs, scoring, comparison
- [ ] **Next.js dashboard** — agent builder, playground, trace viewer, eval reports
- [ ] **One-command self-hosting** — docker compose

## Getting started — the engine

`nexusagent` talks to **any OpenAI-compatible endpoint**: OpenAI, OpenRouter,
vLLM, LM Studio, or a local Ollama.

```bash
git clone https://github.com/Abolfazlrwm/NexusHub.git
cd NexusHub
pip install -e "packages/nexusagent[dev]"
```

```python
import asyncio

from nexusagent import Agent, AgentConfig, OpenAICompatProvider


async def main() -> None:
    provider = OpenAICompatProvider(
        model="gpt-4o-mini",                    # or "qwen2.5" via Ollama
        api_key="sk-...",                       # "ollama" for local models
        base_url="https://api.openai.com/v1",   # or "http://localhost:11434/v1"
    )
    agent = Agent(
        config=AgentConfig(system_prompt="You are a precise assistant."),
        provider=provider,
    )
    result = await agent.run("What is 37 * 142? Use the calculator.")
    print(result.output)              # final answer
    print(result.usage.total_tokens)  # token accounting
    print(result.trace.model_dump())  # every model call & tool call


asyncio.run(main())
```

## Documentation

- [Architecture overview](docs/architecture.md)
- [nexusagent engine docs](packages/nexusagent/README.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md)
for the development setup, branch naming and commit conventions.

## License

[MIT](LICENSE) © 2026 Abolfazlrwm
