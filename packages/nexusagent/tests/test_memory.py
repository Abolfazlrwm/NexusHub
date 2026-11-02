"""Tests for conversation memory."""

from __future__ import annotations

import pytest

from nexusagent.memory import InMemoryMemory
from nexusagent.types import Message, Role


async def test_add_and_snapshot() -> None:
    memory = InMemoryMemory()
    await memory.add(Message.user("hello"))
    snapshot = await memory.messages()
    assert [m.role for m in snapshot] == [Role.USER]
    assert snapshot == await memory.messages()


async def test_snapshot_is_a_copy() -> None:
    memory = InMemoryMemory()
    await memory.add(Message.user("hello"))
    snapshot = await memory.messages()
    snapshot.clear()
    assert len(await memory.messages()) == 1


async def test_extend_preserves_order() -> None:
    memory = InMemoryMemory()
    await memory.extend(
        [
            Message.system("sys"),
            Message.user("one"),
            Message.assistant("two"),
        ]
    )
    roles = [m.role for m in await memory.messages()]
    assert roles == [Role.SYSTEM, Role.USER, Role.ASSISTANT]


async def test_clear() -> None:
    memory = InMemoryMemory()
    await memory.add(Message.user("hello"))
    await memory.clear()
    assert await memory.messages() == []


async def test_unbounded_by_default() -> None:
    memory = InMemoryMemory()
    for index in range(50):
        await memory.add(Message.user(f"m{index}"))
    assert len(await memory.messages()) == 50


async def test_window_trims_oldest_first() -> None:
    memory = InMemoryMemory(max_messages=3)
    await memory.extend(
        [
            Message.user("first"),
            Message.user("second"),
            Message.user("third"),
            Message.user("fourth"),
        ]
    )
    snapshot = await memory.messages()
    assert len(snapshot) == 3
    assert [m.content for m in snapshot] == ["second", "third", "fourth"]


async def test_window_pins_system_messages() -> None:
    memory = InMemoryMemory(max_messages=3)
    await memory.add(Message.system("instructions"))
    for index in range(5):
        await memory.add(Message.user(f"m{index}"))
    snapshot = await memory.messages()
    assert len(snapshot) == 3
    assert snapshot[0].role is Role.SYSTEM  # instructions survived every trim
    assert snapshot[0].content == "instructions"
    assert [m.content for m in snapshot[1:]] == ["m3", "m4"]


async def test_extend_trims_once_after_bulk_add() -> None:
    memory = InMemoryMemory(max_messages=4)
    await memory.extend([Message.system("s"), Message.user("u1"), Message.user("u2")])
    await memory.extend([Message.user("u3"), Message.user("u4"), Message.user("u5")])
    snapshot = await memory.messages()
    assert [m.content for m in snapshot] == ["s", "u3", "u4", "u5"]


def test_invalid_window_size_rejected() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        InMemoryMemory(max_messages=0)
