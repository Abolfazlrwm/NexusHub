"""Pagination envelope shared by list endpoints."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

MAX_LIMIT = 100

T = TypeVar("T")


def clamp_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Sanity-bound page parameters sent by clients."""
    return max(1, min(limit, MAX_LIMIT)), max(0, offset)


class Page(BaseModel, Generic[T]):
    """One page of items plus the window the client asked for."""

    items: list[T]
    total: int
    limit: int
    offset: int
