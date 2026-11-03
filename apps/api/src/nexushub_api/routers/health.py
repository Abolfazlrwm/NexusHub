"""Liveness and version endpoints (unauthenticated)."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__

router = APIRouter(tags=["meta"])


@router.get("/healthz")
def health() -> dict[str, str]:
    """Process is up. Used by docker healthchecks and load balancers."""
    return {"status": "ok"}


@router.get("/version")
def version() -> dict[str, str]:
    return {"service": "nexushub-api", "version": __version__}
