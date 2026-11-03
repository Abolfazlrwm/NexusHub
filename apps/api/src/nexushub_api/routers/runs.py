"""Run endpoints: execute agents and stream them over SSE.

Contract: creating a run always succeeds (201) as long as the agent and
session exist — the *outcome* lives on the run resource. A provider
outage produces a run with ``status="failed"`` and an ``error`` message,
not a 5xx, so clients get a durable record of what happened.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from nexusagent import NexusAgentError
from nexusagent.agents import RunFinishedEvent

from .. import crud
from ..deps import PageParams, ProviderFactoryDep, SessionDep, require_api_key
from ..errors import NotFoundError
from ..models import Agent, ChatSession, Run
from ..pagination import Page
from ..schemas import RunCreate, RunRead
from ..services import execute_run, persist_new_messages, prepare_agent_run

router = APIRouter(tags=["runs"], dependencies=[Depends(require_api_key)])


def _get_agent_or_404(session: SessionDep, agent_id: str) -> Agent:
    agent = crud.get_agent(session, agent_id)
    if agent is None:
        raise NotFoundError(f"agent '{agent_id}' does not exist")
    return agent


def _resolve_session(session: SessionDep, agent: Agent, session_id: str | None) -> ChatSession | None:
    if session_id is None:
        return None
    chat_session = crud.get_session_by_id(session, session_id)
    if chat_session is None or chat_session.agent_id != agent.id:
        raise NotFoundError(f"session '{session_id}' does not exist for this agent")
    return chat_session


@router.post(
    "/agents/{agent_id}/runs", status_code=status.HTTP_201_CREATED, response_model=RunRead
)
async def create_run(agent_id: str, data: RunCreate, session: SessionDep, factory: ProviderFactoryDep) -> Run:
    agent = _get_agent_or_404(session, agent_id)
    chat_session = _resolve_session(session, agent, data.session_id)
    run = crud.create_run(
        session, agent=agent, text_input=data.input, chat_session_id=chat_session.id if chat_session else None
    )
    crud.mark_run_running(session, run)
    try:
        result, prior = await execute_run(
            session, agent_row=agent, text=data.input, chat_session=chat_session, provider_factory=factory
        )
    except NexusAgentError as exc:
        crud.mark_run_finished(session, run, error=str(exc))
        session.commit()
        session.refresh(run)
        return run

    if chat_session is not None:
        persist_new_messages(
            session,
            chat_session.id,
            full=result.messages,
            prior=prior,
            has_system_prompt=bool(agent.system_prompt),
        )
    crud.mark_run_finished(
        session,
        run,
        output=result.output,
        iterations=result.iterations,
        finish_reason=result.finish_reason.value,
        usage=result.usage.model_dump(),
        trace=result.trace.model_dump(),
    )
    session.commit()
    session.refresh(run)
    return run


@router.post("/agents/{agent_id}/runs/stream", response_class=StreamingResponse)
async def stream_run(agent_id: str, data: RunCreate, session: SessionDep, factory: ProviderFactoryDep) -> StreamingResponse:
    agent = _get_agent_or_404(session, agent_id)
    chat_session = _resolve_session(session, agent, data.session_id)
    run = crud.create_run(
        session, agent=agent, text_input=data.input, chat_session_id=chat_session.id if chat_session else None
    )
    crud.mark_run_running(session, run)
    engine_agent, prior = prepare_agent_run(
        session, agent_row=agent, chat_session=chat_session, provider_factory=factory
    )

    async def event_stream() -> Any:
        finished: RunFinishedEvent | None = None
        tool_steps: list[dict[str, Any]] = []
        pending_args: dict[str, dict[str, Any]] = {}
        iterations = 0
        try:
            async for event in engine_agent.run_stream(data.input):
                if event.type == "iteration_started":
                    iterations = event.iteration
                elif event.type == "tool_call_started":
                    pending_args[event.call_id] = event.arguments
                elif event.type == "tool_call_finished":
                    tool_steps.append(
                        {
                            "type": "tool_call",
                            "tool": event.name,
                            "arguments": pending_args.pop(event.call_id, {}),
                            "output": event.output,
                            "is_error": event.is_error,
                            "error": event.output if event.is_error else None,
                            "latency_ms": event.latency_ms,
                        }
                    )
                elif event.type == "run_finished":
                    finished = event
                yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"

            if finished is not None:
                full = await engine_agent.memory.messages()
                if chat_session is not None:
                    persist_new_messages(
                        session,
                        chat_session.id,
                        full=full,
                        prior=prior,
                        has_system_prompt=bool(agent.system_prompt),
                    )
                crud.mark_run_finished(
                    session,
                    run,
                    output=finished.output,
                    iterations=finished.iterations,
                    finish_reason=finished.finish_reason.value,
                    usage=finished.usage.model_dump(),
                    # Streamed runs record tool steps and iterations; full
                    # model-call traces come from the sync endpoint today.
                    trace={"steps": tool_steps, "iterations": iterations, "total_latency_ms": 0.0},
                )
                session.commit()
        except NexusAgentError as exc:
            crud.mark_run_finished(session, run, error=str(exc))
            session.commit()
            payload = json.dumps({"error": str(exc)})
            yield f"event: run_failed\ndata: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/runs", response_model=Page[RunRead])
def list_runs(
    params: PageParams, session: SessionDep, agent_id: str | None = None
) -> Page[RunRead]:
    limit, offset = params
    runs, total = crud.list_runs(session, agent_id, limit, offset)
    return Page(
        items=[RunRead.model_validate(run) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: str, session: SessionDep) -> Run:
    run = crud.get_run(session, run_id)
    if run is None:
        raise NotFoundError(f"run '{run_id}' does not exist")
    return run
