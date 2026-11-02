# nexusagent

> The agent runtime engine behind NexusHub — usable on its own.

`nexusagent` is a small, dependency-light Python runtime for building AI
agents: it runs the conversation loop between a model and a set of tools,
streams every token as it arrives, remembers the conversation, and records
a full trace of what it did.

The [NexusHub platform](../../README.md) is a service layer around this
engine — agents, traces, RAG and evaluation behind a dashboard. The engine
deliberately knows nothing about the platform: you can embed it anywhere.

## Design principles

- **Provider-agnostic by wire format.** Any OpenAI-compatible endpoint
  works — OpenAI, OpenRouter, Together, Groq, vLLM, LM Studio, or a local
  Ollama (`http://localhost:11434/v1`). Just point `base_url` at it.
- **Soft tool failures.** A tool that crashes does not kill the run: the
  error goes back to the model as a tool result, and the model can recover,
  apologize or route around it. Only infrastructure errors (auth, network,
  exhausted budget) raise.
- **First-class tracing.** Every run records every model call (usage,
  latency, finish reason) and every tool call (arguments, output, error
  kind, latency) as structured steps — `result.trace` is the whole story.
- **Streaming as a first-class path.** `run_stream()` yields typed events
  (`text_delta`, `tool_call_started`, …) ready to be serialized straight to
  SSE.
- **No `eval()`/`exec()` on model input.** The calculator parses
  expressions with `ast` and walks them against a strict whitelist — see
  `src/nexusagent/tools/builtin/calculator.py`.

## Installation

From the monorepo:

```bash
pip install -e "packages/nexusagent[dev]"
```

## Quick start

```python
import asyncio

from nexusagent import Agent, AgentConfig, OpenAICompatProvider


async def main() -> None:
    provider = OpenAICompatProvider(
        model="gpt-4o-mini",                  # or "qwen2.5" via Ollama
        api_key="sk-...",                     # "ollama" for local models
        base_url="https://api.openai.com/v1",  # or http://localhost:11434/v1
    )
    agent = Agent(
        provider=provider,
        config=AgentConfig(system_prompt="You are a precise assistant."),
    )
    result = await agent.run("What is 37 * 142? Use the calculator.")
    print(result.output)               # the final answer
    print(result.finish_reason)         # stop | tool_calls | max_iterations
    print(result.usage.total_tokens)    # token accounting
    print(result.trace.model_dump())    # every model call and tool call


asyncio.run(main())
```

## Tools

```python
from nexusagent import Tool, ToolRegistry, register_builtin_tools
from nexusagent.tools import CalculatorTool

registry = register_builtin_tools(ToolRegistry())  # calculator, datetime, uuid


class WeatherTool(Tool):
    name = "get_weather"
    description = "Current weather for a city."
    parameters = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }

    async def execute(self, **kwargs) -> str:
        return f"It is sunny in {kwargs['city']}."


registry.register(WeatherTool())
agent = Agent(provider=provider, tools=registry)
```

Tool calls execute **in parallel** by default
(`AgentConfig(parallel_tool_calls=False)` for strict ordering).

## Streaming

```python
async for event in agent.run_stream("Draft a haiku about traces."):
    match event.type:
        case "text_delta":
            print(event.delta, end="", flush=True)
        case "tool_call_started":
            print(f"\n[tool] {event.name}({event.arguments})")
        case "tool_call_finished":
            print(f"[tool] -> {event.output[:80]}")
        case "run_finished":
            print(f"\n-- {event.finish_reason}, {event.usage.total_tokens} tokens")
```

## Memory

`InMemoryMemory` keeps the conversation in process memory with an optional
sliding window (`InMemoryMemory(max_messages=40)`) that pins system
messages so instructions survive trimming. Share one memory instance
across `run()` calls for a multi-turn conversation.

## Examples

Runnable scripts live in [examples/](examples/):

```bash
export OPENAI_API_KEY=sk-...
export NEXUS_MODEL=gpt-4o-mini          # optional
export OPENAI_BASE_URL=...              # optional (OpenRouter, Ollama, ...)

python examples/basic_chat.py
python examples/tool_agent.py
```

## Development

```bash
make check        # from the repository root: ruff + mypy + pytest
```

- 100+ tests, no network access required (providers are faked/mocked)
- `ruff` for lint and formatting, `mypy --strict`-ish for types
- Python 3.10 – 3.13

## License

MIT — see the [repository license](../../LICENSE).
