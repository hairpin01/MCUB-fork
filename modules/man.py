# requires: telethon>=1.24, re, math
# author: @Hairpin00
# version: 1.0.5
# description: Module manager with localization support and enhanced inline
from telethon import events, Button
import re
import math
from telethon.tl.types import InputWebDocument, DocumentAttributeImageSize

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
}

def get_module_commands(module_name, kernel):
    commands = []
    aliases_info = {}

    for cmd, owner in kernel.command_owners.items():
        if owner == module_name:
            commands.append(cmd)

    if commands:
        for cmd in commands:
            cmd_aliases = []
            for alias, target in kernel.aliases.items():
                if target == cmd:
                    cmd_aliases.append(alias)
            if cmd_aliases:
                aliases_info[cmd] = cmd_aliases
        return commands, aliases_info

    file_path = None
    if module_name in kernel.system_modules:
        file_path = f"modules/{module_name}.py"
    elif module_name in kernel.loaded_modules:
        file_path = f"modules_loaded/{module_name}.py"

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

                patterns = [
                    r"@kernel\.register\.command\(\s*['\"]([^'\"]+)['\"]",
                    r"kernel\.register\.command\(\s*['\"]([^'\"]+)['\"]",
                    r"@kernel\.register_command\(\s*['\"]([^'\"]+)['\"]\)",
                    r"kernel\.register_command\(\s*['\"]([^'\"]+)['\"]",
                    r"register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                    r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)['\"]",
                    r"pattern\s*=\s*r['\"]\\\\.([^'\"]+)['\"]",
                ]

                for pattern in patterns:
                    found = re.findall(pattern, code)
                    commands.extend(found)

                alias_patterns = [
                    r"alias\s*=\s*['\"]([^'\"]+)['\"]",
                    r"alias\s*=\s*\[([^\]]+)\]",
                ]

                for cmd in list(set(commands)):
                    if not cmd:
                        continue
                    esc = re.escape(cmd)
                    cmd_patterns = [
                        rf"(?:@kernel\.register\.command|kernel\.register\.command)\(\s*['\"]{esc}['\"][^)]+\)",
                        rf"(?:@kernel\.register_command|kernel\.register_command)\(\s*['\"]{esc}['\"][^)]+\)",
                    ]

                    for cmd_pattern in cmd_patterns:
                        cmd_match = re.search(cmd_pattern, code, re.DOTALL)
                        if not cmd_match:
                            continue

                        cmd_line = cmd_match.group(0)
                        for alias_pattern in alias_patterns:
                            alias_matches = re.findall(alias_pattern, cmd_line)
                            for alias_match in alias_matches:
                                if "[" in alias_match:
                                    alias_list = [
                                        a.strip().strip("'\"")
                                        for a in alias_match.split(",")
                                        if a.strip()
                                    ]
                                    if alias_list:
                                        aliases_info[cmd] = alias_list
                                else:
                                    aliases_info[cmd] = [alias_match.strip()]
                        break

        except Exception as e:
            kernel.log_error(f"Error reading module {module_name}: {e}")
            return [], {}

    seen = set()
    uniq = []
    for c in commands:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    commands = uniq

    for cmd in commands:
        cmd_aliases = []
        for alias, target in kernel.aliases.items():
            if target == cmd:
                cmd_aliases.append(alias)
        if cmd_aliases:
            aliases_info[cmd] = cmd_aliases

    return commands, aliases_info

