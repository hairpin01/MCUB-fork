# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import json
import os
from html import escape
from typing import Any
from telethon import Button, events
from telethon.tl.types import (
    DocumentAttributeImageSize,
    InputMediaWebPage,
    InputWebDocument,
)

from core.lib.loader.module_base import ModuleBase, command, inline
from core.lib.loader.module_config import Boolean, ConfigValue, ModuleConfig, String

CUSTOM_EMOJI = {
    "crystal": '<tg-emoji emoji-id="5361837567463399422">🔮</tg-emoji>',
    "dna": '<tg-emoji emoji-id="5404451992456156919">🧬</tg-emoji>',
    "alembic": '<tg-emoji emoji-id="5379679518740978720">⚗️</tg-emoji>',
    "snowflake": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "blocked": '<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji>',
    "pancake": '<tg-emoji emoji-id="5373004843210251169">🥞</tg-emoji>',
    "confused": '<tg-emoji emoji-id="5249119354825487565">🫨</tg-emoji>',
    "map": '<tg-emoji emoji-id="5472064286752775254">🗺️</tg-emoji>',
    "tot": '<tg-emoji emoji-id="5085121109574025951">🫧</tg-emoji>',
    "eye_off": '<tg-emoji emoji-id="5228686859663585439">👁‍🗨</tg-emoji>',
}

ZERO_WIDTH_CHAR = "\u2060"

_METADATA_CACHE: dict[str, tuple[float, dict]] = {}
_METADATA_LOCKS: dict[int, asyncio.Lock] = {}


def _get_metadata_lock() -> asyncio.Lock:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.Lock()
    loop_id = id(loop)
    lock = _METADATA_LOCKS.get(loop_id)
    if lock is None:
        lock = asyncio.Lock()
        _METADATA_LOCKS[loop_id] = lock
    return lock


