"""API key generation and hashing.

Plaintext keys are shown once at creation. The database stores only a
SHA-256 hash, so a database leak does not leak usable credentials.
"""

from __future__ import annotations

import hashlib
import secrets

KEY_PREFIX = "nx_"
PREFIX_CHARS = 8  # characters of the key kept visible for identification


def generate_api_key() -> str:
    """Return a fresh plaintext key, e.g. ``nx_9fC2...``."""
    return KEY_PREFIX + secrets.token_urlsafe(24)


def key_prefix(key: str) -> str:
    """The short identifying prefix stored alongside the hash."""
    return key[: len(KEY_PREFIX) + PREFIX_CHARS]


def hash_api_key(key: str) -> str:
    """SHA-256 hex digest of a plaintext key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
