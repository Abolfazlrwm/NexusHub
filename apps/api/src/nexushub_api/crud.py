"""CRUD helpers.

Routers stay thin; every database interaction lives here so the query
patterns are reviewable in one place. Each helper takes an active
``Session`` and never commits — transactions belong to the callers.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, func, select

from .models import Agent, ApiKey, ChatSession, Message, Run, new_id, utcnow
from .schemas import AgentCreate, AgentUpdate, SessionCreate


# -- agents ---------------------------------------------------------------------


def create_agent(session: Session, data: AgentCreate) -> Agent:
    agent = Agent(**data.model_dump())
    session.add(agent)
    session.flush()
    return agent


def get_agent(session: Session, agent_id: str) -> Agent | None:
    return session.get(Agent, agent_id)


def list_agents(session: Session, limit: int, offset: int) -> tuple[list[Agent], int]:
    total = session.exec(select(func.count()).select_from(Agent)).one()
    items = list(session.exec(select(Agent).order_by(Agent.created_at).offset(offset).limit(limit)))
    return items, int(total)


def update_agent(session: Session, agent: Agent, data: AgentUpdate) -> Agent:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    agent.updated_at = utcnow()
    session.add(agent)
    session.flush()
    return agent


def delete_agent(session: Session, agent: Agent) -> None:
    session.delete(agent)


# -- api keys -------------------------------------------------------------------


def create_api_key(session: Session, *, name: str, key_hash: str, prefix: str) -> ApiKey:
    key = ApiKey(name=name, key_hash=key_hash, prefix=prefix)
    session.add(key)
    session.flush()
    return key


def get_api_key(session: Session, key_id: str) -> ApiKey | None:
    return session.get(ApiKey, key_id)


def find_api_key_by_hash(session: Session, key_hash: str) -> ApiKey | None:
    return session.exec(select(ApiKey).where(ApiKey.key_hash == key_hash)).first()


def count_active_api_keys(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(ApiKey).where(ApiKey.revoked_at.is_(None))).one())


def list_api_keys(session: Session) -> list[ApiKey]:
    return list(session.exec(select(ApiKey).order_by(ApiKey.created_at)))


def revoke_api_key(session: Session, key: ApiKey) -> ApiKey:
    key.revoked_at = utcnow()
    session.add(key)
    session.flush()
    return key


# -- sessions and messages ------------------------------------------------------


def create_session(session: Session, agent: Agent, data: SessionCreate) -> ChatSession:
    chat_session = ChatSession(agent_id=agent.id, title=data.title or "New session")
    session.add(chat_session)
    session.flush()
    return chat_session


def get_session_by_id(session: Session, chat_session_id: str) -> ChatSession | None:
    return session.get(ChatSession, chat_session_id)


def list_sessions_for_agent(session: Session, agent_id: str, limit: int, offset: int) -> tuple[list[ChatSession], int]:
    base = select(ChatSession).where(ChatSession.agent_id == agent_id)
    total = session.exec(select(func.count()).select_from(ChatSession).where(ChatSession.agent_id == agent_id)).one()
    items = list(session.exec(base.order_by(ChatSession.created_at).offset(offset).limit(limit)))
    return items, int(total)


def delete_chat_session(session: Session, chat_session: ChatSession) -> None:
    for message in list(session.exec(select(Message).where(Message.session_id == chat_session.id))):
        session.delete(message)
    session.delete(chat_session)


def add_message(
    session: Session,
    chat_session_id: str,
    *,
    role: str,
    content: str | None,
    tool_calls: list[dict[str, object]] | None = None,
    tool_call_id: str | None = None,
) -> Message:
    message = Message(
        id=new_id(),
        session_id=chat_session_id,
        role=role,
        content=content,
        tool_calls=list(tool_calls) if tool_calls else None,
        tool_call_id=tool_call_id,
    )
    session.add(message)
    session.flush()
    return message


def list_messages(session: Session, chat_session_id: str) -> list[Message]:
    return list(session.exec(select(Message).where(Message.session_id == chat_session_id).order_by(Message.created_at, Message.id)))


# -- runs -----------------------------------------------------------------------


def create_run(
    session: Session,
    *,
    agent: Agent,
    text_input: str,
    chat_session_id: str | None,
) -> Run:
    run = Run(agent_id=agent.id, session_id=chat_session_id, input=text_input, model=agent.model, provider=agent.provider)
    session.add(run)
    session.flush()
    return run


def mark_run_running(session: Session, run: Run, *, at: datetime | None = None) -> Run:
    run.status = "running"
    run.started_at = at or utcnow()
    session.add(run)
    session.flush()
    return run


def mark_run_finished(
    session: Session,
    run: Run,
    *,
    output: str | None = None,
    error: str | None = None,
    iterations: int | None = None,
    finish_reason: str | None = None,
    usage: dict[str, int] | None = None,
    trace: dict[str, object] | None = None,
) -> Run:
    run.status = "failed" if error else "completed"
    run.output = output
    run.error = error
    run.iterations = iterations
    run.finish_reason = finish_reason
    run.usage = usage
    run.trace = trace
    run.finished_at = utcnow()
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, run_id: str) -> Run | None:
    return session.get(Run, run_id)


def list_runs(session: Session, agent_id: str | None, limit: int, offset: int) -> tuple[list[Run], int]:
    base = select(Run)
    count = select(func.count()).select_from(Run)
    if agent_id is not None:
        base = base.where(Run.agent_id == agent_id)
        count = count.where(Run.agent_id == agent_id)
    total = session.exec(count).one()
    items = list(session.exec(base.order_by(Run.created_at).offset(offset).limit(limit)))
    return items, int(total)