async def generate_detailed_page(search_term, kernel, strings):
    search_term = search_term.lower()
    exact_match = None
    similar_modules = []

    all_modules = {}
    for name, module in kernel.system_modules.items():
        all_modules[name] = ("system", module)
    for name, module in kernel.loaded_modules.items():
        all_modules[name] = ("user", module)

    for name, (typ, module) in all_modules.items():
        if name.lower() == search_term:
            exact_match = (name, typ, module)
            break

    if exact_match:
        name, typ, module = exact_match
        commands, aliases_info = get_module_commands(name, kernel)
        file_path = (
            f"modules/{name}.py" if typ == "system" else f"modules_loaded/{name}.py"
        )
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
                metadata = await kernel.get_module_metadata(code)
        except:
            metadata = {
                "commands": {},
                "description": strings["no_description"],
                "version": "?.?.?",
                "author": strings["unknown"],
            }

        msg = f'{CUSTOM_EMOJI["dna"]} <b>{strings["module"]}</b> <code>{name}</code>:\n'
        msg += f'{CUSTOM_EMOJI["alembic"]} <b>{strings["description"]}:</b> <i>{metadata.get("description", strings["no_description"])}</i>\n'
        msg += f'{CUSTOM_EMOJI["snowflake"]} <b>{strings["version"]}:</b> <code>{metadata.get("version", "1.0.0")}</code>\n'
        msg += "<blockquote expandable>"
        if commands:
            for cmd in commands:
                cmd_desc = metadata.get("commands", {}).get(
                    cmd, f'{CUSTOM_EMOJI["confused"]} {strings["no_description"]}'
                )
                msg += f'{CUSTOM_EMOJI["tot"]} <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>'

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
            msg += f'{CUSTOM_EMOJI["blocked"]} {strings["no_commands"]}\n'
        msg += "</blockquote>"
        msg += f'\n<blockquote>{CUSTOM_EMOJI["pancake"]} <b>{strings["author"]}:</b> <i>{metadata.get("author", strings["unknown"])}</i></blockquote>'
        return msg

    for name, (typ, module) in all_modules.items():
        if search_term in name.lower():
            commands, _ = get_module_commands(name, kernel)
            similar_modules.append((name, typ, module))
        else:
            commands, _ = get_module_commands(name, kernel)
            for cmd in commands:
                if search_term in cmd.lower():
                    similar_modules.append((name, typ, module))
                    break

    if similar_modules:
        msg = f'{CUSTOM_EMOJI["crystal"]} <b>{strings["found_modules"]}:</b>\n<blockquote expandable>'
        for name, typ, module in similar_modules[:5]:
            commands, _ = get_module_commands(name, kernel)
            if commands:
                cmd_text = ", ".join(
                    [
                        f"<code>{kernel.custom_prefix}{cmd}</code>"
                        for cmd in commands[:2]
                    ]
                )
                msg += f"<b>{name}:</b> {cmd_text}\n"
        msg += "</blockquote>"
        if len(similar_modules) > 5:
            msg += f'... {strings["and_more"].format(count=len(similar_modules)-5)} {CUSTOM_EMOJI["tot"]}\n'
        msg += f'\n<blockquote><i>{strings["no_exact_match"]}</i> {CUSTOM_EMOJI["map"]}</blockquote>'
    else:
        msg = f'<blockquote expandable>{CUSTOM_EMOJI["blocked"]} {strings["module_not_found"]}</blockquote>'
    return msg

