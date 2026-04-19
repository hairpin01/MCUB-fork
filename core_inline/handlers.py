# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import html
import inspect
import json
import threading
import time
import traceback
import uuid
from typing import Any

import aiohttp
from telethon import Button, events
from telethon.tl.types import (
    InputBotInlineMessageID,
    InputWebDocument,
)

from .api import (
    add_inline_keyboard_to_result,
    build_button_callback,
    build_button_game,
    build_button_location,
    build_button_phone,
    build_button_switch,
    build_button_url,
    build_inline_result_media,
    build_inline_result_text,
)
from .lib import InlineManager
from .strings import get_strings

try:
    from aiogram import Bot as AioBot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InlineQueryResultArticle,
        InputTextMessageContent,
    )
except Exception:  # pragma: no cover - optional dependency at runtime
    AioBot = None
    DefaultBotProperties = None
    InlineQueryResultArticle = None
    InputTextMessageContent = None
    InlineKeyboardMarkup = None
    InlineKeyboardButton = None


class _TelethonInlineQueryAdapter:
    """Thin Telethon-compatible wrapper around aiogram InlineQuery."""

    __slots__ = ("_api_bot", "_q", "sender_id", "text")

    def __init__(self, q: Any, api_bot: Any | None) -> None:
        self._q = q
        self._api_bot = api_bot
        self.text: str = getattr(q, "query", "") or ""
        self.sender_id: int = getattr(getattr(q, "from_user", None), "id", 0) or 0

    @property
    def query(self) -> Any:
        return self._q

    class _Builder:
        @staticmethod
        def article(
            title: str,
            text: str,
            description: str = "",
            parse_mode: str = "html",
            thumb: Any = None,
            buttons: Any = None,
        ) -> Any:
            if (
                InlineQueryResultArticle is not None
                and InputTextMessageContent is not None
            ):
                kb = None
                if buttons:
                    rows = []
                    for row in (
                        buttons
                        if hasattr(buttons, "__iter__")
                        and not isinstance(buttons, dict)
                        else [buttons]
                    ):
                        row_btns = []
                        for btn in (
                            row
                            if hasattr(row, "__iter__") and not isinstance(row, dict)
                            else [row]
                        ):
                            if hasattr(btn, "url"):
                                row_btns.append(
                                    InlineKeyboardButton(text=btn.text, url=btn.url)
                                )
                            elif hasattr(btn, "data"):
                                row_btns.append(
                                    InlineKeyboardButton(
                                        text=btn.text,
                                        callback_data=(
                                            btn.data.decode()
                                            if isinstance(btn.data, bytes)
                                            else btn.data
                                        ),
                                    )
                                )
                            elif isinstance(btn, dict):
                                btype = btn.get("type", "callback").lower()
                                if btype == "url":
                                    row_btns.append(
                                        InlineKeyboardButton(
                                            text=btn.get("text", ""),
                                            url=btn.get("url", ""),
                                        )
                                    )
                                elif btype == "callback":
                                    row_btns.append(
                                        InlineKeyboardButton(
                                            text=btn.get("text", ""),
                                            callback_data=btn.get("data", ""),
                                        )
                                    )
                        if row_btns:
                            rows.append(row_btns)
                    if rows:
                        kb = InlineKeyboardMarkup(inline_keyboard=rows)

                return InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description or "",
                    input_message_content=InputTextMessageContent(
                        message_text=text,
                        parse_mode=parse_mode.upper(),
                    ),
                    thumbnail_url=(getattr(thumb, "url", None) if thumb else None),
                    reply_markup=kb,
                )
            return {"title": title, "text": text}

    builder = _Builder()

    async def answer(self, results: list[Any], cache_time: int = 300) -> None:
        if self._api_bot is not None:
            await self._api_bot.answer_inline(
                inline_query_id=self._q.id,
                results=results,
                cache_time=cache_time,
            )


