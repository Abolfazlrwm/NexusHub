"""Tool-calling agent with live streaming output.

Demonstrates the full loop: the model decides to call tools, tool calls are
executed (in parallel when independent), results flow back into the
conversation, and the final answer streams token by token.

Env vars: same as basic_chat.py.
"""

from __future__ import annotations

import asyncio
import os
import sys

from nexusagent import Agent, AgentConfig, InMemoryMemory, OpenAICompatProvider, ToolRegistry
from nexusagent.tools import register_builtin_tools


async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY (use 'ollama' for local models).")

    provider = OpenAICompatProvider(
        model=os.environ.get("NEXUS_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    tools = register_builtin_tools(ToolRegistry())
    agent = Agent(
        provider=provider,
        tools=tools,
        memory=InMemoryMemory(),
        config=AgentConfig(
            system_prompt=(
                "You are a careful assistant. Use the calculator tool for "
                "every arithmetic question, and current_datetime for anything "
                "time-related."
            )
        ),
    )

    prompt = (
        "Compute sqrt(1764) + 2**8, then tell me the current time in Tehran, "
        "and finally generate two ids for me."
    )
    print(f"> {prompt}\n")

    async for event in agent.run_stream(prompt):
        match event.type:
            case "text_delta":
                print(event.delta, end="", flush=True)
            case "tool_call_started":
                print(f"\n  [tool] {event.name}({event.arguments})")
            case "tool_call_finished":
                status = "error" if event.is_error else "ok"
                print(f"  [tool] -> ({status}) {event.output[:60]}")
            case "run_finished":
                print(
                    f"\n\n-- {event.finish_reason.value} | "
                    f"{event.iterations} iteration(s) | "
                    f"{event.usage.total_tokens} tokens | "
                    f"{event.total_latency_ms:.0f} ms"
                )


if __name__ == "__main__":
    asyncio.run(main())
