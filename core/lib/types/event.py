# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Event protocol — structural type for Telegram events.

Covers the intersection of:
* Real ``telethon.events`` event instances
* ``EventProxy`` (core.lib.loader.kernel_proxy)
* ``_SimpleEvent`` (kernel pipeline / lifecycle)
* ``MockEvent`` (test_kernel)

Usage::

    from core.lib.types import Event

    async def handler(self, event: Event) -> None:
        await event.edit("Hello")
        print(event.chat_id)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from core.lib.types.client import Client
    from core.lib.types.message import Message


class Event(Protocol):
    """Telegram event as seen by modules and internal dispatch."""

    text: str
    raw_text: str
    chat_id: int
    sender_id: int
    message_id: int

    # Telethon event also stores message_id under ``.id``
    id: int

    client: Client
    message: Message
    sender: Any
    chat: Any

    reply_to: Any
    reply_to_msg_id: int | None

    is_private: bool
    is_group: bool
    is_channel: bool

    pattern_match: Any

    def format_with_html(self, text: str, *args: Any, **kwargs: Any) -> str: ...

    @property
    def is_admin(self) -> bool: ...
    async def get_thread_id(self) -> int | None: ...

    async def edit(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
    async def reply(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
    async def delete(self) -> Any: ...
    async def respond(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
    async def answer(
        self, text: str | None = None, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def get_reply_message(self) -> Message | None: ...
    async def get_chat(self) -> Any: ...
    async def get_sender(self) -> Any: ...
