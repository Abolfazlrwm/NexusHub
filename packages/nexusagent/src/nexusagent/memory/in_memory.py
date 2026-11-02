"""In-memory conversation history with an optional sliding window."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import Message, Role
from .base import BaseMemory


class InMemoryMemory(BaseMemory):
    """Keeps the conversation in process memory.

    When ``max_messages`` is set, the oldest messages are dropped once the
    history grows past the limit — except system messages, which are pinned
    so the agent's instructions survive every trim. This keeps long
    conversations within a predictable token budget without the model
    "forgetting" who it is.

    The history lives and dies with the instance: use one memory per
    conversation. Durable stores (Postgres, Redis) are provided by the
    platform layer.
    """

    def __init__(self, max_messages: int | None = None) -> None:
        if max_messages is not None and max_messages < 1:
            raise ValueError("max_messages must be at least 1")
        self._max_messages = max_messages
        self._messages: list[Message] = []

    @property
    def max_messages(self) -> int | None:
        """History size limit, or ``None`` for unbounded history."""
        return self._max_messages

    async def add(self, message: Message) -> None:
        self._messages.append(message)
        self._trim()

    async def extend(self, messages: Iterable[Message]) -> None:
        for message in messages:
            self._messages.append(message)
        self._trim()

    async def messages(self) -> list[Message]:
        return list(self._messages)

    async def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        """Drop the oldest non-system messages until within the limit."""
        if self._max_messages is None:
            return
        while len(self._messages) > self._max_messages:
            for index, message in enumerate(self._messages):
                if message.role is not Role.SYSTEM:
                    del self._messages[index]
                    break
            else:
                # Only system messages left — nothing more we can drop.
                break
