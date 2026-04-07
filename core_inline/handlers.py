from __future__ import annotations

import asyncio
import html
import json
import time
import traceback
import uuid
import inspect
from typing import Any

import aiohttp
from telethon import Button, events
from telethon.tl.types import (
    InputWebDocument,
    KeyboardButtonCallback,
    KeyboardButtonUrl,
)

from .lib import InlineManager
from .strings import get_strings
from .api import (
    build_inline_result_text,
    build_inline_result_media,
    add_inline_keyboard_to_result,
    build_inline_keyboard,
    build_button_callback,
    build_button_url,
    build_button_switch,
    build_button_phone,
    build_button_location,
    build_button_game,
    build_input_message_content,
)


class InlineHandlers:
    EMOJI_TELESCOPE = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
    EMOJI_BLOCK = '<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji>'
    EMOJI_CRYSTAL = '<tg-emoji emoji-id="5361837567463399422">🔮</tg-emoji>'
    EMOJI_SHIELD = '<tg-emoji emoji-id="5379679518740978720">🛡</tg-emoji>'
    EMOJI_TOT = '<tg-emoji emoji-id="5085121109574025951">🫧</tg-emoji>'

    def __init__(self, kernel: Any, bot_client: Any) -> None:
        self.kernel = kernel
        self.bot_client = bot_client
        if (
            not hasattr(self.kernel, "session")
            or self.kernel.session is None
            or self.kernel.session.closed
        ):
            self.kernel.session = aiohttp.ClientSession()

        self._form_counter = 0
        self._inline_manager = InlineManager(kernel)
        self.lang = get_strings(kernel)
        self.kernel.logger.debug("[InlineHandlers] __init__")

    async def close(self) -> None:
        """Close aiohttp session on bot shutdown."""
        if hasattr(self.kernel, "session") and self.kernel.session is not None:
            if not self.kernel.session.closed:
                await self.kernel.session.close()
            self.kernel.session = None

    def create_inline_form(
        self,
        text: str,
        buttons: list[Any] | None = None,
        ttl: int = 3600,
        media: Any = None,
        media_type: str = "photo",
    ) -> str:
        """
        Creates an inline form and returns its ID.

        Args:
            text: Message text (supports HTML)
            buttons: Buttons in format:
                - list of lists of Button objects: [[Button.callback(...), ...], ...]
                - list of dicts: [{"text": "...", "type": "callback", "data": "..."}, ...]
                - JSON string
            ttl: Form cache lifetime (seconds)
            media: URL or file_id of media file (optional)
            media_type: Media type - "photo", "document", "gif" (default "photo")

        Returns:
            str: Form ID for use in inline query
        """
        self.kernel.logger.debug(f"[InlineHandlers] create_inline_form ttl={ttl}")
        self._form_counter += 1
        form_id = self._make_form_id()

        # Keep the ttl around so we can expire ad‑hoc callbacks attached to buttons
        self._current_form_ttl = ttl
        self._cleanup_inline_callback_map()

        if isinstance(buttons, str):
            buttons = self._parse_json_buttons(buttons)
        else:
            buttons = self._normalize_buttons(buttons, ttl=ttl)

        form_data = {
            "text": text,
            "buttons": buttons,
            "created_at": time.time(),
            "media": media,
            "media_type": media_type,
        }

        self.kernel.cache.set(form_id, form_data, ttl=ttl)
        self.kernel.logger.debug(
            f"[InlineHandlers] create_inline_form done id={form_id}"
        )
        return form_id

    def get_inline_form(self, form_id):
        return self.kernel.cache.get(form_id)

    async def send_inline_form(
        self,
        chat_id: int,
        text: str,
        buttons: list | None = None,
        media: str | None = None,
        media_type: str = "photo",
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """
        Sends an inline form directly to a chat via Bot API.

        Args:
            chat_id: Chat ID to send to
            text: Message text
            buttons: Buttons (list of dicts or Button objects)
            media: Media file URL
            media_type: Media type
            parse_mode: Parse mode (HTML/Markdown)

        Returns:
            dict: Bot API response
        """
        _bot_token = self.kernel.config.get("inline_bot_token")
        if not _bot_token:
            raise ValueError("inline_bot_token not configured")

        form_id = self.create_inline_form(
            text=text,
            buttons=buttons,
            media=media,
            media_type=media_type,
        )

        result_obj = build_inline_result_text(
            title="Form", text=text, parse_mode=parse_mode
        )

        if media:
            result_obj = build_inline_result_media(
                media_url=media,
                media_type=media_type,
                text=text,
                title="Media",
                parse_mode=parse_mode,
            )

        if buttons:
            if isinstance(buttons[0], dict):
                kb_rows = []
                for btn in buttons:
                    parsed_btn = self._dict_to_button(btn)
                    if parsed_btn:
                        kb_rows.append([parsed_btn])
            else:
                kb_rows = buttons

            if kb_rows:
                result_obj = add_inline_keyboard_to_result(result_obj, kb_rows)

        async with self.kernel.session.post(
            f"https://api.telegram.org/bot{_bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": result_obj.get("reply_markup"),
            },
        ) as resp:
            return await resp.json()

    async def answer_inline_query_custom(
        self,
        inline_query_id: str,
        results: list[dict[str, Any]],
        cache_time: int = 300,
        is_personal: bool = False,
        next_offset: str | None = None,
    ) -> dict[str, Any]:
        """
        Answers an inline query via Bot API.

        Args:
            inline_query_id: Query ID
            results: List of results (dict)
            cache_time: Cache time
            is_personal: Personal result
            next_offset: Offset for next page

        Returns:
            dict: Bot API response
        """
        _bot_token = self.kernel.config.get("inline_bot_token")
        if not _bot_token:
            raise ValueError("inline_bot_token not configured")

        payload = {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
        }
        if next_offset:
            payload["next_offset"] = next_offset

        async with self.kernel.session.post(
            f"https://api.telegram.org/bot{_bot_token}/answerInlineQuery",
            json=payload,
        ) as resp:
            return await resp.json()

    def create_form_with_validation(
        self,
        text: str,
        buttons: list | None = None,
        fields: list[dict] | None = None,
        ttl: int = 3600,
        media: str | None = None,
        media_type: str = "photo",
    ) -> str:
        """
        Creates a form with field validation.

        Args:
            text: Message text
            buttons: Buttons
            fields: List of fields for validation:
                [{"name": "email", "type": "email", "required": True}, ...]
                Types: text, email, phone, number, url
            ttl: Cache lifetime
            media: Media URL
            media_type: Media type

        Returns:
            str: Form ID
        """
        form_id = self.create_inline_form(
            text=text,
            buttons=buttons,
            media=media,
            media_type=media_type,
            ttl=ttl,
        )

        if fields:
            form_data = self.get_inline_form(form_id)
            form_data["validation_fields"] = fields
            self.kernel.cache.set(form_id, form_data, ttl=ttl)

        return form_id

    def validate_form_data(self, form_id: str, data: dict) -> dict[str, Any]:
        """
        Validates form data.

        Args:
            form_id: Form ID
            data: Data to validate

        Returns:
            dict: {"valid": bool, "errors": list}
        """
        form = self.get_inline_form(form_id)
        if not form:
            return {"valid": False, "errors": ["Form not found or expired"]}

        errors = []
        fields = form.get("validation_fields", [])

        for field in fields:
            name = field.get("name")
            f_type = field.get("type", "text")
            required = field.get("required", False)

            value = data.get(name)
            if required and not value:
                errors.append(f"Field '{name}' is required")
                continue

            if value:
                if f_type == "email" and "@" not in value:
                    errors.append(f"Invalid email format for '{name}'")
                elif f_type == "phone" and not value.replace("+", "").isdigit():
                    errors.append(f"Invalid phone format for '{name}'")
                elif (
                    f_type == "number"
                    and not value.replace(".", "").replace("-", "").isdigit()
                ):
                    errors.append(f"Invalid number format for '{name}'")
                elif f_type == "url" and not value.startswith(("http://", "https://")):
                    errors.append(f"Invalid URL format for '{name}'")

        return {"valid": len(errors) == 0, "errors": errors}

    def build_buttons_dict(
        self,
        buttons: list[dict | list],
    ) -> list[list[dict]]:
        """
        Converts buttons from dict format to inline keyboard format.

        Args:
            buttons: [{"text": "...", "type": "callback", "data": "..."}, ...]

        Returns:
            list: [[{"text": ..., "callback_data": ...}, ...], ...]
        """
        result = []
        for row in buttons:
            if not isinstance(row, list):
                row = [row]
            kb_row = []
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                b_type = btn.get("type", "callback").lower()
                if b_type == "callback":
                    kb_row.append(
                        build_button_callback(
                            btn.get("text", ""),
                            btn.get("data", ""),
                            btn.get("emoji"),
                        )
                    )
                elif b_type == "url":
                    kb_row.append(
                        build_button_url(
                            btn.get("text", ""),
                            btn.get("url", ""),
                            btn.get("emoji"),
                        )
                    )
                elif b_type == "switch":
                    kb_row.append(
                        build_button_switch(
                            btn.get("text", ""),
                            btn.get("query", ""),
                            btn.get("hint", ""),
                            btn.get("emoji"),
                        )
                    )
                elif b_type == "phone":
                    kb_row.append(
                        build_button_phone(btn.get("text", ""), btn.get("emoji"))
                    )
                elif b_type == "location":
                    kb_row.append(
                        build_button_location(btn.get("text", ""), btn.get("emoji"))
                    )
                elif b_type == "game":
                    kb_row.append(
                        build_button_game(btn.get("text", ""), btn.get("emoji"))
                    )
            if kb_row:
                result.append(kb_row)
        return result

    def _make_form_id(self):
        return f"form_{int(time.time())}_{self._form_counter}"

    def _normalize_buttons(self, buttons, ttl: int | None = None):
        """Converts buttons to unified format (list of rows)."""
        # Consolidate the three redundant falsy checks into one
        if not buttons or not isinstance(buttons, list):
            return None

        # List of dicts (single-level) → each in separate row
        if isinstance(buttons[0], dict):
            parsed = [
                [btn]
                for item in buttons
                if (btn := self._dict_to_button(item, ttl=ttl)) is not None
            ]
            return parsed or None

        # List of rows
        if isinstance(buttons[0], list):
            parsed = []
            for row in buttons:
                if not isinstance(row, list):
                    continue
                parsed_row = []
                for item in row:
                    if isinstance(item, dict):
                        btn = self._dict_to_button(item, ttl=ttl)
                        if btn:
                            parsed_row.append(btn)
                    else:
                        parsed_row.append(item)
                if parsed_row:
                    parsed.append(parsed_row)
            return parsed or None

        return None

    def _dict_to_button(self, btn_dict, ttl: int | None = None):
        if not isinstance(btn_dict, dict):
            return None

        text = btn_dict.get("text", self.lang["btn_default"])
        b_type = btn_dict.get("type", "callback").lower()
        icon = btn_dict.get("icon")
        style = btn_dict.get("style")

        if b_type == "callback":
            # Support both traditional byte data and callable callbacks with
            # auto‑generated tokens (Heroku/Hikka‑style behavior).
            data = btn_dict.get("data", "")
            callback = btn_dict.get("callback")

            if callable(callback):
                token = btn_dict.get("token") or uuid.uuid4().hex
                # Store mapping globally on kernel so multiple InlineHandlers
                # instances share the same callback map.
                cb_map = getattr(self.kernel, "inline_callback_map", None)
                if cb_map is None:
                    cb_map = {}
                    setattr(self.kernel, "inline_callback_map", cb_map)

                cb_map[token] = {
                    "handler": callback,
                    "args": btn_dict.get("args", []),
                    "kwargs": btn_dict.get("kwargs", {}),
                    "expires_at": time.time() + (ttl or 3600),
                }

                data = token

            if isinstance(data, str):
                data = data.encode()
            return Button.inline(text, data, icon=icon, style=style)
        if b_type == "url":
            url = btn_dict.get("url", btn_dict.get("data", ""))
            return Button.url(text, url, icon=icon, style=style)
        if b_type == "switch":
            query = btn_dict.get("query", "")
            hint = btn_dict.get("hint", "")
            return Button.switch_inline(text, query, hint, icon=icon, style=style)
        return None

    def _parse_json_buttons(self, json_str):
        """Парсит JSON строку с описанием кнопок."""
        try:
            data = json.loads(json_str)
            markup = []

            def make_btn(btn_dict):
                text = btn_dict.get("text", self.lang["btn_default"])
                b_type = btn_dict.get("type", "callback").lower()
                if b_type == "callback":
                    return Button.inline(text, btn_dict.get("data", "").encode())
                if b_type == "url":
                    return Button.url(
                        text, btn_dict.get("url", btn_dict.get("data", ""))
                    )
                if b_type == "switch":
                    return Button.switch_inline(
                        text, btn_dict.get("query", ""), btn_dict.get("hint", "")
                    )
                return None

            if isinstance(data, list):
                for row in data:
                    if isinstance(row, list):
                        current_row = [make_btn(b) for b in row if isinstance(b, dict)]
                        markup.append([b for b in current_row if b])
                    elif isinstance(row, dict):
                        btn = make_btn(row)
                        if btn:
                            markup.append([btn])
            elif isinstance(data, dict):
                btn = make_btn(data)
                if btn:
                    markup.append([btn])
            return markup
        except Exception as e:
            # json.JSONDecodeError is a subclass of ValueError which is a
            # subclass of Exception — no need to list it separately
            self.kernel.logger.warning(f"{self.lang['json_parsing_error']}: {e}")
            return []

    def _cleanup_inline_callback_map(self) -> None:
        """Drop expired auto-generated callback tokens to keep the map small."""
        cb_map = getattr(self.kernel, "inline_callback_map", None)
        if not cb_map:
            return

        now = time.time()
        expired = [
            key
            for key, val in cb_map.items()
            if val.get("expires_at") and val["expires_at"] < now
        ]
        for key in expired:
            cb_map.pop(key, None)

    async def check_admin(self, event):
        try:
            user_id = int(event.sender_id)
            return await self._inline_manager.is_allowed(user_id)
        except (ValueError, TypeError) as e:
            self.kernel.logger.error(f"Ошибка в check_admin: {e}")
            return False

    async def register_handlers(self):
        """Registers all handlers for the bot."""

        @self.bot_client.on(events.InlineQuery)
        async def inline_query_handler(event):
            try:
                query = event.text or ""

                if not await self.check_admin(event):
                    await event.answer(
                        [
                            event.builder.article(
                                self.lang["no_access"],
                                text=(
                                    f"{self.EMOJI_BLOCK} {self.lang['no_access']}\n"
                                    f"<blockquote>{self.EMOJI_SHIELD} {self.lang['no_access_id']}: {event.sender_id}</blockquote>"
                                ),
                                parse_mode="html",
                            )
                        ]
                    )
                    return

                if not query.strip():
                    results = []
                    modules_count = len(self.kernel.loaded_modules) + len(
                        self.kernel.system_modules
                    )

                    info_text = (
                        f"{self.EMOJI_CRYSTAL} <b>{self.lang['mcub_bot_title']}</b>\n"
                        f"<blockquote>{self.EMOJI_SHIELD} {self.lang['version']}: {self.kernel.VERSION}</blockquote>\n"
                        f"<blockquote>{self.EMOJI_TOT} {self.lang['modules']}: {modules_count}</blockquote>\n"
                    )

                    thumb = InputWebDocument(
                        url="https://kappa.lol/KSKoOu",
                        size=0,
                        mime_type="image/jpeg",
                        attributes=[],
                    )

                    results.append(
                        event.builder.article(
                            "MCUB Info",
                            text=info_text,
                            description=self.lang["info_description"],
                            parse_mode="html",
                            thumb=thumb,
                        )
                    )

                    for pattern, handler in self.kernel.inline_handlers.items():
                        if len(results) >= 50:
                            break
                        docstring = getattr(handler, "__doc__", None) or "команда"
                        cmd_text = (
                            f"{self.EMOJI_TELESCOPE} <b>{self.lang['command']}:</b>"
                            f" <code>{html.escape(pattern)}</code>\n\n"
                        )
                        thumb_cmd = InputWebDocument(
                            url="https://kappa.lol/EKhGKM",
                            size=0,
                            mime_type="image/jpeg",
                            attributes=[],
                        )
                        results.append(
                            event.builder.article(
                                f"{self.lang['command']}: {pattern[:20]}",
                                text=cmd_text,
                                parse_mode="html",
                                thumb=thumb_cmd,
                                description=html.escape(docstring.strip()),
                                buttons=[
                                    [
                                        Button.switch_inline(
                                            f"🏄‍♀️ {self.lang['execute']}: {pattern}",
                                            query=pattern,
                                            same_peer=True,
                                        )
                                    ]
                                ],
                            )
                        )

                    if len(results) == 1:
                        no_cmds_text = (
                            f"{self.EMOJI_CRYSTAL} <b>{self.lang['mcub_bot_title']}</b>\n\n"
                            f"{self.EMOJI_BLOCK} <i>{self.lang['no_commands']}</i>\n\n"
                        )
                        results.append(
                            event.builder.article(
                                self.lang["no_commands"],
                                text=no_cmds_text,
                                parse_mode="html",
                            )
                        )

                    await event.answer(results)
                    return

                #  text | {keyboards}
                if "|" in query:
                    try:
                        parts = query.split("|", 1)
                        text = parts[0].strip().strip("\"'")
                        json_str = parts[1].strip() if len(parts) > 1 else ""
                        buttons = self._parse_json_buttons(json_str) if json_str else []

                        builder = event.builder.article(
                            "Message",
                            text=text,
                            buttons=buttons or None,
                            parse_mode="html",
                        )
                    except Exception as e:
                        self.kernel.logger.debug(f"Ошибка обработки JSON формы: {e}")
                        text = query.split("|")[0].strip().strip("\"'")
                        builder = event.builder.article(
                            "Message", text=text, parse_mode="html"
                        )

                    await event.answer([builder])
                    return

                query_cmd = query.lower().split()[0] if query.strip() else ""
                if await self._dispatch_inline_handler(query_cmd, query, event):
                    return

                if query.startswith("form_"):
                    form_data = self.get_inline_form(query)
                    if form_data:
                        media = form_data.get("media")
                        mtype = (form_data.get("media_type") or "photo").lower()
                        buttons = form_data.get("buttons")
                        text = form_data["text"]

                        _bot_token = self.kernel.config.get("inline_bot_token")

                        if not _bot_token:
                            builder = event.builder.article(
                                "Inline Form",
                                text=text,
                                buttons=buttons,
                                parse_mode="html",
                            )
                            await event.answer([builder])
                            return

                        if media:
                            _result_obj = build_inline_result_media(
                                media_url=media,
                                media_type=mtype,
                                text=text,
                                title="Media",
                            )
                        else:
                            _result_obj = build_inline_result_text(
                                title="Inline Form",
                                text=text,
                            )

                        if buttons:
                            _result_obj = add_inline_keyboard_to_result(
                                _result_obj, buttons
                            )

                        async with self.kernel.session.post(
                            f"https://api.telegram.org/bot{_bot_token}/answerInlineQuery",
                            json={
                                "inline_query_id": str(event.query.query_id),
                                "results": [_result_obj],
                                "cache_time": 0,
                            },
                        ) as _resp:
                            _data = await _resp.json()
                            if not _data.get("ok"):
                                self.kernel.logger.error(
                                    f"Bot API answerInlineQuery error: {_data}"
                                )
                        return
                    else:
                        await event.answer(
                            [
                                event.builder.article(
                                    self.lang["form_not_found"],
                                    text=(
                                        f"{self.EMOJI_BLOCK} <b>{self.lang['form_expired']}</b>\n"
                                        f"<i>{self.lang['form_id']}: <code>{html.escape(query)}</code></i>"
                                    ),
                                    parse_mode="html",
                                )
                            ]
                        )
                    return

                await event.answer()

            except Exception as e:
                error_traceback = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                self.kernel.logger.error(f"{self.lang['error']}: {e}")
                self.kernel.logger.error(f"Full traceback: {error_traceback}")
                thumb = InputWebDocument(
                    url="https://kappa.lol/qNFKBT",
                    size=0,
                    mime_type="image/jpeg",
                    attributes=[],
                )
                await event.answer(
                    [
                        event.builder.article(
                            "Error",
                            text=f"🃏 {self.lang['error']}:\n <pre>{html.escape(error_traceback)}</pre>",
                            description=f"{self.lang['error_description']}: {str(e)[:50]}",
                            parse_mode="html",
                            thumb=thumb,
                        )
                    ]
                )

        @self.bot_client.on(events.CallbackQuery)
        async def callback_query_handler(event):
            try:
                if not event.data:
                    return

                data_str = (
                    event.data.decode("utf-8")
                    if isinstance(event.data, bytes)
                    else str(event.data)
                )

                if not await self.check_admin(event) and (
                    not hasattr(self.kernel, "callback_permissions")
                    or not self.kernel.callback_permissions.is_allowed(
                        event.sender_id, data_str
                    )
                ):
                    return await event.answer(self.lang["no_access"], alert=False)

                # 1. Built-in service callbacks
                if data_str.startswith("show_tb:"):
                    await self._handle_show_traceback(event, data_str)
                elif data_str.startswith("find_similar:"):
                    await self._handle_find_similar(event, data_str)
                elif data_str.startswith("mute_err:"):
                    await self._handle_mute_error(event, data_str)

                # 2. Auto-generated callback tokens
                self._cleanup_inline_callback_map()
                cb_map = getattr(self.kernel, "inline_callback_map", None) or {}
                if data_str in cb_map:
                    entry = cb_map[data_str]

                    if entry.get("expires_at") and entry["expires_at"] < time.time():
                        cb_map.pop(data_str, None)
                        return await event.answer(
                            self.lang["form_expired"], alert=False
                        )

                    handler = entry.get("handler")
                    if callable(handler):
                        try:
                            await handler(
                                event, *entry.get("args", []), **entry.get("kwargs", {})
                            )
                        except Exception:
                            self.kernel.logger.error(
                                "Inline callback handler error: %s",
                                traceback.format_exc(),
                            )
                            await event.answer(self.lang["critical_error"], alert=True)
                        return

                # 3. Legacy prefix/pattern handlers
                for pattern, handler in list(self.kernel.callback_handlers.items()):
                    p_str = (
                        pattern.decode() if isinstance(pattern, bytes) else str(pattern)
                    )
                    if data_str.startswith(p_str):
                        await handler(event)

            except Exception as e:
                error_traceback = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                self.kernel.logger.error(f"Error callback_handlers: {error_traceback}")
                await event.answer(f"error: {e}")

    async def _handle_show_traceback(self, event, data_str: str) -> None:
        """Show the stored traceback for a given error ID."""
        try:
            # Format is always "show_tb:{error_id}"
            parts = data_str.split(":", 1)
            if len(parts) < 2 or not parts[1]:
                return await event.answer(
                    f"⚠️ {self.lang['traceback_invalid_id']}", alert=True
                )

            error_id = parts[1]
            traceback_text = self.kernel.cache.get(f"tb_{error_id}")

            if not traceback_text:
                return await event.answer(
                    f"⚠️ {self.lang['traceback_expired']}", alert=True
                )

            # traceback_text is already HTML-formatted by ErrorFormatter
            if len(traceback_text) > 3800:
                traceback_text = (
                    traceback_text[:3800] + "\n<code>... [truncated]</code>"
                )

            await event.edit(
                f"<b>{self.lang['full_traceback']}:</b>\n{traceback_text}",
                parse_mode="html",
                buttons=None,
            )
        except Exception as e:
            self.kernel.logger.error(
                "Error _handle_show_traceback: %s",
                "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            )
            await event.answer(f"{self.lang['critical_error']}: {e}", alert=True)

    async def _handle_find_similar(self, event, data_str: str) -> None:
        """Show inline buttons for all recorded errors from the same source function."""
        try:
            parts = data_str.split(":", 1)
            if len(parts) < 2 or not parts[1]:
                return await event.answer(
                    f"⚠️ {self.lang['invalid_request']}", alert=True
                )

            func_hash = parts[1]

            # KernelLogger may be exposed under various attribute names
            klogger = getattr(self.kernel, "klogger", None) or getattr(
                self.kernel, "kernel_logger", None
            )
            if klogger is not None:
                similar_ids = klogger.get_similar_errors_by_hash(func_hash)
            else:
                # Fallback: access cache directly
                raw = self.kernel.cache.get(f"similar:{func_hash}")
                similar_ids = list(raw) if raw else []

            if not similar_ids:
                return await event.answer(
                    f"📋 {self.lang['no_similar_errors']}", alert=True
                )

            buttons = [
                [Button.inline(f"🔍 {eid}", data=f"show_tb:{eid}")]
                for eid in similar_ids
            ]
            await event.edit(
                f"📋 <b>{self.lang['similar_errors']} ({len(similar_ids)}):</b>",
                parse_mode="html",
                buttons=buttons,
            )
        except Exception as e:
            self.kernel.logger.error(f"Error _handle_find_similar: {e}")
            await event.answer(f"{self.lang['critical_error']}: {e}", alert=True)

    async def _handle_mute_error(self, event, data_str: str) -> None:
        """Mute a specific error type+source for one hour."""
        try:
            # Format: "mute_err:{error_type}:{source}"
            parts = data_str.split(":", 2)
            if len(parts) < 3:
                return await event.answer(
                    f"⚠️ {self.lang['invalid_format']}", alert=True
                )

            error_type, source = parts[1], parts[2]

            klogger = getattr(self.kernel, "klogger", None) or getattr(
                self.kernel, "kernel_logger", None
            )
            if klogger is not None:
                klogger.mute_error(error_type, source)
            else:
                # Fallback: write directly to cache
                self.kernel.cache.set(f"mute:{error_type}:{source}", True, ttl=3600)

            await event.answer(
                f"🔕 {self.lang('muted_for_hour', error_type=html.escape(error_type), source=html.escape(source))}",
                alert=True,
            )
        except Exception as e:
            self.kernel.logger.error(f"Error _handle_mute_error: {e}")
            await event.answer(f"{self.lang['critical_error']}: {e}", alert=True)

    async def _dispatch_inline_handler(self, cmd: str, raw_query: str, event) -> bool:
        """Route to a user inline handler once, supporting hikka proxy if needed."""
        if not cmd or cmd not in self.kernel.inline_handlers:
            return False

        handler = self.kernel.inline_handlers[cmd]

        try:
            # Prefer native event signature; fall back to hikka-compat if handler expects it
            sig = None
            try:
                sig = inspect.signature(handler)
            except (TypeError, ValueError):
                sig = None

            if sig and len(sig.parameters) == 1:
                result = handler(event)
            else:
                from core.lib.loader.hikka_compat.inline_types import (
                    InlineQuery as _HikkaInlineQuery,
                )

                inline_proxy = getattr(self.kernel, "_hikka_compat_inline_proxy", None)
                iq_obj = _HikkaInlineQuery(
                    query_id=event.query.query_id,
                    query=raw_query,
                    offset=event.query.offset or "",
                    user_id=event.sender_id,
                    inline_proxy=inline_proxy,
                    original_event=event,
                )
                result = handler(iq_obj)

            if asyncio.iscoroutine(result):
                result = await result

            if result:
                await event.answer(result)
                return True
        except Exception:
            self.kernel.logger.error(
                f"User inline handler error for {cmd}: {traceback.format_exc()}"
            )
        return False
