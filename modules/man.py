# author: @Hairpin00
# version: 1.0.1
# description: список модулей

from telethon import events, Button
import re

def register(kernel):
    client = kernel.client

    async def generate_man_page(search_term=None):
        user_modules = len(kernel.loaded_modules)
        system_modules = len(kernel.system_modules)

        if not search_term:
            msg = f'<b>🔮 Модулей: </b><code>{user_modules}</code><b>. Системных: </b><code>{system_modules}</code>\n\n'

            if system_modules:
                msg += '<blockquote expandable>'
                for name in sorted(kernel.system_modules.keys()):
                    commands = get_module_commands(name, kernel)
                    if commands:
                        cmd_text = ", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands[:3]])
                        if len(commands) > 3:
                            cmd_text += f" (+{len(commands)-3})"
                        msg += f'<b>{name}:</b> {cmd_text}\n'
                msg += '</blockquote>\n'

            if user_modules:
                msg += '<blockquote expandable>'
                for name in sorted(kernel.loaded_modules.keys()):
                    commands = get_module_commands(name, kernel)
                    if commands:
                        cmd_text = ", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands[:3]])
                        if len(commands) > 3:
                            cmd_text += f" (+{len(commands)-3})"
                        msg += f'<b>{name}:</b> {cmd_text}\n'
                msg += '</blockquote>'

            return msg

        search_term = search_term.lower()
        exact_match = None
        similar_modules = []

        all_modules = {}
        for name, module in kernel.system_modules.items():
            all_modules[name] = ('system', module)
        for name, module in kernel.loaded_modules.items():
            all_modules[name] = ('user', module)

        for name, (typ, module) in all_modules.items():
            if name.lower() == search_term:
                exact_match = (name, typ, module)
                break

        if exact_match:
            name, typ, module = exact_match
            commands = get_module_commands(name, kernel)

            file_path = f"modules/{name}.py" if typ == 'system' else f"modules_loaded/{name}.py"
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                    metadata = await kernel.get_module_metadata(code)
            except:
                metadata = {'commands': {}}

            msg = f'<b>🧬 Модуль </b><code>{name}</code>:\n'
            msg += f'⚗️ <b>D:</b> <i>{metadata["description"]}\n'
            msg += f'❄️ <b>V:</b> <code>{metadata["version"]}</code>\n'
            msg += '<blockquote expandable>'
            if commands:
                for cmd in commands:
                    cmd_desc = metadata['commands'].get(cmd, '🫨 У команды нету описания')
                    msg += f'<code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>\n'
            else:
                msg += '🚫 Команд не найдено\n'
            msg += '</blockquote>'
            msg += f'\n<blockquote>🥞 <b>Автор:</b><i> {metadata["author"]}</blockquote></i>'


            return msg

        for name, (typ, module) in all_modules.items():
            if search_term in name.lower():
                similar_modules.append((name, typ, module))
            else:
                commands = get_module_commands(name, kernel)
                for cmd in commands:
                    if search_term in cmd.lower():
                        similar_modules.append((name, typ, module))
                        break

        if similar_modules:
            msg = f'<b>🔮 Модуль </b><code>{search_term}</code>:\n\n'
            for name, typ, module in similar_modules[:5]:
                commands = get_module_commands(name, kernel)
                if commands:
                    cmd_text = ", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands[:2]])
                    msg += f'<b>{name}:</b> {cmd_text}\n'

            if len(similar_modules) > 5:
                msg += f'... и ещё {len(similar_modules)-5}\n'

            msg += '\n<i>точного совпадения не удалось найти</i> 🗺️'
        else:
            msg = f'<b>🔮 Модуль </b><code>{search_term}</code>:\n\n🚫 Модуль не найден'

        return msg

    def get_module_commands(module_name, kernel):
        commands = []
        file_path = None

        if module_name in kernel.system_modules:
            file_path = f"modules/{module_name}.py"
        elif module_name in kernel.loaded_modules:
            file_path = f"modules_loaded/{module_name}.py"

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()

                    patterns = [
                        r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)",
                        r"register_command\s*\('([^']+)'",
                        r"@kernel\.register_command\('([^']+)'\)",
                        r"kernel\.register_command\('([^']+)'",
                        r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)"
                    ]

                    for pattern in patterns:
                        found = re.findall(pattern, code)
                        commands.extend(found)

            except:
                pass

        return list(set([cmd for cmd in commands if cmd]))

    @kernel.register_command('man')
    # <модуль> без, весь список модулей
    async def man_handler(event):
        args = event.text.split()

        if len(args) == 1:
            msg = await generate_man_page()
            await event.edit(msg, parse_mode='html')
        else:
            search_term = ' '.join(args[1:])
            msg = await generate_man_page(search_term)
            await event.edit(msg, parse_mode='html')
