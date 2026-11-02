"""The agent event protocol for streaming runs.

Every observable moment of a run is an event: the run starting, iteration
boundaries, text fragments as they stream in, tool calls starting and
finishing, and the run finishing. Events are pydantic models so consumers
(the platform's SSE endpoint, CLI clients) can serialize them straight to
JSON frames.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from ..types import FinishReason, Usage
from .trace import RunTrace


class RunStartedEvent(BaseModel):
    """Emitted once when the run begins."""

    type: Literal["run_started"] = "run_started"
    run_id: str
    model: str


class IterationStartedEvent(BaseModel):
    """Emitted at the start of every loop iteration."""

    type: Literal["iteration_started"] = "iteration_started"
    iteration: int


class TextDeltaEvent(BaseModel):
    """A fragment of the assistant's answer, streamed as it arrives."""

    type: Literal["text_delta"] = "text_delta"
    delta: str


class ToolCallStartedEvent(BaseModel):
    """The agent is about to invoke a tool."""

    type: Literal["tool_call_started"] = "tool_call_started"
    call_id: str
    name: str
    arguments: dict[str, Any]


class ToolCallFinishedEvent(BaseModel):
    """A tool invocation completed — successfully or as a soft error."""

    type: Literal["tool_call_finished"] = "tool_call_finished"
    call_id: str
    name: str
    output: str
    is_error: bool
    latency_ms: float


class RunFinishedEvent(BaseModel):
    """Emitted once at the end of the run, carrying the full summary."""

    type: Literal["run_finished"] = "run_finished"
    run_id: str
    finish_reason: FinishReason
    output: str
    usage: Usage
    iterations: int
    total_latency_ms: float
    trace: RunTrace


AgentEvent = (
    RunStartedEvent
    | IterationStartedEvent
    | TextDeltaEvent
    | ToolCallStartedEvent
    | ToolCallFinishedEvent
    | RunFinishedEvent
)
