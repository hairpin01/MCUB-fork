# author: @Hairpin00
# version: 1.0.9
# description: loader modules with custom emoji and HTML support
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
from telethon.tl.functions.messages import EditMessageRequest


current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Кастомные эмодзи
CUSTOM_EMOJI = {
    'loading': '<tg-emoji emoji-id="5323463142775202324">🏓</tg-emoji>',
    'dependencies': '<tg-emoji emoji-id="5328311576736833844">🟠</tg-emoji>',
    'confused': '<tg-emoji emoji-id="5249119354825487565">🫨</tg-emoji>',
    'error': '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
    'file': '<tg-emoji emoji-id="5269353173390225894">💾</tg-emoji>',
    'process': '<tg-emoji emoji-id="5426958067763804056">⏳</tg-emoji>',
    'blocked': '<tg-emoji emoji-id="5431895003821513760">🚫</tg-emoji>',
    'warning': '<tg-emoji emoji-id="5409235172979672859">⚠️</tg-emoji>',
    'idea': '<tg-emoji emoji-id="5411134407517964108">💡</tg-emoji>',
    'success': '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    'test': '<tg-emoji emoji-id="5134183530313548836">🧪</tg-emoji>',
    'crystal': '<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji>',
    'sparkle': '<tg-emoji emoji-id="5426900601101374618">🪩</tg-emoji>',
    'folder': '<tg-emoji emoji-id="5217444336089714383">📂</tg-emoji>',
    'upload': '<tg-emoji emoji-id="5253526631221307799">📤</tg-emoji>',
    'shield': '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji>',
    'angel': '<tg-emoji emoji-id="5404521025465518254">😇</tg-emoji>',
    'nerd': '<tg-emoji emoji-id="5465154440287757794">🤓</tg-emoji>',
    'cloud': '<tg-emoji emoji-id="5370947515220761242">🌩</tg-emoji>',
    'reload': '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    'convert': '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    'download': '<tg-emoji emoji-id="5469785308386041323">⬇️</tg-emoji>',
    'no_cmd': '<tg-emoji emoji-id="5429428837895141860">🫨</tg-emoji>'
}

