"""Minimal chat example against any OpenAI-compatible endpoint.

Env vars:
    OPENAI_API_KEY    API key ("ollama" works for local models)
    OPENAI_BASE_URL   optional, defaults to https://api.openai.com/v1
    NEXUS_MODEL       optional, defaults to gpt-4o-mini
"""

from __future__ import annotations

import asyncio
import os
import sys

from nexusagent import Agent, AgentConfig, OpenAICompatProvider


async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY (use 'ollama' for local models).")

    provider = OpenAICompatProvider(
        model=os.environ.get("NEXUS_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    agent = Agent(
        provider=provider,
        config=AgentConfig(system_prompt="You are a concise, precise assistant."),
    )

    result = await agent.run("Explain what an AI agent is in two sentences.")
    print(result.output)
    print(
        f"\n-- {result.finish_reason.value} | "
        f"{result.usage.total_tokens} tokens | {result.total_latency_ms:.0f} ms"
    )


if __name__ == "__main__":
    asyncio.run(main())
