"""Exception hierarchy for the nexusagent runtime.

Two families of failures are deliberately distinguished:

- **Provider failures** (auth, rate limits, connectivity, timeouts): the
  agent loop cannot usefully continue, so these propagate to the caller.
- **Tool failures** (bad arguments, execution errors): the loop converts
  these into error messages the model itself can react to — a soft failure
  that keeps the conversation alive instead of crashing the run.
"""

from __future__ import annotations


class NexusAgentError(Exception):
    """Base class for every error raised by nexusagent."""


class ConfigurationError(NexusAgentError):
    """The agent or provider was constructed with invalid settings."""


# --- provider failures ---------------------------------------------------------


class ProviderError(NexusAgentError):
    """A chat provider request failed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ProviderAuthError(ProviderError):
    """The provider rejected the API key (HTTP 401/403)."""


class ProviderRateLimitError(ProviderError):
    """The provider throttled the request (HTTP 429)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderError):
    """The provider did not answer within the configured timeout."""


# --- tool failures ---------------------------------------------------------------


class ToolError(NexusAgentError):
    """Base class for tool-related failures."""


class ToolNotFoundError(ToolError):
    """A tool with the requested name is not registered."""


class ToolArgumentError(ToolError):
    """The model supplied arguments the tool cannot accept."""


class ToolExecutionError(ToolError):
    """A tool raised while executing model-controlled input.

    Carrying the tool name on the exception lets the runtime produce
    actionable error messages back to the model.
    """

    def __init__(self, message: str, *, tool: str | None = None) -> None:
        super().__init__(message)
        self.tool = tool