# Случайные эмодзи для завершения (оригинальные из кода)
RANDOM_EMOJIS = [
    'ಠ_ಠ', '( ཀ ʖ̯ ཀ)', '(◕‿◕✿)', '(つ･･)つ', '༼つ◕_◕༽つ',
    '(•_•)', '☜(ﾟヮﾟ☜)', '(☞ﾟヮﾟ)☞', 'ʕ•ᴥ•ʔ', '(づ￣ ³￣)づ'
]

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

    async def log_to_bot(text):
        if hasattr(kernel, 'log_module'):
            await kernel.log_module(text)
        elif hasattr(kernel, 'send_log_message'):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['crystal']} {text}")

    async def log_error_to_bot(text):
        if hasattr(kernel, 'log_error'):
            await kernel.log_error(text)
        elif hasattr(kernel, 'send_log_message'):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['error']} {text}")

    async def edit_with_emoji(message, text, **kwargs):
        """Редактирование сообщения с поддержкой кастомных эмодзи и HTML"""
        try:
            # Если есть кастомные эмодзи или HTML-теги, используем HTML
            if '<tg-emoji' in text or '<emoji' in text or re.search(r'<[^>]+>', text):
                # Преобразуем старый формат в новый
                text = text.replace('<emoji document_id=', '<tg-emoji emoji-id=')
                text = text.replace('</emoji>', '</tg-emoji>')

                # Всегда используем HTML парсинг
                if 'parse_mode' not in kwargs:
                    kwargs['parse_mode'] = 'html'

                await message.edit(text, **kwargs)
                return True
            else:
                # Обычное редактирование
                await message.edit(text, **kwargs)
                return True
        except Exception as e:
            print(f"Error in edit_with_emoji: {e}")
            return False

    async def send_with_emoji(chat_id, text, **kwargs):
        try:
            if '<emoji' in text:
                text = text.replace('<emoji document_id=', '<tg-emoji emoji-id=')
                text = text.replace('</emoji>', '</tg-emoji>')

            if '<tg-emoji' in text or re.search(r'<[^>]+>', text):
                parse_mode = kwargs.pop('parse_mode', 'html')
                return await client.send_message(chat_id, text, parse_mode=parse_mode, **kwargs)
            else:
                return await client.send_message(chat_id, text, **kwargs)
        except Exception as e:
            print(f"Error in send_with_emoji: {e}")
            # Fallback
            fallback_text = re.sub(r'<tg-emoji[^>]*>.*?</tg-emoji>', '', text)
            fallback_text = re.sub(r'<emoji[^>]*>.*?</emoji>', '', fallback_text)
            fallback_text = re.sub(r'<[^>]+>', '', fallback_text)
            return await client.send_message(chat_id, fallback_text, **kwargs)


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
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Ответьте на .py файл</b>')
            return

        reply = await event.get_reply_message()
        if not reply.document or not reply.document.attributes[0].file_name.endswith('.py'):
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Это не .py файл</b>')
            return

        file_name = reply.document.attributes[0].file_name
        module_name = file_name[:-3]

        if module_name in kernel.system_modules:
            await edit_with_emoji(event,
                f'{CUSTOM_EMOJI["confused"]} <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>{CUSTOM_EMOJI["blocked"]} К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>'
            )
            return

        is_update = module_name in kernel.loaded_modules

        action = f'{CUSTOM_EMOJI["reload"]} обновляю' if is_update else f'{CUSTOM_EMOJI["test"]} устанавливаю'
        msg = await event.edit(f'{action} модуль <b>{module_name}</b>', parse_mode='html')

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, file_name)
        await reply.download_media(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            if 'from .. import' in code or 'import loader' in code:
                await log_error_to_bot(f"Модуль {module_name} не совместим")
                await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Модуль не совместим</b>')
                os.remove(file_path)
                return

            metadata = await kernel.get_module_metadata(code)

            dependencies = []
            if 'requires' in code:
                reqs = re.findall(r'# requires: (.+)', code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(',')]

            if dependencies:
                await edit_with_emoji(msg,
                    f'{CUSTOM_EMOJI["dependencies"]} <b>ставлю зависимости:</b>\n<code>{chr(10).join(dependencies)}</code>'
                )
                for dep in dependencies:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        text=True
                    )

            if is_update:
                kernel.unregister_module_commands(module_name)

            success, message_text = await kernel.load_module_from_file(file_path, module_name, False)

            if success:
                commands = get_module_commands(module_name, kernel)

                emoji = random.choice(RANDOM_EMOJIS)

                final_msg = f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} загружен!</b> {emoji}\n'
                final_msg += f'<blockquote>{CUSTOM_EMOJI["idea"]} <i>D: {metadata["description"]}</i> | V: <code>{metadata["version"]}</code></blockquote>'
                final_msg += '<blockquote>'
                if commands:

                    for cmd in commands:
                        cmd_desc = metadata['commands'].get(cmd, f'{CUSTOM_EMOJI["no_cmd"]} У команды нету описания')
                        final_msg += f'{CUSTOM_EMOJI["crystal"]} <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>\n'
                final_msg += '</blockquote>'

                await log_to_bot(f"Модуль {module_name} установлен")
                await edit_with_emoji(msg, final_msg)
            else:
                await log_to_bot(f"{module_name}: {message_text}")
                await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка, смотри логи</b>')
                if os.path.exists(file_path):
                    os.remove(file_path)

        except CommandConflictError as e:
            if e.conflict_type == 'system':
                await edit_with_emoji(msg,
                    f'{CUSTOM_EMOJI["shield"]} <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{e.command}</code>)\n'
                    f'<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>'
                )
            elif e.conflict_type == 'user':
                await edit_with_emoji(msg,
                    f'{CUSTOM_EMOJI["error"]} <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n'
                    f'<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>'
                )
                await kernel.handle_error(e, source=f"module_conflict:{module_name}")
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            await kernel.handle_error(e, source="install_module_handler", event=event)
            await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка, смотри логи</b>')
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register_command('dlm')
    async def download_module_handler(event):
        args = event.text.split()

        if len(args) < 2:
            await edit_with_emoji(event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}dlm [-send/-s] название_модуля или ссылка [номер_репозитория]</code>'
            )
            return

        send_mode = False
        module_or_url = None
        repo_index = None

        if args[1] in ['-send', '-s']:
            if len(args) < 3:
                await edit_with_emoji(event,
                    f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}dlm -send название_модуля или ссылка [номер_репозитория]</code>'
                )
                return
            send_mode = True
            module_or_url = args[2]
            if len(args) > 3 and args[3].isdigit():
                repo_index = int(args[3]) - 1
        else:
            module_or_url = args[1]
            if len(args) > 2 and args[2].isdigit():
                repo_index = int(args[2]) - 1
            send_mode = False

        is_url = False
        if module_or_url.startswith(('http://', 'https://', 'raw.githubusercontent.com')):
            is_url = True
            if module_or_url.endswith('.py'):
                module_name = os.path.basename(module_or_url)[:-3]
            else:
                module_name = os.path.basename(module_or_url).split('?')[0]
                if '.' in module_name:
                    module_name = module_name.split('.')[0]
        else:
            module_name = module_or_url

        if module_name in kernel.system_modules:
            await edit_with_emoji(event,
                f'{CUSTOM_EMOJI["confused"]} <b>Ой, кажется ты попытался скачать системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>{CUSTOM_EMOJI["blocked"]} Системные модули нельзя скачивать через <code>dlm</code></i></blockquote>'
            )
            return

        is_update = module_name in kernel.loaded_modules

        if send_mode:
            action = f"{CUSTOM_EMOJI['download']} скачиваю"
        else:
            action = f"{CUSTOM_EMOJI['test']} обновляю" if is_update else f"{CUSTOM_EMOJI['test']} устанавливаю"

        msg = await event.edit(f'{action} модуль <b>{module_name}</b>', parse_mode='html')

        try:
            code = None
            repo_url = None

            if is_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(module_or_url) as resp:
                            if resp.status == 200:
                                code = await resp.text()
                                save_name = module_name + '.py'
                            else:
                                await log_error_to_bot(f"Не удалось скачать модуль (статус: {resp.status})")
                                await edit_with_emoji(msg,
                                    f'{CUSTOM_EMOJI["warning"]} <b>Не удалось скачать модуль по ссылке</b> (статус: {resp.status})'
                                )
                                return
                except Exception as e:
                    await kernel.handle_error(e, source="install for url", event=event)
                    await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка скачивания:</b> {str(e)[:100]}')
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
                await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден в репозиториях</b>')
                return

            metadata = await kernel.get_module_metadata(code)
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')

            if send_mode:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code)

                await edit_with_emoji(msg, f'{CUSTOM_EMOJI["upload"]} <b>Отправляю модуль {module_name}...</b>')
                await event.delete()

                await client.send_file(
                            event.chat_id,
                            file_path,
                            caption=(
                                f'<blockquote>{CUSTOM_EMOJI["file"]} <b>Модуль:</b> <code>{module_name}.py</code>\n'
                                f'{CUSTOM_EMOJI["idea"]} <b>описание:</b> <i>{metadata["description"]}</i>\n'
                                f'{CUSTOM_EMOJI["crystal"]} <b>версия:</b> <code>{metadata["version"]}</code>\n'
                                f'{CUSTOM_EMOJI["angel"]} <b>автор:</b> <i>{metadata["author"]}</i>\n'
                                f'{CUSTOM_EMOJI["folder"]} <b>Размер:</b> <code>{os.path.getsize(file_path)} байт</code></blockquote>'
                            ),
                            parse_mode='html'
                        )

                os.remove(file_path)
                await log_to_bot(f"✅ Модуль {module_name} отправлен в чат")
                return

            dependencies = []
            if 'requires' in code:
                reqs = re.findall(r'# requires: (.+)', code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(',')]

            if dependencies:
                await edit_with_emoji(msg,
                    f'{CUSTOM_EMOJI["dependencies"]} <b>ставлю зависимости:</b>\n<code>{chr(10).join(dependencies)}</code>'
                )
                for dep in dependencies:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        text=True
                    )

            if is_update:
                kernel.unregister_module_commands(module_name)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            success, message_text = await kernel.load_module_from_file(file_path, module_name, False)

            if success:
                commands = get_module_commands(module_name, kernel)
                emoji = random.choice(RANDOM_EMOJIS)

                final_msg = f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} загружен!</b> {emoji}\n'
                final_msg += f'<blockquote>📝 <i>D: {metadata["description"]}</i> | V: <code>{metadata["version"]}</code></blockquote>'

                if commands:
                    final_msg += '<blockquote>'
                    for cmd in commands:
                        cmd_desc = metadata['commands'].get(cmd, '🫨 У команды нету описания')
                        final_msg += f'{CUSTOM_EMOJI["crystal"]} <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>\n'
                    final_msg += '</blockquote>'

                await log_to_bot(f"✅ Модуль {module_name} скачан")
                await edit_with_emoji(msg, final_msg)
            else:
                await log_error_to_bot(f"⛈️ Ошибка загрузки {module_name}: {message_text}")
                await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка, смотри логи</b>')
                if os.path.exists(file_path):
                    os.remove(file_path)

        except CommandConflictError as e:
            if e.conflict_type == 'system':
                await edit_with_emoji(msg,
                    f'{CUSTOM_EMOJI["shield"]} <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{e.command}</code>)\n'
                    f'<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>'
                )
            elif e.conflict_type == 'user':
                await edit_with_emoji(msg,
                    f'{CUSTOM_EMOJI["error"]} <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n'
                    f'<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>'
                )
                await kernel.handle_error(e, source=f"module_conflict:{module_name}")
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            await log_error_to_bot(f"⛈️ Ошибка скачивания {module_name}: {str(e)}")
            await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка, смотри логи</b>')
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register_command('um')
    # удалить модуль
    async def unload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}um название_модуля</code>'
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден</b>')
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
        await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} удален</b>')

    @kernel.register_command('unlm')
    # выгрузить в виде файла
    async def upload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}unlm название_модуля</code>'
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules and module_name not in kernel.system_modules:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден</b>')
            return

        file_path = None
        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f'{module_name}.py')
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')

        if not os.path.exists(file_path):
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Файл модуля не найден</b>')
            return

        await edit_with_emoji(event, f'{CUSTOM_EMOJI["upload"]} <b>Отправка модуля {module_name}...</b>')
        await send_with_emoji(
            event.chat_id,
            f'{CUSTOM_EMOJI["file"]} <b>Модуль:</b> {module_name}.py\n\n'
            f'<blockquote><code>{kernel.custom_prefix}im</code> для установки</blockquote>',
            file=file_path
        )
        await event.delete()

    @kernel.register_command('reload')
    # <модуль> перезагрузить модуль
    async def reload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}reload название_модуля</code>'
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден</b>')
            return

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')

        if not os.path.exists(file_path):
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Файл модуля не найден</b>')
            return

        msg = await event.edit(f'{CUSTOM_EMOJI["reload"]} <b>Перезагрузка <code>{module_name}</code>...</b>', parse_mode='html')

        if module_name in sys.modules:
            del sys.modules[module_name]

        kernel.unregister_module_commands(module_name)
        del kernel.loaded_modules[module_name]

        success, message_text = await load_module_from_file(file_path, module_name, False)

        if success:
            commands = get_module_commands(module_name, kernel)
            cmd_text = f'{CUSTOM_EMOJI["crystal"]} {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}' if commands else 'Нет команд'

            emoji = random.choice(RANDOM_EMOJIS)
            await log_to_bot(f"⚗️ Модуль {module_name} перезагружен")
            await edit_with_emoji(msg,
                f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} перезагружен!</b> {emoji}\n\n{cmd_text}'
            )
        else:
            await kernel.handle_error(e, source="reload_module_handler", event=event)
            await edit_with_emoji(msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка, смотри логи</b>')

    @kernel.register_command('modules')
    # модули
    async def modules_list_handler(event):
        await log_to_bot(f"🔷 Просмотр списка модулей")

        if not kernel.loaded_modules and not kernel.system_modules:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["folder"]} <b>Модули не загружены</b>')
            return

        msg = f'{CUSTOM_EMOJI["crystal"]} <b>Загруженные модули:</b>\n\n'

        if kernel.system_modules:
            msg += f'{CUSTOM_EMOJI["shield"]} <b>Системные модули:</b>\n'
            for name in sorted(kernel.system_modules.keys()):
                commands = get_module_commands(name, kernel)
                msg += f'• <b>{name}</b> <i>({len(commands)} команд)</i>\n'
            msg += '\n'

        if kernel.loaded_modules:
            msg += f'{CUSTOM_EMOJI["sparkle"]} <b>Пользовательские модули:</b>\n'
            for name in sorted(kernel.loaded_modules.keys()):
                commands = get_module_commands(name, kernel)
                msg += f'• <b>{name}</b> <i>({len(commands)} команд)</i>\n'

        await edit_with_emoji(event, msg)

    @kernel.register_command('addrepo')
    # <URL> добавить repo
    async def add_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}addrepo URL</code>')
            return

        url = args[1].strip()
        success, message = await kernel.add_repository(url)

        if success:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>{message}</b>')
        else:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>{message}</b>')

    @kernel.register_command('delrepo')
    # <id> удалить repo
    async def del_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}delrepo индекс</code>')
            return

        success, message = await kernel.remove_repository(args[1])

        if success:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>{message}</b>')
        else:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>{message}</b>')
