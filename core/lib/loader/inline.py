# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import sys
import time
import traceback
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from html import escape as html_escape
from typing import TYPE_CHECKING, Any

from telethon import Button, events
from telethon.errors import ChatSendInlineForbiddenError

from core_inline.api.inline import make_cb_button

if TYPE_CHECKING:
    from kernel import Kernel
    from telethon.types import Message

from core_inline.handlers import InlineHandlers


@dataclass(slots=True)
class _Session:
    expires_at: float
    data: dict[str, Any]


class InlineManager:
    """Handles inline queries, callback handlers, and inline form creation."""

    def __init__(self, kernel: Kernel) -> None:
        self.k = kernel
        self.k.logger.debug("[InlineManager] __init__ start")
        # Temporary storage for callback-driven UI (gallery/list and one-off views).
        # Keys are strings (uuid or namespaced keys like "gallery:<uuid>").
        self._sessions: dict[str, _Session] = {}
        self._setup_temp_callback_handler()
        self.k.logger.debug("[InlineManager] __init__ done")

    def _purge_expired_sessions(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._sessions.items() if v.expires_at <= now]
        for k in expired:
            self._sessions.pop(k, None)

    def _session_put(self, key: str, data: dict[str, Any], ttl: int) -> None:
        self.k.logger.debug(f"[InlineManager] _session_put key={key} ttl={ttl}")
        self._purge_expired_sessions()
        self._sessions[key] = _Session(
            expires_at=time.monotonic() + max(int(ttl), 1),
            data=data,
        )
        self.k.logger.debug(f"[InlineManager] _session_put done key={key}")

    def _session_get(self, key: str, *, pop: bool = False) -> dict[str, Any] | None:
        self.k.logger.debug(f"[InlineManager] _session_get key={key} pop={pop}")
        self._purge_expired_sessions()
        session = self._sessions.get(key)
        if not session:
            self.k.logger.debug(f"[InlineManager] _session_get miss key={key}")
            return None
        if pop:
            self._sessions.pop(key, None)
            self.k.logger.debug(f"[InlineManager] _session_get pop key={key}")
        return session.data

    @staticmethod
    def _as_bytes(data: Any) -> bytes:
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8", errors="strict")
        return str(data).encode("utf-8", errors="replace")

    @staticmethod
    def _as_text(data: Any) -> str:
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)

    @staticmethod
    def _gallery_session_key(gallery_uuid: str) -> str:
        return f"gallery:{gallery_uuid}"

    @staticmethod
    def _list_session_key(list_uuid: str) -> str:
        return f"list:{list_uuid}"

    def _nav_buttons(self, kind: str, uid: str, *, ttl: int = 900) -> list[list[Any]]:
        handler: Callable | None = None
        match kind:
            case "gallery":
                handler = self._gallery_nav_cb
            case "list":
                handler = self._list_nav_cb
        if handler is None:
            return []

        return [
            [
                make_cb_button(self.k, "◀", handler, args=[uid, "prev"], ttl=ttl),
                make_cb_button(self.k, "🔄", handler, args=[uid, "refresh"], ttl=ttl),
                make_cb_button(self.k, "▶", handler, args=[uid, "next"], ttl=ttl),
            ]
        ]

    def _render_gallery(
        self,
        title: str,
        rows: Sequence[Mapping[str, Any]],
        index: int,
        *,
        escape_html: bool = False,
    ) -> tuple[str, Any, str]:
        total = len(rows)
        if total <= 0:
            return "❌ Empty gallery", None, "photo"

        index = max(0, min(int(index), total - 1))
        row = rows[index]
        media = row.get("photo") or row.get("gif") or row.get("video")
        media_type = "photo"
        if row.get("gif"):
            media_type = "gif"
        elif row.get("video"):
            media_type = "document"

        item_title = self._as_text(row.get("title", f"Item {index + 1}"))
        item_text = self._as_text(row.get("text", ""))
        header = self._as_text(title)
        if escape_html:
            item_title = html_escape(item_title)
            item_text = html_escape(item_text)
            header = html_escape(header)

        parts: list[str] = [
            f"<blockquote>📷 {header}</blockquote>",
            f"<blockquote>📌 {item_title}{'</blockquote>' if not item_text else ''}",
        ]
        if item_text:
            parts.append(f"<b>{item_text[:200]}</b></blockquote>")
        parts += [f"<u><b>🖼 {index + 1}/{total}</b></u>"]
        return "\n".join(parts), media, media_type

    def _render_list(
        self,
        title: str,
        items: Sequence[Any],
        page: int,
        per_page: int,
        *,
        escape_html: bool = False,
    ) -> tuple[str, int, int]:
        per_page = max(int(per_page), 1)
        total_pages = (len(items) + per_page - 1) // per_page
        total_pages = max(total_pages, 1)
        page = max(0, min(int(page), total_pages - 1))

        start_idx = page * per_page
        end_idx = start_idx + per_page
        page_items = items[start_idx:end_idx]

        header = self._as_text(title)
        if escape_html:
            header = html_escape(header)
        lines = [f"<blockquote>{header}</blockquote>", "<blockquote>"]
        for i, item in enumerate(page_items, start_idx + 1):
            v = self._as_text(item)
            if escape_html:
                v = html_escape(v)
            lines.append(f"{i}. {v}")
        lines.append("</blockquote>")
        lines.append(f"<blockquote>📄 {page + 1}/{total_pages}</blockquote>")
        return "\n".join(lines), page, total_pages

    async def _gallery_nav_cb(self, event, gallery_uuid: str, action: str):
        k = self.k
        session_key = self._gallery_session_key(gallery_uuid)
        gallery_data = self._session_get(session_key)
        if not gallery_data:
            await event.answer("❌ Session expired", alert=True)
            return

        rows = gallery_data.get("rows", [])
        title = self._as_text(gallery_data.get("title", ""))
        current_index = int(gallery_data.get("current_index", 0) or 0)
        escape_html_flag = bool(gallery_data.get("escape_html", False))
        total = len(rows)
        if total <= 0:
            await event.answer("❌ Empty gallery", alert=True)
            return

        match action:
            case "prev":
                current_index = (current_index - 1) % total
            case "next":
                current_index = (current_index + 1) % total
            case "refresh":
                current_index = current_index % total
            case _:
                current_index = 0

        gallery_data["current_index"] = current_index
        session = self._sessions.get(session_key)
        if session:
            self._sessions[session_key] = _Session(
                expires_at=session.expires_at, data=gallery_data
            )

        gallery_text, media, _media_type = self._render_gallery(
            title, rows, current_index, escape_html=escape_html_flag
        )
        nav_buttons = self._nav_buttons("gallery", gallery_uuid)
        try:
            await event.edit(
                gallery_text,
                file=media,
                buttons=nav_buttons,
                parse_mode="html",
            )
            await event.answer()
        except Exception as e:
            k.logger.error(f"gallery nav error: {e}")
            await event.answer(f"❌ Error: {e}", alert=True)

    async def _list_nav_cb(self, event, list_uuid: str, action: str):
        k = self.k
        session_key = self._list_session_key(list_uuid)
        list_data = self._session_get(session_key)
        if not list_data:
            await event.answer("❌ Session expired", alert=True)
            return

        items = list_data.get("items", [])
        title = self._as_text(list_data.get("title", ""))
        page = int(list_data.get("page", 0) or 0)
        per_page = int(list_data.get("per_page", 5) or 5)
        escape_html_flag = bool(list_data.get("escape_html", False))

        total_pages = (len(items) + per_page - 1) // per_page
        total_pages = max(total_pages, 1)

        match action:
            case "prev":
                page = (page - 1) % total_pages
            case "next":
                page = (page + 1) % total_pages
            case "refresh":
                page = page % total_pages
            case _:
                page = 0

        list_text, page, _tp = self._render_list(
            title, items, page, per_page, escape_html=escape_html_flag
        )
        list_data["page"] = page
        session = self._sessions.get(session_key)
        if session:
            self._sessions[session_key] = _Session(
                expires_at=session.expires_at, data=list_data
            )

        nav_buttons = self._nav_buttons("list", list_uuid)
        try:
            await event.edit(list_text, buttons=nav_buttons, parse_mode="html")
            await event.answer()
        except Exception as e:
            k.logger.error(f"list nav error: {e}")
            await event.answer(f"❌ Error: {e}", alert=True)

    def _setup_temp_callback_handler(self) -> None:
        """Setup temporary callback handler for gallery/list items."""
        k = self.k
        inline_self = self

        async def temp_callback_handler(event) -> None:
            data_bytes = inline_self._as_bytes(getattr(event, "data", None))
            if not data_bytes:
                return

            data = inline_self._as_text(data_bytes)

            # One-off views: temp_callback_<uuid>
            if data.startswith("temp_callback_"):
                uuid_key = data[len("temp_callback_") :]
                item_data = inline_self._session_get(uuid_key, pop=True)
                if not item_data:
                    await event.answer("❌ Session expired", alert=True)
                    return

                item_type = item_data.get("type", "gallery")
                try:
                    escape_html_flag = bool(item_data.get("escape_html", False))
                    if item_type == "list":
                        title = inline_self._as_text(item_data.get("title", "List"))
                        items = item_data.get("items", [])
                        buttons = item_data.get("buttons")

                        list_title = html_escape(title) if escape_html_flag else title
                        list_text = f"{list_title}\n"
                        for i, item in enumerate(items, 1):
                            v = inline_self._as_text(item)
                            if escape_html_flag:
                                v = html_escape(v)
                            list_text += f"{i}. {v}\n"
                        await event.edit(list_text, buttons=buttons, parse_mode="html")
                        await event.answer()
                        return

                    media = item_data.get("media")
                    text = inline_self._as_text(item_data.get("text", ""))
                    buttons = item_data.get("buttons")
                    title = inline_self._as_text(item_data.get("title", ""))

                    full_text = html_escape(title) if escape_html_flag else title
                    if text:
                        full_text += (
                            f"\n{html_escape(text) if escape_html_flag else text}"
                        )

                    await event.edit(
                        full_text, file=media, buttons=buttons, parse_mode="html"
                    )
                    await event.answer()
                except Exception as e:
                    k.logger.error(f"temp_callback error: {e}")
                    await event.answer(f"❌ Error: {e}", alert=True)
                return

        try:
            self.register_callback_handler("temp_callback_", temp_callback_handler)
        except Exception as e:
            # Inline UI is optional; don't crash loader init.
            k.logger.error(f"Failed to register inline callback handlers: {e}")

    def register_inline_handler(self, pattern: str, handler) -> None:
        """Register an inline query handler for the given pattern.

        Args:
            pattern: Inline query pattern string.
            handler: Async callable to handle matching queries.
        """
        k = self.k
        k.logger.debug(
            f"[InlineManager] register_inline_handler pattern={pattern} module={k.current_loading_module}"
        )
        k.inline_handlers[pattern] = handler
        if k.current_loading_module:
            k.inline_handlers_owners[pattern] = k.current_loading_module
        k.logger.debug(
            f"[InlineManager] register_inline_handler done total_handlers={len(k.inline_handlers)}"
        )

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        """Remove all inline handlers registered by *module_name*.

        Args:
            module_name: Module whose handlers should be removed.
        """
        k = self.k
        to_remove = [
            p for p, owner in k.inline_handlers_owners.items() if owner == module_name
        ]
        for pattern in to_remove:
            k.inline_handlers.pop(pattern, None)
            k.inline_handlers_owners.pop(pattern, None)
            k.logger.debug(f"Removed inline handler: {pattern}")

    def register_callback_handler(self, pattern, handler) -> None:
        """Register a Telethon CallbackQuery handler for *pattern*.

        Attaches the handler to the client immediately if already connected.

        Args:
            pattern: Bytes or str pattern for callback data.
            handler: Async callable.
        """
        k = self.k
        k.logger.debug(f"[InlineManager] register_callback_handler pattern={pattern}")
        try:
            # Telethon: `data=` is exact bytes match; `pattern=` uses `re.match` against bytes.
            # Most callbacks here are prefix-based ("gallery_<id>_next"), so use `pattern=`.
            pattern_bytes = pattern.encode() if isinstance(pattern, str) else pattern
            k.callback_handlers[pattern_bytes] = handler
            k.logger.debug(
                f"[InlineManager] register_callback_handler added total={len(k.callback_handlers)}"
            )

            if k.client:

                @k.client.on(events.CallbackQuery(pattern=pattern_bytes))
                async def _wrapper(event):
                    try:
                        await handler(event)
                    except Exception as e:
                        await k.handle_error(e, source="callback_handler", event=event)

        except Exception as e:
            k.logger.error(f"Callback registration error: {e}")

    def _format_telethon_buttons(self, buttons: Any) -> list[list[Any]]:
        from telethon.tl.custom.button import Button as TelethonButton
        from telethon.tl.tlobject import TLObject

        if not buttons:
            return []

        def is_button_obj(x: Any) -> bool:
            return isinstance(x, (TLObject, TelethonButton))

        def to_button(spec: Any) -> Any:
            if is_button_obj(spec):
                return spec

            if isinstance(spec, Mapping):
                t = str(spec.get("type", "callback")).lower()
                text = self._as_text(spec.get("text", "Button"))
                icon = spec.get("icon")
                style = spec.get("style")
                if t == "callback":
                    return Button.inline(
                        text,
                        self._as_bytes(spec.get("data", b"")),
                        icon=icon,
                        style=style,
                    )
                if t == "url":
                    url = self._as_text(spec.get("url", spec.get("data", "")))
                    return Button.url(text, url, icon=icon, style=style)
                if t == "switch":
                    return Button.switch_inline(
                        text,
                        self._as_text(spec.get("query", "")),
                        self._as_text(spec.get("hint", "")),
                        icon=icon,
                        style=style,
                    )
                return Button.inline(
                    text, self._as_bytes(spec.get("data", b"")), icon=icon, style=style
                )

            if isinstance(spec, (list, tuple)) and len(spec) >= 2:
                text = self._as_text(spec[0])
                t = self._as_text(spec[1]).lower()
                if t == "callback":
                    data = spec[2] if len(spec) >= 3 else b""
                    return Button.inline(text, self._as_bytes(data))
                if t == "url":
                    url = spec[2] if len(spec) >= 3 else ""
                    return Button.url(text, self._as_text(url))
                if t == "switch":
                    query = spec[2] if len(spec) >= 3 else ""
                    hint = spec[3] if len(spec) >= 4 else ""
                    return Button.switch_inline(
                        text, self._as_text(query), self._as_text(hint)
                    )
                data = spec[2] if len(spec) >= 3 else b""
                return Button.inline(text, self._as_bytes(data))

            return Button.inline(self._as_text(spec), b"")

        rows: list[list[Any]] = []

        # Accept both [btn, btn] and [[btn, btn], [btn]] forms.
        if (
            isinstance(buttons, (list, tuple))
            and buttons
            and isinstance(buttons[0], (list, tuple))
        ):
            for row in buttons:
                rows.append([to_button(x) for x in row])
            return rows

        for btn in buttons:
            rows.append([to_button(btn)])
        return rows

    async def inline_query_and_click(
        self,
        chat_id: int,
        query: str,
        bot_username: str | None = None,
        result_index: int = 0,
        buttons: list | None = None,
        silent: bool = False,
        reply_to: int | None = None,
        form_sms: Message | None = None,
        **kwargs,
    ):
        """Perform an inline query and automatically click the specified result.

        Args:
            chat_id: Target chat ID.
            query: Inline query text.
            bot_username: Bot to query (defaults to config ``inline_bot_username``).
            result_index: Which result to click (0-based).
            buttons: Optional list of buttons to attach.
            silent: Send the resulting message silently.
            reply_to: Reply-to message ID.

        Returns:
            (success: bool, message | None)
        """
        k = self.k
        try:
            k.logger.debug(
                "[inline] inline_query_and_click start chat_id=%s query=%s bot=%s",
                chat_id,
                query,
                bot_username,
            )
            if not bot_username:
                bot_username = k.config.get("inline_bot_username")

            if (
                not bot_username
                and getattr(k, "is_bot_available", None)
                and k.is_bot_available()
            ):
                try:
                    bot_info = await k.bot_client.get_me()
                    if bot_info and getattr(bot_info, "username", None):
                        bot_username = bot_info.username
                        k.config["inline_bot_username"] = bot_username

                except Exception:
                    bot_username = None

            if not bot_username:
                k.logger.debug("[inline] inline_query_and_click abort: no bot username")
                raise ValueError("No inline bot configured")

            results = await k.client.inline_query(bot_username, query)
            k.logger.debug(
                "[inline] inline_query results=%d bot=%s",
                len(results) if results else 0,
                bot_username,
            )
            if not results:
                return False, None

            if result_index >= len(results):
                result_index = 0
                k.logger.debug("[inline] result_index reset to 0")

            click_kwargs = {}
            if silent:
                click_kwargs["silent"] = silent
            if reply_to:
                click_kwargs["reply_to"] = reply_to
            click_kwargs.update(kwargs)
            message = await results[result_index].click(chat_id, **click_kwargs)
            if form_sms:
                await form_sms.delete()

            if message:
                inline_msg_id = getattr(message, "inline_message_id", None)
                if inline_msg_id:
                    form_data = handlers.get_inline_form(form_id)
                    if form_data:
                        if (
                            hasattr(inline_msg_id, "dc_id")
                            and hasattr(inline_msg_id, "id")
                            and hasattr(inline_msg_id, "access_hash")
                        ):
                            form_data["inline_message_id"] = (
                                f"{inline_msg_id.dc_id}:{inline_msg_id.id}:{inline_msg_id.access_hash}"
                            )
                        else:
                            form_data["inline_message_id"] = str(inline_msg_id)
                        handlers.create_inline_form(
                            text=form_data.get("text", ""),
                            buttons=form_data.get("buttons"),
                            ttl=ttl,
                            media=form_data.get("media"),
                            media_type=form_data.get("media_type", "photo"),
                        )

            k.logger.debug(
                "[inline] clicked index=%d chat_id=%s silent=%s reply_to=%s",
                result_index,
                chat_id,
                silent,
                reply_to,
            )
            message.form_id = query
            return True, message

        except ChatSendInlineForbiddenError:
            _warning_strings = {
                "ru": "Инлайн-формы запрещены в этом чате.",
                "en": "Inline forms are not allowed in this chat.",
            }
            lang = getattr(k, "config", {}).get("language", "en")
            warning = _warning_strings.get(lang, _warning_strings["en"])
            if form_sms:
                await form_sms.edit(
                    f'<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji> <b>{warning}</b>',
                    parse_mode="html",
                )
            return False, None

        except Exception as e:
            await k.handle_error(e, source="inline_query_and_click")
            raw_tb = "".join(traceback.format_exception(*sys.exc_info())).replace(
                "Traceback (most recent call last):\n", ""
            )
            if form_sms:
                await form_sms.edit(
                    f'<tg-emoji emoji-id="5465665476971471368">❌</tg-emoji> <i><b>Open the inline form, failed!</b></i>\n<pre>{raw_tb}</pre>',
                    parse_mode="html",
                )
            return False, None

    async def inline_form(
        self,
        chat_id: int,
        title: str,
        fields=None,
        buttons=None,
        auto_send: bool = True,
        ttl: int = 200,
        media: str | None = None,
        media_type: str = "photo",
        reply_to: int | None = None,
        parse_mode: str = "html",
        **kwargs,
    ):
        """Create and optionally send an inline form.

        Args:
            chat_id: Target chat.
            title: Form title / first line.
            fields: Dict or list of field values appended below the title.
            buttons: Buttons in any supported format.
            auto_send: If True, send immediately and return (success, message).
                       If False, return the form_id string.
            ttl: Cache TTL for the form (seconds).
            media: Public URL or file_id of a photo/document/gif to attach.
            media_type: One of "photo", "document", "gif" (default "photo").
            reply_to: Topic/thread message ID for supergroups with topics.
            parse_mode: Parse mode for the form message (default "html").

        Returns:
            (success, message) when auto_send=True, else form_id str.
        """
        k = self.k
        form_sms = None
        try:
            lines = [title]
            if isinstance(fields, dict):
                lines += [f"{fk}: {fv}" for fk, fv in fields.items()]
            elif isinstance(fields, list):
                lines += [f"Field {i}: {v}" for i, v in enumerate(fields, 1)]

            handlers = InlineHandlers(k, k.bot_client)
            form_id = handlers.create_inline_form(
                "\n".join(lines),
                buttons,
                ttl,
                media=media,
                media_type=media_type,
            )

            if auto_send:
                try:
                    send_kwargs = {"parse_mode": parse_mode}
                    if reply_to is not None:
                        send_kwargs["reply_to"] = reply_to
                    form_sms = await k.client.send_message(
                        chat_id,
                        '<tg-emoji emoji-id="5204110240752110921">🕳️</tg-emoji> <i><b>Open inline form</b></i>',
                        **send_kwargs,
                    )
                except Exception:
                    form_sms = None
                return await self.inline_query_and_click(
                    chat_id=chat_id,
                    query=form_id,
                    form_sms=form_sms,
                    reply_to=reply_to,
                    **kwargs,
                )
            return form_id

        except Exception as e:
            await k.handle_error(e, source="inline_form")
            raw_tb = "".join(traceback.format_exception(*sys.exc_info())).replace(
                "Traceback (most recent call last):\n", ""
            )
            if auto_send:
                if form_sms:
                    await form_sms.edit(
                        f'<tg-emoji emoji-id="5465665476971471368">❌</tg-emoji> <i><b>Open the inline form, failed!</b></i>\n<pre>{raw_tb}</pre>',
                        parse_mode="html",
                    )
            return (False, None) if auto_send else None

    async def gallery(
        self,
        chat_id: int,
        title: str,
        rows: list,
        ttl: int = 200,
        escape_html: bool = False,
        **kwargs,
    ):
        """Send an inline gallery with navigation.

        Creates a single gallery view with [<] [>] navigation buttons.
        Navigation data stored in cache with uuid.

        Args:
            chat_id: Target chat.
            title: Gallery header text.
            rows: List of items, each item is a dict with:
                - photo/gif/video: media URL
                - text: item description
                - title: item title
            ttl: Cache TTL for navigation data (seconds).

        Returns:
            (success, message) tuple.
        """
        k = self.k
        rows = rows[:10]

        if not rows:
            return False, None

        try:
            gallery_uuid = str(uuid.uuid4())[:8]
            session_key = self._gallery_session_key(gallery_uuid)
            self._session_put(
                session_key,
                {
                    "title": title,
                    "rows": rows,
                    "current_index": 0,
                    "escape_html": bool(escape_html),
                },
                ttl=ttl,
            )

            gallery_text, media, media_type = self._render_gallery(
                title, rows, 0, escape_html=bool(escape_html)
            )
            nav_buttons = self._nav_buttons("gallery", gallery_uuid)

            return await self.inline_form(
                chat_id=chat_id,
                title=gallery_text,
                fields=None,
                buttons=nav_buttons,
                auto_send=True,
                ttl=ttl,
                media=media,
                media_type=media_type,
                **kwargs,
            )

        except Exception as e:
            await k.handle_error(e, source="gallery")
            return (False, None)

    async def list(
        self,
        chat_id: int,
        title: str,
        items: list,
        ttl: int = 200,
        escape_html: bool = False,
        **kwargs,
    ):
        """Send an inline list with pagination.

        Creates a list view with [<] [>] navigation buttons.

        Args:
            chat_id: Target chat.
            title: List header.
            items: List of strings to display.
            ttl: Cache TTL.

        Returns:
            (success, message) tuple.
        """
        k = self.k

        if not items:
            return False, None

        try:
            list_uuid = str(uuid.uuid4())[:8]
            per_page = 5
            session_key = self._list_session_key(list_uuid)
            self._session_put(
                session_key,
                {
                    "title": title,
                    "items": items,
                    "per_page": per_page,
                    "page": 0,
                    "escape_html": bool(escape_html),
                },
                ttl=ttl,
            )

            list_text, _page, _tp = self._render_list(
                title, items, page=0, per_page=per_page, escape_html=bool(escape_html)
            )
            nav_buttons = self._nav_buttons("list", list_uuid)

            return await self.inline_form(
                chat_id=chat_id,
                title=list_text,
                fields=None,
                buttons=nav_buttons,
                auto_send=True,
                ttl=ttl,
                **kwargs,
            )
        except Exception as e:
            k.logger.error(f"list error: {e}")
            await k.handle_error(e, source="list")
            return (False, None)

    def get_module_inline_commands(self, module_name: str) -> list:
        """Get inline commands registered by a module.

        Args:
            module_name: Name of the module.

        Returns:
            List of (command, description) tuples.
        """
        k = self.k
        commands = []

        for cmd, owner in k.inline_handlers_owners.items():
            if owner == module_name:
                handler = k.inline_handlers.get(cmd)
                doc = getattr(handler, "__doc__", None)
                commands.append((cmd, doc if doc else None))

        return commands


