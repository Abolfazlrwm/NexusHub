"""Application settings.

Every value can be overridden with a ``NEXUS_``-prefixed environment
variable (``NEXUS_DATABASE_URL``, ``NEXUS_DEBUG``, ...) so the same image
runs unchanged in dev, docker and production.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration for the API gateway."""

    model_config = SettingsConfigDict(env_prefix="NEXUS_", env_file=".env", extra="ignore")

    app_name: str = "NexusHub API"
    debug: bool = False
    database_url: str = "sqlite:///./nexushub.db"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    default_page_size: int = 20
