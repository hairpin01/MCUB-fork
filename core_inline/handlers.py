# author: @Hairpin00
# version: 1.0.4
# description: handler fixed
from telethon import events, Button
import aiohttp
import traceback
import json
import html


class InlineHandlers:
    def __init__(self, kernel, bot_client):
        self.kernel = kernel
        self.bot_client = bot_client

    def check_admin(self, event):
        try:
            if not hasattr(self.kernel, "ADMIN_ID"):
                return False

            sender_id = event.sender_id
            is_admin = sender_id == self.kernel.ADMIN_ID
            return is_admin
        except Exception as e:
            print(f"[DEBUG] Ошибка в check_admin: {e}")
            return False

    def parse_json_buttons(self, json_str):

        try:
            data = json.loads(json_str)
            buttons = []

            if isinstance(data, list):
                for btn in data:
                    if isinstance(btn, dict):
                        btn_text = btn.get("text", "Кнопка")
                        btn_type = btn.get("type", "callback").lower()

                        if btn_type == "callback":
                            btn_data = btn.get("data", "")
                            buttons.append([Button.inline(btn_text, btn_data.encode())])
                        elif btn_type == "url":
                            btn_url = btn.get("url", btn.get("data", ""))
                            buttons.append([Button.url(btn_text, btn_url)])
                        elif btn_type == "switch":
                            btn_query = btn.get("query", btn.get("data", ""))
                            btn_hint = btn.get("hint", "")
                            buttons.append(
                                [Button.switch_inline(btn_text, btn_query, btn_hint)]
                            )
            elif isinstance(data, dict):

                btn_text = data.get("text", "Кнопка")
                btn_type = data.get("type", "callback").lower()

                if btn_type == "callback":
                    btn_data = data.get("data", "")
                    buttons.append([Button.inline(btn_text, btn_data.encode())])
                elif btn_type == "url":
                    btn_url = data.get("url", data.get("data", ""))
                    buttons.append([Button.url(btn_text, btn_url)])
                elif btn_type == "switch":
                    btn_query = data.get("query", data.get("data", ""))
                    btn_hint = data.get("hint", "")
                    buttons.append(
                        [Button.switch_inline(btn_text, btn_query, btn_hint)]
                    )

            return buttons

        except json.JSONDecodeError as e:
            print(f"[DEBUG] Ошибка парсинга JSON: {e}")
            return []
        except Exception as e:
            print(f"[DEBUG] Ошибка обработки кнопок: {e}")
            return []

    async def handle_show_traceback(event):
        data_str = event.data.decode("utf-8") if isinstance(event.data, bytes) else str(event.data)
        if not data_str.startswith("show_tb"):
            return await event.answer("Неверный формат команды", alert=True)

        к
        parts = data_str.split(":")
        if len(parts) < 3:
            return await event.answer("Не указан ID ошибки", alert=True)

        error_id = parts[2]  # show_tb:<id>

        if not traceback_text:
            return await event.answer(
                "⚠️ Трейсбэк не найден (истекло время жизни кэша)", alert=True
            )

        if len(traceback_text) > 3800:
            traceback_text = traceback_text[:3800] + "\n... [truncated]"

        new_text = (
            event.message.text
            + f"\n\n<b>Full Traceback:</b>\n<pre>{html.escape(traceback_text)}</pre>"
        )

        try:
            await event.edit(new_text, parse_mode="html", buttons=None)
        except Exception as e:
            await event.answer(f"Ошибка: {e}", alert=True)

    async def register_handlers(self):
        # Обработчик InlineQuery (поиск через @bot)
        @self.bot_client.on(events.InlineQuery)
        async def inline_query_handler(event):
            from telethon.tl.types import InputWebDocument

            query = event.text or ""

            premium_emoji_telescope = (
                '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            )
            premium_emoji_block = (
                '<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji>'
            )
            premium_emoji_crystal = (
                '<tg-emoji emoji-id="5361837567463399422">🔮</tg-emoji>'
            )
            premium_emoji_shield = (
                '<tg-emoji emoji-id="5379679518740978720">🛡</tg-emoji>'
            )
            premium_emoji_tot = '<tg-emoji emoji-id="5085121109574025951">🫧</tg-emoji>'

            kernel = self.kernel
            builder = None

            if not self.check_admin(event):
                thumb = InputWebDocument(
                    url="https://x0.at/fo6m.jpg",
                    size=0,
                    mime_type="image/jpeg",
                    attributes=[],
                )

                builder = event.builder.article(
                    "У вас нету доступа и MCUB боту",
                    text=f"{premium_emoji_block} У вас нету доступа к inline MCUB bot\n<blockquote>{premium_emoji_shield} ID: {event.sender_id}</blockquote>",
                    parse_mode="html",
                    thumb=thumb,
                    description="нельзя",
                )
                await event.answer([builder])
                return

            usr_modules = sorted(list(kernel.loaded_modules.keys()))
            sys_modules = sorted(list(kernel.system_modules.keys()))
            modules = int(len(usr_modules)) + int(len(sys_modules))

            # Если запрос ни какои
            if not query:
                thumb = InputWebDocument(
                    url="https://x0.at/fo6m.jpg",
                    size=0,
                    mime_type="image/jpeg",
                    attributes=[],
                )

                builder = event.builder.article(
                    title="MCUB Info",
                    text=f"{premium_emoji_crystal} <b>MCUB Bot</b>\n<blockquote>{premium_emoji_shield} Version: {kernel.VERSION}</blockquote>\n<blockquote>{premium_emoji_tot} Modules: {modules}</blockquote>",
                    parse_mode="html",
                    thumb=thumb,
                    description="info",
                )
                await event.answer([builder])
                return

            # кастомные оброботчики
            try:
                for pattern, handler in self.kernel.inline_handlers.items():
                    if query.startswith(pattern):
                        await handler(event)
                        return
            except Exception as e:
                await self.kernel.handle_error(e, source="inline_handlers:custom")

            # Логика 2FA
            # не юзается :(
            if query.startswith("2fa_"):
                parts = query.split("_", 3)
                if len(parts) >= 4:
                    confirm_key = f"{parts[1]}_{parts[2]}"
                    command = parts[3]
                    text = f"⚠️ **Требуется подтверждение**\n\nКоманда: `{command}`\n\nВы действительно хотите выполнить эту команду?"
                    buttons = [
                        [
                            Button.inline("✅ Подтвердить", b"confirm_yes"),
                            Button.inline("❌ Отменить", b"confirm_no"),
                        ]
                    ]
                    builder = event.builder.article("2FA", text=text, buttons=buttons)
                else:
                    builder = event.builder.article(
                        "Error", text="❌ Ошибка подтверждения"
                    )

            # Логика каталога
            elif query.startswith("catalog"):
                try:
                    # Разбираем запрос вида "catalog_0_1"
                    parts = query.split("_")

                    # Устанавливаем значения по умолчанию
                    repo_index = 0
                    page = 1

                    if len(parts) >= 2 and parts[1].isdigit():
                        repo_index = int(parts[1])

                    if len(parts) >= 3 and parts[2].isdigit():
                        page = int(parts[2])

                    repos = [self.kernel.default_repo] + self.kernel.repositories

                    if repo_index < 0 or repo_index >= len(repos):
                        repo_index = 0

                    repo_url = repos[repo_index]

                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(f"{repo_url}/modules.ini") as resp:
                                if resp.status == 200:
                                    modules_text = await resp.text()
                                    modules = [
                                        line.strip()
                                        for line in modules_text.split("\n")
                                        if line.strip()
                                    ]
                                else:
                                    modules = []

                            async with session.get(f"{repo_url}/name.ini") as resp:
                                if resp.status == 200:
                                    repo_name = await resp.text()
                                    repo_name = repo_name.strip()
                                else:
                                    repo_name = (
                                        repo_url.split("/")[-2]
                                        if "/" in repo_url
                                        else repo_url
                                    )
                    except Exception as e:
                        modules = []
                        repo_name = (
                            repo_url.split("/")[-2] if "/" in repo_url else repo_url
                        )

                    per_page = 8
                    total_pages = (
                        (len(modules) + per_page - 1) // per_page if modules else 1
                    )

                    if page < 1:
                        page = 1
                    if page > total_pages:
                        page = total_pages

                    start_idx = (page - 1) * per_page
                    end_idx = start_idx + per_page
                    page_modules = modules[start_idx:end_idx] if modules else []

                    if repo_index == 0:
                        msg = f"<b>🌩️ Официальный репозиторий MCUB</b> <code>{repo_url}</code>\n\n"
                    else:
                        msg = f"<i>{repo_name}</i> <code>{repo_url}</code>\n\n"

                    if page_modules:
                        modules_text = " | ".join(
                            [f"<code>{m}</code>" for m in page_modules]
                        )
                        msg += modules_text
                    else:
                        msg += "📭 Нет модулей"

                    msg += f"\n\n📄 Страница {page}/{total_pages}"

                    buttons = []
                    nav_buttons = []

                    if page > 1:
                        nav_buttons.append(
                            Button.inline(
                                "⬅️ Назад", f"catalog_{repo_index}_{page-1}".encode()
                            )
                        )

                    if page < total_pages:
                        nav_buttons.append(
                            Button.inline(
                                "➡️ Вперёд", f"catalog_{repo_index}_{page+1}".encode()
                            )
                        )

                    if nav_buttons:
                        buttons.append(nav_buttons)

                    if len(repos) > 1:
                        repo_buttons = []
                        for i in range(len(repos)):
                            repo_buttons.append(
                                Button.inline(f"{i+1}", f"catalog_{i}_1".encode())
                            )
                        buttons.append(repo_buttons)

                    builder = event.builder.article(
                        "Catalog",
                        text=msg,
                        buttons=buttons if buttons else None,
                        parse_mode="html",
                    )

                except Exception as e:
                    builder = event.builder.article(
                        "Error", text=f"❌ Ошибка загрузки каталога: {str(e)[:100]}"
                    )

            # Обработка инлайн-форм с JSON форматом
            elif "|" in query:
                try:
                    # Разделяем текст и JSON
                    parts = query.split("|", 1)
                    text = parts[0].strip().strip("\"'")

                    if len(parts) > 1:
                        json_str = parts[1].strip()
                        buttons = self.parse_json_buttons(json_str)
                    else:
                        buttons = []

                    builder = event.builder.article(
                        "Message",
                        text=text,
                        buttons=buttons if buttons else None,
                        parse_mode="html",
                    )

                except Exception as e:
                    print(f"[DEBUG] Ошибка обработки JSON формы: {e}")
                    text = query.split("|")[0].strip().strip("\"'")
                    builder = event.builder.article(
                        "Message", text=text, parse_mode="html"
                    )

            else:
                if query:
                    builder = event.builder.article(
                        "Message", text=query, parse_mode="html"
                    )
                else:
                    builder = event.builder.article(
                        "Empty", text="...", parse_mode="html"
                    )

            if builder:
                await event.answer([builder])

        # CallbackQuery
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

                is_admin = self.check_admin(event=event)
                has_permission = self.kernel.callback_permissions.is_allowed(
                    event.sender_id, data_str
                )

                if not is_admin and not has_permission:
                    await event.answer("Нет доступа (callback)", alert=True)
                    return

                for pattern, handler in self.kernel.callback_handlers.items():
                    pattern_str = (
                        pattern.decode("utf-8")
                        if isinstance(pattern, bytes)
                        else str(pattern)
                    )

                    if data_str.startswith(pattern_str):
                        try:
                            await handler(event)
                        except Exception as e:
                            print(
                                f"Ошибка в кастомном обработчике [{pattern_str}]: {e}"
                            )
                            traceback.print_exc()
                        return

                # Обработка стандартных callback'ов
                if data_str == "confirm_yes":
                    from .keyboards import InlineKeyboards

                    keyboards = InlineKeyboards(self.kernel)
                    await keyboards.handle_confirm_yes(event)

                elif data_str == "confirm_no":
                    from .keyboards import InlineKeyboards

                    keyboards = InlineKeyboards(self.kernel)
                    await keyboards.handle_confirm_no(event)
                elif data_str.startswith("show_tb"):
                    await self.handle_show_traceback(event)


                elif data_str.startswith("catalog_"):
                    try:
                        parts = data_str.split("_")

                        if len(parts) < 3:
                            await event.answer(
                                "Некорректный запрос каталога", alert=True
                            )
                            return

                        repo_index = 0
                        page = 1

                        if parts[1].isdigit():
                            repo_index = int(parts[1])

                        if parts[2].isdigit():
                            page = int(parts[2])

                        repos = [self.kernel.default_repo] + self.kernel.repositories

                        if repo_index < 0 or repo_index >= len(repos):
                            repo_index = 0

                        repo_url = repos[repo_index]

                        async with aiohttp.ClientSession() as session:
                            async with session.get(f"{repo_url}/modules.ini") as resp:
                                if resp.status == 200:
                                    modules_text = await resp.text()
                                    modules = [
                                        line.strip()
                                        for line in modules_text.split("\n")
                                        if line.strip()
                                    ]
                                else:
                                    modules = []

                            async with session.get(f"{repo_url}/name.ini") as resp:
                                if resp.status == 200:
                                    repo_name = await resp.text()
                                    repo_name = repo_name.strip()
                                else:
                                    repo_name = (
                                        repo_url.split("/")[-2]
                                        if "/" in repo_url
                                        else repo_url
                                    )

                        per_page = 8
                        total_pages = (
                            (len(modules) + per_page - 1) // per_page if modules else 1
                        )

                        if page < 1:
                            page = 1
                        if page > total_pages:
                            page = total_pages

                        start_idx = (page - 1) * per_page
                        end_idx = start_idx + per_page
                        page_modules = modules[start_idx:end_idx] if modules else []

                        if repo_index == 0:
                            msg = f"<b>🌩️ Официальный репозиторий MCUB</b> <code>{repo_url}</code>\n\n"
                        else:
                            msg = f"<i>{repo_name}</i> <code>{repo_url}</code>\n\n"

                        if page_modules:
                            modules_text = " | ".join(
                                [f"<code>{m}</code>" for m in page_modules]
                            )
                            msg += modules_text
                        else:
                            msg += "📭 Нет модулей"

                        msg += f"\n\n📄 Страница {page}/{total_pages}"

                        buttons = []
                        nav_buttons = []

                        if page > 1:
                            nav_buttons.append(
                                Button.inline(
                                    "⬅️ Назад", f"catalog_{repo_index}_{page-1}".encode()
                                )
                            )

                        if page < total_pages:
                            nav_buttons.append(
                                Button.inline(
                                    "➡️ Вперёд",
                                    f"catalog_{repo_index}_{page+1}".encode(),
                                )
                            )

                        if nav_buttons:
                            buttons.append(nav_buttons)

                        if len(repos) > 1:
                            repo_buttons = []
                            for i in range(len(repos)):
                                repo_buttons.append(
                                    Button.inline(f"{i+1}", f"catalog_{i}_1".encode())
                                )
                            buttons.append(repo_buttons)

                        await event.edit(
                            msg, buttons=buttons if buttons else None, parse_mode="html"
                        )

                    except Exception as e:
                        await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)

                else:
                    await event.answer("❌ Неизвестная команда", alert=True)

            except Exception as e:
                print(f"Критическая ошибка в bot_callback_handler: {e}")
                traceback.print_exc()