class ManModule(ModuleBase):
    name = "man"
    version = "1.1.0"
    author = "@hairpin00"
    description = {"ru": "Менеджер модулей", "en": "Module manager"}

    strings = {
        "ru": {
            "help_not_command": "Ты имел в виду ",
            "module": "Модуль",
            "description": "Описание",
            "version": "Версия",
            "no_description": "Нет описания",
            "unknown": "Неизвестно",
            "aliases": "Алиасы",
            "no_commands": "Нет команд",
            "author": "Автор",
            "found_modules": "Найдены модули",
            "and_more": "... и еще <code>{count}</code>",
            "no_exact_match": "Точное совпадение не найдено",
            "module_not_found": "Модуль не найден",
            "system_modules": "Системные модули",
            "user_modules_page": "Пользовательские модули (Страница {page} |<code> {count}</code>)",
            "close": "Закрыть",
            "inline_bot_not_configured": "Inline бот не настроен\nУстановите inline_bot_token в config",
            "no_inline_results": "❌ Нет inline результатов",
            "error": "Ошибка",
            "module_manager": 'Менеджер модулей\n\nИспользуйте "man" для просмотра модулей или "man [модуль]" для поиска.',
            "search_hint": '🔍 Поиск модулей\n\nНапишите "man [название]" для поиска модулей и команд\nПример: man ping',
            "search_results": "Результаты поиска",
            "command": "Command",
            "and_more_commands": "... и еще {count} команд",
            "not_found_hint": "Попробуйте другой запрос.",
            "closed": "Closed",
            "page_error": "Error",
            "search_error": "Search Error",
            "search_error_desc": "An error occurred",
            "module_hidden": f"{CUSTOM_EMOJI['eye_off']} <b>Модуль скрыт из списка.</b>",
            "module_already_hidden": f"{CUSTOM_EMOJI['blocked']} Модуль уже скрыт.",
            "module_unhidden": "✅ <b>Модуль убран из скрытых.</b>",
            "module_not_hidden": f"{CUSTOM_EMOJI['blocked']} Этот модуль не скрыт.",
            "manhide_usage": f"{CUSTOM_EMOJI['confused']} Использование: <code>.manhide [модуль]</code>",
            "manunhide_usage": f"{CUSTOM_EMOJI['confused']} Использование: <code>.manunhide [модуль]</code>",
            "system_module_note": f"{CUSTOM_EMOJI['blocked']} <b>Это системный модуль, и его просто так нельзя выгрузить loader'ом</b>",
        },
        "en": {
            "help_not_command": "Did you mean ",
            "module": "Module",
            "description": "Description",
            "version": "Version",
            "no_description": "No description",
            "unknown": "Unknown",
            "aliases": "Aliases",
            "no_commands": "No commands",
            "author": "Author",
            "found_modules": "Found modules",
            "and_more": "... and <code>{count}</code> more",
            "no_exact_match": "No exact match found",
            "module_not_found": "Module not found",
            "system_modules": "System modules",
            "user_modules_page": "User modules (Page {page} | Count<code> {count}</code>)",
            "close": "Close",
            "inline_bot_not_configured": "Inline bot not configured\nSet inline_bot_token in config",
            "no_inline_results": "❌ No inline results",
            "error": "Error",
            "module_manager": 'Module Manager\n\nUse "man" to browse modules or "man [module]" to search.',
            "search_hint": '🔍 Search Modules\n\nType "man [name]" to search for modules and commands\nExample: man ping',
            "search_results": "Search results",
            "command": "Command",
            "and_more_commands": "... and {count} more commands",
            "not_found_hint": "Try another query.",
            "closed": "Closed",
            "page_error": "Error",
            "search_error": "Search Error",
            "search_error_desc": "An error occurred",
            "module_hidden": f"{CUSTOM_EMOJI['eye_off']} <b>Module hidden from list.</b>",
            "module_already_hidden": f"{CUSTOM_EMOJI['blocked']} Module is already hidden.",
            "module_unhidden": "✅ <b>Module removed from hidden.</b>",
            "module_not_hidden": f"{CUSTOM_EMOJI['blocked']} This module is not hidden.",
            "manhide_usage": f"{CUSTOM_EMOJI['confused']} Usage: <code>.manhide [module]</code>",
            "manunhide_usage": f"{CUSTOM_EMOJI['confused']} Usage: <code>.manunhide [module]</code>",
            "system_module_note": f"{CUSTOM_EMOJI['blocked']} <b>This is a system module, and it cannot simply be unloaded with a loader</b>",
        },
    }

    config = ModuleConfig(
        ConfigValue(
            "man_quote_media",
            True,
            description="Send media in quotes",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "man_banner_url",
            "",
            description="Banner image URL for inline preview",
            validator=String(default=""),
        ),
        ConfigValue(
            "man_invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(default=False),
        ),
    )

    async def on_load(self) -> None:
        config_dict = await self.kernel.get_module_config(
            self.name,
            {
                "man_quote_media": True,
                "man_banner_url": "",
                "man_invert_media": False,
            },
        )
        self.config.from_dict(config_dict)
        config_dict_clean = {
            k: v for k, v in self.config.to_dict().items() if v is not None
        }
        if config_dict_clean:
            await self.kernel.save_module_config(self.name, config_dict_clean)
        self.kernel.store_module_config_schema(self.name, self.config)

    def _add_inline_banner_preview(self, message_html: str) -> str:
        cfg = self.config
        banner_url = cfg.get("man_banner_url") if cfg else ""
        quote_media = cfg.get("man_quote_media", False) if cfg else False
        if not (
            quote_media
            and isinstance(banner_url, str)
            and banner_url.startswith(("http://", "https://"))
        ):
            return message_html
        return f'<a href="{escape(banner_url, quote=True)}">{ZERO_WIDTH_CHAR}</a>{message_html}'

    async def _get_hidden_modules(self) -> list[str]:
        data = await self.kernel.db_get("man", "hidden_modules")
        if not data:
            return []
        try:
            if isinstance(data, str):
                return json.loads(data)
            return json.loads(str(data))
        except Exception:
            return []

    async def _save_hidden_modules(self, hidden: list[str]) -> None:
        await self.kernel.db_set("man", "hidden_modules", json.dumps(hidden))

    def _resolve_module_path(self, name: str, typ: str) -> str:
        if typ == "system":
            return f"{self.kernel.MODULES_DIR}/{name}.py"
        resolved = self.kernel._loader.get_module_path(name)
        if resolved:
            return resolved
        package_dir = f"{self.kernel.MODULES_LOADED_DIR}/{name}"
        if os.path.isdir(package_dir):
            init_file = os.path.join(package_dir, "__init__.py")
            if os.path.exists(init_file):
                return init_file
        return f"{self.kernel.MODULES_LOADED_DIR}/{name}.py"

    async def _load_module_metadata(self, name: str, typ: str) -> dict:
        file_path = self._resolve_module_path(name, typ)
        s = self.strings
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return {
                "commands": {},
                "description": s["no_description"],
                "description_i18n": {},
                "version": "?.?.?",
                "author": s["unknown"],
                "banner_url": None,
            }

        lock = _get_metadata_lock()
        async with lock:
            cached = _METADATA_CACHE.get(file_path)
            if cached and cached[0] == mtime:
                return cached[1]

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                code = f.read()
            metadata = await self.kernel.get_module_metadata(code)
        except Exception:
            metadata = {
                "commands": {},
                "description": s["no_description"],
                "description_i18n": {},
                "version": "?.?.?",
                "author": s["unknown"],
                "banner_url": None,
            }

        async with lock:
            _METADATA_CACHE[file_path] = (mtime, metadata)

        return metadata

    def _get_module_commands(self, module_name: str) -> tuple[dict, dict, dict]:
        lang = self.kernel.config.get("language", "ru")
        return self.kernel._loader.get_module_commands(module_name, lang)

    def _gather_all_modules(
        self, show_hidden: bool, hidden: list[str]
    ) -> dict[str, tuple[str, object]]:
        all_modules: dict[str, tuple[str, object]] = {}
        for name, module in self.kernel.system_modules.items():
            all_modules[name] = ("system", module)
        for name, module in self.kernel.loaded_modules.items():
            all_modules[name] = ("user", module)
        if not show_hidden:
            all_modules = {k: v for k, v in all_modules.items() if k not in hidden}
        return all_modules

    async def _generate_detailed_page(
        self, search_term: str, show_hidden: bool = False
    ) -> tuple[str, str | None]:
        search_term_clean = search_term.lower()
        exact_match = None
        similar_modules = []
        s = self.strings

        hidden = await self._get_hidden_modules()
        all_modules = self._gather_all_modules(show_hidden, hidden)

        for name, (typ, module) in all_modules.items():
            if name.lower() == search_term_clean:
                exact_match = (name, typ, module)
                break

        if exact_match:
            return await self._build_module_detail(exact_match)

        seen = set()
        for name, (typ, module) in all_modules.items():
            if search_term_clean in name.lower():
                if name not in seen:
                    similar_modules.append((name, typ, module))
                    seen.add(name)
            else:
                commands, _, _ = self._get_module_commands(name)
                for cmd in commands:
                    if search_term_clean in cmd.lower():
                        if name not in seen:
                            similar_modules.append((name, typ, module))
                            seen.add(name)
                        break

        if len(similar_modules) == 1:
            return await self._build_module_detail(similar_modules[0])

        if similar_modules:
            msg = f"{CUSTOM_EMOJI['crystal']} <b>{s['found_modules']}:</b>\n<blockquote expandable>"
            for name, typ, module in similar_modules[:5]:
                commands, _, _ = self._get_module_commands(name)
                hidden_mark = f" {CUSTOM_EMOJI['eye_off']}" if name in hidden else ""
                if commands:
                    cmd_text = ", ".join(
                        f"<code>{self.kernel.custom_prefix}{cmd}</code>"
                        for cmd in commands[:2]
                    )
                    msg += f"<b>{name}</b>{hidden_mark}: {cmd_text}\n"
            msg += "</blockquote>"
            if len(similar_modules) > 5:
                msg += f"... {s['and_more'].format(count=len(similar_modules) - 5)} {CUSTOM_EMOJI['tot']}\n"
            msg += f"\n<blockquote><i>{s['no_exact_match']}</i> {CUSTOM_EMOJI['map']}</blockquote>"
        else:
            msg = f"<blockquote expandable>{CUSTOM_EMOJI['blocked']} {s['module_not_found']}</blockquote>"
        return msg, None

    async def _build_module_detail(
        self, match_tuple: tuple[str, str, Any]
    ) -> tuple[str, str | None]:
        name, typ, _module = match_tuple
        s = self.strings

        class_instance = getattr(_module, "_class_instance", None)
        if class_instance is not None:
            display_name = getattr(type(class_instance), "name", name)
        else:
            display_name = name

        commands, aliases_info, descriptions = self._get_module_commands(name)
        metadata = await self._load_module_metadata(name, typ)

        lang = self.kernel.config.get("language", "ru")
        i18n = metadata.get("description_i18n")
        fallback = metadata.get("description", s["no_description"])
        description = self.kernel._loader.pick_localized_text(i18n, lang, fallback)

        msg = (
            f"{CUSTOM_EMOJI['dna']} <b>{s['module']}</b> <code>{display_name}</code>:\n"
        )
        msg += f"{CUSTOM_EMOJI['alembic']} <b>{s['description']}:</b> <i>{description}</i>\n"
        msg += f"{CUSTOM_EMOJI['snowflake']} <b>{s['version']}:</b> <code>{metadata.get('version', '1.0.0')}</code>\n"
        msg += "<blockquote expandable>"
        if commands:
            for cmd in commands:
                cmd_desc = (
                    descriptions.get(cmd)
                    or metadata.get("commands", {}).get(cmd)
                    or f"{CUSTOM_EMOJI['confused']} {s['no_description']}"
                )
                msg += f"{CUSTOM_EMOJI['tot']} <code>{self.kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>"

                if cmd in aliases_info:
                    aliases = aliases_info[cmd]
                    if isinstance(aliases, str):
                        aliases = [aliases]
                    if aliases:
                        alias_text = ", ".join(
                            f"<code>{self.kernel.custom_prefix}{a}</code>"
                            for a in aliases
                        )
                        msg += f" | {s['aliases']}: {alias_text}"
                msg += "\n"
        else:
            msg += f"{CUSTOM_EMOJI['blocked']} {s['no_commands']}\n"
        msg += "</blockquote>"

        inline_commands = self.kernel.get_module_inline_commands(name)
        if inline_commands:
            inline_emoji = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
            msg += "<blockquote expandable>"
            for cmd, desc in inline_commands:
                if desc:
                    msg += f"{inline_emoji} <code>@{self.kernel.config.get('inline_bot_username', 'bot')} {cmd}</code> – <b>{desc}</b>\n"
                else:
                    msg += f"{inline_emoji} <code>@{self.kernel.config.get('inline_bot_username', 'bot')} {cmd}</code>\n"
            msg += "</blockquote>"

        msg += f"\n<blockquote>{CUSTOM_EMOJI['pancake']} <b>{s['author']}:</b> <i>{metadata.get('author', s['unknown'])}</i></blockquote>"
        if typ == "system":
            msg += f"\n<blockquote>{s['system_module_note']}</blockquote>"
        return msg, metadata.get("banner_url")

    async def _man_close_cb(self, event: events.CallbackQuery.Event) -> None:
        try:
            await self.kernel.client.delete_messages(event.chat_id, [event.message_id])
        except Exception:
            await event.answer(self.strings["closed"], alert=False)

    async def _man_page_cb(self, event: events.CallbackQuery.Event, page: int) -> None:
        try:
            hidden = await self._get_hidden_modules()
            msg, buttons = self._get_paginated_data(
                page,
                hidden_list=hidden,
                page_cb=self._man_page_cb,
                close_cb=self._man_close_cb,
            )
            invert_media = (
                self.config.get("man_invert_media", False) if self.config else False
            )
            try:
                await event.edit(
                    self._add_inline_banner_preview(msg),
                    buttons=buttons,
                    parse_mode="html",
                    invert_media=invert_media,
                )
            except TypeError:
                await event.edit(
                    self._add_inline_banner_preview(msg),
                    buttons=buttons,
                    parse_mode="html",
                )
        except Exception as e:
            await event.answer(
                f"{self.strings['page_error']}: {str(e)[:50]}", alert=True
            )

    def _get_paginated_data(
        self,
        page: int,
        hidden_list: list[str] | None = None,
        show_hidden: bool = False,
        *,
        page_cb=None,
        close_cb=None,
        ttl: int = 900,
    ) -> tuple[str, list]:
        MAX_MSG_LENGTH = 2000
        if hidden_list is None:
            hidden_list = []
        s = self.strings
        kernel = self.kernel

        def filter_modules(names: list) -> list:
            if show_hidden:
                return names
            return [n for n in names if n not in hidden_list]

        def render_module_line(name: str) -> str:
            module_obj = kernel.loaded_modules.get(name)
            class_instance = getattr(module_obj, "_class_instance", None)
            if class_instance is not None:
                display_name = getattr(type(class_instance), "name", name)
            else:
                display_name = name

            commands, aliases_info, _ = self._get_module_commands(name)
            hidden_mark = (
                f" {CUSTOM_EMOJI['eye_off']}"
                if (show_hidden and name in hidden_list)
                else ""
            )
            inline_commands = kernel.get_module_inline_commands(name)

            if commands:
                cmd_display = []
                for cmd in commands[:3]:
                    display_cmd = f"<code>{kernel.custom_prefix}{cmd}</code>"
                    if cmd in aliases_info:
                        aliases = aliases_info[cmd]
                        if isinstance(aliases, list):
                            alias_text = ", ".join(
                                f"<code>{kernel.custom_prefix}{a}</code>"
                                for a in aliases[:2]
                            )
                            if len(aliases) > 2:
                                alias_text += f" (+{len(aliases) - 2})"
                            display_cmd += f" [{alias_text}]"
                        elif isinstance(aliases, str):
                            display_cmd += f" [{kernel.custom_prefix}{aliases}]"
                    cmd_display.append(display_cmd)

                cmd_text = ", ".join(cmd_display)
                if len(commands) > 3:
                    cmd_text += f" (+{len(commands) - 3})"

                if inline_commands:
                    inline_emoji = (
                        '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
                    )
                    inline_cmds = ", ".join(
                        f"{inline_emoji} <code>{cmd}</code>"
                        for cmd, _ in inline_commands[:3]
                    )
                    if len(inline_commands) > 3:
                        inline_cmds += f" (+{len(inline_commands) - 3})"
                    cmd_text += f" {inline_cmds}"

                return f"<b>{display_name}</b>{hidden_mark}: {cmd_text}\n"
            elif inline_commands:
                inline_emoji = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
                inline_cmds = ", ".join(
                    f"{inline_emoji} <code>{cmd}</code>"
                    for cmd, _ in inline_commands[:3]
                )
                if len(inline_commands) > 3:
                    inline_cmds += f" (+{len(inline_commands) - 3})"
                return f"<b>{display_name}</b>{hidden_mark}: {inline_cmds}\n"
            else:
                no_cmd_emoji = '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>'
                return f"<b>{display_name}</b>{hidden_mark}: {no_cmd_emoji} <i>{s.get('no_commands', 'no commands')}</i>\n"

        def chunk_by_size(items: list, start_msg: str = "") -> list[list]:
            chunks = []
            current_chunk = []
            current_len = len(start_msg)

            for item in items:
                line = render_module_line(item)
                line_len = len(line)

                if current_chunk and current_len + line_len > MAX_MSG_LENGTH:
                    chunks.append(current_chunk)
                    current_chunk = [item]
                    current_len = line_len
                else:
                    current_chunk.append(item)
                    current_len += line_len

            if current_chunk:
                chunks.append(current_chunk)
            return chunks

        sys_modules = sorted(filter_modules(list(kernel.system_modules.keys())))
        usr_modules = sorted(filter_modules(list(kernel.loaded_modules.keys())))

        if page == 0:
            header_len = len(
                f"{CUSTOM_EMOJI['crystal']} <b>{s['system_modules']}:</b> <code>{len(sys_modules)}</code><blockquote expandable>\n</blockquote>"
            )
            sys_chunks = chunk_by_size(sys_modules, " " * header_len)
        else:
            sys_chunks = [[]]

        usr_chunks = chunk_by_size(usr_modules)
        total_pages = len(sys_chunks) + len(usr_chunks)

        if page < len(sys_chunks):
            msg = f"{CUSTOM_EMOJI['crystal']} <b>{s['system_modules']}:</b> <code>{len(sys_modules)}</code>"
            if len(sys_chunks) > 1:
                msg += f" ({page + 1}/{len(sys_chunks)})"
            msg += "<blockquote expandable>"
            for name in sys_chunks[page]:
                msg += render_module_line(name)
            msg += "</blockquote>"
        else:
            usr_page = page - len(sys_chunks)
            current_chunk = usr_chunks[usr_page] if usr_page < len(usr_chunks) else []

            msg = f"{CUSTOM_EMOJI['crystal']} <b>{s['user_modules_page'].format(page=usr_page + 1, count=len(usr_modules))}:</b>"
            if len(usr_chunks) > 1:
                msg += f" ({usr_page + 1}/{len(usr_chunks)})"
            msg += "<blockquote expandable>"
            for name in current_chunk:
                msg += render_module_line(name)
            msg += "</blockquote>"

        buttons = []
        page_buttons = []

        prev_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        if page_cb:
            page_buttons.append(
                self.Button.inline("<", page_cb, args=[prev_page], ttl=ttl)
            )
        else:
            page_buttons.append(Button.inline("<", data=f"man_page_{prev_page}"))

        max_page_buttons = 7
        if total_pages <= max_page_buttons:
            for i in range(total_pages):
                text = "•" if i == page else str(i + 1)
                if page_cb:
                    page_buttons.append(
                        self.Button.inline(text, page_cb, args=[i], ttl=ttl)
                    )
                else:
                    page_buttons.append(Button.inline(text, data=f"man_page_{i}"))
        else:
            start_idx = max(0, page - 3)
            end_idx = min(total_pages, start_idx + max_page_buttons)
            if end_idx - start_idx < max_page_buttons:
                start_idx = max(0, end_idx - max_page_buttons)

            if start_idx > 0:
                if page_cb:
                    page_buttons.append(
                        self.Button.inline("1", page_cb, args=[0], ttl=ttl)
                    )
                else:
                    page_buttons.append(Button.inline("1", data="man_page_0"))
                if start_idx > 1:
                    page_buttons.append(Button.inline("...", data="noop"))

            for i in range(start_idx, end_idx):
                text = "•" if i == page else str(i + 1)
                if page_cb:
                    page_buttons.append(
                        self.Button.inline(text, page_cb, args=[i], ttl=ttl)
                    )
                else:
                    page_buttons.append(Button.inline(text, data=f"man_page_{i}"))

            if end_idx < total_pages:
                if end_idx < total_pages - 1:
                    page_buttons.append(Button.inline("...", data="noop"))
                if page_cb:
                    page_buttons.append(
                        self.Button.inline(
                            str(total_pages),
                            page_cb,
                            args=[total_pages - 1],
                            ttl=ttl,
                            allow_user=None,
                        )
                    )
                else:
                    page_buttons.append(
                        Button.inline(
                            str(total_pages), data=f"man_page_{total_pages - 1}"
                        )
                    )

        if page_cb:
            page_buttons.append(
                self.Button.inline(">", page_cb, args=[next_page], ttl=ttl)
            )
        else:
            page_buttons.append(Button.inline(">", data=f"man_page_{next_page}"))

        buttons.append(page_buttons)

        if close_cb:
            buttons.append([self.Button.inline("❌ " + s["close"], close_cb, ttl=ttl)])
        else:
            buttons.append([Button.inline("❌ " + s["close"], data="man_close")])

        return msg, buttons

    @command(
        "man",
        doc_ru="<name/None> показать информацию о модуле или список модулей",
        doc_en="<name/None> show module info or list modules",
    )
    async def cmd_man(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).split()
            show_hidden = "-f" in args
            clean_args = [a for a in args if a != "-f"]

            if not clean_args:
                try:
                    success, sent = await self.kernel.inline_query_and_click(
                        chat_id=event.chat_id,
                        query="man",
                        reply_to=event.reply_to_msg_id,
                    )
                    if not success:
                        await self.edit(event, self.strings["no_inline_results"])
                        return
                    else:
                        await self.client.delete_messages(event.chat_id, [event.id])
                        await sent.click(1)

                    if self.config.get("man_invert_media", False):
                        try:
                            hidden = await self._get_hidden_modules()
                            page_msg, page_buttons = self._get_paginated_data(
                                0,
                                hidden_list=hidden,
                                show_hidden=show_hidden,
                                page_cb=self._man_page_cb,
                                close_cb=self._man_close_cb,
                            )
                            page_msg = self._add_inline_banner_preview(page_msg)
                            sent_id = (
                                sent[0].id
                                if isinstance(sent, list) and sent
                                else getattr(sent, "id", None)
                            )
                            if sent_id:
                                await self.client.edit_message(
                                    event.chat_id,
                                    sent_id,
                                    page_msg,
                                    buttons=page_buttons,
                                    parse_mode="html",
                                    invert_media=True,
                                )
                        except Exception:
                            pass

                except Exception as e:
                    await self.kernel.handle_error(e, source="man_inline", event=event)
                    await self.edit(event, f"{self.strings['error']}: {str(e)[:100]}")
            else:
                search_term = " ".join(clean_args)
                msg, banner_url = await self._generate_detailed_page(
                    search_term, show_hidden=show_hidden
                )
                if banner_url and banner_url.startswith(("http://", "https://")):
                    try:
                        media = InputMediaWebPage(banner_url, optional=True)
                        await self.edit(
                            event, msg, file=media, parse_mode="html", invert_media=True
                        )
                    except Exception as e:
                        await self.kernel.handle_error(e, source="man_banner")
                        await self.edit(event, msg, parse_mode="html")
                else:
                    await self.edit(event, msg, parse_mode="html")

        except Exception as e:
            await self.kernel.handle_error(e, source="man", event=event)

    @command(
        "manhide",
        doc_ru="<name> скрыть модуль из списка man",
        doc_en="<name> hide module from man list",
    )
    async def cmd_manhide(self, event: events.NewMessage.Event) -> None:
        try:
            module_name = self.args_raw(event).strip()
            if not module_name:
                await self.edit(event, self.strings["manhide_usage"], parse_mode="html")
                return
            s = self.strings

            all_modules = set(self.kernel.system_modules.keys()) | set(
                self.kernel.loaded_modules.keys()
            )
            if module_name not in all_modules:
                matches = [m for m in all_modules if module_name.lower() in m.lower()]
                if len(matches) == 1:
                    module_name = matches[0]
                else:
                    await self.edit(
                        event,
                        f"{CUSTOM_EMOJI['blocked']} {s['module_not_found']}",
                        parse_mode="html",
                    )
                    return

            hidden = await self._get_hidden_modules()
            if module_name in hidden:
                await self.edit(event, s["module_already_hidden"], parse_mode="html")
                return

            hidden.append(module_name)
            await self._save_hidden_modules(hidden)
            await self.edit(
                event,
                f"{s['module_hidden']}\n<code>{module_name}</code>",
                parse_mode="html",
            )
        except Exception as e:
            await self.kernel.handle_error(e, source="manhide", event=event)

    @command(
        "manunhide",
        doc_ru="<name> показать модуль в списке man",
        doc_en="<name> unhide module from man list",
    )
    async def cmd_manunhide(self, event: events.NewMessage.Event) -> None:
        try:
            module_name = self.args_raw(event).strip()
            if not module_name:
                await self.edit(
                    event, self.strings["manunhide_usage"], parse_mode="html"
                )
                return
            s = self.strings

            hidden = await self._get_hidden_modules()

            if module_name not in hidden:
                matches = [m for m in hidden if module_name.lower() in m.lower()]
                if len(matches) == 1:
                    module_name = matches[0]
                else:
                    await self.edit(event, s["module_not_hidden"], parse_mode="html")
                    return

            hidden.remove(module_name)
            await self._save_hidden_modules(hidden)
            await self.edit(
                event,
                f"{s['module_unhidden']}\n<code>{module_name}</code>",
                parse_mode="html",
            )
        except Exception as e:
            await self.kernel.handle_error(e, source="manunhide", event=event)

    @command("help", doc_ru="перенаправляет на man", doc_en="redirects to man")
    async def cmd_help(self, event: events.NewMessage.Event) -> None:
        await self.edit(
            event,
            f"<b>{self.strings['help_not_command']}</b><code>{self.kernel.custom_prefix}man?</code>",
            parse_mode="html",
        )

    @inline("man")
    async def inline_man(self, event) -> None:
        query = event.text.strip()
        s = self.strings

        if query == "man":
            thumb1 = InputWebDocument(
                url="https://kappa.lol/6plQLz",
                size=0,
                mime_type="image/jpeg",
                attributes=[DocumentAttributeImageSize(w=0, h=0)],
            )
            hidden = await self._get_hidden_modules()
            msg1, buttons = self._get_paginated_data(
                0,
                hidden_list=hidden,
                page_cb=self._man_page_cb,
                close_cb=self._man_close_cb,
            )
            article1 = event.builder.article(
                title="Module Manager",
                description="Browse all modules",
                text=self._add_inline_banner_preview(msg1),
                buttons=buttons,
                parse_mode="html",
                thumb=thumb1,
            )

            thumb2 = InputWebDocument(
                url="https://kappa.lol/wujauv",
                size=0,
                mime_type="image/jpeg",
                attributes=[DocumentAttributeImageSize(w=0, h=0)],
            )
            article2 = event.builder.article(
                title="Search Modules",
                description="Type 'man [name]' to search",
                text=f"<b>{s['search_hint']}</b>",
                parse_mode="html",
                thumb=thumb2,
            )

            await event.answer([article1, article2])
            return

        if query.startswith("man "):
            search_term = query[4:].strip()
            if search_term:
                try:
                    (
                        exact_matches,
                        similar_modules,
                    ) = await self._search_modules_for_inline(search_term)
                    articles = []

                    if exact_matches or similar_modules:
                        thumb_search = InputWebDocument(
                            url="https://kappa.lol/LOuqBO",
                            size=0,
                            mime_type="image/jpeg",
                            attributes=[DocumentAttributeImageSize(w=0, h=0)],
                        )

                        result_count = len(exact_matches) + len(similar_modules)
                        search_header = event.builder.article(
                            title=f"Search: {search_term}",
                            description=f"Found {result_count} modules",
                            text=f'<b>🔍 {s["search_results"]}: "{search_term}"</b>\n'
                            f"<i>Найдено {result_count} модулей</i>\n\n",
                            parse_mode="html",
                            thumb=thumb_search,
                        )
                        articles.append(search_header)

                        for module_info in exact_matches[:10]:
                            name, typ, _ = module_info
                            msg = await self._generate_module_article(module_info)
                            thumb_module = InputWebDocument(
                                url="https://kappa.lol/POFDmQ",
                                size=0,
                                mime_type="image/jpeg",
                                attributes=[DocumentAttributeImageSize(w=0, h=0)],
                            )
                            article = event.builder.article(
                                title=f"📦 {name}",
                                description="Exact match",
                                text=msg,
                                parse_mode="html",
                                thumb=thumb_module,
                            )
                            articles.append(article)

                        for module_info in similar_modules[:10]:
                            name, _typ, _ = module_info
                            msg = await self._generate_module_article(module_info)
                            thumb_module = InputWebDocument(
                                url="https://kappa.lol/POFDmQ",
                                size=0,
                                mime_type="image/jpeg",
                                attributes=[DocumentAttributeImageSize(w=0, h=0)],
                            )
                            article = event.builder.article(
                                title=f"🔍 {name}",
                                description="Similar match",
                                text=msg,
                                parse_mode="html",
                                thumb=thumb_module,
                            )
                            articles.append(article)

                    else:
                        thumb_not_found = InputWebDocument(
                            url="https://kappa.lol/N5jMQR",
                            size=0,
                            mime_type="image/jpeg",
                            attributes=[DocumentAttributeImageSize(w=0, h=0)],
                        )
                        not_found_article = event.builder.article(
                            title="Module not found",
                            description=f"No results for '{search_term}'",
                            text=f"<b>{CUSTOM_EMOJI['blocked']} {s['module_not_found']}</b>\n\n"
                            f'<i>По запросу "{search_term}" ничего не найдено.</i>\n'
                            f"{s['not_found_hint']}",
                            parse_mode="html",
                            thumb=thumb_not_found,
                        )
                        articles.append(not_found_article)

                    await event.answer(articles[:50])
                    return

                except Exception as e:
                    thumb_error = InputWebDocument(
                        url="https://kappa.lol/N5jMQR",
                        size=0,
                        mime_type="image/jpeg",
                        attributes=[DocumentAttributeImageSize(w=0, h=0)],
                    )
                    error_article = event.builder.article(
                        title=s["search_error"],
                        description=s["search_error_desc"],
                        text=f"<b>{CUSTOM_EMOJI['blocked']} {s['error']}</b>\n\n"
                        f"<code>{str(e)[:200]}</code>",
                        parse_mode="html",
                        thumb=thumb_error,
                    )
                    await event.answer([error_article])
                    return

        builder = event.builder.article(
            title="Module Manager",
            description="Type 'man' or 'man [module]'",
            text=f"{CUSTOM_EMOJI['crystal']} <b>{s['module_manager']}</b>",
            parse_mode="html",
        )
        await event.answer([builder])

    async def _search_modules_for_inline(
        self, search_term: str, show_hidden: bool = False
    ) -> tuple[list, list]:
        search_term = search_term.lower().strip()
        hidden = await self._get_hidden_modules()
        all_modules = self._gather_all_modules(show_hidden, hidden)

        search_words = search_term.split()
        concatenated = "".join(search_words)
        underscored = "_".join(search_words)
        camel_cased = "".join(w.capitalize() for w in search_words)

        scored_modules: list[tuple[int, tuple]] = []

        for name, (typ, module) in all_modules.items():
            name_lower = name.lower()
            score = 0

            if name_lower == search_term:
                scored_modules.append((1000, (name, typ, module)))
                continue

            if name_lower.startswith(search_term):
                score += 500
            elif search_term in name_lower:
                score += 300
            elif concatenated in name_lower:
                score += 250
            elif underscored in name_lower or camel_cased.lower() in name_lower:
                score += 220
            else:
                words = search_words
                if all(w in name_lower for w in words):
                    score += 200

            if score > 0:
                scored_modules.append((score, (name, typ, module)))
                continue

            commands, _, _descriptions = self._get_module_commands(name)
            cmd_match = False
            for cmd in commands:
                cmd_lower = cmd.lower()
                if cmd_lower == search_term:
                    scored_modules.append((900, (name, typ, module)))
                    cmd_match = True
                    break
                elif cmd_lower.startswith(search_term):
                    score = 600
                elif concatenated in cmd_lower:
                    score = 550
                elif underscored in cmd_lower or camel_cased.lower() in cmd_lower:
                    score = 520
                elif search_term in cmd_lower:
                    score = 400

                if score > 0:
                    scored_modules.append((score, (name, typ, module)))
                    cmd_match = True
                    break
            if cmd_match:
                continue

            metadata = await self._load_module_metadata(name, typ)

            desc = metadata.get("description", "").lower()
            if desc and search_term in desc:
                scored_modules.append((100, (name, typ, module)))
                continue

            for cmd, cmd_desc in metadata.get("commands", {}).items():
                if (
                    cmd_desc
                    and isinstance(cmd_desc, str)
                    and search_term in cmd_desc.lower()
                ):
                    scored_modules.append((50, (name, typ, module)))
                    break

        scored_modules.sort(key=lambda x: -x[0])
        seen = set()
        exact_matches = []
        similar_modules = []
        for score, (name, typ, module) in scored_modules:
            if name in seen:
                continue
            seen.add(name)
            if score >= 900:
                exact_matches.append((name, typ, module))
            else:
                similar_modules.append((name, typ, module))

        return exact_matches, similar_modules

    async def _generate_module_article(self, module_info: tuple) -> str:
        name, typ, _module = module_info
        s = self.strings
        commands, _aliases_info, descriptions = self._get_module_commands(name)
        metadata = await self._load_module_metadata(name, typ)

        msg = f"<blockquote>{CUSTOM_EMOJI['dna']} <b>{s['module']}</b> <code>{name}</code></blockquote>\n"
        msg += f"<blockquote expandable>{CUSTOM_EMOJI['alembic']} <b>{s['description']}:</b> <i>{metadata.get('description', s['no_description'])}</i>\n</blockquote>"

        if commands:
            msg += f"\n<b>{s['command']}:</b>\n"
            msg += "<blockquote expandable>"
            for cmd in commands[:5]:
                cmd_desc = (
                    descriptions.get(cmd)
                    or metadata.get("commands", {}).get(cmd)
                    or f"{CUSTOM_EMOJI['confused']} {s['no_description']}"
                )
                msg += f"• <code>{self.kernel.custom_prefix}{cmd}</code> - {cmd_desc}\n"
            if len(commands) > 5:
                msg += f"... {s['and_more_commands'].format(count=len(commands) - 5)}\n"
        else:
            msg += f"\n{CUSTOM_EMOJI['blocked']} {s['no_commands']}\n"
        msg += "</blockquote>"

        msg += f"\n<blockquote>{CUSTOM_EMOJI['snowflake']} <b>{s['version']}:</b> <code>{metadata.get('version', '1.0.0')}</code>"
        msg += f"\n{CUSTOM_EMOJI['pancake']} <b>{s['author']}:</b> <i>{metadata.get('author', s['unknown'])}</i></blockquote>"

        if typ == "system":
            msg += f"\n<blockquote>{s['system_module_note']}</blockquote>"

        return msg
