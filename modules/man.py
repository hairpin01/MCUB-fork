# requires: re, math
# author: @Hairpin00
# version: 1.1.0
# description: Module manager
from telethon import Button
import re
import asyncio
from html import escape
import math
import json
from telethon.tl.types import (
    InputWebDocument,
    DocumentAttributeImageSize,
    InputMediaWebPage,
)

from core.lib.loader.module_config import (
    ModuleConfig,
    ConfigValue,
    String,
    Boolean,
)

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


def get_module_commands(module_name, kernel):
    return kernel._loader.get_module_commands(module_name)


async def get_hidden_modules(kernel):
    """Получить список скрытых модулей из БД."""
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
    """Сохранить список скрытых модулей в БД."""
    await kernel.db_set("man", "hidden_modules", json.dumps(hidden))


async def generate_detailed_page(search_term, kernel, strings, show_hidden=False):
    """
    Найти модуль по search_term.
    Если точное совпадение — вернуть его страницу.
    Если частичных совпадений ровно одно — показать его напрямую.
    Если несколько — показать список похожих.
    """
    search_term_clean = search_term.lower()
    exact_match = None
    similar_modules = []

    hidden = await get_hidden_modules(kernel)

    all_modules = {}
    for name, module in kernel.system_modules.items():
        all_modules[name] = ("system", module)
    for name, module in kernel.loaded_modules.items():
        all_modules[name] = ("user", module)

    if not show_hidden:
        all_modules = {k: v for k, v in all_modules.items() if k not in hidden}

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
    """Построить детальную страницу модуля."""
    name, typ, module = match_tuple
    commands, aliases_info, descriptions = get_module_commands(name, kernel)
    file_path = (
        f"{kernel.MODULES_DIR}/{name}.py"
        if typ == "system"
        else f"{kernel.MODULES_LOADED_DIR}/{name}.py"
    )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
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

    msg = f"{CUSTOM_EMOJI['dna']} <b>{strings['module']}</b> <code>{name}</code>:\n"
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
    return msg, metadata.get("banner_url")