class InlineMessage:
    """Inline message wrapper for easy editing and deleting.

    Provides a clean API to manage inline messages without needing to store
    inline_message_id manually.

    Example:
        ```python
        # Create inline form
        success, msg = await kernel.inline_form(chat_id, "Hello!")

        # Later edit it
        msg.edit("New text!")

        # Or delete it
        msg.delete()

        # Or get existing message by form_id
        msg = InlineMessage.get(form_id, kernel)
        await msg.edit("Updated!")
        ```
    """

    def __init__(
        self,
        unit_id: str,
        kernel: Kernel,
    ) -> None:
        """Initialize InlineMessage.

        Args:
            unit_id: The form ID of the inline message (returned by inline_form).
            kernel: The kernel instance.
        """
        self.unit_id = unit_id
        self._kernel = kernel
        self._form_data: dict | None = None

    @classmethod
    def get(cls, unit_id: str, kernel: Kernel) -> InlineMessage | None:
        """Get an InlineMessage by unit/form ID or message ID.

        Args:
            unit_id: The form ID or message ID to look up.
            kernel: The kernel instance.

        Returns:
            InlineMessage instance if found, None otherwise.
        """
        msg = cls(unit_id, kernel)
        if msg._load_form_data():
            return msg
        return None

    def _load_form_data(self) -> bool:
        """Load form data from cache."""
        from core_inline.handlers import InlineHandlers

        handlers = InlineHandlers(self._kernel, self._kernel.bot_client)

        form_data = handlers.get_inline_form(self.unit_id)
        if form_data:
            self._form_data = form_data
            return True

        form_id = f"msg_{self.unit_id}"
        form_data = handlers.get_inline_form(form_id)
        if form_data:
            self._form_data = form_data
            return True

        return False

    @property
    def text(self) -> str:
        """Get current message text."""
        if self._form_data:
            return self._form_data.get("text", "")
        return ""

    @property
    def buttons(self) -> list | None:
        """Get current message buttons."""
        if self._form_data:
            return self._form_data.get("buttons")
        return None

    async def edit(
        self,
        text: str | None = None,
        buttons: list | None = None,
        **kwargs,
    ) -> InlineMessage:
        """Edit the inline message.

        Args:
            text: New message text (optional).
            buttons: New buttons (optional).
            **kwargs: Additional arguments passed to edit_message.

        Returns:
            Self for chaining.

        Example:
            ```python
            msg = InlineMessage.get(form_id, kernel)
            await msg.edit("New text", buttons=[[Button.callback("Click", "data")]])
            ```
        """
        from telethon.tl.functions.messages import EditInlineBotMessageRequest
        from telethon.tl.types import InputBotInlineMessageID

        from core_inline.handlers import InlineHandlers

        handlers = InlineHandlers(self._kernel, self._kernel.bot_client)
        form_data = handlers.get_inline_form(self.unit_id)
        if not form_data:
            alt_id = f"msg_{self.unit_id}"
            form_data = handlers.get_inline_form(alt_id)
        if not form_data:
            return self

        update_data = dict(form_data)
        if text is not None:
            update_data["text"] = text
        if buttons is not None:
            update_data["buttons"] = self._normalize_buttons(buttons)

        cache = getattr(self._kernel, "cache", None)
        if cache:
            cache.set(self.unit_id, update_data, ttl=3600)

        bot_client = getattr(self._kernel, "bot_client", None)
        user_client = getattr(self._kernel, "client", None)
        client = bot_client or user_client
        if client is None:
            return self

        inline_msg_id = form_data.get("inline_message_id")
        if inline_msg_id:
            try:
                msg_id = None
                if isinstance(inline_msg_id, InputBotInlineMessageID):
                    msg_id = inline_msg_id
                elif isinstance(inline_msg_id, str):
                    if ":" in inline_msg_id:
                        parts = inline_msg_id.split(":")
                        if len(parts) == 3:
                            msg_id = InputBotInlineMessageID(
                                dc_id=int(parts[0]),
                                id=int(parts[1]),
                                access_hash=int(parts[2]),
                            )
                        elif len(parts) == 2:
                            msg_id = InputBotInlineMessageID(
                                dc_id=0,
                                id=int(parts[0]),
                                access_hash=int(parts[1]),
                            )

                if msg_id and bot_client:
                    reply_markup = None
                    if buttons:
                        reply_markup = bot_client.build_reply_markup(
                            self._to_telethon_buttons(buttons)
                        )
                    await bot_client(
                        EditInlineBotMessageRequest(
                            id=msg_id,
                            message=text or form_data.get("text", ""),
                            reply_markup=reply_markup,
                            parse_mode="html",
                        )
                    )
            except Exception as e:
                self._kernel.logger.debug(f"InlineMessage.edit inline error: {e}")

        message = form_data.get("message")
        chat = form_data.get("chat")
        if message is not None and chat is not None and hasattr(client, "edit_message"):
            edit_kwargs = {"parse_mode": "html"}
            if buttons:
                edit_kwargs["buttons"] = self._to_telethon_buttons(buttons)
            edit_kwargs.update(kwargs)
            try:
                await client.edit_message(
                    chat,
                    message,
                    text or form_data.get("text", ""),
                    **edit_kwargs,
                )
            except Exception as e:
                self._kernel.logger.debug(f"InlineMessage.edit message error: {e}")

        self._form_data = update_data
        return self

    async def delete(self) -> bool:
        """Delete the inline message.

        Returns:
            True if deleted successfully, False otherwise.

        Example:
            ```python
            msg = InlineMessage.get(form_id, kernel)
            await msg.delete()
            ```
        """
        from telethon.tl.functions.messages import DeleteBotCallbackMessage

        from core_inline.handlers import InlineHandlers

        bot_client = getattr(self._kernel, "bot_client", None)
        user_client = getattr(self._kernel, "client", None)
        client = bot_client or user_client
        if client is None:
            return False

        handlers = InlineHandlers(self._kernel, bot_client)
        form_data = handlers.get_inline_form(self.unit_id)
        if not form_data:
            alt_id = f"msg_{self.unit_id}"
            form_data = handlers.get_inline_form(alt_id)
        if not form_data:
            return False

        inline_msg_id = form_data.get("inline_message_id")
        if inline_msg_id and bot_client:
            try:
                await bot_client(DeleteBotCallbackMessage(inline_msg_id))
            except Exception as e:
                self._kernel.logger.debug(f"InlineMessage.delete inline error: {e}")

        message = form_data.get("message")
        chat = form_data.get("chat")
        if (
            message is not None
            and chat is not None
            and hasattr(client, "delete_messages")
        ):
            try:
                await client.delete_messages(chat, message)
            except Exception as e:
                self._kernel.logger.debug(f"InlineMessage.delete message error: {e}")

        cache = getattr(self._kernel, "cache", None)
        if cache:
            cache.delete(self.unit_id)
            cache.delete(f"msg_{self.unit_id}")

        return True

    async def unload(self) -> bool:
        """Unload the inline unit (remove from cache).

        Returns:
            True if unloaded successfully.

        Example:
            ```python
            msg = InlineMessage.get(form_id, kernel)
            await msg.unload()
            ```
        """
        cache = getattr(self._kernel, "cache", None)
        if cache:
            cache.delete(self.unit_id)
            cache.delete(f"msg_{self.unit_id}")
        return True

    def _normalize_buttons(self, buttons: list) -> list:
        """Normalize buttons to internal format."""
        if not buttons:
            return []

        normalized = []
        for row in buttons:
            if isinstance(row, list):
                normalized.append(row)
            elif isinstance(row, dict):
                normalized.append([row])
            else:
                normalized.append([row])
        return normalized

    def _to_telethon_buttons(self, buttons) -> list | None:
        """Convert buttons to Telethon format."""
        if not buttons:
            return None

        from telethon import Button

        prepared = []
        for row in buttons:
            out_row = []
            for btn in row:
                if isinstance(btn, Button):
                    out_row.append(btn)
                elif isinstance(btn, dict):
                    btn_text = btn.get("text", "")
                    btn_data = btn.get("data", b"").encode() if btn.get("data") else b""
                    out_row.append(Button.callback(btn_text, btn_data))
                elif isinstance(btn, (tuple, list)) and len(btn) >= 2:
                    btn_text, btn_data = btn[0], btn[1]
                    if isinstance(btn_data, str):
                        btn_data = btn_data.encode()
                    out_row.append(Button.callback(btn_text, btn_data))
            if out_row:
                prepared.append(out_row)
        return prepared if prepared else None
