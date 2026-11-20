"""Request and response schemas.

Read models are deliberately explicit (not ``model_config = from_orm``
dumped wholesale) so the HTTP contract stays stable even if a table gains
internal columns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

RUN_STATUS_VALUES = ("pending", "running", "completed", "failed")

# -- agents ---------------------------------------------------------------------


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    provider: str = Field(default="openai-compat", max_length=40)
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=120)
    system_prompt: str = Field(default="", max_length=8000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_iterations: int = Field(default=8, ge=1, le=64)
    provider_config: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    provider: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    system_prompt: str | None = Field(default=None, max_length=8000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_iterations: int | None = Field(default=None, ge=1, le=64)
    provider_config: dict[str, Any] | None = None


# Keys whose values must never leave the server verbatim (provider_config
# may carry an OpenAI-compatible api_key).
_PROVIDER_SECRET_KEYS = {"api_key", "apikey", "secret", "token", "password", "authorization"}


def _mask_provider_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Redact secret-looking provider_config values, keeping a 4-char tail."""
    out: dict[str, Any] = {}
    for key, value in (cfg or {}).items():
        if key.lower() in _PROVIDER_SECRET_KEYS and isinstance(value, str) and value:
            out[key] = f"***{value[-4:]}" if len(value) > 4 else "***"
        else:
            out[key] = value
    return out


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    provider: str
    model: str
    system_prompt: str
    temperature: float
    max_iterations: int
    provider_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @field_serializer("provider_config")
    def _serialize_provider_config(self, cfg: dict[str, Any], _info: object) -> dict[str, Any]:
        # GET responses never echo stored secrets; the runner reads the
        # unmasked values straight from storage.
        return _mask_provider_config(cfg)


# -- api keys -------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ApiKeyCreated(BaseModel):
    """Creation response — the only time the plaintext key is ever returned."""

    id: str
    name: str
    prefix: str
    key: str
    created_at: datetime


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None


# -- sessions and messages ------------------------------------------------------


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    title: str
    created_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str | None
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    created_at: datetime


# -- runs -----------------------------------------------------------------------


class RunCreate(BaseModel):
    input: str = Field(min_length=1, max_length=32000)
    session_id: str | None = None


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    session_id: str | None
    status: str
    input: str
    output: str | None
    error: str | None
    model: str
    provider: str
    iterations: int | None
    finish_reason: str | None
    usage: dict[str, int] | None
    trace: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