def get_paginated_data(kernel, page, strings):
    CHUNK_SIZE = 10
    sys_modules = sorted(list(kernel.system_modules.keys()))
    usr_modules = sorted(list(kernel.loaded_modules.keys()))

    user_pages_count = math.ceil(len(usr_modules) / CHUNK_SIZE) if usr_modules else 0
    total_pages = 1 + user_pages_count

    if page == 0:
        msg = f'{CUSTOM_EMOJI["crystal"]} <b>{strings["system_modules"]}:</b> <code>{len(sys_modules)}</code>\n\n'
        msg += "<blockquote expandable>"
        for name in sys_modules:
            commands, aliases_info = get_module_commands(name, kernel)
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
                                alias_text += f" (+{len(aliases)-2})"
                            display_cmd += f" [{alias_text}]"
                        elif isinstance(aliases, str):
                            display_cmd += f" [{kernel.custom_prefix}{aliases}]"
                    cmd_display.append(display_cmd)

                cmd_text = ", ".join(cmd_display)
                if len(commands) > 3:
                    cmd_text += f" (+{len(commands)-3})"
                msg += f"<b>{name}:</b> {cmd_text}\n"
        msg += "</blockquote>"
    else:
        start_idx = (page - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        current_chunk = usr_modules[start_idx:end_idx]

        msg = f'{CUSTOM_EMOJI["crystal"]} <b>{strings["user_modules_page"].format(page=page, count=len(usr_modules))}:</b>\n'
        msg += "<blockquote expandable>"
        for name in current_chunk:
            commands, aliases_info = get_module_commands(name, kernel)
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
                                alias_text += f" (+{len(aliases)-2})"
                            display_cmd += f" [{alias_text}]"
                        elif isinstance(aliases, str):
                            display_cmd += f" [{kernel.custom_prefix}{aliases}]"
                    cmd_display.append(display_cmd)

                cmd_text = ", ".join(cmd_display)
                if len(commands) > 3:
                    cmd_text += f" (+{len(commands)-3})"
                msg += f"<b>{name}:</b> {cmd_text}\n"
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

    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'help_not_command': 'Ты имел в виду ',
            'module': 'Модуль',
            'description': 'Описание',
            'version': 'Версия',
            'no_description': 'Нет описания',
            'unknown': 'Неизвестно',
            'aliases': 'Алиасы',
            'no_commands': 'Нет команд',
            'author': 'Автор',
            'found_modules': 'Найдены модули',
            'and_more': '... и еще <code>{count}</code>',
            'no_exact_match': 'Точное совпадение не найдено',
            'module_not_found': 'Модуль не найден',
            'system_modules': 'Системные модули',
            'user_modules_page': 'Пользовательские модули (Страница {page}/<code>{count}</code>)',
            'close': 'Закрыть',
            'inline_bot_not_configured': 'Inline бот не настроен\nУстановите inline_bot_token в config',
            'no_inline_results': '❌ Нет inline результатов',
            'error': '❌ Ошибка',
            'module_manager': 'Менеджер модулей\n\nИспользуйте "man" для просмотра модулей или "man [модуль]" для поиска.',
            'search_hint': '🔍 Поиск модулей\n\nНапишите "man [название]" для поиска модулей и команд\nПример: man ping',
            'search_results': 'Результаты поиска',
        },
        'en': {
            'help_not_command': 'Did you mean ',
            'module': 'Module',
            'description': 'Description',
            'version': 'Version',
            'no_description': 'No description',
            'unknown': 'Unknown',
            'aliases': 'Aliases',
            'no_commands': 'No commands',
            'author': 'Author',
            'found_modules': 'Found modules',
            'and_more': '... and <code>{count}</code> more',
            'no_exact_match': 'No exact match found',
            'module_not_found': 'Module not found',
            'system_modules': 'System modules',
            'user_modules_page': 'User modules (Page {page}/<code>{count}</code>)',
            'close': 'Close',
            'inline_bot_not_configured': 'Inline bot not configured\nSet inline_bot_token in config',
            'no_inline_results': '❌ No inline results',
            'error': 'Error',
            'module_manager': 'Module Manager\n\nUse "man" to browse modules or "man [module]" to search.',
            'search_hint': '🔍 Search Modules\n\nType "man [name]" to search for modules and commands\nExample: man ping',
            'search_results': 'Search results',
        }
    }

    lang_strings = strings.get(language, strings['en'])

    async def search_modules_for_inline(search_term, kernel, strings):
        """Поиск модулей для inline режима"""
        search_term = search_term.lower()
        exact_matches = []
        similar_modules = []

        all_modules = {}
        for name, module in kernel.system_modules.items():
            all_modules[name] = ("system", module)
        for name, module in kernel.loaded_modules.items():
            all_modules[name] = ("user", module)

        # Ищем точные совпадения по имени
        for name, (typ, module) in all_modules.items():
            if name.lower() == search_term:
                exact_matches.append((name, typ, module))

        # Ищем частичные совпадения
        for name, (typ, module) in all_modules.items():
            if search_term in name.lower():
                if (name, typ, module) not in exact_matches:
                    similar_modules.append((name, typ, module))
            else:
                commands, _ = get_module_commands(name, kernel)
                for cmd in commands:
                    if search_term in cmd.lower():
                        if (name, typ, module) not in exact_matches:
                            similar_modules.append((name, typ, module))
                        break

        return exact_matches, similar_modules

    async def generate_module_article(module_info, kernel, strings):
        """Генерирует статью для одного модуля"""
        name, typ, module = module_info
        commands, aliases_info = get_module_commands(name, kernel)
        file_path = f"modules/{name}.py" if typ == "system" else f"modules_loaded/{name}.py"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
                metadata = await kernel.get_module_metadata(code)
        except:
            metadata = {
                "commands": {},
                "description": strings["no_description"],
                "version": "?.?.?",
                "author": strings["unknown"],
            }

        msg = f'<blockquote>{CUSTOM_EMOJI["dna"]} <b>{strings["module"]}</b> <code>{name}</code></blockquote>\n'
        msg += f'<blockquote>{CUSTOM_EMOJI["alembic"]} <b>{strings["description"]}:</b> <i>{metadata.get("description", strings["no_description"])}</i>\n</blockquote>'

        if commands:
            msg += f'\n<b>Command:</b>\n'
            msg += '<blockquote>'
            for cmd in commands[:5]:  # Показываем только первые 5 команд
                cmd_desc = metadata.get("commands", {}).get(
                    cmd, f'{CUSTOM_EMOJI["confused"]} {strings["no_description"]}'
                )
                msg += f'• <code>{kernel.custom_prefix}{cmd}</code> - {cmd_desc}\n'

            if len(commands) > 5:
                msg += f'... и еще {len(commands)-5} команд\n'
        else:
            msg += f'\n{CUSTOM_EMOJI["blocked"]} {strings["no_commands"]}\n'
        msg += '</blockquote>'

        msg += f'\n<blockquote>{CUSTOM_EMOJI["snowflake"]} <b>{strings["version"]}:</b> <code>{metadata.get("version", "1.0.0")}</code>'
        msg += f'\n{CUSTOM_EMOJI["pancake"]} <b>{strings["author"]}:</b> <i>{metadata.get("author", strings["unknown"])}</i></blockquote>'

        return msg

    async def man_inline_handler(event):
        query = event.text.strip()

        if query == "man":
            # Первая статья: пагинированный список модулей
            thumb1 = InputWebDocument(
                url='https://kappa.lol/6plQLz',
                size=0,
                mime_type='image/jpeg',
                attributes=[DocumentAttributeImageSize(w=0, h=0)]
            )
            msg1, buttons = get_paginated_data(kernel, 0, lang_strings)
            article1 = event.builder.article(
                title="Module Manager",
                description="Browse all modules",
                text=msg1,
                buttons=buttons,
                parse_mode="html",
                thumb=thumb1
            )

            # Вторая статья: подсказка по поиску
            thumb2 = InputWebDocument(
                url='https://kappa.lol/wujauv',
                size=0,
                mime_type='image/jpeg',
                attributes=[DocumentAttributeImageSize(w=0, h=0)]
            )
            article2 = event.builder.article(
                title="Search Modules",
                description="Type 'man [name]' to search",
                text=f'<b>{lang_strings["search_hint"]}</b>',
                parse_mode="html",
                thumb=thumb2
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
                        # Статья с заголовком поиска
                        thumb_search = InputWebDocument(
                            url='https://kappa.lol/LOuqBO',
                            size=0,
                            mime_type='image/jpeg',
                            attributes=[DocumentAttributeImageSize(w=0, h=0)]
                        )

                        result_count = len(exact_matches) + len(similar_modules)
                        search_header = event.builder.article(
                            title=f"Search: {search_term}",
                            description=f"Found {result_count} modules",
                            text=f'<b>🔍 {lang_strings["search_results"]}: "{search_term}"</b>\n'
                                 f'<i>Найдено {result_count} модулей</i>\n\n',
                            parse_mode="html",
                            thumb=thumb_search
                        )
                        articles.append(search_header)

                        # Статьи для точных совпадений
                        for module_info in exact_matches[:10]:  # Ограничиваем 10 результатами
                            name, typ, _ = module_info
                            msg = await generate_module_article(module_info, kernel, lang_strings)

                            thumb_module = InputWebDocument(
                                url='https://kappa.lol/POFDmQ',
                                size=0,
                                mime_type='image/jpeg',
                                attributes=[DocumentAttributeImageSize(w=0, h=0)]
                            )

                            article = event.builder.article(
                                title=f"📦 {name}",
                                description="Exact match",
                                text=msg,
                                parse_mode="html",
                                thumb=thumb_module
                            )
                            articles.append(article)

                        # Статьи для похожих модулей
                        for module_info in similar_modules[:10]:  # Ограничиваем 10 результатами
                            name, typ, _ = module_info
                            msg = await generate_module_article(module_info, kernel, lang_strings)

                            thumb_module = InputWebDocument(
                                url='https://kappa.lol/POFDmQ',
                                size=0,
                                mime_type='image/jpeg',
                                attributes=[DocumentAttributeImageSize(w=0, h=0)]
                            )

                            article = event.builder.article(
                                title=f"🔍 {name}",
                                description="Similar match",
                                text=msg,
                                parse_mode="html",
                                thumb=thumb_module
                            )
                            articles.append(article)

                    else:
                        # Статья "не найдено"
                        thumb_not_found = InputWebDocument(
                            url='https://kappa.lol/N5jMQR',
                            size=0,
                            mime_type='image/jpeg',
                            attributes=[DocumentAttributeImageSize(w=0, h=0)]
                        )

                        not_found_article = event.builder.article(
                            title="Module not found",
                            description=f"No results for '{search_term}'",
                            text=f'<b>{CUSTOM_EMOJI["blocked"]} {lang_strings["module_not_found"]}</b>\n\n'
                                 f'<i>По запросу "{search_term}" ничего не найдено.</i>\n'
                                 f'Попробуйте другой запрос.',
                            parse_mode="html",
                            thumb=thumb_not_found
                        )
                        articles.append(not_found_article)

                    await event.answer(articles[:50])  # Telegram ограничивает 50 статьями
                    return

                except Exception as e:
                    # Статья с ошибкой
                    thumb_error = InputWebDocument(
                        url='https://kappa.lol/N5jMQR',
                        size=0,
                        mime_type='image/jpeg',
                        attributes=[DocumentAttributeImageSize(w=0, h=0)]
                    )

                    error_article = event.builder.article(
                        title="Search Error",
                        description="An error occurred",
                        text=f'<b>{CUSTOM_EMOJI["blocked"]} {lang_strings["error"]}</b>\n\n'
                             f'<code>{str(e)[:200]}</code>',
                        parse_mode="html",
                        thumb=thumb_error
                    )
                    await event.answer([error_article])
                    return

        # Статья по умолчанию
        builder = event.builder.article(
            title="Module Manager",
            description="Type 'man' or 'man [module]'",
            text=f'{CUSTOM_EMOJI["crystal"]} <b>{lang_strings["module_manager"]}</b>',
            parse_mode="html",
        )
        await event.answer([builder])

    async def man_callback_handler(event):
        data = event.data.decode()

        if data == "man_close":
            try:
                await kernel.client.delete_messages(event.chat_id, [event.message_id])
            except Exception:
                await event.answer("Closed", alert=False)

        elif data.startswith("man_page_"):
            try:
                page = int(data.split("_")[-1])
                msg, buttons = get_paginated_data(kernel, page, lang_strings)
                await event.edit(msg, buttons=buttons, parse_mode="html")
            except Exception as e:
                await event.answer(f"Error: {str(e)[:50]}", alert=True)

    @kernel.register.command("man")
    async def man_handler(event):
        try:
            args = event.text.split()

            if len(args) == 1:
                bot_username = kernel.config.get("inline_bot_username")
                if not bot_username:
                    await event.edit(
                        f'{CUSTOM_EMOJI["blocked"]} <b>{lang_strings["inline_bot_not_configured"]}</b>',
                        parse_mode="html",
                    )
                    return

                await event.delete()

                try:
                    results = await client.inline_query(bot_username, "man")
                    if results:
                        await results[0].click(
                            event.chat_id, reply_to=event.reply_to_msg_id
                        )
                    else:
                        await client.send_message(event.chat_id, lang_strings["no_inline_results"])
                except Exception as e:
                    await kernel.handle_error(e, source="man_inline", event=event)
                    await client.send_message(
                        event.chat_id, f'{lang_strings["error"]}: {str(e)[:100]}'
                    )

            else:
                search_term = " ".join(args[1:])
                msg = await generate_detailed_page(search_term, kernel, lang_strings)
                await event.edit(msg, parse_mode="html")

        except Exception as e:
            await kernel.handle_error(e, source="man", event=event)

    @kernel.register.command("help")
    async def help_cmd(event):
        await event.edit(
            f'<b>{lang_strings["help_not_command"]}</b><code>{kernel.custom_prefix}man?</code>',
            parse_mode='html'
        )

    kernel.register_inline_handler("man", man_inline_handler)
    kernel.register_callback_handler("man_", man_callback_handler)
