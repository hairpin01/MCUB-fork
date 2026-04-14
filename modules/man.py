# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import json
import os
from html import escape

# author: @Hairpin00
# version: 1.1.0
# description: Module manager / Менеджер модулей
from telethon import Button
from telethon.tl.types import (
    DocumentAttributeImageSize,
    InputMediaWebPage,
    InputWebDocument,
)

from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    ModuleConfig,
    String,
)
from core_inline.api.inline import make_cb_button

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


# Cache module metadata keyed by file path and mtime
_METADATA_CACHE: dict[str, tuple[float, dict]] = {}
_METADATA_LOCKS: dict[int, asyncio.Lock] = {}


def _get_metadata_lock() -> asyncio.Lock:
    """Return a lock bound to the current event loop."""
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


def get_module_commands(module_name, kernel, lang=None):
    if lang is None:
        lang = kernel.config.get("language", "ru")
    return kernel._loader.get_module_commands(module_name, lang)


def resolve_module_path(name: str, typ: str, kernel) -> str:
    """Return module file path (system or user)."""
    if typ == "system":
        return f"{kernel.MODULES_DIR}/{name}.py"

    # Check for package directory (archive modules with local imports)
    package_dir = f"{kernel.MODULES_LOADED_DIR}/{name}"
    if os.path.isdir(package_dir):
        init_file = os.path.join(package_dir, "__init__.py")
        if os.path.exists(init_file):
            return init_file

    return f"{kernel.MODULES_LOADED_DIR}/{name}.py"

    # Search for class-style modules by class attribute "name = '...'"
    try:
        for fname in os.listdir(kernel.MODULES_LOADED_DIR):
            fpath = os.path.join(kernel.MODULES_LOADED_DIR, fname)
            if not (os.path.isfile(fpath) and fname.endswith(".py")):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    code = f.read()
                pattern = (
                    r'class\s+\w+\s*\([^)]*\):[^}]*?name\s*=\s*["\']([^"\']+)["\']'
                )
                for match in re.finditer(pattern, code, re.DOTALL):
                    if match.group(1) == name:
                        return fpath
            except:
                pass
    except OSError:
        pass

    return default_path


