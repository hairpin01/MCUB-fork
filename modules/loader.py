# author: @Hairpin00
# version: 1.0.9
# description: loader modules
import asyncio
import os
import re
import sys
import subprocess
import importlib.util
import inspect
import aiohttp
from datetime import datetime
import html
import json
import random
from telethon import events, Button
from telethon.tl.functions.messages import EditMessageRequest

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Кастомные эмодзи
CUSTOM_EMOJI = {
    "loading": '<tg-emoji emoji-id="5323463142775202324">🏓</tg-emoji>',
    "dependencies": '<tg-emoji emoji-id="5328311576736833844">🟠</tg-emoji>',
    "confused": '<tg-emoji emoji-id="5249119354825487565">🫨</tg-emoji>',
    "error": '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
    "file": '<tg-emoji emoji-id="5269353173390225894">💾</tg-emoji>',
    "process": '<tg-emoji emoji-id="5426958067763804056">⏳</tg-emoji>',
    "blocked": '<tg-emoji emoji-id="5431895003821513760">🚫</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5409235172979672859">⚠️</tg-emoji>',
    "idea": '<tg-emoji emoji-id="5411134407517964108">💡</tg-emoji>',
    "success": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    "test": '<tg-emoji emoji-id="5134183530313548836">🧪</tg-emoji>',
    "crystal": '<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji>',
    "sparkle": '<tg-emoji emoji-id="5426900601101374618">🪩</tg-emoji>',
    "folder": '<tg-emoji emoji-id="5217444336089714383">📂</tg-emoji>',
    "upload": '<tg-emoji emoji-id="5253526631221307799">📤</tg-emoji>',
    "shield": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji>',
    "angel": '<tg-emoji emoji-id="5404521025465518254">😇</tg-emoji>',
    "nerd": '<tg-emoji emoji-id="5465154440287757794">🤓</tg-emoji>',
    "cloud": '<tg-emoji emoji-id="5370947515220761242">🌩</tg-emoji>',
    "reload": '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    "convert": '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    "download": '<tg-emoji emoji-id="5469785308386041323">⬇️</tg-emoji>',
    "no_cmd": '<tg-emoji emoji-id="5429428837895141860">🫨</tg-emoji>',
}

