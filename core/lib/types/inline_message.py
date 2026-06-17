# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def _normalize_inline_message_id(value: Any) -> Any:
    """Return a Telethon InputBotInlineMessageID-like object when possible.

    Telethon ``UpdateBotInlineSend.msg_id`` is already an
    ``InputBotInlineMessageID``/``InputBotInlineMessageID64`` object. Older MCUB
    code may store it as ``"dc_id:id:access_hash"``; convert that string back
    before passing it to ``messages.EditInlineBotMessageRequest(id=...)``.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    parts = value.split(":")
    if len(parts) < 3:
        return value
    try:
        dc_id, msg_id, access_hash = (int(parts[0]), int(parts[1]), int(parts[2]))
    except (TypeError, ValueError):
        return value
    try:
        from telethon.tl.types import InputBotInlineMessageID64

        return InputBotInlineMessageID64(
            dc_id=dc_id,
            owner_id=0,
            id=msg_id,
            access_hash=access_hash,
        )
    except (ImportError, TypeError):
        from telethon.tl.types import InputBotInlineMessageID

        return InputBotInlineMessageID(
            dc_id=dc_id,
            id=msg_id,
            access_hash=access_hash,
        )


def _serialize_inline_message_id(value: Any) -> Any:
    """Serialize Telethon inline message id for cache/storage."""
    if value is None or isinstance(value, str):
        return value
    dc_id = getattr(value, "dc_id", None)
    msg_id = getattr(value, "id", None)
    access_hash = getattr(value, "access_hash", None)
    if dc_id is None or msg_id is None or access_hash is None:
        return value
    return f"{dc_id}:{msg_id}:{access_hash}"


def _inline_buttons(buttons: Any) -> Any:
    """Normalize MCUB inline button rows for Telethon edit requests."""
    if buttons is None:
        return None
    from telethon import Button as TelethonButton

    rows = [list(row) if isinstance(row, tuple) else row for row in buttons]
    if hasattr(TelethonButton, "from_array"):
        return TelethonButton.from_array(rows)
    return rows


def _rich_message_unsupported(error: BaseException) -> bool:
    """Return True for Telegram peers that reject rich_message edits."""
    return "RICH_MESSAGE_UNSUPPORTED" in str(error)


def _build_input_rich_message(
    *,
    html: str | None = None,
    markdown: str | None = None,
    rich_message: Any = None,
    rtl: bool | None = None,
    noautolink: bool | None = None,
    files: Any = None,
) -> Any:
    """Build a Telethon InputRichMessage object from friendly arguments."""
    if rich_message is not None:
        return rich_message

    from telethon.tl import types

    if html is not None:
        return types.InputRichMessageHTML(
            html=html,
            rtl=rtl,
            noautolink=noautolink,
            files=files,
        )
    if markdown is not None:
        return types.InputRichMessageMarkdown(
            markdown=markdown,
            rtl=rtl,
            noautolink=noautolink,
            files=files,
        )
    raise ValueError("Either html, markdown or rich_message must be provided")


def _rich_fallback(
    html: str | None, markdown: str | None, text: str
) -> tuple[str, Any]:
    """Return fallback text and parse mode for regular edit()."""
    if html is not None:
        return html, "html"
    if markdown is not None:
        return markdown, ()
    return text, None


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
        self.inline_message_id = _serialize_inline_message_id(
            getattr(event, "inline_message_id", None)
            or getattr(event, "_inline_msg_id", None)
            or getattr(event, "msg_id", None)
        )
        self.unit_id = unit_id or getattr(event, "unit_id", "")
        if self.inline_message_id is None and self.unit_id and kernel is not None:
            cache = getattr(kernel, "cache", None)
            if cache is not None:
                form_data = cache.get(self.unit_id) or cache.get(f"msg_{self.unit_id}")
                if form_data:
                    self.inline_message_id = _serialize_inline_message_id(
                        form_data.get("inline_message_id")
                    )
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

                    if hasattr(TelethonButton, "from_array"):
                        edit_kw["buttons"] = TelethonButton.from_array(
                            [list(r) if isinstance(r, tuple) else r for r in buttons]
                        )
                    else:
                        edit_kw["buttons"] = [
                            list(r) if isinstance(r, tuple) else r for r in buttons
                        ]
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

                    imid = _normalize_inline_message_id(imid)
                    send = {}
                    if text is not None:
                        send["message"] = text
                        send["parse_mode"] = parse_mode
                    if buttons is not None:
                        from telethon import Button as TelethonButton

                        if hasattr(TelethonButton, "from_array"):
                            send["buttons"] = TelethonButton.from_array(
                                [
                                    list(r) if isinstance(r, tuple) else r
                                    for r in buttons
                                ]
                            )
                        else:
                            send["buttons"] = [
                                list(r) if isinstance(r, tuple) else r for r in buttons
                            ]
                    if send:
                        client = getattr(k, "client", None)
                        if client is not None:
                            await client(EditInlineBotMessageRequest(id=imid, **send))
                    return self

        imid = self.inline_message_id
        if imid is not None and k is not None:
            from telethon.tl.functions.messages import EditInlineBotMessageRequest

            imid = _normalize_inline_message_id(imid)
            send = {}
            if text is not None:
                send["message"] = text
                send["parse_mode"] = parse_mode
            if buttons is not None:
                from telethon import Button as TelethonButton

                if hasattr(TelethonButton, "from_array"):
                    send["buttons"] = TelethonButton.from_array(
                        [list(r) if isinstance(r, tuple) else r for r in buttons]
                    )
                else:
                    send["buttons"] = [
                        list(r) if isinstance(r, tuple) else r for r in buttons
                    ]
            if send:
                client = getattr(k, "client", None)
                if client is not None:
                    await client(EditInlineBotMessageRequest(id=imid, **send))
            return self

        kwargs.setdefault("parse_mode", parse_mode)
        if text is not None:
            kwargs["text"] = text
        if buttons is not None:
            kwargs["buttons"] = buttons
        await self._event.edit(**kwargs)
        return self

    async def edit_rich(
        self,
        html: str | None = None,
        buttons: Any = None,
        *,
        rich_message: Any = None,
        markdown: str | None = None,
        text: str = "",
        fallback: bool = True,
        fallback_text: str | None = None,
        fallback_parse_mode: Any = None,
        link_preview: bool = False,
        rtl: bool | None = None,
        noautolink: bool | None = None,
        files: Any = None,
        **kwargs: Any,
    ) -> InlineMessage:
        """Edit this inline message using Telegram rich_message formatting.

        Falls back to regular ``edit()`` when Telegram rejects rich messages for
        the current peer with ``RICH_MESSAGE_UNSUPPORTED``.
        """
        input_rich_message = _build_input_rich_message(
            html=html,
            markdown=markdown,
            rich_message=rich_message,
            rtl=rtl,
            noautolink=noautolink,
            files=files,
        )

        async def fallback_edit(inline_message_id: Any = None) -> InlineMessage:
            nonlocal fallback_text, fallback_parse_mode
            if fallback_text is None:
                fallback_text, default_parse_mode = _rich_fallback(html, markdown, text)
                if fallback_parse_mode is None:
                    fallback_parse_mode = default_parse_mode

            k = self._kernel
            client = getattr(k, "client", None) if k is not None else None
            if inline_message_id is not None and hasattr(client, "edit_message"):
                await client.edit_message(
                    _normalize_inline_message_id(inline_message_id),
                    fallback_text,
                    parse_mode=fallback_parse_mode,
                    link_preview=link_preview,
                    buttons=buttons,
                    **kwargs,
                )
                return self

            await self.edit(
                fallback_text,
                buttons=buttons,
                parse_mode=fallback_parse_mode,
                **kwargs,
            )
            return self

        async def edit_inline_id(inline_message_id: Any) -> bool:
            k = self._kernel
            client = getattr(k, "client", None) if k is not None else None
            if client is None:
                return False

            inline_message_id = _normalize_inline_message_id(inline_message_id)
            if hasattr(client, "edit_rich_message"):
                await client.edit_rich_message(
                    inline_message_id,
                    html,
                    rich_message=input_rich_message,
                    markdown=markdown,
                    text=text,
                    fallback=fallback,
                    fallback_text=fallback_text,
                    fallback_parse_mode=fallback_parse_mode,
                    link_preview=link_preview,
                    buttons=buttons,
                )
                return True

            from telethon.tl.functions.messages import EditInlineBotMessageRequest

            await client(
                EditInlineBotMessageRequest(
                    id=inline_message_id,
                    message=text,
                    no_webpage=not link_preview,
                    reply_markup=_inline_buttons(buttons),
                    rich_message=input_rich_message,
                )
            )
            return True

        k = self._kernel
        if k is not None and self.chat_id and self.message_id:
            bot_client = getattr(k, "bot_client", None)
            if bot_client is not None and hasattr(bot_client, "edit_rich_message"):
                try:
                    await bot_client.edit_rich_message(
                        self.chat_id,
                        self.message_id,
                        html,
                        rich_message=input_rich_message,
                        markdown=markdown,
                        text=text,
                        fallback=fallback,
                        fallback_text=fallback_text,
                        fallback_parse_mode=fallback_parse_mode,
                        link_preview=link_preview,
                        buttons=buttons,
                    )
                    return self
                except Exception as error:
                    if fallback and _rich_message_unsupported(error):
                        return await fallback_edit()

        if self.unit_id and k is not None and self.message_id:
            from core_inline.handlers import InlineHandlers

            handlers = InlineHandlers(k, getattr(k, "bot_client", None))
            form_data = handlers.get_inline_form(self.unit_id)
            if not form_data:
                form_data = handlers.get_inline_form(f"msg_{self.unit_id}")
            if form_data:
                inline_message_id = form_data.get("inline_message_id")
                if inline_message_id:
                    try:
                        if await edit_inline_id(inline_message_id):
                            return self
                    except Exception as error:
                        if fallback and _rich_message_unsupported(error):
                            return await fallback_edit(inline_message_id)
                        raise

        if self.inline_message_id is not None and k is not None:
            try:
                if await edit_inline_id(self.inline_message_id):
                    return self
            except Exception as error:
                if fallback and _rich_message_unsupported(error):
                    return await fallback_edit(self.inline_message_id)
                raise

        event_edit_rich = getattr(self._event, "edit_rich", None)
        if event_edit_rich is not None:
            await event_edit_rich(
                html,
                rich_message=input_rich_message,
                markdown=markdown,
                text=text,
                fallback=fallback,
                fallback_text=fallback_text,
                fallback_parse_mode=fallback_parse_mode,
                link_preview=link_preview,
                buttons=buttons,
                **kwargs,
            )
            return self

        return await fallback_edit()

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
                            id=_normalize_inline_message_id(self.inline_message_id),
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

                if hasattr(TelethonButton, "from_array"):
                    send["buttons"] = TelethonButton.from_array(
                        [list(b) if isinstance(b, tuple) else b for b in buttons]
                    )
                else:
                    send["buttons"] = [
                        list(b) if isinstance(b, tuple) else b for b in buttons
                    ]
            if send:
                try:
                    await kernel.client(
                        EditInlineBotMessageRequest(
                            id=_normalize_inline_message_id(inline_msg_id), **send
                        )
                    )
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
                    id=_normalize_inline_message_id(inline_msg_id),
                    message="",
                )
            )
        except Exception:
            pass

    return _delete
