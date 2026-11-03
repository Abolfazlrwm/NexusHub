"""Chat session and message endpoints.

Sessions are the persistence side of conversations: the engine holds an
in-memory history while a run executes, and the gateway replays the stored
messages into it so the next run in the same session continues the thread.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from .. import crud
from ..deps import PageParams, SessionDep, require_api_key
from ..errors import NotFoundError
from ..models import Agent, ChatSession
from ..pagination import Page
from ..schemas import MessageRead, SessionCreate, SessionRead

router = APIRouter(tags=["sessions"], dependencies=[Depends(require_api_key)])


def _get_agent_or_404(session: SessionDep, agent_id: str) -> Agent:
    agent = crud.get_agent(session, agent_id)
    if agent is None:
        raise NotFoundError(f"agent '{agent_id}' does not exist")
    return agent


def _get_session_or_404(session: SessionDep, chat_session_id: str) -> ChatSession:
    chat_session = crud.get_session_by_id(session, chat_session_id)
    if chat_session is None:
        raise NotFoundError(f"session '{chat_session_id}' does not exist")
    return chat_session


@router.post(
    "/agents/{agent_id}/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionRead
)
def create_session(agent_id: str, data: SessionCreate, session: SessionDep) -> ChatSession:
    agent = _get_agent_or_404(session, agent_id)
    chat_session = crud.create_session(session, agent, data)
    session.commit()
    session.refresh(chat_session)
    return chat_session


@router.get("/agents/{agent_id}/sessions", response_model=Page[SessionRead])
def list_sessions(agent_id: str, params: PageParams, session: SessionDep) -> Page[SessionRead]:
    _get_agent_or_404(session, agent_id)
    limit, offset = params
    sessions, total = crud.list_sessions_for_agent(session, agent_id, limit, offset)
    return Page(
        items=[SessionRead.model_validate(chat_session) for chat_session in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}", response_model=SessionRead)
def get_session_by_id(session_id: str, session: SessionDep) -> ChatSession:
    return _get_session_or_404(session, session_id)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageRead])
def list_session_messages(session_id: str, session: SessionDep) -> list[MessageRead]:
    chat_session = _get_session_or_404(session, session_id)
    return [
        MessageRead.model_validate(message)
        for message in crud.list_messages(session, chat_session.id)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, session: SessionDep) -> None:
    chat_session = _get_session_or_404(session, session_id)
    crud.delete_chat_session(session, chat_session)
    session.commit()