def get_paginated_data(kernel, page, strings, hidden_list=None, show_hidden=False):
    CHUNK_SIZE = 10
    if hidden_list is None:
        hidden_list = []

    def filter_modules(names):
        if show_hidden:
            return names
        return [n for n in names if n not in hidden_list]

    sys_modules = sorted(filter_modules(list(kernel.system_modules.keys())))
    usr_modules = sorted(filter_modules(list(kernel.loaded_modules.keys())))

    user_pages_count = math.ceil(len(usr_modules) / CHUNK_SIZE) if usr_modules else 0
    total_pages = 1 + user_pages_count

    def render_module_line(name):
        commands, aliases_info, _ = get_module_commands(name, kernel)
        hidden_mark = (
            f" {CUSTOM_EMOJI['eye_off']}"
            if (show_hidden and name in hidden_list)
            else ""
        )
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

            inline_commands = kernel.get_module_inline_commands(name)
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

            return f"<b>{name}</b>{hidden_mark}: {cmd_text}\n"
        return None

    if page == 0:
        msg = f"{CUSTOM_EMOJI['crystal']} <b>{strings['system_modules']}:</b> <code>{len(sys_modules)}</code>\n\n"
        msg += "<blockquote expandable>"
        for name in sys_modules:
            line = render_module_line(name)
            if line:
                msg += line
        msg += "</blockquote>"
    else:
        start_idx = (page - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        current_chunk = usr_modules[start_idx:end_idx]

        msg = f"{CUSTOM_EMOJI['crystal']} <b>{strings['user_modules_page'].format(page=page, count=len(usr_modules))}:</b>\n"
        msg += "<blockquote expandable>"
        for name in current_chunk:
            line = render_module_line(name)
            if line:
                msg += line
        msg += "</blockquote>"

    buttons = []
    page_buttons = []
    for i in range(total_pages):
        text = "•" if i == page else str(i + 1)
        page_buttons.append(Button.inline(text, data=f"man_page_{i}"))

    buttons.append(page_buttons)
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
            "user_modules_page": "Пользовательские модули (Страница {page}/<code>{count}</code>)",
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
            "module_unhidden": f"✅ <b>Модуль убран из скрытых.</b>",
            "module_not_hidden": f"{CUSTOM_EMOJI['blocked']} Этот модуль не скрыт.",
            "manhide_usage": f"{CUSTOM_EMOJI['confused']} Использование: <code>.manhide [модуль]</code>",
            "manunhide_usage": f"{CUSTOM_EMOJI['confused']} Использование: <code>.manunhide [модуль]</code>",
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
            "user_modules_page": "User modules (Page {page}/<code>{count}</code>)",
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
            "module_unhidden": f"✅ <b>Module removed from hidden.</b>",
            "module_not_hidden": f"{CUSTOM_EMOJI['blocked']} This module is not hidden.",
            "manhide_usage": f"{CUSTOM_EMOJI['confused']} Usage: <code>.manhide [module]</code>",
            "manunhide_usage": f"{CUSTOM_EMOJI['confused']} Usage: <code>.manunhide [module]</code>",
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

    async def search_modules_for_inline(
        search_term, kernel, strings, show_hidden=False
    ):
        """Поиск модулей для inline режима."""
        search_term = search_term.lower().strip()
        hidden = await get_hidden_modules(kernel)

        all_modules = {}
        for name, module in kernel.system_modules.items():
            all_modules[name] = ("system", module)
        for name, module in kernel.loaded_modules.items():
            all_modules[name] = ("user", module)

        if not show_hidden:
            all_modules = {k: v for k, v in all_modules.items() if k not in hidden}

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

            commands, _, descriptions = get_module_commands(name, kernel)
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

            try:
                file_path = (
                    f"{kernel.MODULES_DIR}/{name}.py"
                    if typ == "system"
                    else f"{kernel.MODULES_LOADED_DIR}/{name}.py"
                )
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                metadata = await kernel.get_module_metadata(code)
            except Exception:
                metadata = {"description": "", "commands": {}}

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
        """Генерирует статью для одного модуля."""
        name, typ, module = module_info
        commands, aliases_info, descriptions = get_module_commands(name, kernel)
        file_path = (
            f"modules/{name}.py" if typ == "system" else f"modules_loaded/{name}.py"
        )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
                metadata = await kernel.get_module_metadata(code)
        except Exception:
            metadata = {
                "commands": {},
                "description": strings["no_description"],
                "version": "?.?.?",
                "author": strings["unknown"],
            }

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
                kernel, 0, lang_strings, hidden_list=hidden
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

    async def man_callback_handler(event):
        data = event.data.decode()

        if data == "man_close":
            try:
                await kernel.client.delete_messages(event.chat_id, [event.message_id])
            except Exception:
                await event.answer(lang_strings["closed"], alert=False)

        elif data.startswith("man_page_"):
            try:
                page = int(data.split("_")[-1])
                hidden = await get_hidden_modules(kernel)
                msg, buttons = get_paginated_data(
                    kernel, page, lang_strings, hidden_list=hidden
                )
                invert_media = (
                    get_config().get("man_invert_media", False)
                    if get_config()
                    else False
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

    @kernel.register.command("man")
    # [module/-f] — info about module or list (-f shows hidden)
    async def man_handler(event):
        try:
            args = event.text.split()

            # Parse flags
            show_hidden = "-f" in args
            clean_args = [a for a in args[1:] if a != "-f"]

            if not clean_args:
                bot_username = kernel.config.get("inline_bot_username")
                if not bot_username:
                    await event.edit(
                        f"{CUSTOM_EMOJI['blocked']} <b>{lang_strings['inline_bot_not_configured']}</b>",
                        parse_mode="html",
                    )
                    return

                await event.delete()

                try:
                    results = await client.inline_query(bot_username, "man")
                    if results:
                        sent = await results[0].click(
                            event.chat_id, reply_to=event.reply_to_msg_id
                        )

                        if get_config().get("man_invert_media", False):
                            try:
                                hidden = await get_hidden_modules(kernel)
                                page_msg, page_buttons = get_paginated_data(
                                    kernel,
                                    0,
                                    lang_strings,
                                    hidden_list=hidden,
                                    show_hidden=show_hidden,
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
                    else:
                        await client.send_message(
                            event.chat_id, lang_strings["no_inline_results"]
                        )
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

    @kernel.register.command("manhide")
    # hide module from .man list
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

    @kernel.register.command("manunhide")
    # unhide module from hidden
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

    @kernel.register.command("help")
    async def help_cmd(event):
        """fallback"""
        await event.edit(
            f"<b>{lang_strings['help_not_command']}</b><code>{kernel.custom_prefix}man?</code>",
            parse_mode="html",
        )

    kernel.register_inline_handler("man", man_inline_handler)
    kernel.register_callback_handler("man_", man_callback_handler)
