import uuid
import time
from dataclasses import dataclass
from html import escape as html_escape
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from telethon import Button, events

if TYPE_CHECKING:
    from kernel import Kernel


@dataclass(slots=True)
class _Session:
    expires_at: float
    data: dict[str, Any]


class InlineManager:
    """Handles inline queries, callback handlers, and inline form creation."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel
        # Temporary storage for callback-driven UI (gallery/list and one-off views).
        # Keys are strings (uuid or namespaced keys like "gallery:<uuid>").
        self._sessions: dict[str, _Session] = {}
        self._setup_temp_callback_handler()

    def _purge_expired_sessions(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._sessions.items() if v.expires_at <= now]
        for k in expired:
            self._sessions.pop(k, None)

    def _session_put(self, key: str, data: dict[str, Any], ttl: int) -> None:
        self._purge_expired_sessions()
        self._sessions[key] = _Session(
            expires_at=time.monotonic() + max(int(ttl), 1),
            data=data,
        )

    def _session_get(self, key: str, *, pop: bool = False) -> dict[str, Any] | None:
        self._purge_expired_sessions()
        session = self._sessions.get(key)
        if not session:
            return None
        if pop:
            self._sessions.pop(key, None)
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

    @staticmethod
    def _nav_buttons(prefix: str, uid: str) -> list[list[Any]]:
        return [
            [
                Button.inline("◀", f"{prefix}_{uid}_prev".encode()),
                Button.inline("🔄", f"{prefix}_{uid}_refresh".encode()),
                Button.inline("▶", f"{prefix}_{uid}_next".encode()),
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

            # Navigation: gallery_<uuid>_<action>
            if data.startswith("gallery_"):
                parts = data.split("_", 2)
                if len(parts) < 3:
                    return
                gallery_uuid, action = parts[1], parts[2]
                session_key = inline_self._gallery_session_key(gallery_uuid)
                gallery_data = inline_self._session_get(session_key)
                if not gallery_data:
                    await event.answer("❌ Session expired", alert=True)
                    return

                rows = gallery_data.get("rows", [])
                title = inline_self._as_text(gallery_data.get("title", ""))
                current_index = int(gallery_data.get("current_index", 0) or 0)
                escape_html_flag = bool(gallery_data.get("escape_html", False))
                total = len(rows)
                if total <= 0:
                    await event.answer("❌ Empty gallery", alert=True)
                    return

                if action == "prev":
                    current_index = (current_index - 1) % total
                elif action == "next":
                    current_index = (current_index + 1) % total
                elif action == "refresh":
                    current_index = current_index % total
                else:
                    current_index = 0

                gallery_data["current_index"] = current_index
                # Preserve original TTL by updating the session in-place.
                session = inline_self._sessions.get(session_key)
                if session:
                    inline_self._sessions[session_key] = _Session(
                        expires_at=session.expires_at, data=gallery_data
                    )

                gallery_text, media, _media_type = inline_self._render_gallery(
                    title, rows, current_index, escape_html=escape_html_flag
                )
                nav_buttons = inline_self._nav_buttons("gallery", gallery_uuid)
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
                return

            # Navigation: list_<uuid>_<action>
            if data.startswith("list_"):
                parts = data.split("_", 2)
                if len(parts) < 3:
                    return
                list_uuid, action = parts[1], parts[2]
                session_key = inline_self._list_session_key(list_uuid)
                list_data = inline_self._session_get(session_key)
                if not list_data:
                    await event.answer("❌ Session expired", alert=True)
                    return

                items = list_data.get("items", [])
                title = inline_self._as_text(list_data.get("title", ""))
                page = int(list_data.get("page", 0) or 0)
                per_page = int(list_data.get("per_page", 5) or 5)
                escape_html_flag = bool(list_data.get("escape_html", False))

                total_pages = (len(items) + per_page - 1) // per_page
                total_pages = max(total_pages, 1)

                if action == "prev":
                    page = (page - 1) % total_pages
                elif action == "next":
                    page = (page + 1) % total_pages
                elif action == "refresh":
                    page = page % total_pages
                else:
                    page = 0

                list_text, page, _tp = inline_self._render_list(
                    title, items, page, per_page, escape_html=escape_html_flag
                )
                list_data["page"] = page
                session = inline_self._sessions.get(session_key)
                if session:
                    inline_self._sessions[session_key] = _Session(
                        expires_at=session.expires_at, data=list_data
                    )

                nav_buttons = inline_self._nav_buttons("list", list_uuid)
                try:
                    await event.edit(list_text, buttons=nav_buttons, parse_mode="html")
                    await event.answer()
                except Exception as e:
                    k.logger.error(f"list nav error: {e}")
                    await event.answer(f"❌ Error: {e}", alert=True)
                return

        try:
            self.register_callback_handler("temp_callback_", temp_callback_handler)
            self.register_callback_handler("gallery_", temp_callback_handler)
            self.register_callback_handler("list_", temp_callback_handler)
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
        k.inline_handlers[pattern] = handler
        if k.current_loading_module:
            k.inline_handlers_owners[pattern] = k.current_loading_module

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
        try:
            # Telethon: `data=` is exact bytes match; `pattern=` uses `re.match` against bytes.
            # Most callbacks here are prefix-based ("gallery_<id>_next"), so use `pattern=`.
            pattern_bytes = pattern.encode() if isinstance(pattern, str) else pattern
            k.callback_handlers[pattern_bytes] = handler

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
        from telethon.tl.tlobject import TLObject
        from telethon.tl.custom.button import Button as TelethonButton

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
                if t == "callback":
                    return Button.inline(text, self._as_bytes(spec.get("data", b"")))
                if t == "url":
                    url = self._as_text(spec.get("url", spec.get("data", "")))
                    return Button.url(text, url)
                if t == "switch":
                    return Button.switch_inline(
                        text,
                        self._as_text(spec.get("query", "")),
                        self._as_text(spec.get("hint", "")),
                    )
                return Button.inline(text, self._as_bytes(spec.get("data", b"")))

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
            if not bot_username:
                bot_username = k.config.get("inline_bot_username")
                if not bot_username:
                    raise ValueError("No inline bot configured")

            results = await k.client.inline_query(bot_username, query)
            if not results:
                return False, None

            if result_index >= len(results):
                result_index = 0

            click_kwargs = {}
            if buttons:
                rows = self._format_telethon_buttons(buttons)
                if rows:
                    click_kwargs["buttons"] = rows
            if silent:
                click_kwargs["silent"] = silent
            if reply_to:
                click_kwargs["reply_to"] = reply_to
            click_kwargs.update(kwargs)

            message = await results[result_index].click(chat_id, **click_kwargs)
            k.logger.info(f"Inline query OK: {query[:50]}...")
            return True, message

        except Exception as e:
            k.logger.error(f"Inline query error: {e}")
            await k.handle_error(e, source="inline_query_and_click")
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

        Returns:
            (success, message) when auto_send=True, else form_id str.
        """
        k = self.k
        try:
            from core_inline.handlers import InlineHandlers

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
                return await self.inline_query_and_click(
                    chat_id=chat_id, query=form_id, **kwargs
                )
            return form_id

        except Exception as e:
            k.logger.error(f"inline_form error: {e}")
            await k.handle_error(e, source="inline_form")
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
            k.logger.error(f"gallery error: {e}")
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
