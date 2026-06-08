# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Client protocol — structural type for the Telegram client.

Covers the intersection of:
* ``telethon.TelegramClient``
* ``ClientProxy`` (core.lib.loader.kernel_proxy)
* ``MockTelegramClient`` (test_kernel)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from core.lib.types.message import Message


class Client(Protocol):
    """Telegram client as seen by modules and internal code.

    Because ``ClientProxy`` blocks dangerous operations (disconnect,
    logout, add_event_handler, …) the protocol only exposes the safe
    subset that modules can actually call.
    """

    @property
    def parse_mode(self) -> str: ...

    async def send_message(
        self, entity: Any, text: str, *args: Any, **kwargs: Any
    ) -> Message: ...
    async def edit_message(
        self, entity: Any, message: Any, text: str, *args: Any, **kwargs: Any
    ) -> Message: ...
    async def delete_messages(
        self, entity: Any, message_ids: list[int], *args: Any, **kwargs: Any
    ) -> Any: ...
    async def forward_messages(
        self, entity: Any, messages: Any, *args: Any, **kwargs: Any
    ) -> Any: ...

    async def send_file(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_photo(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_video(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_audio(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_document(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_voice(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_sticker(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...
    async def send_animation(
        self, entity: Any, file: Any, *args: Any, **kwargs: Any
    ) -> Any: ...

    async def get_entity(self, *args: Any, **kwargs: Any) -> Any: ...
    async def get_me(self) -> Any: ...
    async def get_messages(self, entity: Any, *args: Any, **kwargs: Any) -> Any: ...
    async def get_dialogs(self, *args: Any, **kwargs: Any) -> Any: ...

    async def respond(
        self, entity: Any, text: str, *args: Any, **kwargs: Any
    ) -> Message: ...
