"""The FastAPI application factory.

``create_app`` composes settings, database, routers and error handlers so
tests and deployments can build isolated instances; the module-level
``app`` is what ``uvicorn nexushub_api.main:app`` expects.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .db import engine_from_settings, init_db
from .errors import register_exception_handlers
from .routers import agents, api_keys, health, sessions
from .settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db(engine_from_settings(app.state.settings))
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured application instance."""
    settings = settings or Settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="REST and SSE access to nexusagent agents.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_keys.router, prefix="/v1")
    app.include_router(agents.router, prefix="/v1")
    app.include_router(sessions.router, prefix="/v1")

    return app


app = create_app()