async def load_module_metadata(name: str, typ: str, kernel, strings) -> dict:
    """Load and cache module metadata keyed by file mtime."""

    file_path = resolve_module_path(name, typ, kernel)

    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return {
            "commands": {},
            "description": strings["no_description"],
            "version": "?.?.?",
            "author": strings["unknown"],
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
        metadata = await kernel.get_module_metadata(code)
    except Exception:
        metadata = {
            "commands": {},
            "description": strings["no_description"],
            "version": "?.?.?",
            "author": strings["unknown"],
            "banner_url": None,
        }

    async with lock:
        _METADATA_CACHE[file_path] = (mtime, metadata)

    return metadata


def gather_all_modules(
    kernel, show_hidden: bool, hidden: list[str]
) -> dict[str, tuple[str, object]]:
    """Collect system and user modules into one dict."""

    all_modules: dict[str, tuple[str, object]] = {}
    for name, module in kernel.system_modules.items():
        all_modules[name] = ("system", module)
    for name, module in kernel.loaded_modules.items():
        all_modules[name] = ("user", module)

    if not show_hidden:
        all_modules = {k: v for k, v in all_modules.items() if k not in hidden}

    return all_modules


async def get_hidden_modules(kernel):
    """Fetch hidden modules list from DB."""
    data = await kernel.db_get("man", "hidden_modules")
    if not data:
        return []
    try:
        if isinstance(data, str):
            return json.loads(data)
        return json.loads(str(data))
    except Exception:
        return []


async def save_hidden_modules(kernel, hidden):
    """Persist hidden modules list to DB."""
    await kernel.db_set("man", "hidden_modules", json.dumps(hidden))


async def generate_detailed_page(search_term, kernel, strings, show_hidden=False):
    """Build detail page or search list for a module name/substring."""
    search_term_clean = search_term.lower()
    exact_match = None
    similar_modules = []

    hidden = await get_hidden_modules(kernel)

    all_modules = gather_all_modules(kernel, show_hidden, hidden)

    for name, (typ, module) in all_modules.items():
        if name.lower() == search_term_clean:
            exact_match = (name, typ, module)
            break

    if exact_match:
        return await _build_module_detail(exact_match, kernel, strings)

    seen = set()
    for name, (typ, module) in all_modules.items():
        if search_term_clean in name.lower():
            if name not in seen:
                similar_modules.append((name, typ, module))
                seen.add(name)
        else:
            commands, _, _ = get_module_commands(name, kernel)
            for cmd in commands:
                if search_term_clean in cmd.lower():
                    if name not in seen:
                        similar_modules.append((name, typ, module))
                        seen.add(name)
                    break

    if len(similar_modules) == 1:
        return await _build_module_detail(similar_modules[0], kernel, strings)

    if similar_modules:
        msg = f"{CUSTOM_EMOJI['crystal']} <b>{strings['found_modules']}:</b>\n<blockquote expandable>"
        for name, typ, module in similar_modules[:5]:
            commands, _, _ = get_module_commands(name, kernel)
            hidden_mark = f" {CUSTOM_EMOJI['eye_off']}" if name in hidden else ""
            if commands:
                cmd_text = ", ".join(
                    [
                        f"<code>{kernel.custom_prefix}{cmd}</code>"
                        for cmd in commands[:2]
                    ]
                )
                msg += f"<b>{name}</b>{hidden_mark}: {cmd_text}\n"
        msg += "</blockquote>"
        if len(similar_modules) > 5:
            msg += f"... {strings['and_more'].format(count=len(similar_modules) - 5)} {CUSTOM_EMOJI['tot']}\n"
        msg += f"\n<blockquote><i>{strings['no_exact_match']}</i> {CUSTOM_EMOJI['map']}</blockquote>"
    else:
        msg = f"<blockquote expandable>{CUSTOM_EMOJI['blocked']} {strings['module_not_found']}</blockquote>"
    return msg, None


async def _build_module_detail(match_tuple, kernel, strings):
    """Build a module detail page."""
    name, typ, _module = match_tuple

    class_instance = getattr(_module, "_class_instance", None)
    if class_instance is not None:
        display_name = getattr(type(class_instance), "name", name)
    else:
        display_name = name

    commands, aliases_info, descriptions = get_module_commands(name, kernel)
    metadata = await load_module_metadata(name, typ, kernel, strings)

    msg = f"{CUSTOM_EMOJI['dna']} <b>{strings['module']}</b> <code>{display_name}</code>:\n"
    msg += f"{CUSTOM_EMOJI['alembic']} <b>{strings['description']}:</b> <i>{metadata.get('description', strings['no_description'])}</i>\n"
    msg += f"{CUSTOM_EMOJI['snowflake']} <b>{strings['version']}:</b> <code>{metadata.get('version', '1.0.0')}</code>\n"
    msg += "<blockquote expandable>"
    if commands:
        for cmd in commands:
            cmd_desc = (
                descriptions.get(cmd)
                or metadata.get("commands", {}).get(cmd)
                or f"{CUSTOM_EMOJI['confused']} {strings['no_description']}"
            )
            msg += f"{CUSTOM_EMOJI['tot']} <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>"

            if cmd in aliases_info:
                aliases = aliases_info[cmd]
                if isinstance(aliases, str):
                    aliases = [aliases]
                if aliases:
                    alias_text = ", ".join(
                        [f"<code>{kernel.custom_prefix}{a}</code>" for a in aliases]
                    )
                    msg += f" | {strings['aliases']}: {alias_text}"
            msg += "\n"
    else:
        msg += f"{CUSTOM_EMOJI['blocked']} {strings['no_commands']}\n"
    msg += "</blockquote>"

    inline_commands = kernel.get_module_inline_commands(name)
    if inline_commands:
        inline_emoji = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
        msg += "<blockquote expandable>"
        for cmd, desc in inline_commands:
            if desc:
                msg += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code> – <b>{desc}</b>\n"
            else:
                msg += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code>\n"
        msg += "</blockquote>"

    msg += f"\n<blockquote>{CUSTOM_EMOJI['pancake']} <b>{strings['author']}:</b> <i>{metadata.get('author', strings['unknown'])}</i></blockquote>"
    if typ == "system":
        msg += f"\n<blockquote>{strings['system_module_note']}</blockquote>"
    return msg, metadata.get("banner_url")


def get_paginated_data(
    kernel,
    page,
    strings,
    hidden_list=None,
    show_hidden=False,
    *,
    page_cb=None,
    close_cb=None,
    ttl: int = 900,
):
    MAX_MSG_LENGTH = 2000
    if hidden_list is None:
        hidden_list = []

    def filter_modules(names):
        if show_hidden:
            return names
        return [n for n in names if n not in hidden_list]

    def render_module_line(name):
        module_obj = kernel.loaded_modules.get(name)
        class_instance = getattr(module_obj, "_class_instance", None)
        if class_instance is not None:
            display_name = getattr(type(class_instance), "name", name)
        else:
            display_name = name

        commands, aliases_info, _ = get_module_commands(name, kernel)
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
                            [
                                f"<code>{kernel.custom_prefix}{a}</code>"
                                for a in aliases[:2]
                            ]
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
                inline_emoji = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
                inline_cmds = ", ".join(
                    [
                        f"{inline_emoji} <code>{cmd}</code>"
                        for cmd, _ in inline_commands[:3]
                    ]
                )
                if len(inline_commands) > 3:
                    inline_cmds += f" (+{len(inline_commands) - 3})"
                cmd_text += f" {inline_cmds}"

            return f"<b>{display_name}</b>{hidden_mark}: {cmd_text}\n"
        elif inline_commands:
            inline_emoji = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
            inline_cmds = ", ".join(
                [f"{inline_emoji} <code>{cmd}</code>" for cmd, _ in inline_commands[:3]]
            )
            if len(inline_commands) > 3:
                inline_cmds += f" (+{len(inline_commands) - 3})"
            return f"<b>{display_name}</b>{hidden_mark}: {inline_cmds}\n"
        else:
            no_cmd_emoji = '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>'
            return f"<b>{display_name}</b>{hidden_mark}: {no_cmd_emoji} <i>{strings.get('no_commands', 'no commands')}</i>\n"

    def chunk_by_size(items, start_msg=""):
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
            f"{CUSTOM_EMOJI['crystal']} <b>{strings['system_modules']}:</b> <code>{len(sys_modules)}</code><blockquote expandable>\n</blockquote>"
        )
        sys_chunks = chunk_by_size(sys_modules, " " * header_len)
    else:
        sys_chunks = [[]]

    usr_chunks = chunk_by_size(usr_modules)
    total_pages = len(sys_chunks) + len(usr_chunks)

    if page < len(sys_chunks):
        msg = f"{CUSTOM_EMOJI['crystal']} <b>{strings['system_modules']}:</b> <code>{len(sys_modules)}</code>"
        if len(sys_chunks) > 1:
            msg += f" ({page + 1}/{len(sys_chunks)})"
        msg += "<blockquote expandable>"
        for name in sys_chunks[page]:
            msg += render_module_line(name)
        msg += "</blockquote>"
    else:
        usr_page = page - len(sys_chunks)
        current_chunk = usr_chunks[usr_page] if usr_page < len(usr_chunks) else []

        msg = f"{CUSTOM_EMOJI['crystal']} <b>{strings['user_modules_page'].format(page=usr_page + 1, count=len(usr_modules))}:</b>"
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
            make_cb_button(kernel, "<", page_cb, args=[prev_page], ttl=ttl)
        )
    else:
        page_buttons.append(Button.inline("<", data=f"man_page_{prev_page}"))

    max_page_buttons = 7
    if total_pages <= max_page_buttons:
        for i in range(total_pages):
            text = "•" if i == page else str(i + 1)
            if page_cb:
                page_buttons.append(
                    make_cb_button(kernel, text, page_cb, args=[i], ttl=ttl)
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
                    make_cb_button(kernel, "1", page_cb, args=[0], ttl=ttl)
                )
            else:
                page_buttons.append(Button.inline("1", data="man_page_0"))
            if start_idx > 1:
                page_buttons.append(Button.inline("...", data="noop"))

        for i in range(start_idx, end_idx):
            text = "•" if i == page else str(i + 1)
            if page_cb:
                page_buttons.append(
                    make_cb_button(kernel, text, page_cb, args=[i], ttl=ttl)
                )
            else:
                page_buttons.append(Button.inline(text, data=f"man_page_{i}"))

        if end_idx < total_pages:
            if end_idx < total_pages - 1:
                page_buttons.append(Button.inline("...", data="noop"))
            if page_cb:
                page_buttons.append(
                    make_cb_button(
                        kernel,
                        str(total_pages),
                        page_cb,
                        args=[total_pages - 1],
                        ttl=ttl,
                    )
                )
            else:
                page_buttons.append(
                    Button.inline(str(total_pages), data=f"man_page_{total_pages - 1}")
                )

    if page_cb:
        page_buttons.append(
            make_cb_button(kernel, ">", page_cb, args=[next_page], ttl=ttl)
        )
    else:
        page_buttons.append(Button.inline(">", data=f"man_page_{next_page}"))

    buttons.append(page_buttons)

    if close_cb:
        buttons.append(
            [make_cb_button(kernel, "❌ " + strings["close"], close_cb, ttl=ttl)]
        )
    else:
        buttons.append([Button.inline("❌ " + strings["close"], data="man_close")])

    return msg, buttons


