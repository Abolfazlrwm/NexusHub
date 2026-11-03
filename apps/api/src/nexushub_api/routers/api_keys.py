"""API key management.

Keys are the only credential type in v0.2: single-tenant self-hosted
deployments authenticate machines, not humans. Creating a key returns the
plaintext exactly once; afterwards only the prefix is visible.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from .. import crud
from ..deps import SessionDep
from ..errors import ConflictError, NotFoundError
from ..schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from ..security import generate_api_key, hash_api_key, key_prefix

router = APIRouter(prefix="/api-keys", tags=["api keys"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiKeyCreated)
def create_api_key(data: ApiKeyCreate, session: SessionDep) -> ApiKeyCreated:
    plaintext = generate_api_key()
    key = crud.create_api_key(
        session, name=data.name, key_hash=hash_api_key(plaintext), prefix=key_prefix(plaintext)
    )
    session.commit()
    session.refresh(key)
    return ApiKeyCreated(
        id=key.id, name=key.name, prefix=key.prefix, key=plaintext, created_at=key.created_at
    )


@router.get("", response_model=list[ApiKeyRead])
def list_api_keys(session: SessionDep) -> list[ApiKeyRead]:
    return [ApiKeyRead.model_validate(key) for key in crud.list_api_keys(session)]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(key_id: str, session: SessionDep) -> None:
    key = crud.get_api_key(session, key_id)
    if key is None:
        raise NotFoundError(f"api key '{key_id}' does not exist")
    if key.revoked_at is not None:
        raise ConflictError(f"api key '{key_id}' is already revoked")
    crud.revoke_api_key(session, key)
    session.commit()
