# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

from typing import Any


def make_simple_event(kernel: Any, msg: Any, text: str, chat_id: int) -> Any:
    """Build a lightweight event object wrapping a freshly sent message."""

    class _SimpleEvent:
        def __init__(self) -> None:
            self.id = getattr(msg, "id", None)
            self.message_id = self.id
            self.chat_id = chat_id
            self.text = text
            self.raw_text = text
            self.message = msg
            self.sender_id = getattr(msg, "sender_id", None)
            self.reply_to_msg_id = getattr(msg, "reply_to_msg_id", None)
            self._client = kernel.client
            self.pipe_input = None
            self.pipe_output = None
            self.pipe_exit_code = 0
            self.piped = False
            self.no_add_args_to_input = False

        async def delete(self) -> None:
            try:
                await self._client.delete_messages(self.chat_id, [self.id])
            except Exception:
                pass

        async def get_reply_message(self) -> Any:
            if not self.reply_to_msg_id:
                return None
            try:
                return await self._client.get_messages(
                    self.chat_id, ids=self.reply_to_msg_id
                )
            except Exception:
                return None

        async def edit(
            self,
            new_text: str,
            *args: Any,
            parse_mode: str | None = None,
            **kwargs: Any,
        ) -> Any:
            try:
                return await self._client.edit_message(
                    self.chat_id,
                    self.id,
                    new_text,
                    parse_mode=parse_mode,
                )
            except Exception as err:
                kernel.logger.debug(
                    "[SimpleEvent.edit] edit failed (%s), falling back to send_message",
                    err,
                )
                try:
                    sent = await self._client.send_message(
                        self.chat_id, new_text, parse_mode=parse_mode
                    )
                    if sent and hasattr(sent, "id"):
                        self.id = sent.id
                        self.message_id = sent.id
                    return sent
                except Exception:
                    return None

        async def get_sender(self) -> Any:
            return await self._client.get_entity(self.sender_id)

        async def get_chat(self) -> Any:
            return await self._client.get_entity(self.chat_id)

    return _SimpleEvent()


async def run_and_capture(kernel: Any, ev: Any, depth: int) -> str | None:
    """Run ev through process_command and return captured edit text."""
    captured: list[str] = []
    orig_edit = getattr(ev, "edit", None)

    class _FakeMsg:
        async def edit(self, *args: Any, **kwargs: Any) -> Any:
            return self

    async def _cap(new_text: Any, *args: Any, **kwargs: Any) -> _FakeMsg:
        if isinstance(new_text, str):
            captured.append(new_text)
        return _FakeMsg()

    ev.edit = _cap
    try:
        await kernel.process_command(ev, depth=depth)
    finally:
        if orig_edit is not None:
            ev.edit = orig_edit
        else:
            try:
                del ev.edit
            except AttributeError:
                pass

    explicit = getattr(ev, "pipe_output", None)
    return explicit if explicit is not None else (captured[-1] if captured else None)
