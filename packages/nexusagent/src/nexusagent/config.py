"""Immutable configuration for an agent run."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """Settings that shape a single agent's behaviour.

    Instances are frozen on purpose: a running agent should never observe a
    configuration that changes mid-run. Validation bounds catch obvious
    mistakes (a temperature of 10, a one-iteration agent) at construction
    time instead of mid-conversation.
    """

    model_config = ConfigDict(frozen=True)

    model: str = Field(
        default="gpt-4o-mini",
        description="Model identifier forwarded to the provider.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="System message seeded into every conversation.",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature forwarded to the provider.",
    )
    max_iterations: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Budget of model calls per run; tool-calling loops stop here.",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Optional per-response token cap forwarded to the provider.",
    )
    parallel_tool_calls: bool = Field(
        default=True,
        description="Execute multiple requested tool calls concurrently.",
    )
    request_timeout: float = Field(
        default=120.0,
        gt=0,
        description="Per-request timeout (seconds) used by the platform's provider clients.",
    )
    extra_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Extra HTTP headers appended to every provider request.",
    )
