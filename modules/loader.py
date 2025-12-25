# author: @Hairpin00
# version: 1.0.5
# description: loader modules
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


current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from core.kernel import CommandConflictError
except ImportError:
    class CommandConflictError(Exception):
        def __init__(self, message, conflict_type=None, command=None):
            super().__init__(message)
            self.conflict_type = conflict_type
            self.command = command

def register(kernel):
    client = kernel.client

    emojis = ['ಠ_ಠ', '( ཀ ʖ̯ ཀ)', '(◕‿◕✿)', '(つ･･)つ', '༼つ◕_◕༽つ', '(•_•)', '☜(ﾟヮﾟ☜)', '(☞ﾟヮﾟ)☞', 'ʕ•ᴥ•ʔ', '(づ￣ ³￣)づ']

    async def log_to_bot(text):
        if hasattr(kernel, 'log_module'):
            await kernel.log_module(text)
        elif hasattr(kernel, 'send_log_message'):
            await kernel.send_log_message(f" {text}")

    async def log_error_to_bot(text):
        if hasattr(kernel, 'log_error'):
            await kernel.log_error(text)
        elif hasattr(kernel, 'send_log_message'):
            await kernel.send_log_message(f"{text}")

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

            kernel.set_loading_module(module_name, 'system' if is_system else 'user')
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

        except kernel.CommandConflictError as e:
            raise e
        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                return False, f'Требуется зависимость: {dep}. Используйте: pip install {dep}'
            return False, f'Ошибка импорта: {error_msg}'
        except Exception as e:
            return False, f'Ошибка загрузки: {str(e)}'
        finally:
            kernel.clear_loading_module()


    @kernel.register_command('im')
    # загрузить модуль
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

        if module_name in kernel.system_modules:
            await event.edit(
                f'🫨 <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>🚫 К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>',
                parse_mode='html'
            )
            return

        is_update = module_name in kernel.loaded_modules

        action = "🧪 обновляю" if is_update else "🧪 устанавливаю"
        msg = await event.edit(f'{action} модуль <b>{module_name}</b>', parse_mode='html')

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, file_name)
        await reply.download_media(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            if 'from .. import' in code or 'import loader' in code:
                await log_error_to_bot(f" Модуль {module_name} не совместим")
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

            if is_update:
                kernel.unregister_module_commands(module_name)

            success, message = await kernel.load_module_from_file(file_path, module_name, False)

            if success:
                commands = get_module_commands(module_name, kernel)
                cmd_text = f'🔶 {", ".join([f"<blockquote><code>{kernel.custom_prefix}{cmd}</code></blockquote>" for cmd in commands])}' if commands else '🔶 Нет команд'

                emoji = random.choice(emojis)

                final_msg = f'🧬 Модуль <b>{module_name}</b> загружен! {emoji}\n\n'
                final_msg += cmd_text

                await log_to_bot(f" Модуль {module_name} установлен")
                await msg.edit(final_msg, parse_mode='html')
            else:
                await log_error_to_bot(f" Ошибка установки {module_name}: {message}")
                await msg.edit(f'❌ Ошибка, смотри логи')
                if os.path.exists(file_path):
                    os.remove(file_path)

        except CommandConflictError as e:
            if e.conflict_type == 'system':
                await msg.edit(
                    f'😶‍🌫️ <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{e.command}</code>)\n'
                    f'<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>',
                    parse_mode='html'
                )
            elif e.conflict_type == 'user':
                await msg.edit(
                    f'😖 <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n'
                    f'<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>',
                    parse_mode='html'
                )
                await kernel.handle_error(e, source=f"module_conflict:{module_name}")
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            await log_error_to_bot(f" Критическая ошибка при установке {module_name}: {str(e)}")
            await msg.edit(f'❌ Ошибка, смотри логи')
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register_command('dlm')
    # скачать из ссылки
    async def download_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}dlm название_модуля или ссылка')
            return

        module_or_url = args[1]
        repo_index = None

        if len(args) > 2 and args[2].isdigit():
            repo_index = int(args[2]) - 1

        if module_or_url.startswith('http'):
            if not module_or_url.endswith('.py'):
                await event.edit('❌ Ссылка должна вести на .py файл')
                return
            module_name = os.path.basename(module_or_url)[:-3]
            is_url = True
        else:
            module_name = module_or_url
            is_url = False

        if module_name in kernel.system_modules:
            await event.edit(
                f'🫨 <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>🚫 К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>',
                parse_mode='html'
            )
            return

        action = "🧪 обновляю" if module_name in kernel.loaded_modules else "🧪 устанавливаю"
        msg = await event.edit(f'{action} модуль <b>{module_name}</b>', parse_mode='html')

        try:
            code = None
            repo_url = None

            if is_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(module_or_url) as resp:
                        if resp.status == 200:
                            code = await resp.text()
                        else:
                            await log_error_to_bot(f" Не удалось скачать модуль по ссылке")
                            await msg.edit(f'❌ Не удалось скачать модуль по ссылке')
                            return
            else:
                repos = [kernel.default_repo] + kernel.repositories

                if repo_index is not None and 0 <= repo_index < len(repos):
                    repo_url = repos[repo_index]
                    code = await kernel.download_module_from_repo(repo_url, module_name)
                else:
                    for repo in repos:
                        code = await kernel.download_module_from_repo(repo, module_name)
                        if code:
                            repo_url = repo
                            break

            if not code:
                await log_error_to_bot(f" Модуль {module_name} не найден")
                await msg.edit(f'❌ Модуль {module_name} не найден в репозиториях')
                return

            metadata = await kernel.get_module_metadata(code)

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')

            dependencies = []
            if 'requires' in code:
                reqs = re.findall(r'# requires: (.+)', code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(',')]

            if dependencies:
                await msg.edit(f'🔬 ставлю зависимости:\n{dependencies}', parse_mode='html')
                for dep in dependencies:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        text=True
                    )

            if module_name in kernel.loaded_modules:
                kernel.unregister_module_commands(module_name)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            success, message = await kernel.load_module_from_file(file_path, module_name, False)

            if success:
                commands = get_module_commands(module_name, kernel)

                emoji = random.choice(emojis)

                final_msg = f'🧬 Модуль <b>{module_name}</b> загружен! {emoji}\n'
                final_msg += f'📝 D: <i>{metadata["description"]}</i> | V: <code>{metadata["version"]}</code>\n'
                final_msg += '<blockquote expandable>'
                if commands:

                    for cmd in commands:
                        cmd_desc = metadata['commands'].get(cmd, '🫨 У команды нету описания')
                        final_msg += f'🔶 <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>\n'

                final_msg += '</blockquote>'
                await msg.edit(final_msg, parse_mode='html')

            else:
                await log_error_to_bot(f"❌ Ошибка загрузки {module_name}: {message}")
                await msg.edit(f'❌ Ошибка, смотри логи')
                if os.path.exists(file_path):
                    os.remove(file_path)
        except CommandConflictError as e:
            if e.conflict_type == 'system':
                await msg.edit(
                    f'😶‍🌫️ <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{e.command}</code>)\n'
                    f'<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>',
                    parse_mode='html'
                )
            elif e.conflict_type == 'user':
                await msg.edit(
                    f'😖 <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n'
                    f'<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>',
                    parse_mode='html'
                )
                await kernel.handle_error(e, source=f"module_conflict:{module_name}")
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            await log_error_to_bot(f" Ошибка скачивания {module_name}: {str(e)}")
            await msg.edit(f'❌ Ошибка, смотри логи')

    @kernel.register_command('dlml')
    # список модулей из repo
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
            await log_error_to_bot(f" Ошибка каталога: {str(e)}")
            await client.send_message(event.chat_id, f'❌ Ошибка, смотри логи')

    @kernel.register_command('um')
    # удалить модуль
    async def unload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}um название_модуля')
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return

        kernel.unregister_module_commands(module_name)

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        if os.path.exists(file_path):
            os.remove(file_path)

        if module_name in sys.modules:
            del sys.modules[module_name]

        if module_name in kernel.loaded_modules:
            del kernel.loaded_modules[module_name]

        await log_to_bot(f"Модуль {module_name} удалён")
        await event.edit(f'🗑️ Модуль {module_name} удален')

    @kernel.register_command('unlm')
    # выгрузить в виде файла
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

        await event.edit(f'🧊 Отправка модуля {module_name}...')
        await client.send_file(event.chat_id, file_path, caption=f'🍬 Модуль: {module_name}.py\n\n<blockquote><code>{kernel.custom_prefix}im</code> для установки</blockquote>', parse_mode='html')
        await event.delete()

    @kernel.register_command('reload')
    # <модуль> перезагрузить модуль
    async def reload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}reload название_модуля')
            return

        module_name = args[1]

        if module_name in kernel.system_modules:
            await event.edit(
                f'🫨 <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>🚫 К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>',
                parse_mode='html'
            )
            return

        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return

        await log_to_bot(f"🔭 Перезагрузка модуля {module_name}")

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')

        if not os.path.exists(file_path):
            await event.edit(f'❌ Файл модуля не найден')
            return

        msg = await event.edit(f'🔭 Перезагрузка <mono>{module_name}</mono>...', parse_mode='html')

        if module_name in sys.modules:
            del sys.modules[module_name]

        kernel.unregister_module_commands(module_name)
        del kernel.loaded_modules[module_name]

        success, message = await load_module_from_file(file_path, module_name, False)

        if success:
            commands = get_module_commands(module_name, kernel)
            cmd_text = f'🔶 {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}' if commands else '🔶 Нет команд'

            emoji = random.choice(emojis)
            await log_to_bot(f"⚗️ Модуль {module_name} перезагружен")
            await msg.edit(f'🧬 Модуль <b>{module_name}</b> перезагружен! {emoji}\n\n{cmd_text}', parse_mode='html')
        else:
            await log_error_to_bot(f"❌ Ошибка перезагрузки {module_name}: {message}")
            await msg.edit(f'❌ Ошибка, смотри логи')

    @kernel.register_command('convert')
    # конвертировать модуль (работает не очень)
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

            await log_to_bot(f"✅ Модуль {module_name} конвертирован")
            await event.edit(f'⚗️ Модуль конвертирован\n📦 Бэкап: {module_name}.py.backup')

        except Exception as e:
            await log_error_to_bot(f"❌ Ошибка конвертации {module_name}: {str(e)}")
            await event.edit(f'❌ Ошибка, смотри логи')

    @kernel.register_command('modules')
    # модули
    async def modules_list_handler(event):
        await log_to_bot(f"🔷 Просмотр списка модулей")

        if not kernel.loaded_modules and not kernel.system_modules:
            await event.edit('📦 Модули не загружены')
            return

        msg = '💠 <b>Загруженные модули:</b>\n\n'

        if kernel.system_modules:
            msg += '🔷 <b>Системные модули:</b>\n'
            for name in sorted(kernel.system_modules.keys()):
                commands = get_module_commands(name, kernel)
                msg += f'• <b>{name}</b> <i>({len(commands)} команд)</i>\n'
            msg += '\n'

        if kernel.loaded_modules:
            msg += '🔶 <b>Пользовательские модули:</b>\n'
            for name in sorted(kernel.loaded_modules.keys()):
                commands = get_module_commands(name, kernel)
                msg += f'• <b>{name}</b> <i>({len(commands)} команд)</i>\n'

        await event.edit(msg, parse_mode='html')

    @kernel.register_command('addrepo')
    # <URL> добавить repo
    async def add_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'⛈️ Использование: {kernel.custom_prefix}addrepo URL')
            return

        url = args[1].strip()
        success, message = await kernel.add_repository(url)

        if success:
            await event.edit(f'🧬 {message}')
        else:
            await event.edit(f'⛈️ {message}')

    @kernel.register_command('delrepo')
    # <id> удалить repo
    async def del_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}delrepo индекс')
            return

        success, message = await kernel.remove_repository(args[1])

        if success:
            await event.edit(f'🗑️ {message}')
        else:
            await event.edit(f'⛈️ {message}')




