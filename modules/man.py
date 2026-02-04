# requires: telethon>=1.24, re, math
# author: @Hairpin00
# version: 1.0.3
# description: Module manager with inline interface
from telethon import events, Button
import re
import math

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
    """Extract commands from module file or from kernel's command_owners"""
    commands = []
    aliases_info = {}

    # 1) Try kernel command_owners first
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

    # 2) Parse module file
    file_path = None
    if module_name in kernel.system_modules:
        file_path = f"modules/{module_name}.py"
    elif module_name in kernel.loaded_modules:
        file_path = f"modules_loaded/{module_name}.py"

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

                # NOTE: support both ' and "
                patterns = [
                    r"@kernel\.register\.command\(\s*['\"]([^'\"]+)['\"]",
                    r"kernel\.register\.command\(\s*['\"]([^'\"]+)['\"]",
                    r"@kernel\.register_command\(\s*['\"]([^'\"]+)['\"]\)",
                    r"kernel\.register_command\(\s*['\"]([^'\"]+)['\"]",
                    r"register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                    # common telethon style: pattern=r'\.cmd'
                    r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)['\"]",
                    # optional: client.on(...) pattern=r'\.cmd'
                    r"pattern\s*=\s*r['\"]\\\\.([^'\"]+)['\"]",
                ]

                for pattern in patterns:
                    found = re.findall(pattern, code)
                    commands.extend(found)

                # Alias parsing
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

    # De-dup while keeping order
    seen = set()
    uniq = []
    for c in commands:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    commands = uniq

    # Supplement aliases from kernel
    for cmd in commands:
        cmd_aliases = []
        for alias, target in kernel.aliases.items():
            if target == cmd:
                cmd_aliases.append(alias)
        if cmd_aliases:
            aliases_info[cmd] = cmd_aliases

    return commands, aliases_info


async def generate_detailed_page(search_term, kernel):
    """Generate detailed info for a module"""
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
                "description": "No description",
                "version": "?.?.?",
                "author": "Unknown",
            }

        msg = f'{CUSTOM_EMOJI["dna"]} <b>Module</b> <code>{name}</code>:\n'
        msg += f'{CUSTOM_EMOJI["alembic"]} <b>Description:</b> <i>{metadata.get("description", "...")}</i>\n'
        msg += f'{CUSTOM_EMOJI["snowflake"]} <b>Version:</b> <code>{metadata.get("version", "1.0.0")}</code>\n'
        msg += "<blockquote expandable>"
        if commands:
            for cmd in commands:
                cmd_desc = metadata.get("commands", {}).get(
                    cmd, f'{CUSTOM_EMOJI["confused"]} No description'
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
                        msg += f" | Aliases: {alias_text}"
                msg += "\n"
        else:
            msg += f'{CUSTOM_EMOJI["blocked"]} No commands found\n'
        msg += "</blockquote>"
        msg += f'\n<blockquote>{CUSTOM_EMOJI["pancake"]} <b>Author:</b> <i>{metadata.get("author", "Unknown")}</i></blockquote>'
        return msg

    # Find similar modules
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
        msg = f'{CUSTOM_EMOJI["crystal"]} <b>Found modules:</b>\n<blockquote expandable>'
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
            msg += f'... and <code>{len(similar_modules)-5} more</code> {CUSTOM_EMOJI["tot"]}\n'
        msg += f'\n<blockquote><i>No exact match found</i> {CUSTOM_EMOJI["map"]}</blockquote>'
    else:
        msg = f'<blockquote expandable>{CUSTOM_EMOJI["blocked"]} Module not found</blockquote>'
    return msg


def get_paginated_data(kernel, page=0):
    """Get paginated module list for inline interface"""
    CHUNK_SIZE = 10
    sys_modules = sorted(list(kernel.system_modules.keys()))
    usr_modules = sorted(list(kernel.loaded_modules.keys()))

    user_pages_count = math.ceil(len(usr_modules) / CHUNK_SIZE) if usr_modules else 0
    total_pages = 1 + user_pages_count

    if page == 0:
        # System modules page
        msg = f'{CUSTOM_EMOJI["crystal"]} <b>System modules:</b> <code>{len(sys_modules)}</code>\n\n'
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
        # User modules page
        start_idx = (page - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        current_chunk = usr_modules[start_idx:end_idx]

        msg = f'{CUSTOM_EMOJI["crystal"]} <b>User modules (Page {page}/<code>{len(usr_modules)}</code>):</b>\n'
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
    buttons.append([Button.inline("❌ Close", data="man_close")])

    return msg, buttons


def register(kernel):
    client = kernel.client

    async def man_inline_handler(event):
        query = event.text.strip()

        if query == "man":
            msg, buttons = get_paginated_data(kernel, 0)
            builder = event.builder.article(
                title="Module Manager", text=msg, buttons=buttons, parse_mode="html"
            )
            await event.answer([builder])
            return

        if query.startswith("man "):
            search_term = query[4:].strip()
            if search_term:
                msg = await generate_detailed_page(search_term, kernel)
                builder = event.builder.article(
                    title=f"Search: {search_term}", text=msg, parse_mode="html"
                )
                await event.answer([builder])
                return

        # Default response
        builder = event.builder.article(
            title="Module Manager",
            text=f'{CUSTOM_EMOJI["crystal"]} <b>Module Manager</b>\n\nUse "man" to browse modules or "man [module]" to search.',
            parse_mode="html",
        )
        await event.answer([builder])

    async def man_callback_handler(event):
        data = event.data.decode()

        if data == "man_close":
            try:
                await event.delete()
            except:
                await event.answer("Closed", alert=False)

        elif data.startswith("man_page_"):
            try:
                page = int(data.split("_")[-1])
                msg, buttons = get_paginated_data(kernel, page)
                await event.edit(msg, buttons=buttons, parse_mode="html")
            except Exception as e:
                await event.answer(f"Error: {str(e)[:50]}", alert=True)

    @kernel.register_command("man")
    async def man_handler(event):
        try:
            args = event.text.split()

            if len(args) == 1:
                bot_username = kernel.config.get("inline_bot_username")
                if not bot_username:
                    await event.edit(
                        f'{CUSTOM_EMOJI["blocked"]} <b>Inline bot not configured</b>\nSet inline_bot_token in config',
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
                        await client.send_message(event.chat_id, "❌ No inline results")
                except Exception as e:
                    await kernel.handle_error(e, source="man_inline", event=event)
                    await client.send_message(
                        event.chat_id, f"❌ Error: {str(e)[:100]}"
                    )

            else:
                search_term = " ".join(args[1:])
                msg = await generate_detailed_page(search_term, kernel)
                await event.edit(msg, parse_mode="html")

        except Exception as e:
            await kernel.handle_error(e, source="man", event=event)

    kernel.register_inline_handler("man", man_inline_handler)
    kernel.register_callback_handler("man_", man_callback_handler)