"""Typed API errors with a single JSON error envelope.

Every error the API returns has the same shape::

    {"error": {"code": "not_found", "message": "..."}}

Clients only ever need to read ``error.code``; humans read the message.
Engine failures surface as ``upstream_error`` — a gateway should never
pretend a provider outage is a client mistake.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nexusagent import ConfigurationError, NexusAgentError


class ApiError(Exception):
    """Base class for errors that map onto a deliberate HTTP response."""

    status_code: int = 400
    code: str = "invalid_request"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(ApiError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class UpstreamError(ApiError):
    status_code = 502
    code = "upstream_error"


def _envelope(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the error envelope handlers to ``app``."""

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, str(exc)))

    @app.exception_handler(ConfigurationError)
    async def handle_configuration_error(request: Request, exc: ConfigurationError) -> JSONResponse:  # noqa: ARG001
        # A bad provider name or model setting is a deployment problem, not
        # something the caller can fix — answer 500, not 4xx.
        return JSONResponse(status_code=500, content=_envelope("config_error", str(exc)))

    @app.exception_handler(NexusAgentError)
    async def handle_engine_error(request: Request, exc: NexusAgentError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(status_code=502, content=_envelope("upstream_error", str(exc)))
