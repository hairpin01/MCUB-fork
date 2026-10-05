# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def _inline_id_types() -> tuple[type, ...]:
    """Return every TL class usable as ``InputBotInlineMessageID``.

    Layer 229 declares ``inputBotInlineMessageID#890c3d89`` (dc_id, id,
    access_hash) and ``inputBotInlineMessageID64#b6d915d7`` (dc_id, owner_id,
    id, access_hash) under the same TL type name, so Telethon generates two
    sibling classes with no shared Python base. Always compare against this
    tuple - ``isinstance(x, InputBotInlineMessageID)`` alone silently rejects
    the 64-bit variant.
    """
    from telethon.tl import types

    found = [types.InputBotInlineMessageID]
    for name in ("InputBotInlineMessageID64", "InputBotInlineMessageIDOld"):
        candidate = getattr(types, name, None)
        if candidate is not None:
            found.append(candidate)
    return tuple(found)


def is_inline_message_id(value: Any) -> bool:
    """Return True for ``InputBotInlineMessageID`` and its 64-bit sibling."""
    return isinstance(value, _inline_id_types())


def _decode_bot_api_inline_message_id(value: str) -> Any | None:
    """Decode a Bot API ``inline_message_id`` into an MTProto input id.

    The Bot API hands out ``inline_message_id`` as urlsafe-base64 wrapping
    ``struct.pack("<iiiq", dc_id, message_id, peer_id, access_hash)``. The
    third field is negative for channels and equals the owner user id for
    private chats, which is exactly the ``owner_id`` required by
    ``inputBotInlineMessageID64`` - so a Bot API id is always reconstructed as
    the 64-bit variant.

    Returns ``None`` when the string is not in this format (for example when it
    is MCUB's own ``"dc_id:id:access_hash"`` form).
    """
    import base64
    import binascii
    import struct

    try:
        raw = base64.urlsafe_b64decode(value + "=" * (len(value) % 4))
        dc_id, msg_id, peer_id, access_hash = struct.unpack("<iiiq", raw)
    except (binascii.Error, struct.error, ValueError, TypeError):
        return None

    from telethon.tl import types

    id64 = getattr(types, "InputBotInlineMessageID64", None)
    if id64 is None:  # pragma: no cover - very old Telethon
        return types.InputBotInlineMessageID(
            dc_id=dc_id,
            id=msg_id,
            access_hash=access_hash,
        )

    return id64(
        dc_id=dc_id,
        owner_id=abs(peer_id),
        id=msg_id,
        access_hash=access_hash,
    )


