# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Message protocol — structural type for Telegram messages.

Covers the intersection of:
* ``telethon.types.Message``
* Mock message objects (test_kernel / _SimpleEvent)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from core.lib.types.client import Client


class Message(Protocol):
    """Telegram message as seen by modules and internal dispatch."""

    id: int
    text: str
    raw_text: str
    message: str | bytes | Any

    sender_id: int
    chat_id: int
    reply_to_msg_id: int | None

    media: Any

    async def edit(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
    async def reply(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
    async def delete(self) -> Any: ...
    async def forward_to(self, entity: Any, *args: Any, **kwargs: Any) -> Any: ...
    async def get_reply_message(self) -> Message | None: ...
    async def get_sender(self) -> Any: ...
    async def get_chat(self) -> Any: ...
