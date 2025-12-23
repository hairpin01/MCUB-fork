import asyncio
import os
import re
import sys
import subprocess
import importlib.util
import inspect
import aiohttp
import json
import random
from telethon import events, Button

def register(kernel):
    client = kernel.client

    emojis = ['ಠ_ಠ', '( ཀ ʖ̯ ཀ)', '(◕‿◕✿)', '(つ･･)つ', '༼つ◕_◕༽つ', '(•_•)', '☜(ﾟヮﾟ☜)', '(☞ﾟヮﾟ)☞', 'ʕ•ᴥ•ʔ', '(づ￣ ³￣)づ']

    def get_module_commands(module_name, kernel):
        commands = []
        file_path = None

        if module_name in kernel.system_modules:
            file_path = f"modules/{module_name}.py"
        elif module_name in kernel.loaded_modules:
            file_path = f"modules_loaded/{module_name}.py"

        if file_path and os.path.exists(file_path):
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

    def detect_module_type(module):
        if hasattr(module, 'register'):
            sig = inspect.signature(module.register)
            params = list(sig.parameters.keys())

            if len(params) == 0:
                return 'unknown'
            elif len(params) == 1:
                param_name = params[0]
                if param_name == 'kernel':
                    return 'new'
                elif param_name == 'client':
                    return 'old'
            return 'unknown'
        return 'none'

    async def load_module_from_file(file_path, module_name, is_system=False):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            if 'from .. import' in code or 'import loader' in code:
                return False, 'Несовместимый модуль (старая версия)'

            if module_name in sys.modules:
                del sys.modules[module_name]

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)

            module.kernel = kernel
            module.client = client
            module.custom_prefix = kernel.custom_prefix

            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            module_type = detect_module_type(module)

            if module_type == 'new':
                module.register(kernel)
            elif module_type == 'old':
                module.register(client)
            elif module_type == 'none':
                return False, 'Модуль не имеет функции register'
            else:
                return False, 'Неизвестный тип модуля'

            if is_system:
                kernel.system_modules[module_name] = module
            else:
                kernel.loaded_modules[module_name] = module

            return True, f'Модуль {module_name} загружен ({module_type})'

        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                return False, f'Требуется зависимость: {dep}. Используйте: pip install {dep}'
            return False, f'Ошибка импорта: {error_msg}'
        except Exception as e:
            return False, f'Ошибка загрузки: {str(e)}'

    @kernel.register_command('im')
    async def install_module_handler(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на .py файл')
            return

        reply = await event.get_reply_message()
        if not reply.document or not reply.document.attributes[0].file_name.endswith('.py'):
            await event.edit('❌ Это не .py файл')
            return

        file_name = reply.document.attributes[0].file_name
        module_name = file_name[:-3]
        is_update = module_name in kernel.loaded_modules

        action = "🧪 обновляю" if is_update else "🧪 устанавливаю"
        msg = await event.edit(f'{action} модуль <b>{module_name}</b>', parse_mode='html')

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, file_name)
        await reply.download_media(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            if 'from .. import' in code or 'import loader' in code:
                await msg.edit(f'❌ Модуль не совместим')
                os.remove(file_path)
                return

            dependencies = []
            if 'requires' in code:
                reqs = re.findall(r'# requires: (.+)', code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(',')]

            if dependencies:
                await msg.edit(f'{action} модуль <b>{module_name}</b>\n🔬 ставлю зависимости:\n{dependencies}', parse_mode='html')
                for dep in dependencies:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        text=True
                    )

            success, message = await load_module_from_file(file_path, module_name, False)

            if success:
                commands = get_module_commands(module_name, kernel)
                cmd_text = f'🔶 {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}' if commands else '🔶 Нет команд'

                emoji = random.choice(emojis)

                final_msg = f'🧬 Модуль <b>{module_name}</b> загружен! {emoji}\n\n'
                final_msg += cmd_text

                await msg.edit(final_msg, parse_mode='html')
            else:
                await msg.edit(f'❌ {message}')
                if os.path.exists(file_path):
                    os.remove(file_path)

        except Exception as e:
            await msg.edit(f'❌ Ошибка: {str(e)}')
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register_command('dlm')
    async def download_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}dlm название_модуля')
            return

        module_name = args[1]
        is_update = module_name in kernel.loaded_modules

        action = "🧪 обновляю" if is_update else "🧪 устанавливаю"
        msg = await event.edit(f'{action} модуль <b>{module_name}</b>', parse_mode='html')

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{kernel.MODULES_REPO}/{module_name}.py') as resp:
                    if resp.status == 200:
                        code = await resp.text()

                        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')

                        dependencies = []
                        if 'requires' in code:
                            reqs = re.findall(r'# requires: (.+)', code)
                            if reqs:
                                dependencies = [req.strip() for req in reqs[0].split(',')]

                        if dependencies:
                            await msg.edit(f'{action} модуль <b>{module_name}</b>\n🔬 ставлю зависимости:\n{dependencies}', parse_mode='html')
                            for dep in dependencies:
                                subprocess.run(
                                    [sys.executable, '-m', 'pip', 'install', dep],
                                    capture_output=True,
                                    text=True
                                )

                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(code)

                        success, message = await load_module_from_file(file_path, module_name, False)

                        if success:
                            commands = get_module_commands(module_name, kernel)
                            cmd_text = f'🔶 {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}' if commands else '🔶 Нет команд'

                            emoji = random.choice(emojis)

                            final_msg = f'🧬 Модуль <b>{module_name}</b> загружен! {emoji}\n\n'
                            final_msg += cmd_text

                            await msg.edit(final_msg, parse_mode='html')
                        else:
                            await msg.edit(f'❌ {message}')
                            if os.path.exists(file_path):
                                os.remove(file_path)
                    else:
                        await msg.edit(f'❌ Модуль {module_name} не найден')
        except Exception as e:
            await msg.edit(f'❌ Ошибка: {str(e)}')

    @kernel.register_command('dlml')
    async def catalog_handler(event):
        page = 1
        args = event.text.split()
        if len(args) > 1:
            try:
                page = int(args[1])
            except:
                page = 1
        
        bot_username = kernel.config.get('inline_bot_username')
        if not bot_username:
            await event.edit('❌ Inline-бот не настроен')
            return
        
        await event.delete()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{kernel.MODULES_REPO}/catalog.json') as resp:
                    if resp.status == 200:
                        text_data = await resp.text()
                        catalog = json.loads(text_data)
                        
                        kernel.catalog_cache = catalog
                        
                        query = f'catalog_{page}'
                        results = await client.inline_query(bot_username, query)
                        
                        if results:
                            await results[0].click(event.chat_id)
                        else:
                            await client.send_message(event.chat_id, '❌ Ошибка инлайн-бота')
                    else:
                        await client.send_message(event.chat_id, '❌ Каталог не найден')
        except Exception as e:
            await client.send_message(event.chat_id, f'❌ Ошибка: {str(e)}')
    
    @kernel.register_command('um')
    async def unload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}um название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        if module_name in kernel.loaded_modules:
            del kernel.loaded_modules[module_name]
        
        await event.edit(f'🗑️ Модуль {module_name} удален')
    
    @kernel.register_command('unlm')
    async def upload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}unlm название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules and module_name not in kernel.system_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = None
        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f'{module_name}.py')
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        
        if not os.path.exists(file_path):
            await event.edit(f'❌ Файл модуля не найден')
            return
        
        await event.edit(f'📤 Отправка модуля {module_name}...')
        await client.send_file(event.chat_id, file_path, caption=f'📦 Модуль: {module_name}.py')
        await event.delete()
    
    @kernel.register_command('reload')
    async def reload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}reload название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules and module_name not in kernel.system_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = None
        is_system = False
        
        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f'{module_name}.py')
            is_system = True
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        
        if not os.path.exists(file_path):
            await event.edit(f'❌ Файл модуля не найден')
            return
        
        msg = await event.edit(f'🔭 Перезагрузка <mono>{module_name}</mono>...', parse_mode='html')
        
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        if is_system and module_name in kernel.system_modules:
            del kernel.system_modules[module_name]
        elif module_name in kernel.loaded_modules:
            del kernel.loaded_modules[module_name]
        
        success, message = await load_module_from_file(file_path, module_name, is_system)
        
        if success:
            commands = get_module_commands(module_name, kernel)
            cmd_text = f'🔶 {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}' if commands else '🔶 Нет команд'
            
            emoji = random.choice(emojis)
            await msg.edit(f'🧬 Модуль <b>{module_name}</b> перезагружен! {emoji}\n\n{cmd_text}', parse_mode='html')
        else:
            await msg.edit(f'❌ {message}')
    
    @kernel.register_command('convert')
    async def convert_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}convert название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        if not os.path.exists(file_path):
            await event.edit(f'❌ Файл модуля не найден')
            return
        
        await event.edit(f'🍰 Конвертация {module_name} в новый формат...')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            old_patterns = [
                (r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)", r"@kernel.register_command('\1')"),
                (r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'([^']+)'\)\)", r"@kernel.register_command('\1'.lstrip('^\\\\' + kernel.custom_prefix))"),
                (r"def register\(client\):", "def register(kernel):\n    client = kernel.client"),
                (r"async def (\w+)\(event\):", r"async def \1(event):")
            ]
            
            for old, new in old_patterns:
                code = re.sub(old, new, code)
            
            backup_path = file_path + '.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            await event.edit(f'⚗️ Модуль конвертирован\n📦 Бэкап: {module_name}.py.backup')
            
        except Exception as e:
            await event.edit(f'❌ Ошибка конвертации: {str(e)}')
    
    @kernel.register_command('modules')
    async def modules_list_handler(event):
        if not kernel.loaded_modules and not kernel.system_modules:
            await event.edit('📦 Модули не загружены')
            return
        
        msg = '💠 **Загруженные модули:**\n\n'
        
        if kernel.system_modules:
            msg += '🔷 **Системные модули:**\n'
            for name in sorted(kernel.system_modules.keys()):
                msg += f'• **{name}**\n'
            msg += '\n'
        
        if kernel.loaded_modules:
            msg += '🔶 **Пользовательские модули:**\n'
            for name in sorted(kernel.loaded_modules.keys()):
                msg += f'• **{name}**\n'
        
        await event.edit(msg)
