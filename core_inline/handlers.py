import aiohttp
import json
import html
import time
import traceback
from telethon import events, Button
from telethon.tl.types import InputWebDocument

class InlineHandlers:
    EMOJI_TELESCOPE = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
    EMOJI_BLOCK = '<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji>'
    EMOJI_CRYSTAL = '<tg-emoji emoji-id="5361837567463399422">🔮</tg-emoji>'
    EMOJI_SHIELD = '<tg-emoji emoji-id="5379679518740978720">🛡</tg-emoji>'
    EMOJI_TOT = '<tg-emoji emoji-id="5085121109574025951">🫧</tg-emoji>'

    def __init__(self, kernel, bot_client):
        self.kernel = kernel
        self.bot_client = bot_client
        if not hasattr(self.kernel, "session") or self.kernel.session.closed:
            self.kernel.session = aiohttp.ClientSession()

        self._form_counter = 0

    def create_inline_form(self, text, buttons=None, ttl=3600):
        """
        Создаёт инлайн-форму и возвращает её ID.

        Args:
            text: Текст сообщения (поддерживает HTML)
            buttons: Кнопки в формате:
                - список списков Button объектов: [[Button.callback(...), ...], ...]
                - список словарей: [{"text": "...", "type": "callback", "data": "..."}, ...]
                - JSON строка
            ttl: Время жизни формы в кэше (секунды)

        Returns:
            str: ID формы для использования в inline query
        """
        self._form_counter += 1
        form_id = self._make_form_id()

        if isinstance(buttons, str):
            buttons = self._parse_json_buttons(buttons)
        else:
            buttons = self._normalize_buttons(buttons)

        form_data = {
            "text": text,
            "buttons": buttons,
            "created_at": time.time()
        }

        self.kernel.cache.set(form_id, form_data, ttl=ttl)
        return form_id

    def get_inline_form(self, form_id):
        return self.kernel.cache.get(form_id)

    def _make_form_id(self):
        return f"form_{int(time.time())}_{self._form_counter}"

    def _normalize_buttons(self, buttons):
        """Приводит кнопки к единому формату (список рядов)."""
        if not buttons:
            return None
        if not isinstance(buttons, list):
            return None
        if len(buttons) == 0:
            return None

        # Если передан список словарей (одноуровневый)
        if isinstance(buttons[0], dict):
            parsed = []
            for btn_dict in buttons:
                btn = self._dict_to_button(btn_dict)
                if btn:
                    parsed.append([btn])
            return parsed if parsed else None

        # Если передан список рядов
        if isinstance(buttons[0], list):
            parsed = []
            for row in buttons:
                if not isinstance(row, list):
                    continue
                parsed_row = []
                for item in row:
                    if isinstance(item, dict):
                        btn = self._dict_to_button(item)
                        if btn:
                            parsed_row.append(btn)
                    else:
                        parsed_row.append(item)
                if parsed_row:
                    parsed.append(parsed_row)
            return parsed if parsed else None

        return None

    def _dict_to_button(self, btn_dict):
        if not isinstance(btn_dict, dict):
            return None

        text = btn_dict.get("text", "Кнопка")
        b_type = btn_dict.get("type", "callback").lower()

        if b_type == "callback":
            data = btn_dict.get("data", "")
            if isinstance(data, str):
                data = data.encode()
            return Button.inline(text, data)
        elif b_type == "url":
            url = btn_dict.get("url", btn_dict.get("data", ""))
            return Button.url(text, url)
        elif b_type == "switch":
            query = btn_dict.get("query", "")
            hint = btn_dict.get("hint", "")
            return Button.switch_inline(text, query, hint)
        return None

    def _parse_json_buttons(self, json_str):
        """Парсит JSON строку с описанием кнопок."""
        try:
            data = json.loads(json_str)
            markup = []

            def make_btn(btn_dict):
                text = btn_dict.get("text", "Кнопка")
                b_type = btn_dict.get("type", "callback").lower()
                if b_type == "callback":
                    return Button.inline(text, btn_dict.get("data", "").encode())
                elif b_type == "url":
                    return Button.url(text, btn_dict.get("url", btn_dict.get("data", "")))
                elif b_type == "switch":
                    return Button.switch_inline(text, btn_dict.get("query", ""), btn_dict.get("hint", ""))
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
        except (json.JSONDecodeError, Exception) as e:
            self.kernel.logger.debug(f"Ошибка парсинга JSON кнопок: {e}")
            return []

    def check_admin(self, event):
        try:
            if not hasattr(self.kernel, "ADMIN_ID") or self.kernel.ADMIN_ID is None:
                return False
            return int(event.sender_id) == int(self.kernel.ADMIN_ID)
        except (ValueError, TypeError) as e:
            self.kernel.logger.error(f"Ошибка в check_admin: {e}")
            return False

    async def register_handlers(self):
        """Регистрирует все обработчики для бота."""

        @self.bot_client.on(events.InlineQuery)
        async def inline_query_handler(event):
            try:
                query = event.text or ""

                if not self.check_admin(event):
                    await event.answer([event.builder.article(
                        "Нет доступа",
                        text=f"{self.EMOJI_BLOCK} У вас нет доступа к inline MCUB bot\n"
                            f"<blockquote>{self.EMOJI_SHIELD} ID: {event.sender_id}</blockquote>",
                        parse_mode="html"
                    )])
                    return

                if query.startswith("form_"):
                    form_data = self.get_inline_form(query)
                    if form_data:
                        builder = event.builder.article(
                            "Inline Form",
                            text=form_data["text"],
                            buttons=form_data.get("buttons"),
                            parse_mode="html"
                        )
                        await event.answer([builder])
                    else:
                        await event.answer([event.builder.article(
                            "Форма не найдена",
                            text=f"{self.EMOJI_BLOCK} <b>Форма не найдена или истекла</b>\n"
                                f"<i>ID: <code>{html.escape(query)}</code></i>",
                            parse_mode="html"
                        )])
                    return

                for pattern, handler in self.kernel.inline_handlers.items():
                    if query.startswith(pattern):
                        await handler(event)
                        return

                if not query.strip():
                    results = []
                    modules_count = len(self.kernel.loaded_modules) + len(self.kernel.system_modules)
                    inline_cmd_count = len(self.kernel.inline_handlers)

                    info_text = (
                        f"{self.EMOJI_CRYSTAL} <b>MCUB Bot</b>\n"
                        f"<blockquote>{self.EMOJI_SHIELD} Version: {self.kernel.VERSION}</blockquote>\n"
                        f"<blockquote>{self.EMOJI_TOT} Modules: {modules_count}</blockquote>\n"
                    )

                    thumb = InputWebDocument(
                        url='https://kappa.lol/KSKoOu',
                        size=0,
                        mime_type='image/jpeg'
                    )

                    info_article = event.builder.article(
                        "MCUB Info",
                        text=info_text,
                        description="Info userbot",
                        parse_mode="html",
                        thumb=thumb
                    )
                    results.append(info_article)

                    for pattern, handler in self.kernel.inline_handlers.items():
                        if len(results) >= 50:
                            break
                        handler_name = getattr(handler, '__name__', 'Обработчик')
                        docstring = handler.__doc__ or "команда"
                        cmd_text = f"{self.EMOJI_TELESCOPE} <b>Команда:</b> <code>{html.escape(pattern)}</code>\n\n"
                        thumb_cmd = InputWebDocument(
                            url='https://kappa.lol/EKhGKM',
                            size=0,
                            mime_type='image/jpeg'
                        )
                        cmd_article = event.builder.article(
                            f"Команда: {pattern[:20]}",
                            text=cmd_text,
                            parse_mode="html",
                            thumb=thumb_cmd,
                            description=html.escape(docstring.strip()),
                            buttons=[
                                [Button.switch_inline(f"🏄‍♀️ Выполнить: {pattern}",
                                                    query=pattern, same_peer=True)]
                            ]
                        )
                        results.append(cmd_article)

                    if len(results) == 1:
                        no_cmds_text = (
                            f"{self.EMOJI_CRYSTAL} <b>MCUB Bot</b>\n\n"
                            f"{self.EMOJI_BLOCK} <i>Нет зарегистрированных inline-команд</i>\n\n"
                        )
                        no_cmds_article = event.builder.article(
                            "Нет команд",
                            text=no_cmds_text,
                            parse_mode="html"
                        )
                        results.append(no_cmds_article)

                    await event.answer(results)
                    return

                #  text | {keyboards}
                elif "|" in query:
                    try:
                        parts = query.split("|", 1)
                        text = parts[0].strip().strip("\"'")
                        if len(parts) > 1:
                            json_str = parts[1].strip()
                            buttons = self._parse_json_buttons(json_str)
                        else:
                            buttons = []

                        builder = event.builder.article(
                            "Message",
                            text=text,
                            buttons=buttons if buttons else None,
                            parse_mode="html",
                        )
                    except Exception as e:
                        self.kernel.logger.debug(f"Ошибка обработки JSON формы: {e}")
                        text = query.split("|")[0].strip().strip("\"'")
                        builder = event.builder.article(
                            "Message", text=text, parse_mode="html"
                        )
                else:
                    text = query
                    builder = event.builder.article("Message", text=text, parse_mode="html")

                await event.answer([builder] if builder else [])

            except Exception as e:
                error_traceback = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )

                thumb = InputWebDocument(
                    url='https://kappa.lol/qNFKBT',
                    size=0,
                    mime_type='image/jpeg',
                    attributes=[]
                )

                error = event.builder.article(
                    f"Error",
                    text=f'🃏 Inline query error: <pre>{error_traceback}</pre>',
                    description=f"E: {str(e)[:50]}",
                    parse_mode="html",
                    thumb=thumb,

                )
                await event.answer([error])

        @self.bot_client.on(events.CallbackQuery)
        async def callback_query_handler(event):
            if not event.data:
                return
            data_str = event.data.decode("utf-8") if isinstance(event.data, bytes) else str(event.data)

            if not self.check_admin(event) and not self.kernel.callback_permissions.is_allowed(event.sender_id, data_str):
                return await event.answer("Нет доступа", alert=True)

            if data_str.startswith("show_tb"):
                await self._handle_show_traceback(event)
            elif data_str.startswith("confirm_"):
                from .keyboards import InlineKeyboards
                kb = InlineKeyboards(self.kernel)
                if "yes" in data_str:
                    await kb.handle_confirm_yes(event)
                else:
                    await kb.handle_confirm_no(event)


            for pattern, handler in self.kernel.callback_handlers.items():
                p_str = pattern.decode() if isinstance(pattern, bytes) else str(pattern)
                if data_str.startswith(p_str):
                    await handler(event)

    async def _handle_show_traceback(self, event):
        try:
            data_str = event.data.decode("utf-8") if isinstance(event.data, bytes) else str(event.data)
            sep = ":" if ":" in data_str else "_"
            parts = data_str.split(sep)

            if len(parts) < 2:
                return await event.answer("⚠️ Неверный ID ошибки", alert=True)

            error_id = parts[1]
            traceback_text = self.kernel.cache.get(f"tb_{error_id}")

            if not traceback_text:
                return await event.answer("⚠️ Трейсбэк истек в кэше", alert=True)

            if len(traceback_text) > 3800:
                traceback_text = traceback_text[:3800] + "\n... [truncated]"

            await event.edit(
                f"<b>Full Traceback:</b>\n<pre>{html.escape(traceback_text)}</pre>",
                parse_mode="html",
                buttons=None
            )
        except Exception as e:
            await event.answer(f"Критическая ошибка: {e}", alert=True)
