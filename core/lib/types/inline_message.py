# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class InlineMessage:
    """Native MCUB inline message with edit/delete/answer API.

    Wraps a Telethon CallbackQuery event (for callback handlers) or an inline
    form record (for programmatic use) so that modules always receive a uniform
    ``InlineMessage`` — never a raw Telethon object.

    Usage in a callback handler::

        @loader.callback(ttl=300)
        async def on_click(self, call: InlineMessage) -> None:
            await call.answer("Clicked!")
            await call.edit("New text", buttons=...)

    Usage after ``self.inline()``::

        ok, msg = await self.inline(chat_id, "Hello")
        if ok:
            await msg.edit("Updated!")
    """

    def __init__(self, event: Any, *, unit_id: str = "", kernel: Any = None) -> None:
        self._event = event
        self._kernel = kernel
        self.data: bytes = getattr(event, "data", b"")
        self.inline_message_id = getattr(event, "inline_message_id", None) or getattr(
            event, "_inline_msg_id", None
        )
        self.unit_id = unit_id or getattr(event, "unit_id", "")
        self.chat_id = getattr(event, "chat_id", None)
        self.message_id = (
            getattr(event, "message_id", None)
            or getattr(event, "id", None)
            or getattr(getattr(event, "message", None), "id", None)
        )
        self.sender_id = getattr(event, "sender_id", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._event, name)

    async def answer(self, text: str = "", alert: bool = False) -> None:
        """Answer the callback query (toast or alert popup).

        Args:
            text: Message text (empty = no toast).
            alert: If True, show a modal alert instead of a toast.
        """
        await self._event.answer(text, alert=alert)

    async def edit(
        self,
        text: str | None = None,
        buttons: Any = None,
        *,
        parse_mode: str = "html",
        **kwargs: Any,
    ) -> InlineMessage:
        k = self._kernel

        if k is not None and self.chat_id and self.message_id:
            bot_client = getattr(k, "bot_client", None)
            if bot_client is not None:
                edit_kw = {"parse_mode": parse_mode}
                if buttons is not None:
                    from telethon import Button as TelethonButton

                    edit_kw["buttons"] = TelethonButton.from_array(
                        [list(r) if isinstance(r, tuple) else r for r in buttons]
                    )
                edit_kw.update(kwargs)
                try:
                    await bot_client.edit_message(
                        self.chat_id,
                        self.message_id,
                        text,
                        **edit_kw,
                    )
                    return self
                except Exception:
                    pass

        # 2. Try form_data by unit_id (populated by inline_query_and_click)
        if self.unit_id and k is not None and self.message_id:
            from core_inline.handlers import InlineHandlers

            handlers = InlineHandlers(k, getattr(k, "bot_client", None))
            form_data = handlers.get_inline_form(self.unit_id)
            if not form_data:
                form_data = handlers.get_inline_form(f"msg_{self.unit_id}")
            if form_data:
                imid = form_data.get("inline_message_id")
                if imid:
                    from telethon.tl.functions.messages import (
                        EditInlineBotMessageRequest,
                    )
                    from telethon.tl.types import InputBotInlineMessageID

                    if isinstance(imid, str) and ":" in imid:
                        parts = imid.split(":")
                        imid = InputBotInlineMessageID(
                            dc_id=int(parts[0]) if len(parts) > 0 else 0,
                            id=int(parts[1]) if len(parts) > 1 else 0,
                            access_hash=int(parts[2]) if len(parts) > 2 else 0,
                        )
                    send = {}
                    if text is not None:
                        send["message"] = text
                        send["parse_mode"] = parse_mode
                    if buttons is not None:
                        from telethon import Button as TelethonButton

                        send["buttons"] = TelethonButton.from_array(
                            [list(r) if isinstance(r, tuple) else r for r in buttons]
                        )
                    if send:
                        client = getattr(k, "client", None)
                        if client is not None:
                            await client(EditInlineBotMessageRequest(peer=imid, **send))
                    return self

        imid = self.inline_message_id
        if imid is not None and k is not None:
            from telethon.tl.functions.messages import EditInlineBotMessageRequest
            from telethon.tl.types import InputBotInlineMessageID

            if isinstance(imid, str) and ":" in imid:
                parts = imid.split(":")
                imid = InputBotInlineMessageID(
                    dc_id=int(parts[0]) if len(parts) > 0 else 0,
                    id=int(parts[1]) if len(parts) > 1 else 0,
                    access_hash=int(parts[2]) if len(parts) > 2 else 0,
                )
            send = {}
            if text is not None:
                send["message"] = text
                send["parse_mode"] = parse_mode
            if buttons is not None:
                from telethon import Button as TelethonButton

                send["buttons"] = TelethonButton.from_array(
                    [list(r) if isinstance(r, tuple) else r for r in buttons]
                )
            if send:
                client = getattr(k, "client", None)
                if client is not None:
                    await client(EditInlineBotMessageRequest(peer=imid, **send))
            return self

        kwargs.setdefault("parse_mode", parse_mode)
        if text is not None:
            kwargs["text"] = text
        if buttons is not None:
            kwargs["buttons"] = buttons
        await self._event.edit(**kwargs)
        return self

        imid = self.inline_message_id
        if imid is not None and self._kernel is not None:
            from telethon.tl.functions.messages import EditInlineBotMessageRequest
            from telethon.tl.types import InputBotInlineMessageID

            if isinstance(imid, str) and ":" in imid:
                parts = imid.split(":")
                imid = InputBotInlineMessageID(
                    dc_id=int(parts[0]) if len(parts) > 0 else 0,
                    id=int(parts[1]) if len(parts) > 1 else 0,
                    access_hash=int(parts[2]) if len(parts) > 2 else 0,
                )
            send = {}
            if text is not None:
                send["message"] = text
                send["parse_mode"] = parse_mode
            if buttons is not None:
                from telethon import Button as TelethonButton

                send["buttons"] = TelethonButton.from_array(
                    [list(r) if isinstance(r, tuple) else r for r in buttons]
                )
            if send:
                client = getattr(self._kernel, "client", None)
                if client is not None:
                    await client(EditInlineBotMessageRequest(peer=imid, **send))
            return self

        kwargs.setdefault("parse_mode", parse_mode)
        if text is not None:
            kwargs["text"] = text
        if buttons is not None:
            kwargs["buttons"] = buttons
        await self._event.edit(**kwargs)
        return self

    async def delete(self) -> None:
        """Delete the inline message."""
        try:
            await self._event.delete()
        except Exception:
            if self._kernel is not None and self.inline_message_id:
                try:
                    from telethon.tl.functions.messages import (
                        EditInlineBotMessageRequest,
                    )

                    await self._kernel.client(
                        EditInlineBotMessageRequest(
                            peer=self.inline_message_id,
                            message="",
                        )
                    )
                except Exception:
                    pass

    @classmethod
    def from_event(cls, event: Any, kernel: Any = None) -> InlineMessage:
        """Wrap a Telethon CallbackQuery event as an InlineMessage."""
        return cls(event, kernel=kernel)

    @classmethod
    def from_form(
        cls,
        form_data: dict[str, Any],
        unit_id: str,
        kernel: Any,
    ) -> InlineMessage:
        """Create an InlineMessage from a stored form record (no live event)."""
        from types import SimpleNamespace

        event = SimpleNamespace()
        event.data = b""
        event.inline_message_id = form_data.get("inline_message_id")
        event.chat_id = form_data.get("chat_id")
        event.message_id = form_data.get("message_id")
        event.sender_id = form_data.get("sender_id")
        event.unit_id = unit_id
        event.edit = _make_form_edit(kernel, unit_id, form_data)
        event.delete = _make_form_delete(kernel, unit_id, form_data)
        event.answer = lambda text="", alert=False: None
        return cls(event, unit_id=unit_id, kernel=kernel)

    @property
    def text(self) -> str:
        """Current message text (from the underlying event or form data)."""
        msg = getattr(self._event, "message", None)
        if msg is not None:
            return getattr(msg, "text", "") or getattr(msg, "message", "") or ""
        return getattr(self._event, "text", "") or ""


