"""Agent CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from .. import crud
from ..deps import PageParams, SessionDep, require_api_key
from ..errors import ConflictError, NotFoundError
from ..models import Agent
from ..pagination import Page
from ..schemas import AgentCreate, AgentRead, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(require_api_key)])


def _get_or_404(session: SessionDep, agent_id: str) -> Agent:
    agent = crud.get_agent(session, agent_id)
    if agent is None:
        raise NotFoundError(f"agent '{agent_id}' does not exist")
    return agent


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentRead)
def create_agent(data: AgentCreate, session: SessionDep) -> Agent:
    if crud.get_agent_by_name(session, data.name) is not None:
        raise ConflictError(f"agent name '{data.name}' is already taken")
    agent = crud.create_agent(session, data)
    session.commit()
    session.refresh(agent)
    return agent


@router.get("", response_model=Page[AgentRead])
def list_agents(params: PageParams, session: SessionDep) -> Page[AgentRead]:
    limit, offset = params
    agents, total = crud.list_agents(session, limit, offset)
    return Page(
        items=[AgentRead.model_validate(agent) for agent in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(agent_id: str, session: SessionDep) -> Agent:
    return _get_or_404(session, agent_id)


@router.patch("/{agent_id}", response_model=AgentRead)
def update_agent(agent_id: str, data: AgentUpdate, session: SessionDep) -> Agent:
    agent = _get_or_404(session, agent_id)
    if data.name is not None and data.name != agent.name:
        existing = crud.get_agent_by_name(session, data.name)
        if existing is not None and existing.id != agent.id:
            raise ConflictError(f"agent name '{data.name}' is already taken")
    agent = crud.update_agent(session, agent, data)
    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, session: SessionDep) -> None:
    agent = _get_or_404(session, agent_id)
    crud.delete_agent(session, agent)
    session.commit()