class _TelethonCallbackAdapter:
    """Thin Telethon-compatible wrapper around aiogram CallbackQuery."""

    __slots__ = (
        "_api_bot",
        "_kernel",
        "_q",
        "chat_instance",
        "data",
        "message",
        "sender_id",
    )

    def __init__(self, q: Any, api_bot: Any | None, kernel: Any) -> None:
        self._q = q
        self._api_bot = api_bot
        self._kernel = kernel
        self.data: bytes | str = (
            q.data.decode() if isinstance(q.data, bytes) else q.data or b""
        )
        self.sender_id: int = getattr(getattr(q, "from_user", None), "id", 0) or 0
        self.message: Any = getattr(q, "message", None)
        self.chat_instance: int = getattr(q, "chat_instance", 0) or 0

    @property
    def kernel(self) -> Any:
        return self._kernel

    async def answer(
        self,
        message: str = "",
        alert: bool = False,
        url: str = "",
    ) -> None:
        try:
            await self._q.answer(
                message=message,
                alert=alert,
                url=url if url else None,
            )
        except Exception as e:
            self._kernel.logger.warning(
                "[InlineHandlers] answer_callback failed: %s", e
            )

    async def edit(
        self,
        text: str,
        parse_mode: str = "html",
        buttons: Any = None,
    ) -> None:
        msg = self.message
        if msg is None:
            return
        kb = None
        if buttons:
            rows = []
            for row in (
                buttons
                if hasattr(buttons, "__iter__") and not isinstance(buttons, dict)
                else [buttons]
            ):
                row_btns = []
                for btn in (
                    row
                    if hasattr(row, "__iter__") and not isinstance(row, dict)
                    else [row]
                ):
                    if hasattr(btn, "url"):
                        row_btns.append(
                            InlineKeyboardButton(text=btn.text, url=btn.url)
                        )
                    elif hasattr(btn, "data"):
                        row_btns.append(
                            InlineKeyboardButton(
                                text=btn.text,
                                callback_data=(
                                    btn.data.decode()
                                    if isinstance(btn.data, bytes)
                                    else btn.data
                                ),
                            )
                        )
                if row_btns:
                    rows.append(row_btns)
            if rows:
                kb = InlineKeyboardMarkup(inline_keyboard=rows)

        try:
            await msg.edit_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=kb,
            )
        except Exception as e:
            self._kernel.logger.warning(
                "[InlineHandlers] aiogram edit_message_text failed: %s", e
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
        self._api_bot = None
        if (
            not hasattr(self.kernel, "session")
            or self.kernel.session is None
            or self.kernel.session.closed
        ):
            self.kernel.session = aiohttp.ClientSession()

        self._inline_manager = InlineManager(kernel)
        self.lang = get_strings(kernel)
        self.kernel.logger.debug("[InlineHandlers] __init__")
        self._setup_inline_send_handler()
        self._cb_lock = threading.Lock()
        self._last_cleanup_time = 0.0
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_interval = 300.0
        self._form_counter = 0

    def _is_aiogram_event(self, event: Any) -> bool:
        """Detect whether event is from aiogram or Telethon.

        Uses method signature inspection (most reliable):
        - aiogram CallbackQuery.answer(text=..., show_alert=...)
        - Telethon CallbackQuery.Event.answer(message=..., alert=...)

        Args:
            event: Event object.

        Returns:
            True for aiogram events, False for Telethon.
        """
        try:
            import inspect

            sig = inspect.signature(event.answer)
            params = list(sig.parameters.keys())
            return "text" in params
        except (TypeError, ValueError):
            return False

    def _wrap_aiogram_inline_query(self, query: Any) -> Any:
        """Wrap aiogram InlineQuery in a Telethon-compatible event interface.

        This allows the existing Telethon handler logic to run unchanged
        when the event comes from aiogram instead of Telethon.

        Args:
            query: Aiogram InlineQuery object.

        Returns:
            Object with Telethon-compatible .text, .sender_id,
            .builder (with .article()), and .answer() methods.
        """

        if not self._is_aiogram_event(query):
            return query

        bot = self._get_api_bot()
        return _TelethonInlineQueryAdapter(query, bot)

    def _wrap_aiogram_callback_query(self, query: Any) -> Any:
        """Wrap aiogram CallbackQuery in a Telethon-compatible event interface.

        This allows the existing Telethon handler logic to run unchanged
        when the event comes from aiogram instead of Telethon.

        Args:
            query: Aiogram CallbackQuery object.

        Returns:
            Object with Telethon-compatible .data, .sender_id,
            .answer(), and .edit() methods.
        """

        if hasattr(query, "builder") or isinstance(query, events.CallbackQuery.Event):
            return query

        bot = self._get_api_bot()
        return _TelethonCallbackAdapter(query, bot, self.kernel)

    def _build_article_result(
        self,
        event: Any,
        title: str,
        text: str,
        description: str | None = None,
        thumb_url: str | None = None,
        buttons: Any = None,
        parse_mode: str = "HTML",
    ) -> Any:
        """Build an inline query article result compatible with both frameworks.

        Args:
            event: Event object (aiogram or Telethon).
            title: Article title.
            text: Message text.
            description: Optional description.
            thumb_url: Optional thumbnail URL.
            buttons: Optional buttons (Telethon Button or aiogram InlineKeyboardButton).
            parse_mode: Parse mode for text.

        Returns:
            Telethon builder.article() result or InlineQueryResultArticle.
        """

        if self._is_aiogram_event(event):
            if InlineQueryResultArticle is None:
                return None
            content = InputTextMessageContent(
                message_text=text,
                parse_mode=parse_mode,
            )
            kb = None
            if buttons:
                rows = []
                for row in buttons if hasattr(buttons, "__iter__") else [buttons]:
                    row_btns = []
                    for btn in row if hasattr(row, "__iter__") else [row]:
                        if hasattr(btn, "url"):
                            row_btns.append(
                                InlineKeyboardButton(text=btn.text, url=btn.url)
                            )
                        elif hasattr(btn, "data"):
                            row_btns.append(
                                InlineKeyboardButton(
                                    text=btn.text,
                                    callback_data=(
                                        btn.data.decode()
                                        if isinstance(btn.data, bytes)
                                        else btn.data
                                    ),
                                )
                            )
                    if row_btns:
                        rows.append(row_btns)
                if rows:
                    kb = InlineKeyboardMarkup(inline_keyboard=rows)

            return InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=title,
                description=description or "",
                input_message_content=content,
                thumb_url=thumb_url,
                reply_markup=kb,
            )
        else:
            thumb = None
            if thumb_url:
                try:
                    thumb = InputWebDocument(
                        url=thumb_url,
                        size=0,
                        mime_type="image/jpeg",
                        attributes=[],
                    )
                except Exception:
                    pass
            return event.builder.article(
                title,
                text=text,
                description=description or "",
                parse_mode=parse_mode,
                thumb=thumb,
                buttons=buttons,
            )

    async def _answer_inline_query(
        self,
        event: Any,
        results: list[Any],
        cache_time: int = 300,
        is_personal: bool = False,
        next_offset: str | None = None,
    ) -> None:
        """Answer an inline query using the appropriate framework API.

        Args:
            event: Telethon InlineQuery event or aiogram InlineQuery.
            results: List of built article results.
            cache_time: Bot API cache time in seconds.
            is_personal: Return results only for this user.
            next_offset: Offset for pagination.
        """

        if self._is_aiogram_event(event):
            try:
                await event.answer(
                    results=results,
                    cache_time=cache_time,
                    is_personal=is_personal,
                    next_offset=next_offset,
                )
            except Exception as e:
                self.kernel.logger.error(
                    "[InlineHandlers] aiogram answer_inline_query failed: %s",
                    e,
                )
        else:
            try:
                await event.answer(results)
            except Exception as e:
                self.kernel.logger.error(
                    "[InlineHandlers] Telethon answer failed: %s",
                    e,
                )

    def _setup_inline_send_handler(self) -> None:
        @self.bot_client.on(events.Raw)
        async def inline_send_handler(event):
            from telethon.tl.types import UpdateBotInlineSend

            if isinstance(event, UpdateBotInlineSend):
                msg_id = event.msg_id
                if isinstance(msg_id, InputBotInlineMessageID):
                    inline_msg_id_str = (
                        f"{msg_id.dc_id}:{msg_id.id}:{msg_id.access_hash}"
                    )
                    self.kernel.logger.debug(
                        f"[InlineHandlers] UpdateBotInlineSend: form_id={event.id} inline_msg_id={inline_msg_id_str}"
                    )
                    form_data = self.kernel.cache.get(event.id)
                    if form_data:
                        form_data["inline_message_id"] = inline_msg_id_str
                        self.kernel.cache.set(
                            event.id, form_data, ttl=form_data.get("_ttl", 3600)
                        )

                temp_uuid = str(event.id)
                cache_key = f"inline_temp_{temp_uuid}"
                temp_data = (
                    self.kernel.cache.get(cache_key)
                    if hasattr(self.kernel, "cache")
                    else None
                )

                if temp_data:
                    allow_user = temp_data.get("allow_user")
                    user_id = getattr(event, "user_id", None)

                    if allow_user:
                        if allow_user != "all":
                            is_allowed = False
                            if hasattr(self.kernel, "callback_permissions"):
                                is_allowed = (
                                    self.kernel.callback_permissions.is_allowed(
                                        user_id, temp_uuid
                                    )
                                )
                            if not is_allowed:
                                if hasattr(event, "answer"):
                                    await event.answer("Not allowed", alert=True)
                                return

                    handler = temp_data.get("handler")
                    data = temp_data.get("data")
                    query_args = temp_data.get("query_args", "")

                    if handler:
                        try:
                            is_bound = (
                                hasattr(handler, "__bound_instance__")
                                and handler.__bound_instance__ is not None
                            )

                            if is_bound:
                                await handler(event, query_args, data)
                            else:
                                sig = None
                                try:
                                    sig = inspect.signature(handler)
                                except (TypeError, ValueError):
                                    pass

                                if is_bound and sig and len(sig.parameters) >= 3:
                                    await handler(event, query_args, data)
                                elif is_bound and sig and len(sig.parameters) >= 2:
                                    await handler(event, query_args)
                                elif is_bound:
                                    await handler(event)
                                elif sig and len(sig.parameters) >= 3:
                                    await handler(event, query_args, data)
                                elif sig and len(sig.parameters) >= 2:
                                    await handler(event, query_args)
                                else:
                                    await handler(event)
                        except Exception as e:
                            self.kernel.logger.error(f"inline_temp handler error: {e}")
                            if hasattr(event, "answer"):
                                await event.answer(f"Error: {e}", alert=True)

    async def close(self) -> None:
        """Close aiohttp session on bot shutdown."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception):
                pass
            self._cleanup_task = None

        if self._api_bot is not None:
            try:
                await self._api_bot.session.close()
            except Exception:
                self.kernel.logger.debug(
                    "[InlineHandlers] failed to close aiogram session"
                )
            self._api_bot = None

        if hasattr(self.kernel, "session") and self.kernel.session is not None:
            if not self.kernel.session.closed:
                await self.kernel.session.close()
            self.kernel.session = None

    def _get_bot_token(self) -> str:
        """Get inline bot token from config.

        Returns:
            Bot token string.

        Raises:
            ValueError: If token is missing in config.
        """

        token = self.kernel.config.get("inline_bot_token")
        if not token:
            raise ValueError("inline_bot_token not configured")
        return token

    def _get_api_bot(self) -> Any | None:
        """Get cached aiogram bot instance for Bot API calls."""

        if AioBot is None or DefaultBotProperties is None:
            return None

        if self._api_bot is not None:
            return self._api_bot

        try:
            token = self._get_bot_token()
            self._api_bot = AioBot(
                token=token,
                default=DefaultBotProperties(parse_mode="HTML"),
            )
            return self._api_bot
        except Exception as e:
            self.kernel.logger.warning(
                "[InlineHandlers] aiogram bot init failed: %s",
                e,
            )
            return None

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
            "_ttl": ttl,
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
        _bot_token = self._get_bot_token()

        self.create_inline_form(
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

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": result_obj.get("reply_markup"),
        }

        api_bot = self._get_api_bot()
        if api_bot is not None:
            try:
                msg = await api_bot.send_message(**payload)
                return {
                    "ok": True,
                    "result": {
                        "message_id": getattr(msg, "message_id", None),
                        "chat": {"id": chat_id},
                    },
                }
            except Exception as e:
                self.kernel.logger.warning(
                    "[InlineHandlers] aiogram send_message failed: %s",
                    e,
                )

        async with self.kernel.session.post(
            f"https://api.telegram.org/bot{_bot_token}/sendMessage",
            json=payload,
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
        _bot_token = self._get_bot_token()

        payload = {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
        }
        if next_offset:
            payload["next_offset"] = next_offset

        api_bot = self._get_api_bot()
        if api_bot is not None:
            try:
                await api_bot.answer_inline_query(
                    inline_query_id=inline_query_id,
                    results=results,
                    cache_time=cache_time,
                    is_personal=is_personal,
                    next_offset=next_offset,
                )
                return {"ok": True, "result": True}
            except Exception as e:
                self.kernel.logger.warning(
                    "[InlineHandlers] aiogram answer_inline_query failed: %s",
                    e,
                )

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
        return f"form_{uuid.uuid4().hex[:16]}"

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

        # If no explicit type, detect from keys (hikka style)
        if (
            b_type == "callback"
            and not btn_dict.get("callback")
            and not btn_dict.get("data")
        ):
            if "url" in btn_dict:
                b_type = "url"
            elif "switch" in btn_dict or "input" in btn_dict:
                b_type = "switch"
            elif "phone" in btn_dict:
                b_type = "phone"
            elif "location" in btn_dict:
                b_type = "location"
            elif "game" in btn_dict:
                b_type = "game"

        icon = btn_dict.get("icon")
        style = btn_dict.get("style")

        if b_type == "callback":
            # Support both traditional byte data and callable callbacks with
            data = btn_dict.get("data", "")
            callback = btn_dict.get("callback")

            if callable(callback):
                token = btn_dict.get("token") or uuid.uuid4().hex
                # Store mapping globally on kernel so multiple InlineHandlers
                # instances share the same callback map and lock.
                if not hasattr(self.kernel, "_inline_cb_lock"):
                    self.kernel._inline_cb_lock = threading.Lock()
                lock = self.kernel._inline_cb_lock

                with lock:
                    cb_map = getattr(self.kernel, "inline_callback_map", None)
                    if cb_map is None:
                        cb_map = {}
                        self.kernel.inline_callback_map = cb_map

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
        if b_type == "phone":
            return Button.request_phone(text, icon=icon, style=style)
        if b_type == "location":
            return Button.request_location(text, icon=icon, style=style)
        if b_type == "game":
            return Button.game(text, icon=icon, style=style)
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

    def _cleanup_inline_callback_map(self, force: bool = False) -> None:
        """Drop expired auto-generated callback tokens to keep the map small.

        Args:
            force: If True, cleanup regardless of interval. Otherwise, cleanup
                   only if enough time has passed since last cleanup.
        """
        now = time.time()
        if not force and (now - self._last_cleanup_time) < self._cleanup_interval:
            return

        self._last_cleanup_time = now
        lock = getattr(self.kernel, "_inline_cb_lock", None)
        if lock is None:
            return

        with lock:
            cb_map = getattr(self.kernel, "inline_callback_map", None)
            if not cb_map:
                return

            expired = [
                key
                for key, val in list(cb_map.items())
                if val.get("expires_at") and val["expires_at"] < now
            ]
            if expired:
                for key in expired:
                    cb_map.pop(key, None)
                self.kernel.logger.debug(
                    f"[InlineHandlers] cleaned {len(expired)} expired callbacks"
                )

    async def _save_inline_temp_data(
        self, temp_uuid: str, query_args: str, entry: dict
    ) -> None:
        """Save inline_temp data to cache for later retrieval on UpdateBotInlineSend."""
        if not hasattr(self.kernel, "cache"):
            return
        temp_data = {
            "handler": entry.get("handler"),
            "data": entry.get("data"),
            "query_args": query_args,
            "module_name": entry.get("module_name"),
            "allow_user": entry.get("allow_user"),
            "allow_ttl": entry.get("allow_ttl", 100),
        }
        self.kernel.cache.set(
            f"inline_temp_{temp_uuid}", temp_data, ttl=entry.get("expires_at", 300)
        )

    def _cleanup_inline_temp(self, force: bool = False) -> int:
        """Clean up expired temporary inline handlers."""
        if not hasattr(self.kernel, "_inline_temp_map"):
            return 0

        now = time.time()
        removed = 0

        for temp_uuid in list(self.kernel._inline_temp_map.keys()):
            entry = self.kernel._inline_temp_map.get(temp_uuid)
            if not entry:
                continue
            expires_at = entry.get("expires_at")
            if force or (expires_at and expires_at < now):
                del self.kernel._inline_temp_map[temp_uuid]
                self.kernel.cache.pop(f"inline_temp_{temp_uuid}", None)
                removed += 1

        if removed:
            self.kernel.logger.debug(
                f"[InlineHandlers] cleaned {removed} expired inline_temp handlers"
            )
        return removed

    async def _start_cleanup_task(self) -> None:
        """Start background task for periodic cleanup."""

        async def _periodic_cleanup():
            while True:
                await asyncio.sleep(60)
                self._cleanup_inline_callback_map(force=True)
                self._cleanup_inline_temp(force=False)

        self._cleanup_task = asyncio.create_task(_periodic_cleanup())

    async def check_admin(self, event):
        try:
            user_id = int(event.sender_id)
            result = await self._inline_manager.is_allowed(user_id)
            return result
        except (ValueError, TypeError) as e:
            self.kernel.logger.error(f"Ошибка в check_admin: {e}")
            return False

    async def register_handlers(self):
        """Registers all handlers for the bot.

        Registers Telethon event handlers that delegate to adapter methods.
        These methods can also be called directly from aiogram handlers.
        """
        await self._start_cleanup_task()

        @self.bot_client.on(events.InlineQuery)
        async def inline_query_handler(event):
            await self.process_inline_query(event)

        @self.bot_client.on(events.CallbackQuery)
        async def callback_query_handler(event):
            await self.process_callback_query(event)

    async def process_inline_query(self, event: Any) -> None:
        """Process an inline query event.

        Extracted into a separate method so it can be called from both
        Telethon and aiogram event handlers without duplication.
        Aiogram events are wrapped in a Telethon-compatible adapter.

        Args:
            event: Telethon InlineQuery event or aiogram InlineQuery.
        """

        event = self._wrap_aiogram_inline_query(event)

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

            query_cmd = query.lower().split()[0] if query.strip() else ""
            query_args = ""
            if query.strip() and " " in query:
                query_args = query.split(" ", 1)[1]
            self.kernel.logger.debug(
                f"[InlineHandlers] query_cmd={query_cmd}, query={query}"
            )

            temp_map = getattr(self.kernel, "_inline_temp_map", None)
            if temp_map and query_cmd in temp_map:
                entry = temp_map[query_cmd]
                article_callable = entry.get("article")
                try:
                    if article_callable:
                        builder = article_callable(event)
                        if hasattr(builder, "id"):
                            builder.id = query_cmd
                    else:
                        builder = event.builder.article(
                            id=query_cmd,
                            title="Do not delete ID!",
                            text="I send a request to the module...",
                        )

                    entry["user_id"] = event.sender_id
                    await self._save_inline_temp_data(query_cmd, query_args, entry)
                    await event.answer([builder])
                    return
                except Exception as e:
                    self.kernel.logger.error(f"inline_temp article error: {e}")
                    await event.answer(
                        [event.builder.article("Error", text=f"Error: {e}")]
                    )
                    return

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
                            result_id=query,
                        )
                    else:
                        _result_obj = build_inline_result_text(
                            title="Inline Form",
                            text=text,
                            result_id=query,
                        )

                    if buttons:
                        _result_obj = add_inline_keyboard_to_result(
                            _result_obj, buttons
                        )

                    _data = await self.answer_inline_query_custom(
                        inline_query_id=str(event.query.query_id),
                        results=[_result_obj],
                        cache_time=0,
                        is_personal=False,
                    )
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

            try:
                await event.answer()
            except Exception as answer_error:
                self.kernel.logger.debug(
                    f"Inline query answer (empty) failed: {answer_error}"
                )

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
            try:
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
            except Exception as answer_error:
                self.kernel.logger.debug(
                    f"Inline query error answer failed: {answer_error}"
                )

    async def process_callback_query(self, event: Any) -> None:
        """Process a callback query event.

        Extracted into a separate method so it can be called from both
        Telethon and aiogram event handlers without duplication.
        Aiogram events are wrapped in a Telethon-compatible adapter.

        Args:
            event: Telethon CallbackQuery event or aiogram CallbackQuery.
        """

        event = self._wrap_aiogram_callback_query(event)

        try:
            if not event.data:
                return

            data_str = (
                event.data.decode("utf-8")
                if isinstance(event.data, bytes)
                else str(event.data)
            )

            # Check auto-generated callback tokens first for allow_all
            self._cleanup_inline_callback_map()
            with self._cb_lock:
                cb_map = getattr(self.kernel, "inline_callback_map", None) or {}

            entry = None
            is_allowed = False

            if data_str in cb_map:
                entry = cb_map[data_str]
                if entry.get("allow_all"):
                    is_allowed = True

            if not is_allowed:
                if not await self.check_admin(event) and (
                    not hasattr(self.kernel, "callback_permissions")
                    or not self.kernel.callback_permissions.is_allowed(
                        event.sender_id, data_str
                    )
                ):
                    if entry is None:
                        return await event.answer(self.lang["no_access"], alert=False)
                    elif not entry.get("allow_user"):
                        return await event.answer(self.lang["no_access"], alert=False)

            # 1. Built-in service callbacks
            if data_str.startswith("show_tb:"):
                await self._handle_show_traceback(event, data_str)
            elif data_str.startswith("find_similar:"):
                await self._handle_find_similar(event, data_str)
            elif data_str.startswith("mute_err:"):
                await self._handle_mute_error(event, data_str)

            if entry is None:
                entry = cb_map.get(data_str)

            if entry:
                if entry.get("expires_at") and entry["expires_at"] < time.time():
                    with self._cb_lock:
                        cb_map.pop(data_str, None)
                    return await event.answer(self.lang["form_expired"], alert=False)

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
                elif entry.get("kwargs", {}).get("url"):
                    return

            # 3. Legacy prefix/pattern handlers
            for pattern, handler in list(self.kernel.callback_handlers.items()):
                p_str = pattern.decode() if isinstance(pattern, bytes) else str(pattern)
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
        self.kernel.logger.debug(f"[InlineHandlers] _dispatch_inline_handler cmd={cmd}")
        if not cmd or cmd not in self.kernel.inline_handlers:
            self.kernel.logger.debug("[InlineHandlers] cmd not in inline_handlers")
            return False

        handler = self.kernel.inline_handlers[cmd]
        self.kernel.logger.debug(
            f"[InlineHandlers] handler found: {handler}, cmd={cmd}"
        )

        try:
            # Check if this is a hikka-compat handler by checking attributes
            is_hikka_handler = getattr(
                handler, "__hikka_inline_handler__", False
            ) or getattr(handler, "is_inline_handler", False)

            sig = None
            if not is_hikka_handler:
                try:
                    sig = inspect.signature(handler)
                except (TypeError, ValueError):
                    sig = None

            if is_hikka_handler:
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
                try:
                    result = handler(iq_obj)
                except Exception as handler_error:
                    self.kernel.logger.debug(
                        f"[InlineHandlers] hikka handler error: {handler_error}"
                    )
                    result = None
                self.kernel.logger.debug(
                    f"[InlineHandlers] handler result type: {type(result)}"
                )
            elif sig and len(sig.parameters) == 1:
                try:
                    result = handler(event)
                except Exception as handler_error:
                    self.kernel.logger.debug(
                        f"[InlineHandlers] handler error: {handler_error}"
                    )
                    result = None
                self.kernel.logger.debug(
                    f"[InlineHandlers] handler result type: {type(result)}"
                )
            else:
                try:
                    result = handler(event)
                except Exception as handler_error:
                    self.kernel.logger.debug(
                        f"[InlineHandlers] handler error: {handler_error}"
                    )
                    result = None
                self.kernel.logger.debug(
                    f"[InlineHandlers] handler result type: {type(result)}"
                )

            if asyncio.iscoroutine(result):
                try:
                    result = await result
                except Exception as await_error:
                    self.kernel.logger.debug(
                        f"[InlineHandlers] await error: {await_error}"
                    )
                    result = None
                self.kernel.logger.debug(
                    f"[InlineHandlers] awaited result: {type(result)}"
                )

            self.kernel.logger.debug(f"[InlineHandlers] final result: {result}")

            if result:
                from telethon.tl.types import InputWebDocument

                if isinstance(result, dict):
                    thumb_url = result.get("thumb_url") or result.get(
                        "thumbnail_url", ""
                    )
                    if thumb_url:
                        try:
                            thumb = InputWebDocument(
                                url=thumb_url,
                                size=0,
                                mime_type="image/jpeg",
                                attributes=[],
                            )
                        except Exception:
                            thumb = None
                    else:
                        thumb = None

                    result = await event.builder.article(
                        title=result.get("title", ""),
                        description=result.get("description", ""),
                        text=result.get("message", result.get("text", "")),
                        thumb=thumb,
                    )
                    result = [result]
                elif isinstance(result, list):
                    converted = []
                    for item in result:
                        # Skip if already a Telethon-compatible object (has _bytes method)
                        if hasattr(item, "_bytes"):
                            converted.append(item)
                        # Check for aiogram types (they have 'id' and 'title' but no '_bytes')
                        elif hasattr(item, "id") and hasattr(item, "title"):
                            converted.append(item)
                        elif isinstance(item, dict):
                            article = await event.builder.article(
                                title=item.get("title", ""),
                                description=item.get("description", ""),
                                text=item.get("message", item.get("text", "")),
                            )
                            converted.append(article)
                        else:
                            converted.append(item)
                    result = converted
                self.kernel.logger.debug(
                    f"[InlineHandlers] converted result: {result}, len={len(result) if result else 0}"
                )
                try:
                    await event.answer(result)
                except Exception as answer_error:
                    self.kernel.logger.debug(
                        f"Inline handler event.answer failed: {answer_error}"
                    )
                return True
        except Exception:
            self.kernel.logger.error(
                f"User inline handler error for {cmd}: {traceback.format_exc()}"
            )
        return False
