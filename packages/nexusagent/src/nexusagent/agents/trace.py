"""Run traces: a durable record of everything a run did.

Every model call and every tool invocation becomes a step with its own
latency and usage. The platform persists these steps with each run — they
are what the trace viewer renders and what eval cost metrics are computed
from. A trace is proof of what the agent actually did, not what we think
it did.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from ..types import FinishReason, Usage


class ModelCallStep(BaseModel):
    """One round-trip to the chat provider."""

    type: Literal["model_call"] = "model_call"
    model: str
    prompt_messages: int
    completion: str
    tool_call_count: int
    usage: Usage
    finish_reason: FinishReason
    latency_ms: float


class ToolCallStep(BaseModel):
    """One tool invocation, successful or not."""

    type: Literal["tool_call"] = "tool_call"
    tool: str
    arguments: dict[str, Any]
    output: str
    is_error: bool = False
    error: str | None = None
    latency_ms: float


TraceStep = Annotated[ModelCallStep | ToolCallStep, Field(discriminator="type")]


class RunTrace(BaseModel):
    """All steps of one agent run, in order."""

    steps: list[TraceStep] = Field(default_factory=list)
    iterations: int = 0
    total_latency_ms: float = 0.0

    @property
    def model_calls(self) -> list[ModelCallStep]:
        """Just the model-call steps, in order."""
        return [step for step in self.steps if isinstance(step, ModelCallStep)]

    @property
    def tool_calls(self) -> list[ToolCallStep]:
        """Just the tool-call steps, in order."""
        return [step for step in self.steps if isinstance(step, ToolCallStep)]
