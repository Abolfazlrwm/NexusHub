"""Conversation memory: persistence of message history between runs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..types import Message


class BaseMemory(ABC):
    """Storage for conversation history.

    Memory is what turns a stateless model call into a conversation: the
    runtime seeds it with the system prompt and user input, appends every
    assistant message and tool result, and reads the full history back
    before each model call.

    Implementations must return *snapshots* from :meth:`messages` — mutating
    the returned list must never affect stored history.
    """

    @abstractmethod
    async def add(self, message: Message) -> None:
        """Append a message to the history."""

    async def extend(self, messages: Iterable[Message]) -> None:
        """Append several messages in order."""
        for message in messages:
            await self.add(message)

    @abstractmethod
    async def messages(self) -> list[Message]:
        """Return a snapshot of the current history."""

    @abstractmethod
    async def clear(self) -> None:
        """Drop all history."""
