"""SQL persistence models.

The gateway stores agents, API keys, chat sessions, messages and runs.
Tables are deliberately thin: agent behaviour lives in the engine, so the
database only needs to reproduce configuration and record what happened.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """A hex UUID for primary keys (URL-safe and sortable enough)."""
    return uuid.uuid4().hex


def load_models() -> None:
    """Import every table module so SQLModel.metadata is fully populated.

    Kept as a function so ``db.init_db`` can guarantee all tables exist no
    matter which module the process happened to import first.
    """

    from . import models  # noqa: F401  circular-import safe at call time


class Agent(SQLModel, table=True):
    """A stored agent configuration, ready to run through the engine."""

    __tablename__ = "agents"

    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str = ""
    provider: str = "openai-compat"
    model: str = "gpt-4o-mini"
    system_prompt: str = ""
    temperature: float = 0.7
    max_iterations: int = 8
    provider_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ApiKey(SQLModel, table=True):
    """A bearer credential for the HTTP API.

    Only the SHA-256 hash is stored; the plaintext is shown exactly once,
    in the response of the request that created it.
    """

    __tablename__ = "api_keys"

    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True)
    key_hash: str = Field(unique=True, index=True)
    prefix: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class ChatSession(SQLModel, table=True):
    """One conversation thread with one agent."""

    __tablename__ = "chat_sessions"

    id: str = Field(default_factory=new_id, primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)
    title: str = "New session"
    created_at: datetime = Field(default_factory=utcnow)


class Message(SQLModel, table=True):
    """A single stored message inside a chat session."""

    __tablename__ = "messages"

    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="chat_sessions.id", index=True)
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    tool_call_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Run(SQLModel, table=True):
    """One execution of an agent, with outcome and observability data."""

    __tablename__ = "runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)
    session_id: str | None = Field(default=None, foreign_key="chat_sessions.id", index=True)
    status: str = "pending"
    input: str = ""
    output: str | None = None
    error: str | None = None
    model: str = ""
    provider: str = ""
    iterations: int | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = Field(default=None, sa_column=Column(JSON))
    trace: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


RUN_PENDING = "pending"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_STATUSES = (RUN_PENDING, RUN_RUNNING, RUN_COMPLETED, RUN_FAILED)
