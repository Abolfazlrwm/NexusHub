"""The bridge between HTTP resources and the nexusagent runtime.

The gateway never re-implements agent behaviour: it stores configuration,
builds engine objects per run, and records what happened back to SQL.

One deliberate choice: DB-backed sessions run with unlimited in-run memory
(``max_messages=None``). The database is the source of truth for history —
trimming already happened before stored messages were written — so the
gateway replays the full transcript and lets the engine append to it.
"""

from __future__ import annotations

import os
from typing import Any

from sqlmodel import Session

from nexusagent import (
    Agent,
    AgentConfig,
    AgentRunResult,
    InMemoryMemory,
    Message as EngineMessage,
    Role,
    ToolCall,
    ToolRegistry,
    register_builtin_tools,
)

from . import crud
from .deps import ProviderFactory
from .models import Agent as AgentRow
from .models import ChatSession, Message as StoredMessage


def provider_kwargs(agent_row: AgentRow) -> dict[str, Any]:
    """Resolve provider construction settings for a stored agent.

    Explicit ``provider_config`` wins over environment variables
    (``OPENAI_API_KEY``, ``OPENAI_BASE_URL``) so operators can keep secrets
    out of the database while still configuring agents per deployment.
    """
    cfg = dict(agent_row.provider_config or {})
    kwargs: dict[str, Any] = {"model": agent_row.model}
    base_url = cfg.get("base_url") or os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    api_key = cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def build_engine_agent(agent_row: AgentRow, provider_factory: ProviderFactory) -> Agent:
    """Materialise a stored agent as an engine ``Agent`` ready to run."""
    config = AgentConfig(
        model=agent_row.model,
        system_prompt=agent_row.system_prompt or None,
        temperature=agent_row.temperature,
        max_iterations=agent_row.max_iterations,
    )
    provider = provider_factory(agent_row.provider, **provider_kwargs(agent_row))
    tools = register_builtin_tools(ToolRegistry())
    return Agent(provider=provider, config=config, tools=tools, memory=InMemoryMemory())


def stored_to_engine(stored: list[StoredMessage]) -> list[EngineMessage]:
    """Replay stored message rows as engine messages."""
    messages: list[EngineMessage] = []
    for row in stored:
        tool_calls = [ToolCall.model_validate(call) for call in (row.tool_calls or [])]
        messages.append(
            EngineMessage(
                role=Role(row.role),
                content=row.content,
                tool_calls=tool_calls,
                tool_call_id=row.tool_call_id,
            )
        )
    return messages


def prepare_agent_run(
    session: Session,
    *,
    agent_row: AgentRow,
    chat_session: ChatSession | None,
    provider_factory: ProviderFactory,
) -> tuple[Agent, list[EngineMessage]]:
    """Build the engine agent and seed it with the session's history.

    Returns the agent plus the replayed prior messages; callers need the
    prior list to slice off the messages a run appends.
    """
    engine_agent = build_engine_agent(agent_row, provider_factory)
    prior: list[EngineMessage] = []
    if chat_session is not None:
        prior = stored_to_engine(crud.list_messages(session, chat_session.id))
    return engine_agent, prior


async def seed_memory(engine_agent: Agent, prior: list[EngineMessage]) -> None:
    """Replay prior conversation turns into the agent's memory."""
    for message in prior:
        await engine_agent.memory.add(message)


def persist_new_messages(
    session: Session,
    chat_session_id: str,
    *,
    full: list[EngineMessage],
    prior: list[EngineMessage],
    has_system_prompt: bool,
) -> list[StoredMessage]:
    """Store the messages a run appended to the conversation.

    The engine seeds ``[system?] + prior + [user input]`` before looping,
    so everything past that prefix is new. Memory is unbounded on the
    gateway side, which keeps this slice stable.
    """
    offset = len(prior) + 1 + (1 if has_system_prompt else 0)
    added = full[offset:] if len(full) > offset else []
    rows: list[StoredMessage] = []
    for message in added:
        rows.append(
            crud.add_message(
                session,
                chat_session_id,
                role=message.role.value,
                content=message.content,
                tool_calls=[call.model_dump() for call in message.tool_calls] or None,
                tool_call_id=message.tool_call_id,
            )
        )
    return rows


async def execute_run(
    session: Session,
    *,
    agent_row: AgentRow,
    text: str,
    chat_session: ChatSession | None,
    provider_factory: ProviderFactory,
) -> tuple[AgentRunResult, list[EngineMessage]]:
    """Run an agent to completion, replaying stored history first."""
    engine_agent, prior = prepare_agent_run(
        session, agent_row=agent_row, chat_session=chat_session, provider_factory=provider_factory
    )
    await seed_memory(engine_agent, prior)
    result = await engine_agent.run(text)
    return result, prior
