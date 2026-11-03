"""Shared FastAPI dependencies.

Dependencies are the seam between HTTP and the rest of the app: tests
override them (``app.dependency_overrides``) to inject a throwaway
database or a fake provider factory without monkey-patching modules.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from nexusagent import ChatProvider, ProviderRegistry
from sqlmodel import Session

from . import crud
from .db import engine_from_settings, open_session
from .errors import ForbiddenError, UnauthorizedError
from .models import ApiKey, utcnow
from .pagination import clamp_pagination
from .security import hash_api_key
from .settings import Settings

#: Builds a chat provider from a registered name plus per-agent settings.
ProviderFactory = Callable[..., ChatProvider]

_bearer = HTTPBearer(auto_error=False)

#: Raw ``Authorization: Bearer`` credentials, or ``None`` when absent.
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)]


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


def check_api_key(credentials: CredentialsDep, session: SessionDep) -> ApiKey:
    """Validate raw bearer credentials and return the stored key row.

    Raises 401 for missing or unknown keys and 403 for revoked ones.
    Touches ``last_used_at`` so operators can spot dead credentials.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("missing bearer api key")
    key = crud.find_api_key_by_hash(session, hash_api_key(credentials.credentials))
    if key is None:
        raise UnauthorizedError("invalid api key")
    if key.revoked_at is not None:
        raise ForbiddenError("api key has been revoked")
    key.last_used_at = utcnow()
    session.add(key)
    session.commit()
    return key


def require_api_key(credentials: CredentialsDep, session: SessionDep) -> ApiKey:
    """Dependency form of :func:`check_api_key`."""
    return check_api_key(credentials, session)


ApiKeyDep = Annotated[ApiKey, Depends(require_api_key)]