def _normalize_inline_message_id(value: Any) -> Any:
    """Return a Telethon InputBotInlineMessageID-like object when possible.

    Telethon ``UpdateBotInlineSend.msg_id`` is already an
    ``InputBotInlineMessageID``/``InputBotInlineMessageID64`` object. Older MCUB
    code may store it as a string; convert that string back before passing it
    to ``messages.EditInlineBotMessageRequest(id=...)``.

    Serialized form is positional, so the field count selects the constructor:

    * ``"dc_id:id:access_hash"`` -> ``InputBotInlineMessageID``
    * ``"dc_id:owner_id:id:access_hash"`` -> ``InputBotInlineMessageID64``

    Guessing ``InputBotInlineMessageID64`` with a placeholder ``owner_id=0``
    yields ``MESSAGE_ID_INVALID`` from Telegram, so the 3-part form must keep
    using the 32-bit message id constructor.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    parts = value.split(":")
    if len(parts) not in (3, 4):
        # Not MCUB's positional form - try the Bot API base64 format, which is
        # what aiogram delivers as CallbackQuery.inline_message_id.
        return _decode_bot_api_inline_message_id(value) or value
    try:
        numbers = [int(part) for part in parts]
    except (TypeError, ValueError):
        return _decode_bot_api_inline_message_id(value) or value

    from telethon.tl import types

    if len(numbers) == 3:
        dc_id, msg_id, access_hash = numbers
        return types.InputBotInlineMessageID(
            dc_id=dc_id,
            id=msg_id,
            access_hash=access_hash,
        )

    dc_id, owner_id, msg_id, access_hash = numbers
    id64 = getattr(types, "InputBotInlineMessageID64", None)
    if id64 is None:  # pragma: no cover - very old Telethon
        return types.InputBotInlineMessageID(
            dc_id=dc_id,
            id=msg_id,
            access_hash=access_hash,
        )
    return id64(
        dc_id=dc_id,
        owner_id=owner_id,
        id=msg_id,
        access_hash=access_hash,
    )


def _serialize_inline_message_id(value: Any) -> Any:
    """Serialize Telethon inline message id for cache/storage.

    Output is the inverse of :func:`_normalize_inline_message_id`: the 64-bit
    variant keeps ``owner_id`` so it survives a cache round-trip.
    """
    if value is None or isinstance(value, str):
        return value
    dc_id = getattr(value, "dc_id", None)
    msg_id = getattr(value, "id", None)
    access_hash = getattr(value, "access_hash", None)
    if dc_id is None or msg_id is None or access_hash is None:
        return value
    owner_id = getattr(value, "owner_id", None)
    if owner_id is not None:
        return f"{dc_id}:{owner_id}:{msg_id}:{access_hash}"
    return f"{dc_id}:{msg_id}:{access_hash}"


async def _parse_inline_text(
    client: Any, text: str, parse_mode: Any
) -> tuple[str, Any]:
    """Split ``text`` into (plain_text, entities) for a raw TL request.

    ``messages.editInlineBotMessage`` has no ``parse_mode`` flag - formatting
    travels as a separate ``Vector<MessageEntity>``. Prefer the client's own
    parser so ``parse_mode=()`` (auto-detect) and HTML emoji conversion behave
    exactly as they do in ``client.edit_message()``.
    """
    try:
        parser = getattr(client, "_parse_message_text", None)
    except Exception:
        # ClientProxy raises CallInsecure for any "_"-prefixed attribute, and
        # getattr(..., default) does not suppress that.
        parser = None

    if callable(parser):
        try:
            return await parser(text, parse_mode)
        except Exception:
            return text, None

    from telethon import utils

    try:
        resolved = utils.sanitize_parse_mode(parse_mode)
    except Exception:
        return text, None
    if not resolved:
        return text, None
    return resolved.parse(text)


async def build_inline_edit_request(
    client: Any,
    inline_message_id: Any,
    *,
    text: str | None = None,
    buttons: Any = None,
    parse_mode: Any = "html",
    link_preview: bool = False,
    **extra: Any,
) -> Any:
    """Build ``EditInlineBotMessageRequest`` with schema-correct fields.

    ``buttons`` is converted through ``client.build_reply_markup`` into
    ``reply_markup``; passing ``buttons=``/``parse_mode=`` to the request
    raises ``TypeError`` because neither exists in the TL schema.
    """
    from telethon.tl.functions.messages import EditInlineBotMessageRequest

    imid = _normalize_inline_message_id(inline_message_id)
    if imid is None:
        return None

    kwargs: dict[str, Any] = {"id": imid}
    if text is not None:
        plain, entities = await _parse_inline_text(client, text, parse_mode)
        kwargs["message"] = plain
        if entities:
            kwargs["entities"] = entities

    if buttons:
        builder = getattr(client, "build_reply_markup", None)
        markup = builder(buttons) if callable(builder) else buttons
        if markup is not None:
            kwargs["reply_markup"] = markup

    if not link_preview:
        kwargs["no_webpage"] = True

    kwargs.update(extra)
    return EditInlineBotMessageRequest(**kwargs)


def _inline_client(kernel: Any) -> Any:
    """Return the client that owns inline messages.

    Inline results belong to the inline bot, so ``messages.editInlineBotMessage``
    must be issued by ``bot_client``. The user account (``kernel.client``) gets
    ``MESSAGE_ID_INVALID``/``BOT_METHOD_INVALID``. Falls back to ``client`` for
    kernels where the bot *is* the main client.
    """
    if kernel is None:
        return None
    return getattr(kernel, "bot_client", None) or getattr(kernel, "client", None)


def _inline_buttons(client: Any, buttons: Any) -> Any:
    """Build a ``ReplyMarkup`` from MCUB inline button rows.

    ``Button.from_array`` returns a nested list of ``Button`` objects, which is
    not a TL object - it must go through ``client.build_reply_markup`` before it
    can be assigned to a request's ``reply_markup`` field.
    """
    if not buttons:
        return None

    from telethon import Button as TelethonButton

    rows = [list(row) if isinstance(row, tuple) else row for row in buttons]
    buttons = (
        TelethonButton.from_array(rows)
        if hasattr(TelethonButton, "from_array")
        else rows
    )

    try:
        builder = getattr(client, "build_reply_markup", None)
    except Exception:
        # ClientProxy blocks underscore-prefixed attributes only; this one is
        # public, but stay defensive since it raises rather than returning None.
        builder = None
    return builder(buttons) if callable(builder) else None


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
    ``InlineMessage`` - never a raw Telethon object.

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
        # Callback payloads arrive as bytes from Telethon but as str from the
        # aiogram adapters, so both shapes are accepted here.
        self.data: bytes | str = getattr(event, "data", b"")
        self.inline_message_id = _serialize_inline_message_id(
            getattr(event, "inline_message_id", None)
            or getattr(event, "_inline_msg_id", None)
            or (
                getattr(event, "msg_id", None)
                if is_inline_message_id(getattr(event, "msg_id", None))
                else None
            )
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
        # Guard against recursion when _event is itself missing (e.g. during
        # unpickling or when a subclass forgets to call __init__).
        event = self.__dict__.get("_event")
        if event is None:
            raise AttributeError(name)
        return getattr(event, name)

    async def answer(self, text: str = "", alert: bool = False) -> None:
        """Answer the callback query (toast or alert popup).

        Args:
            text: Message text (empty = no toast).
            alert: If True, show a modal alert instead of a toast.
        """
        await self._event.answer(text, alert=alert)

    def _is_via_bot_message(self) -> bool:
        """Return True if the underlying event is a message sent via an inline bot.

        Such messages are only editable through
        ``messages.editInlineBotMessage``; ``messages.editMessage`` rejects them
        with ``INLINE_BOT_REQUIRED`` or ``CHAT_WRITE_FORBIDDEN``. Knowing this
        lets ``edit()`` fail fast instead of issuing a doomed chat edit.

        Detection covers the plain Telethon ``Message``, the aiogram adapters
        (which nest the payload under ``.message``) and a sender-id match
        against the configured inline bot.
        """
        event = self._event
        for candidate in (event, getattr(event, "message", None)):
            if candidate is None:
                continue
            if getattr(candidate, "via_bot_id", None):
                return True
            via_bot = getattr(candidate, "via_bot", None)
            if via_bot is not None and getattr(via_bot, "id", None):
                return True

        bot_id = getattr(self._kernel, "inline_bot_user_id", None)
        if bot_id is not None:
            for candidate in (event, getattr(event, "message", None)):
                sender = getattr(candidate, "sender_id", None) or getattr(
                    candidate, "from_id", None
                )
                if sender is None:
                    continue
                try:
                    if int(sender) == int(bot_id):
                        return True
                except (TypeError, ValueError):
                    continue

        return False

    def _form_data(self) -> dict[str, Any] | None:
        """Read the cached form record for this message, if any.

        Uses ``kernel.cache`` directly instead of instantiating
        ``InlineHandlers``: building that object opens an ``aiohttp`` session,
        constructs an ``InlineManager`` and re-runs handler registration, all
        just to read one cache entry.
        """
        if not self.unit_id:
            return None
        cache = getattr(self._kernel, "cache", None)
        if cache is None:
            return None
        return cache.get(self.unit_id) or cache.get(f"msg_{self.unit_id}")

    def _resolve_inline_message_id(self) -> Any:
        """Return the inline message id from the event or the cached form."""
        if self.inline_message_id is not None:
            return self.inline_message_id
        form_data = self._form_data()
        if form_data:
            return _serialize_inline_message_id(form_data.get("inline_message_id"))
        return None

    async def edit(
        self,
        text: str | None = None,
        buttons: Any = None,
        *,
        parse_mode: str = "html",
        **kwargs: Any,
    ) -> InlineMessage:
        k = self._kernel

        # inline_message_id identifies the inline result itself, so it takes
        # priority over chat_id/message_id - the latter points at whatever
        # regular message the bot happens to know about, which is the wrong
        # target for an inline message.
        imid = self._resolve_inline_message_id()
        if imid is not None:
            client = _inline_client(k)
            if client is not None:
                request = await build_inline_edit_request(
                    client,
                    imid,
                    text=text,
                    buttons=buttons,
                    parse_mode=parse_mode,
                    **kwargs,
                )
                if request is not None:
                    await client(request)
                return self

        via_bot = self._is_via_bot_message()

        if k is not None and self.chat_id and self.message_id and not via_bot:
            bot_client = getattr(k, "bot_client", None)
            if bot_client is not None:
                edit_kw = {"parse_mode": parse_mode}
                if buttons is not None:
                    # edit_message(buttons=...) runs build_reply_markup itself,
                    # so pass the raw rows rather than a pre-built markup.
                    edit_kw["buttons"] = buttons
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

        if via_bot:
            # A message that reached the chat through an inline result has no
            # chat-edit permissions for the bot: EditMessageRequest fails with
            # CHAT_WRITE_FORBIDDEN or INLINE_BOT_REQUIRED. It is only editable
            # through EditInlineBotMessageRequest, which needs the
            # inline_message_id from UpdateBotInlineSend.msg_id.
            #
            # Telegram sends that field as None when the inline result was sent
            # from the same account that answered the query - which is what
            # subinline.form() does. The id is then never delivered, so this is
            # permanent rather than a race: say so instead of implying that
            # waiting will help.
            raise RuntimeError(
                "Cannot edit this inline message: Telegram did not provide an "
                "inline_message_id for it (UpdateBotInlineSend.msg_id is None, "
                "which happens when the result is sent from the account that "
                "answered the query). Delete and resend the message instead."
            )

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
        rich_buttons=None,
        rich_message: Any = None,
        markdown: str | None = None,
        text: str = "",
        fallback: bool = False,
        fallback_text: str | None = None,
        fallback_parse_mode: Any = None,
        link_preview: bool = False,
        rtl: bool | None = None,
        noautolink: bool | None = None,
        files: Any = None,
        **kwargs: Any,
    ) -> InlineMessage:
        """Edit this inline message using Telegram rich_message formatting.

        By default rich edit errors are propagated so debugging shows the real
        Telegram error. Pass ``fallback=True`` to fall back to regular
        ``edit()`` when Telegram rejects rich messages for the current peer.
        """
        if rich_buttons is not None:
            if not isinstance(html, str):
                raise TypeError("html must be a string when rich_buttons are used")
            if markdown is not None or rich_message is not None:
                raise ValueError(
                    "rich_buttons require HTML, not markdown or rich_message"
                )
            from core.lib.rich_buttons import append_rich_buttons

            html = append_rich_buttons(html, rich_buttons)

        from telethon.tl.functions.messages import EditInlineBotMessageRequest

        input_rich_message = _build_input_rich_message(
            html=html,
            markdown=markdown,
            rich_message=rich_message,
            rtl=rtl,
            noautolink=noautolink,
            files=files,
        )

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

        async def fallback_edit(inline_message_id: Any = None) -> InlineMessage:
            nonlocal fallback_text, fallback_parse_mode
            if fallback_text is None:
                fallback_text, default_parse_mode = _rich_fallback(html, markdown, text)
                if fallback_parse_mode is None:
                    fallback_parse_mode = default_parse_mode

            client = _inline_client(self._kernel)
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
            client = _inline_client(self._kernel)
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

            await client(
                EditInlineBotMessageRequest(
                    id=inline_message_id,
                    message=text,
                    no_webpage=not link_preview,
                    reply_markup=_inline_buttons(client, buttons),
                    rich_message=input_rich_message,
                )
            )
            return True

        inline_message_id = self._resolve_inline_message_id()
        if inline_message_id is not None and self._kernel is not None:
            try:
                if await edit_inline_id(inline_message_id):
                    return self
            except Exception as error:
                if fallback and _rich_message_unsupported(error):
                    return await fallback_edit(inline_message_id)
                raise

        if fallback:
            return await fallback_edit()
        raise RuntimeError("No rich inline edit path available for this InlineMessage")

    async def delete(self) -> None:
        """Delete the inline message."""
        inline_message_id = self._resolve_inline_message_id()
        client = _inline_client(self._kernel)

        if inline_message_id and client is not None:
            # An inline message cannot be deleted through the chat API - the
            # only way to remove it is editing its text to empty. Prefer this
            # over _event.delete(), which would remove a different (regular)
            # message from the chat instead of the inline result.
            try:
                from telethon.tl.functions.messages import (
                    EditInlineBotMessageRequest,
                )

                await client(
                    EditInlineBotMessageRequest(
                        id=_normalize_inline_message_id(inline_message_id),
                        message="",
                    )
                )
                return
            except Exception:
                pass

        try:
            await self._event.delete()
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

        async def _noop_answer(text: str = "", alert: bool = False) -> None:
            """Form-only messages have no callback query to answer."""
            return None

        event = SimpleNamespace()
        event.data = b""
        event.inline_message_id = form_data.get("inline_message_id")
        event.chat_id = form_data.get("chat_id")
        event.message_id = form_data.get("message_id")
        event.sender_id = form_data.get("sender_id")
        event.unit_id = unit_id
        event.text = form_data.get("text", "")
        # No event.edit/event.delete here on purpose: InlineMessage already
        # defines edit()/delete() and those class methods take precedence over
        # anything this namespace could expose via __getattr__.
        event.answer = _noop_answer
        return cls(event, unit_id=unit_id, kernel=kernel)

    @property
    def text(self) -> str:
        """Current message text (from the underlying event or form data)."""
        msg = getattr(self._event, "message", None)
        if msg is not None:
            return getattr(msg, "text", "") or getattr(msg, "message", "") or ""
        return getattr(self._event, "text", "") or ""