# Случайные эмодзи для завершения
RANDOM_EMOJIS = [
    "ಠ_ಠ",
    "( ཀ ʖ̯ ཀ)",
    "(◕‿◕✿)",
    "(つ･･)つ",
    "༼つ◕_◕༽つ",
    "(•_•)",
    "☜(ﾟヮﾟ☜)",
    "(☞ﾟヮﾟ)☞",
    "ʕ•ᴥ•ʔ",
    "(づ￣ ³￣)づ",
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
        if hasattr(kernel, "log_module"):
            await kernel.log_module(text)
        elif hasattr(kernel, "send_log_message"):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['crystal']} {text}")

    async def log_error_to_bot(text):
        if hasattr(kernel, "log_error"):
            await kernel.log_error(text)
        elif hasattr(kernel, "send_log_message"):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['error']} {text}")

    async def edit_with_emoji(message, text, **kwargs):
        try:
            await message.edit(text, parse_mode='html', **kwargs)
            return True
        except Exception as e:
            kernel.logger.error('loader', f"Error in edit_with_emoji: {e}")
            return False

    async def send_with_emoji(chat_id, text, **kwargs):
        try:
            if "<emoji" in text:
                text = text.replace("<emoji document_id=", "<tg-emoji emoji-id=")
                text = text.replace("</emoji>", "</tg-emoji>")
            if "<tg-emoji" in text or re.search(r"<[^>]+>", text):
                parse_mode = kwargs.pop("parse_mode", "html")
                return await client.send_message(
                    chat_id, text, parse_mode=parse_mode, **kwargs
                )
            else:
                return await client.send_message(chat_id, text, **kwargs)
        except Exception as e:
            print(f"Error in send_with_emoji: {e}")
            # Fallback
            fallback_text = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", "", text)
            fallback_text = re.sub(r"<emoji[^>]*>.*?</emoji>", "", fallback_text)
            fallback_text = re.sub(r"<[^>]+>", "", fallback_text)
            return await client.send_message(chat_id, fallback_text, **kwargs)

    def get_module_commands(module_name, kernel):
        commands = []
        aliases_info = {}
        file_path = None

        if module_name in kernel.system_modules:
            file_path = f"modules/{module_name}.py"
        elif module_name in kernel.loaded_modules:
            file_path = f"modules_loaded/{module_name}.py"

        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                    patterns = [

                        r"@kernel\.register\.command\('([^']+)'",
                        r"kernel\.register\.command\('([^']+)'",

                        r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)",
                        r"register_command\s*\('([^']+)'",
                        r"@kernel\.register_command\('([^']+)'\)",
                        r"kernel\.register_command\('([^']+)'",
                        r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)",
                    ]
                    for pattern in patterns:
                        found = re.findall(pattern, code)
                        commands.extend(found)

                    alias_patterns = [
                        r"alias\s*=\s*['\"]([^'\"]+)['\"]",
                        r"alias\s*=\s*\[([^\]]+)\]",
                    ]
                    for i, cmd in enumerate(commands):

                        cmd_pattern = rf"(?:@kernel\.register\.command|kernel\.register\.command)\(['\"]{cmd}['\"][^)]+\)"
                        cmd_match = re.search(cmd_pattern, code, re.DOTALL)
                        if cmd_match:
                            cmd_line = cmd_match.group(0)
                            for alias_pattern in alias_patterns:
                                alias_matches = re.findall(alias_pattern, cmd_line)
                                for alias_match in alias_matches:
                                    if "[" in alias_match:
                                        alias_list = [
                                            a.strip().strip("'\"")
                                            for a in alias_match.split(",")
                                        ]
                                        aliases_info[cmd] = alias_list
                                    else:
                                        aliases_info[cmd] = [alias_match.strip()]
            except:
                pass
        for cmd in commands:
            if cmd in kernel.aliases:
                if isinstance(kernel.aliases[cmd], str):
                    aliases_info[cmd] = [kernel.aliases[cmd]]
                elif isinstance(kernel.aliases[cmd], list):
                    aliases_info[cmd] = kernel.aliases[cmd]
        return list(set([cmd for cmd in commands if cmd])), aliases_info

    def detect_module_type(module):
        if hasattr(module, "register"):
            sig = inspect.signature(module.register)
            params = list(sig.parameters.keys())
            if len(params) == 0:
                return "unknown"
            elif len(params) == 1:
                param_name = params[0]
                if param_name == "kernel":
                    return "new"
                elif param_name == "client":
                    return "old"
            return "unknown"
        return "none"

    async def load_module_from_file(file_path, module_name, is_system=False):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            if "from .. import" in code or "import loader" in code:
                return False, "Несовместимый модуль, [Heroku/Hikka]"
            if module_name in sys.modules:
                del sys.modules[module_name]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            module.kernel = kernel
            module.client = client
            module.custom_prefix = kernel.custom_prefix
            sys.modules[module_name] = module
            kernel.set_loading_module(module_name, "system" if is_system else "user")
            spec.loader.exec_module(module)
            module_type = detect_module_type(module)
            if module_type == "new":
                module.register(kernel)
            elif module_type == "old":
                module.register(client)
            elif module_type == "none":
                return False, "Модуль не имеет функции register"
            else:
                return False, "Неизвестный тип модуля"
            if is_system:
                kernel.system_modules[module_name] = module
            else:
                kernel.loaded_modules[module_name] = module
            return True, f"Модуль {module_name} загружен ({module_type})"
        except kernel.CommandConflictError as e:
            raise e
        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                return (
                    False,
                    f"Требуется зависимость: {dep}. Используйте: pip install {dep}",
                )
            return False, f"Ошибка импорта: {error_msg}"
        except Exception as e:
            return False, f"Ошибка загрузки: {str(e)}"
        finally:
            kernel.clear_loading_module()

    async def handle_catalog(event, query_or_data):
        try:
            parts = query_or_data.split('_')

            repo_index = 0
            page = 1

            if len(parts) >= 2 and parts[1].isdigit():
                repo_index = int(parts[1])

            if len(parts) >= 3 and parts[2].isdigit():
                page = int(parts[2])

            repos = [kernel.default_repo] + kernel.repositories

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
                repo_name = repo_url.split("/")[-2] if "/" in repo_url else repo_url

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

            return msg, buttons

        except Exception as e:
            print(f"Ошибка в handle_catalog: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ Ошибка загрузки каталога: {str(e)[:100]}", []

    async def catalog_inline_handler(event):
        try:


            query = event.text or ""


            if not query or query == "catalog":
                query = "catalog_0_1"

            msg, buttons = await handle_catalog(event, query)

            if buttons:
                builder = event.builder.article(
                    "Catalog",
                    text=msg,
                    buttons=buttons,
                    parse_mode="html"
                )
            else:
                builder = event.builder.article(
                    "Catalog",
                    text=msg,
                    parse_mode="html"
                )

            await event.answer([builder])

        except Exception as e:
            print(f"Ошибка в catalog_inline_handler: {e}")

    async def catalog_callback_handler(event):
        try:

            data_str = event.data.decode("utf-8") if isinstance(event.data, bytes) else str(event.data)

            msg, buttons = await handle_catalog(event, data_str)

            await event.edit(msg, buttons=buttons if buttons else None, parse_mode="html")

        except Exception as e:
            print(f"Ошибка в catalog_callback_handler: {e}")
            await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)

    kernel.register_inline_handler("catalog", catalog_inline_handler)
    kernel.register_callback_handler("catalog_", catalog_callback_handler)

    @kernel.register.command("iload", alias="im") # загрузить модуль
    async def install_module_handler(event):
        if not event.is_reply:
            await edit_with_emoji(
                event, f'{CUSTOM_EMOJI["warning"]} <b>Ответьте на .py файл</b>'
            )
            return

        reply = await event.get_reply_message()
        if not reply.document or not reply.document.attributes[0].file_name.endswith(".py"):
            await edit_with_emoji(
                event, f'{CUSTOM_EMOJI["warning"]} <b>Это не .py файл</b>'
            )
            return

        file_name = reply.document.attributes[0].file_name
        module_name = file_name[:-3]


        install_log = []

        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            kernel.logger.debug(log_entry)

        if module_name in kernel.system_modules:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["confused"]} <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>{CUSTOM_EMOJI["blocked"]} К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>',
            )
            return

        is_update = module_name in kernel.loaded_modules

        action = (
            f'{CUSTOM_EMOJI["reload"]} обновляю'
            if is_update
            else f'{CUSTOM_EMOJI["test"]} устанавливаю'
        )
        msg = await event.edit(
            f"{action} модуль <b>{module_name}</b>", parse_mode="html"
        )

        add_log(f"=- Начинаю {'обновление' if is_update else 'установку'} модуля {module_name}")
        add_log(f"=> Имя файла: {file_name}")

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, file_name)

        try:

            add_log(f"=- Скачиваю файл в {file_path}")
            await reply.download_media(file_path)
            add_log("=> Файл успешно скачан")

            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            add_log("=> Файл прочитан")


            add_log("=- Проверяю совместимость модуля...")
            if "from .. import" in code or "import loader" in code:
                add_log("=X Модуль не совместим (Heroku/Hikka тип)")
                await edit_with_emoji(
                    msg, f'{CUSTOM_EMOJI["warning"]} <b>Модуль не совместим</b>'
                )
                os.remove(file_path)
                return
            add_log("=> Модуль совместим")


            add_log("Получаю метаданные модуля...")
            metadata = await kernel.get_module_metadata(code)
            add_log(f"Автор: {metadata['author']}")
            add_log(f"Версия: {metadata['version']}")
            add_log(f"Описание: {metadata['description']}")

            dependencies = []
            add_log("=- Проверяю зависимости...")
            if "requires" in code:
                reqs = re.findall(r"# requires: (.+)", code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(",")]
                    add_log(f"=> Найдены зависимости: {', '.join(dependencies)}")

            if dependencies:
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["dependencies"]} <b>ставлю зависимости:</b>\n<code>{chr(10).join(dependencies)}</code>',
                )

                for dep in dependencies:
                    add_log(f"=- Устанавливаю зависимость: {dep}")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", dep],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        add_log(f"=> Зависимость {dep} установлена успешно")
                    else:
                        add_log(f"=X Ошибка установки {dep}: {result.stderr[:200]}")

            if is_update:
                add_log(f"=- Удаляю старые команды модуля {module_name}")
                kernel.unregister_module_commands(module_name)

            add_log(f"=- Загружаю модуль {module_name}...")
            success, message_text = await kernel.load_module_from_file(
                file_path, module_name, False
            )

            if success:
                add_log("=> Модуль успешно загружен")
                commands, aliases_info = get_module_commands(module_name, kernel)

                emoji = random.choice(RANDOM_EMOJIS)

                final_msg = f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} загружен!</b> {emoji}\n'
                final_msg += f'<blockquote>{CUSTOM_EMOJI["idea"]} <i>D: {metadata["description"]}</i> | V: <code>{metadata["version"]}</code></blockquote>\n'
                final_msg += "<blockquote>"

                if commands:
                    add_log(f"=> Найдено команд: {len(commands)}")
                    for cmd in commands:
                        cmd_desc = metadata["commands"].get(
                            cmd, f'{CUSTOM_EMOJI["no_cmd"]} У команды нету описания'
                        )
                        final_msg += f'{CUSTOM_EMOJI["crystal"]} <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>'

                        if cmd in aliases_info:
                            aliases = aliases_info[cmd]
                            if isinstance(aliases, str):
                                aliases = [aliases]
                            if aliases:
                                alias_text = ", ".join(
                                    [
                                        f"<code>{kernel.custom_prefix}{a}</code>"
                                        for a in aliases
                                    ]
                                )
                                final_msg += f" (Aliases: {alias_text})"
                                add_log(f"Команда {cmd} имеет алиасы: {', '.join(aliases)}")
                        final_msg += "\n"
                final_msg += '</blockquote>'

                kernel.logger.info(f"Модуль {module_name} установлен")
                await edit_with_emoji(msg, final_msg)

            else:
                add_log(f"=X Ошибка загрузки модуля: {message_text}")
                log_text = "\n".join(install_log)
                await edit_with_emoji(
                    msg,
                    f'<b>{CUSTOM_EMOJI['blocked']} Кажется установка прошла не удачно</b>\n'
                    f'<b>{CUSTOM_EMOJI['idea']} Install Log:</b>\n<pre>{html.escape(log_text)}</pre>'
                )

                if os.path.exists(file_path):
                    os.remove(file_path)

        except CommandConflictError as e:
            add_log(f"✗ Конфликт команд: {e}")
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["shield"]} <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{e.command}</code>)\n'
                    f"<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>\n"
                    f"<b>Лог установки:</b>\n<pre>{html.escape(log_text)}</pre>",
                )
            elif e.conflict_type == "user":
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["error"]} <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n'
                    f"<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>\n"
                    f"<b>Лог установки:</b>\n<pre>{html.escape(log_text)}</pre>",
                )
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            add_log(f"=X Критическая ошибка: {str(e)}")
            import traceback
            add_log(f"Трейсбэк:\n{traceback.format_exc()}")

            log_text = "\n".join(install_log)
            await edit_with_emoji(
                msg,
                f'<b>{CUSTOM_EMOJI['blocked']} Кажется установка прошла не удачно</b>\n'
                f'<b>{CUSTOM_EMOJI['idea']} Install Log:</b>\n<pre>{html.escape(log_text)}</pre>'
            )
            await kernel.handle_error(e, source="install_module_handler", event=event)
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register.command("dlm")
    async def download_module_handler(event):
        args = event.text.split()

        if len(args) < 2:
            try:
                bot_username = None
                if hasattr(kernel, "bot_client") and kernel.bot_client:
                    bot_info = await kernel.bot_client.get_me()
                    bot_username = bot_info.username

                if bot_username:
                    results = await client.inline_query(bot_username, "catalog_")
                    if results:
                        await results[0].click(event.chat_id)
                        await event.delete()
                        return
            except Exception as e:
                kernel.logger.error(f"Error calling inline catalog: {e}")
                pass

            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}dlm [-send/-s/-list] название_модуля или ссылка</code>',
            )
            return

        if args[1] == "-list":
            if len(args) == 2:
                await edit_with_emoji(
                    event, f'{CUSTOM_EMOJI["loading"]} <b>Получаю список модулей...</b>'
                )

                repos = [kernel.default_repo] + kernel.repositories
                message_lines = []
                errors = []

                for i, repo in enumerate(repos):
                    try:
                        modules = await kernel.get_repo_modules_list(repo)
                        repo_name = await kernel.get_repo_name(repo)

                        if modules:
                            module_list = " | ".join(modules)
                            message_lines.append(f"<b>{repo_name}</b>: {module_list}")
                        else:
                            errors.append(f"{i+1}. {repo_name}: пустой список")
                    except Exception as e:
                        errors.append(f"{i+1}. {repo}: ошибка - {str(e)[:50]}")

                if message_lines:
                    msg_text = "\n".join(message_lines)
                    final_msg = f'{CUSTOM_EMOJI["folder"]} <b>Список модулей из репозиториев:</b>\n<blockquote>{msg_text}</blockquote>'

                    if errors:
                        final_msg += f'\n\n{CUSTOM_EMOJI["warning"]} <b>Ошибки:</b>\n<blockquote>{"<br>".join(errors)}</blockquote>'
                else:
                    final_msg = f'{CUSTOM_EMOJI["warning"]} <b>Не удалось получить список модулей</b>'
                    if errors:
                        final_msg += f'\n<blockquote>{"<br>".join(errors)}</blockquote>'

                await edit_with_emoji(event, final_msg)
                return
            else:
                module_name = args[2]
                msg = await event.edit(
                    f'{CUSTOM_EMOJI["loading"]} <b>Ищу модуль {module_name}...</b>',
                    parse_mode="html",
                )

                repos = [kernel.default_repo] + kernel.repositories
                found = False

                for repo in repos:
                    try:
                        code = await kernel.download_module_from_repo(repo, module_name)
                        if code:
                            found = True
                            metadata = await kernel.get_module_metadata(code)
                            size = len(code.encode("utf-8"))

                            info = (
                                f'{CUSTOM_EMOJI["file"]} <b>Модуль:</b> <code>{module_name}</code>\n'
                                f'{CUSTOM_EMOJI["idea"]} <b>Описание:</b> <i>{metadata["description"]}</i>\n'
                                f'{CUSTOM_EMOJI["crystal"]} <b>Версия:</b> <code>{metadata["version"]}</code>\n'
                                f'{CUSTOM_EMOJI["angel"]} <b>Автор:</b> <i>{metadata["author"]}</i>\n'
                                f'{CUSTOM_EMOJI["folder"]} <b>Размер:</b> <code>{size} байт</code>\n'
                                f'{CUSTOM_EMOJI["cloud"]} <b>Репозиторий:</b> <code>{repo}</code>'
                            )
                            await edit_with_emoji(msg, info)
                            break
                    except Exception as e:
                        await kernel.log_error(
                            f"Ошибка поиска модуля {module_name} в {repo}: {e}"
                        )
                        continue

                if not found:
                    await edit_with_emoji(
                        msg,
                        f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден ни в одном репозитории</b>',
                    )
                return

        send_mode = False
        module_or_url = None
        repo_index = None

        if args[1] in ["-send", "-s"]:
            if len(args) < 3:
                await edit_with_emoji(
                    event,
                    f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}dlm -send название_модуля или ссылка</code>',
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
        if module_or_url.startswith(
            ("http://", "https://", "raw.githubusercontent.com")
        ):
            is_url = True
            if module_or_url.endswith(".py"):
                module_name = os.path.basename(module_or_url)[:-3]
            else:
                module_name = os.path.basename(module_or_url).split("?")[0]
                if "." in module_name:
                    module_name = module_name.split(".")[0]
        else:
            module_name = module_or_url

        if module_name in kernel.system_modules:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["confused"]} <b>Ой, кажется ты попытался установить системный модуль</b> <code>{module_name}</code>\n'
                f'<blockquote><i>{CUSTOM_EMOJI["blocked"]} Системные модули нельзя устанавливать через <code>dlm</code></i></blockquote>',
            )
            return

        is_update = module_name in kernel.loaded_modules

        if send_mode:
            action = f"{CUSTOM_EMOJI['download']} скачиваю"
        else:
            action = (
                f"{CUSTOM_EMOJI['test']} обновляю"
                if is_update
                else f"{CUSTOM_EMOJI['test']} устанавливаю"
            )

        msg = await event.edit(
            f"{action} модуль <b>{module_name}</b>", parse_mode="html"
        )


        install_log = []

        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            kernel.logger.debug(log_entry)

        try:
            code = None
            repo_url = None

            add_log(f"=> Начинаю {'скачивание' if send_mode else 'установку'} модуля {module_name}")
            add_log(f"=+ Режим: {'отправка' if send_mode else 'установка'}")
            add_log(f"=+ Тип: {'URL' if is_url else 'из репозитория'}")

            if is_url:
                try:
                    add_log(f"=- Скачиваю модуль по URL: {module_or_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(module_or_url) as resp:
                            if resp.status == 200:
                                code = await resp.text()
                                add_log(f"=> ✓ Модуль скачан успешно (статус: {resp.status})")
                                save_name = module_name + ".py"
                            else:
                                add_log(f"=X Ошибка скачивания (статус: {resp.status})")
                                await edit_with_emoji(
                                    msg,
                                    f'{CUSTOM_EMOJI["warning"]} <b>Не удалось скачать модуль по ссылке</b> (статус: {resp.status})',
                                )
                                return
                except Exception as e:
                    add_log(f"=X Ошибка скачивания: {str(e)}")
                    await kernel.handle_error(e, source="install_for_url", event=event)
                    await edit_with_emoji(
                        msg,
                        f'{CUSTOM_EMOJI["warning"]} <b>Ошибка скачивания:</b> {str(e)[:100]}',
                    )
                    return
            else:
                repos = [kernel.default_repo] + kernel.repositories
                add_log(f"=- Проверяю репозитории ({len(repos)} шт.)")

                if repo_index is not None and 0 <= repo_index < len(repos):
                    repo_url = repos[repo_index]
                    add_log(f"=- Использую указанный репозиторий: {repo_url}")
                    code = await kernel.download_module_from_repo(repo_url, module_name)
                    if code:
                        add_log(f"=> Модуль найден в указанном репозитории")
                    else:
                        add_log(f"=X Модуль не найден в указанном репозитории")
                else:
                    for i, repo in enumerate(repos):
                        try:
                            add_log(f"=- Проверяю репозиторий {i+1}: {repo}")
                            code = await kernel.download_module_from_repo(repo, module_name)
                            if code:
                                repo_url = repo
                                add_log(f"=> Модуль найден в репозитории {repo}")
                                break
                            else:
                                add_log(f"=X Модуль не найден в репозитории {repo}")
                        except Exception as e:
                            add_log(f"=X Ошибка проверки репозитория {repo}: {str(e)[:100]}")
                            await kernel.log_error(
                                f"Ошибка скачивания модуля {module_name} из {repo}: {e}"
                            )
                            continue

            if not code:
                add_log("=X Модуль не найден ни в одном репозитории")
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден в репозиториях</b>',
                )
                return

            metadata = await kernel.get_module_metadata(code)
            add_log(f"=> Получены метаданные модуля:")
            add_log(f"=+  Автор: {metadata['author']}")
            add_log(f"=+  Версия: {metadata['version']}")
            add_log(f"=+  Описание: {metadata['description']}")

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")

            if send_mode:
                add_log("Сохраняю файл для отправки")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["upload"]} <b>Отправляю модуль {module_name}...</b>',
                )
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
                    parse_mode="html",
                )

                add_log("=> Файл отправлен, удаляю временный файл")
                os.remove(file_path)
                return

            # Режим установки
            add_log("=- Режим установки, продолжаю...")

            dependencies = []
            if "requires" in code:
                reqs = re.findall(r"# requires: (.+)", code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(",")]
                    add_log(f"=- Найдены зависимости: {', '.join(dependencies)}")

            if dependencies:
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["dependencies"]} <b>ставлю зависимости:</b>\n<code>{chr(10).join(dependencies)}</code>',
                )

                for dep in dependencies:
                    add_log(f"=- Устанавливаю зависимость: {dep}")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", dep],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        add_log(f"=> Зависимость {dep} установлена")
                    else:
                        add_log(f"=X Ошибка установки {dep}: {result.stderr[:200]}")

            if is_update:
                add_log(f"=- Обновляю модуль, удаляю старые команды")
                kernel.unregister_module_commands(module_name)

            add_log(f"=- Сохраняю файл модуля: {file_path}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            add_log(f"=- Загружаю модуль в ядро")
            success, message_text = await kernel.load_module_from_file(
                file_path, module_name, False
            )

            if success:
                add_log("=> Модуль успешно загружен")
                commands, aliases_info = get_module_commands(module_name, kernel)
                emoji = random.choice(RANDOM_EMOJIS)

                final_msg = f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} загружен!</b> {emoji}\n'
                final_msg += f'<blockquote>📝 <i>D: {metadata["description"]}</i> | V: <code>{metadata["version"]}</code></blockquote>\n'

                if commands:
                    add_log(f"=> Найдено команд: {len(commands)}")
                    final_msg += "<blockquote>"
                    for cmd in commands:
                        cmd_desc = metadata["commands"].get(
                            cmd, f'{CUSTOM_EMOJI["no_cmd"]} У команды нету описания'
                        )
                        final_msg += f'{CUSTOM_EMOJI["crystal"]} <code>{kernel.custom_prefix}{cmd}</code> – <b>{cmd_desc}</b>'

                        if cmd in aliases_info:
                            aliases = aliases_info[cmd]
                            if isinstance(aliases, str):
                                aliases = [aliases]
                            if aliases:
                                alias_text = ", ".join(
                                    [
                                        f"<code>{kernel.custom_prefix}{a}</code>"
                                        for a in aliases
                                    ]
                                )
                                final_msg += f" (aliases: {alias_text})"
                                add_log(f"=> Команда {cmd} имеет алиасы: {', '.join(aliases)}")
                        final_msg += "\n"
                    final_msg += "</blockquote>"

                kernel.logger.info(f"Модуль {module_name} скачан")
                await edit_with_emoji(msg, final_msg)
            else:
                add_log(f"=X Ошибка загрузки модуля: {message_text}")
                log_text = "\n".join(install_log)
                await edit_with_emoji(
                    msg,
                    f'<b>{CUSTOM_EMOJI['blocked']} Кажется установка прошла не удачно</b>\n'
                    f'<b>{CUSTOM_EMOJI['idea']} Install Log:</b>\n<pre>{html.escape(log_text)}</pre>'
                )
                if os.path.exists(file_path):
                    add_log("=> Удаляю файл модуля из-за ошибки")
                    os.remove(file_path)

        except CommandConflictError as e:
            add_log(f"=X Конфликт команд: {e}")
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["shield"]} <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{e.command}</code>)\n'
                    f"<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>\n"
                    f"<b>Лог установки:</b>\n<pre>{html.escape(log_text)}</pre>",
                )
            elif e.conflict_type == "user":
                await edit_with_emoji(
                    msg,
                    f'{CUSTOM_EMOJI["error"]} <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n'
                    f"<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>\n"
                    f"<b>Лог установки:</b>\n<pre>{html.escape(log_text)}</pre>",
                )

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
            if os.path.exists(file_path):
                add_log("=> Удаляю файл модуля из-за конфликта")
                os.remove(file_path)

        except Exception as e:
            add_log(f"=X Критическая ошибка: {str(e)}")
            import traceback
            add_log(f"Трейсбэк:\n{traceback.format_exc()}")

            log_text = "\n".join(install_log)
            await edit_with_emoji(
                msg,
                f'<b>{CUSTOM_EMOJI['blocked']} Кажется установка прошла не удачно</b>\n'
                f'<b>{CUSTOM_EMOJI['idea']} Install Log:</b>\n<pre>{html.escape(log_text)}</pre>'
            )

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
            if os.path.exists(file_path):
                add_log("=> Удаляю файл модуля из-за ошибки")
                os.remove(file_path)

    @kernel.register.command("um")
    # удалить модуль
    async def unload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}um название_модуля</code>',
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден</b>',
            )
            return

        kernel.unregister_module_commands(module_name)

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        if module_name in sys.modules:
            del sys.modules[module_name]

        if module_name in kernel.loaded_modules:
            del kernel.loaded_modules[module_name]

        await log_to_bot(f"Модуль {module_name} удалён")
        await edit_with_emoji(
            event, f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} удален</b>'
        )

    @kernel.register.command("unlm")
    # выгрузить в виде файла
    async def upload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}unlm название_модуля</code>',
            )
            return

        module_name = args[1]

        if (
            module_name not in kernel.loaded_modules
            and module_name not in kernel.system_modules
        ):
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден</b>',
            )
            return

        file_path = None
        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f"{module_name}.py")
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")

        if not os.path.exists(file_path):
            await edit_with_emoji(
                event, f'{CUSTOM_EMOJI["warning"]} <b>Файл модуля не найден</b>'
            )
            return

        await edit_with_emoji(
            event, f'{CUSTOM_EMOJI["upload"]} <b>Отправка модуля {module_name}...</b>'
        )
        await send_with_emoji(
            event.chat_id,
            f'{CUSTOM_EMOJI["file"]} <b>Модуль:</b> {module_name}.py\n\n'
            f"<blockquote><code>{kernel.custom_prefix}im</code> для установки</blockquote>",
            file=file_path,
        )
        await event.delete()

    @kernel.register.command("reload")
    # <модуль> перезагрузить модуль
    async def reload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}reload название_модуля</code>',
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules and module_name not in kernel.system_modules:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Модуль {module_name} не найден</b>',
            )
            return

        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f"{module_name}.py")
            is_system = True
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
            is_system = False

        if not os.path.exists(file_path):
            await edit_with_emoji(
                event, f'{CUSTOM_EMOJI["warning"]} <b>Файл модуля не найден</b>'
            )
            return

        msg = await event.edit(
            f'{CUSTOM_EMOJI["reload"]} <b>Перезагрузка <code>{module_name}</code>...</b>',
            parse_mode="html",
        )

        if module_name in sys.modules:
            del sys.modules[module_name]

        kernel.unregister_module_commands(module_name)


        if is_system:
            if module_name in kernel.system_modules:
                del kernel.system_modules[module_name]
        else:
            if module_name in kernel.loaded_modules:
                del kernel.loaded_modules[module_name]

        success, message_text = await load_module_from_file(
            file_path, module_name, is_system
        )

        if success:
            commands, aliases = get_module_commands(module_name, kernel)
            cmd_text = (
                f'{CUSTOM_EMOJI["crystal"]} {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}'
                if commands
                else "Нет команд"
            )

            emoji = random.choice(RANDOM_EMOJIS)
            kernel.logger.info(f"Модуль {module_name} перезагружен")
            await edit_with_emoji(
                msg,
                f'{CUSTOM_EMOJI["success"]} <b>Модуль {module_name} перезагружен!</b> {emoji}\n\n<blockquote>{cmd_text}</blockquote>',
            )
        else:
            await kernel.handle_error(Exception(message_text), source="reload_module_handler", event=event)
            await edit_with_emoji(
                msg, f'{CUSTOM_EMOJI["warning"]} <b>Ошибка, смотри логи</b>'
            )

    @kernel.register.command("modules")
    # модули
    async def modules_list_handler(event):
        await log_to_bot(f"🔷 Просмотр списка модулей")

        if not kernel.loaded_modules and not kernel.system_modules:
            await edit_with_emoji(
                event, f'{CUSTOM_EMOJI["folder"]} <b>Модули не загружены</b>'
            )
            return

        msg = f'{CUSTOM_EMOJI["crystal"]} <b>Загруженные модули:</b>\n\n'

        if kernel.system_modules:
            msg += f'{CUSTOM_EMOJI["shield"]} <b>Системные модули:</b>\n'
            for name in sorted(kernel.system_modules.keys()):
                commands = get_module_commands(name, kernel)
                msg += f"• <b>{name}</b> <i>({len(commands)} команд)</i>\n"
            msg += "\n"

        if kernel.loaded_modules:
            msg += f'{CUSTOM_EMOJI["sparkle"]} <b>Пользовательские модули:</b>\n'
            for name in sorted(kernel.loaded_modules.keys()):
                commands = get_module_commands(name, kernel)
                msg += f"• <b>{name}</b> <i>({len(commands)} команд)</i>\n"

        await edit_with_emoji(event, msg)

    @kernel.register.command("addrepo")
    # <URL> добавить repo
    async def add_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}addrepo URL</code>',
            )
            return

        url = args[1].strip()
        success, message = await kernel.add_repository(url)

        if success:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>{message}</b>')
        else:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>{message}</b>')

    @kernel.register.command("delrepo")
    # <id> удалить repo
    async def del_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                f'{CUSTOM_EMOJI["warning"]} <b>Использование:</b> <code>{kernel.custom_prefix}delrepo индекс</code>',
            )
            return

        success, message = await kernel.remove_repository(args[1])

        if success:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>{message}</b>')
        else:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>{message}</b>')