def _make_form_edit(
    kernel: Any,
    unit_id: str,
    form_data: dict[str, Any],
):
    """Build an async edit function for a form-only InlineMessage."""

    async def _edit(
        text: str | None = None,
        buttons: Any = None,
        *,
        parse_mode: str = "html",
        **kwargs,
    ):
        from core_inline.handlers import InlineHandlers

        kwargs.setdefault("parse_mode", parse_mode)
        handlers = InlineHandlers(kernel, getattr(kernel, "bot_client", None))
        update = dict(form_data)
        if text is not None:
            update["text"] = text
        if buttons is not None:
            update["buttons"] = buttons
        cache = getattr(kernel, "cache", None)
        if cache:
            cache.set(unit_id, update, ttl=3600)
        inline_msg_id = form_data.get("inline_message_id")
        if inline_msg_id:
            from telethon.tl.functions.messages import EditInlineBotMessageRequest

            send: dict = {}
            if text is not None:
                send["message"] = text
            if buttons is not None:
                from telethon import Button as TelethonButton

                send["buttons"] = TelethonButton.from_array(
                    [list(b) if isinstance(b, tuple) else b for b in buttons]
                )
            if send:
                try:
                    await kernel.client(EditInlineBotMessageRequest(**send))
                except Exception:
                    pass

    return _edit


def _make_form_delete(
    kernel: Any,
    unit_id: str,
    form_data: dict[str, Any],
):
    """Build an async delete function for a form-only InlineMessage."""

    async def _delete():
        inline_msg_id = form_data.get("inline_message_id")
        if not inline_msg_id:
            return
        from telethon.tl.functions.messages import EditInlineBotMessageRequest

        try:
            await kernel.client(
                EditInlineBotMessageRequest(
                    peer=inline_msg_id,
                    message="",
                )
            )
        except Exception:
            pass

    return _delete
