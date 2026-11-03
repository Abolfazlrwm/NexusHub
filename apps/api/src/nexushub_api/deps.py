"""Shared FastAPI dependencies.

Dependencies are the seam between HTTP and the rest of the app: tests
override them (``app.dependency_overrides``) to inject a throwaway
database or a fake provider factory without monkey-patching modules.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from nexusagent import ChatProvider, ProviderRegistry

from .db import engine_from_settings, open_session
from .pagination import clamp_pagination
from .settings import Settings

#: Builds a chat provider from a registered name plus per-agent settings.
ProviderFactory = Callable[..., ChatProvider]


def get_settings(request: Request) -> Settings:
    """Read settings from app state, so ``create_app(settings)`` owns config."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_db_session(settings: SettingsDep) -> Iterator[Session]:
    session = open_session(engine_from_settings(settings))
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_db_session)]


def get_provider_factory() -> ProviderFactory:
    """Default provider construction goes through the engine registry."""
    return ProviderRegistry.create


ProviderFactoryDep = Annotated[ProviderFactory, Depends(get_provider_factory)]


def page_params(limit: int = 20, offset: int = 0) -> tuple[int, int]:
    """Common ``limit``/``offset`` query parameters, bounded.

    Used as a dependency so the two query parameters are declared once.
    """
    return clamp_pagination(limit, offset)


PageParams = Annotated[tuple[int, int], Depends(page_params)]