def register(kernel):
    client = kernel.client
    language = kernel.config.get("language", "en")

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

    lang_strings = strings.get(language, strings["en"])

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

    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        if live_cfg:
            return live_cfg
        return config

    async def startup():
        config_dict = await kernel.get_module_config(
            __name__,
            {
                "man_quote_media": True,
                "man_banner_url": "",
                "man_invert_media": False,
            },
        )
        config.from_dict(config_dict)
        config_dict_clean = {k: v for k, v in config.to_dict().items() if v is not None}
        if config_dict_clean:
            await kernel.save_module_config(__name__, config_dict_clean)
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(startup())

    def add_inline_banner_preview(message_html):
        cfg = get_config()
        banner_url = cfg.get("man_banner_url") if cfg else ""
        quote_media = cfg.get("man_quote_media", False) if cfg else False
        if not (
            quote_media
            and isinstance(banner_url, str)
            and banner_url.startswith(("http://", "https://"))
        ):
            return message_html
        return f'<a href="{escape(banner_url, quote=True)}">{ZERO_WIDTH_CHAR}</a>{message_html}'

    async def _man_close_cb(event):
        try:
            await kernel.client.delete_messages(event.chat_id, [event.message_id])
        except Exception:
            await event.answer(lang_strings["closed"], alert=False)

    async def _man_page_cb(event, page: int):
        try:
            hidden = await get_hidden_modules(kernel)
            msg, buttons = get_paginated_data(
                kernel,
                page,
                lang_strings,
                hidden_list=hidden,
                page_cb=_man_page_cb,
                close_cb=_man_close_cb,
            )
            invert_media = (
                get_config().get("man_invert_media", False) if get_config() else False
            )
            try:
                await event.edit(
                    add_inline_banner_preview(msg),
                    buttons=buttons,
                    parse_mode="html",
                    invert_media=invert_media,
                )
            except TypeError:
                await event.edit(
                    add_inline_banner_preview(msg),
                    buttons=buttons,
                    parse_mode="html",
                )
        except Exception as e:
            await event.answer(
                f"{lang_strings['page_error']}: {str(e)[:50]}", alert=True
            )

    async def search_modules_for_inline(
        search_term, kernel, strings, show_hidden=False
    ):
        """Search modules for inline mode."""
        search_term = search_term.lower().strip()
        hidden = await get_hidden_modules(kernel)

        all_modules = gather_all_modules(kernel, show_hidden, hidden)

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

            commands, _, _descriptions = get_module_commands(name, kernel)
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

            metadata = await load_module_metadata(name, typ, kernel, strings)

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

    async def generate_module_article(module_info, kernel, strings):
        """Generate article for a single module (inline)."""
        name, typ, _module = module_info
        commands, _aliases_info, descriptions = get_module_commands(name, kernel)
        metadata = await load_module_metadata(name, typ, kernel, strings)

        msg = f"<blockquote>{CUSTOM_EMOJI['dna']} <b>{strings['module']}</b> <code>{name}</code></blockquote>\n"
        msg += f"<blockquote expandable>{CUSTOM_EMOJI['alembic']} <b>{strings['description']}:</b> <i>{metadata.get('description', strings['no_description'])}</i>\n</blockquote>"

        if commands:
            msg += f"\n<b>{strings['command']}:</b>\n"
            msg += "<blockquote expandable>"
            for cmd in commands[:5]:
                cmd_desc = (
                    descriptions.get(cmd)
                    or metadata.get("commands", {}).get(cmd)
                    or f"{CUSTOM_EMOJI['confused']} {strings['no_description']}"
                )
                msg += f"• <code>{kernel.custom_prefix}{cmd}</code> - {cmd_desc}\n"
            if len(commands) > 5:
                msg += f"... {strings['and_more_commands'].format(count=len(commands) - 5)}\n"
        else:
            msg += f"\n{CUSTOM_EMOJI['blocked']} {strings['no_commands']}\n"
        msg += "</blockquote>"

        msg += f"\n<blockquote>{CUSTOM_EMOJI['snowflake']} <b>{strings['version']}:</b> <code>{metadata.get('version', '1.0.0')}</code>"
        msg += f"\n{CUSTOM_EMOJI['pancake']} <b>{strings['author']}:</b> <i>{metadata.get('author', strings['unknown'])}</i></blockquote>"

        if typ == "system":
            msg += f"\n<blockquote>{strings['system_module_note']}</blockquote>"

        return msg

    async def man_inline_handler(event):
        query = event.text.strip()

        if query == "man":
            thumb1 = InputWebDocument(
                url="https://kappa.lol/6plQLz",
                size=0,
                mime_type="image/jpeg",
                attributes=[DocumentAttributeImageSize(w=0, h=0)],
            )
            hidden = await get_hidden_modules(kernel)
            msg1, buttons = get_paginated_data(
                kernel,
                0,
                lang_strings,
                hidden_list=hidden,
                page_cb=_man_page_cb,
                close_cb=_man_close_cb,
            )
            article1 = event.builder.article(
                title="Module Manager",
                description="Browse all modules",
                text=add_inline_banner_preview(msg1),
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
                text=f"<b>{lang_strings['search_hint']}</b>",
                parse_mode="html",
                thumb=thumb2,
            )

            await event.answer([article1, article2])
            return

        if query.startswith("man "):
            search_term = query[4:].strip()
            if search_term:
                try:
                    exact_matches, similar_modules = await search_modules_for_inline(
                        search_term, kernel, lang_strings
                    )

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
                            text=f'<b>🔍 {lang_strings["search_results"]}: "{search_term}"</b>\n'
                            f"<i>Найдено {result_count} модулей</i>\n\n",
                            parse_mode="html",
                            thumb=thumb_search,
                        )
                        articles.append(search_header)

                        for module_info in exact_matches[:10]:
                            name, typ, _ = module_info
                            msg = await generate_module_article(
                                module_info, kernel, lang_strings
                            )
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
                            msg = await generate_module_article(
                                module_info, kernel, lang_strings
                            )
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
                            text=f"<b>{CUSTOM_EMOJI['blocked']} {lang_strings['module_not_found']}</b>\n\n"
                            f'<i>По запросу "{search_term}" ничего не найдено.</i>\n'
                            f"{lang_strings['not_found_hint']}",
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
                        title=lang_strings["search_error"],
                        description=lang_strings["search_error_desc"],
                        text=f"<b>{CUSTOM_EMOJI['blocked']} {lang_strings['error']}</b>\n\n"
                        f"<code>{str(e)[:200]}</code>",
                        parse_mode="html",
                        thumb=thumb_error,
                    )
                    await event.answer([error_article])
                    return

        builder = event.builder.article(
            title="Module Manager",
            description="Type 'man' or 'man [module]'",
            text=f"{CUSTOM_EMOJI['crystal']} <b>{lang_strings['module_manager']}</b>",
            parse_mode="html",
        )
        await event.answer([builder])

    @kernel.register.command(
        "man",
        doc_en="<name/None> show module info or list modules",
        doc_ru="<name/None> показать информацию о модуле или список модулей",
    )
    async def man_handler(event):
        try:
            args = event.text.split()

            # Parse flags
            show_hidden = "-f" in args
            clean_args = [a for a in args[1:] if a != "-f"]

            if not clean_args:
                try:
                    success, sent = await kernel.inline_query_and_click(
                        chat_id=event.chat_id,
                        query="man",
                        reply_to=event.reply_to_msg_id,
                    )
                    if not success:
                        await event.edit(lang_strings["no_inline_results"])
                        return
                    else:
                        await event.delete()
                        await sent.click(1)

                    if get_config().get("man_invert_media", False):
                        try:
                            hidden = await get_hidden_modules(kernel)
                            page_msg, page_buttons = get_paginated_data(
                                kernel,
                                0,
                                lang_strings,
                                hidden_list=hidden,
                                show_hidden=show_hidden,
                                page_cb=_man_page_cb,
                                close_cb=_man_close_cb,
                            )
                            page_msg = add_inline_banner_preview(page_msg)
                            sent_id = (
                                sent[0].id
                                if isinstance(sent, list) and sent
                                else getattr(sent, "id", None)
                            )
                            if sent_id:
                                try:
                                    await client.edit_message(
                                        event.chat_id,
                                        sent_id,
                                        page_msg,
                                        buttons=page_buttons,
                                        parse_mode="html",
                                        invert_media=True,
                                    )
                                except TypeError:
                                    await client.edit_message(
                                        event.chat_id,
                                        sent_id,
                                        page_msg,
                                        buttons=page_buttons,
                                        parse_mode="html",
                                    )
                        except Exception:
                            pass

                except Exception as e:
                    await kernel.handle_error(e, source="man_inline", event=event)
                    await client.send_message(
                        event.chat_id, f"{lang_strings['error']}: {str(e)[:100]}"
                    )
            else:
                search_term = " ".join(clean_args)
                msg, banner_url = await generate_detailed_page(
                    search_term, kernel, lang_strings, show_hidden=show_hidden
                )
                if banner_url and banner_url.startswith(("http://", "https://")):
                    try:
                        media = InputMediaWebPage(banner_url, optional=True)
                        await event.edit(
                            msg, file=media, parse_mode="html", invert_media=True
                        )
                    except Exception as e:
                        await kernel.handle_error(e, source="man_banner")
                        await event.edit(msg, parse_mode="html")
                else:
                    await event.edit(msg, parse_mode="html")

        except Exception as e:
            await kernel.handle_error(e, source="man", event=event)

    @kernel.register.command(
        "manhide",
        doc_en="<name> hide module from man list",
        doc_ru="<name> скрыть модуль из списка man",
    )
    async def manhide_handler(event):
        try:
            args = event.text.split(maxsplit=1)
            if len(args) < 2:
                await event.edit(lang_strings["manhide_usage"], parse_mode="html")
                return

            module_name = args[1].strip()

            all_modules = set(kernel.system_modules.keys()) | set(
                kernel.loaded_modules.keys()
            )
            if module_name not in all_modules:
                matches = [m for m in all_modules if module_name.lower() in m.lower()]
                if len(matches) == 1:
                    module_name = matches[0]
                else:
                    await event.edit(
                        f"{CUSTOM_EMOJI['blocked']} {lang_strings['module_not_found']}",
                        parse_mode="html",
                    )
                    return

            hidden = await get_hidden_modules(kernel)
            if module_name in hidden:
                await event.edit(
                    lang_strings["module_already_hidden"], parse_mode="html"
                )
                return

            hidden.append(module_name)
            await save_hidden_modules(kernel, hidden)
            await event.edit(
                f"{lang_strings['module_hidden']}\n<code>{module_name}</code>",
                parse_mode="html",
            )
        except Exception as e:
            await kernel.handle_error(e, source="manhide", event=event)

    @kernel.register.command(
        "manunhide",
        doc_en="<name> unhide module from man list",
        doc_ru="<name> показать модуль в списке man",
    )
    async def manunhide_handler(event):
        try:
            args = event.text.split(maxsplit=1)
            if len(args) < 2:
                await event.edit(lang_strings["manunhide_usage"], parse_mode="html")
                return

            module_name = args[1].strip()

            hidden = await get_hidden_modules(kernel)

            if module_name not in hidden:
                matches = [m for m in hidden if module_name.lower() in m.lower()]
                if len(matches) == 1:
                    module_name = matches[0]
                else:
                    await event.edit(
                        lang_strings["module_not_hidden"], parse_mode="html"
                    )
                    return

            hidden.remove(module_name)
            await save_hidden_modules(kernel, hidden)
            await event.edit(
                f"{lang_strings['module_unhidden']}\n<code>{module_name}</code>",
                parse_mode="html",
            )
        except Exception as e:
            await kernel.handle_error(e, source="manunhide", event=event)

    @kernel.register.command(
        "help",
        doc_en="redirects to man",
        doc_ru="перенаправляет на man",
    )
    async def help_cmd(event):
        """Fallback help stub: redirect to man."""
        await event.edit(
            f"<b>{lang_strings['help_not_command']}</b><code>{kernel.custom_prefix}man?</code>",
            parse_mode="html",
        )

    kernel.register_inline_handler("man", man_inline_handler)
