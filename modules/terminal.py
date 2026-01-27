# requires: telethon>=1.24
# author: @Hairpin00
# version: 1.0.5
# description: выполнить команду в terminal с поддержкой sudo и алиасами

import asyncio
import subprocess
import time
import html
import re
import signal
import os
from pathlib import Path
from telethon import events

# premium emoji dictionary
CUSTOM_EMOJI = {
    '💻': '<tg-emoji emoji-id="5472111548572900003">💻</tg-emoji>',
    '📝': '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    '🧮': '<tg-emoji emoji-id="5472404950673791399">🧮</tg-emoji>',
    '📎': '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    '📁': '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    '📰': '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
    '📚': '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    '⌨️': '<tg-emoji emoji-id="5472111548572900003">⌨️</tg-emoji>',
    '💼': '<tg-emoji emoji-id="5359785904535774578">💼</tg-emoji>',
    '🖨': '<tg-emoji emoji-id="5386494631112353009">🖨</tg-emoji>',
    '☑️': '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    '➕': '<tg-emoji emoji-id="5226945370684140473">➕</tg-emoji>',
    '➖': '<tg-emoji emoji-id="5229113891081956317">➖</tg-emoji>',
    '💬': '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    '💭': '<tg-emoji emoji-id="5465143921912846619">💭</tg-emoji>',
    '🗯': '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    '✏️': '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    '🐉': '<tg-emoji emoji-id="5470088387048266598">🐉</tg-emoji>',
    '🐢': '<tg-emoji emoji-id="5350813992732338949">🐢</tg-emoji>',
    '🧊': '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
    '❄️': '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    '🔐': '<tg-emoji emoji-id="5413720894091851002">🔐</tg-emoji>',
    '⚠️': '<tg-emoji emoji-id="5453943626921666997">⚠️</tg-emoji>',
    '✅': '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
}

def register(kernel):
    client = kernel.client

    class TerminalModule:
        def __init__(self):
            self.running_commands = {}
            self.update_tasks = {}
            self.sudo_auth = {}
            self.kernel = kernel
            self.client = kernel.client
            
            # Регулярные выражения для sudo (из кода Heroku)
            self.PASS_REQ = ["[sudo] password for", "[sudo] пароль для"]
            self.WRONG_PASS = [
                r"\[sudo\] password for (.*): Sorry, try again\.",
                r"\[sudo\] пароль для (.*): Попробуйте еще раз\."
            ]
            self.TOO_MANY_TRIES = [
                r"\[sudo\] password for (.*): sudo: [0-9]+ incorrect password attempts",
                r"\[sudo\] пароль для (.*): sudo: [0-9]+ неверные попытки ввода пароля"
            ]

        def format_output(self, text, max_length=2000):
            if not text:
                return "пусто"
            text = str(text)
            if len(text) > max_length:
                text = text[:max_length] + "..."
            text = html.escape(text)
            text = text.replace("\n", "<br>")
            text = text.replace("\t", "&nbsp;" * 4)
            return text

        async def run_command(self, chat_id, command, sudo_auth=None):
            if chat_id in self.running_commands:
                await client.send_message(chat_id, f"{CUSTOM_EMOJI['🗯']} <i>Уже выполняется команда</i>", parse_mode='html')
                return

            try:
                # Подготавливаем команду для sudo
                cmd_data = {
                    'command': command,
                    'sudo_auth': sudo_auth,
                    'sudo_state': 0,  # 0 - ожидание пароля, 1 - пароль отправлен, 2 - аутентификация завершена
                    'auth_msg_id': None,
                    'stdout': b'',
                    'stderr': b'',
                    'completed': False,
                    'return_code': None,
                    'process': None
                }

                # Создаем процесс
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE
                )

                cmd_data['process'] = process
                start_time = time.time()
                cmd_data['start_time'] = start_time
                self.running_commands[chat_id] = cmd_data

                msg = await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['💻']} <i>системная команда:</i> <code>{html.escape(command)}</code>\n"
                    f"{CUSTOM_EMOJI['❄️']} <i>выполняется...</i>",
                    parse_mode='html'
                )

                cmd_data['message_id'] = msg.id

                # Запускаем задачи для чтения вывода и обновления
                update_task = asyncio.create_task(self.update_output(chat_id))
                read_task = asyncio.create_task(self.read_output(chat_id))
                
                self.update_tasks[chat_id] = {
                    'update': update_task,
                    'read': read_task
                }

            except Exception as e:
                await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['🗯']} <i>Ошибка запуска:</i> <code>{html.escape(str(e))}</code>",
                    parse_mode='html'
                )
                if chat_id in self.running_commands:
                    del self.running_commands[chat_id]

        async def read_output(self, chat_id):
            if chat_id not in self.running_commands:
                return

            cmd_data = self.running_commands[chat_id]
            process = cmd_data['process']

            async def read_stream(stream, is_stderr=False):
                data = b''
                try:
                    while True:
                        chunk = await stream.read(4096)
                        if not chunk:
                            break
                        data += chunk
                        
                        # Если это stderr, проверяем на запрос sudo пароля
                        if is_stderr:
                            decoded = chunk.decode('utf-8', errors='ignore')
                            await self.check_sudo_prompt(chat_id, decoded)
                            
                except Exception as e:
                    print(f"Error reading stream: {e}")

                if is_stderr:
                    cmd_data['stderr'] += data
                else:
                    cmd_data['stdout'] += data

            await asyncio.gather(
                read_stream(process.stdout, False),
                read_stream(process.stderr, True)
            )

            await process.wait()

            cmd_data['completed'] = True
            cmd_data['return_code'] = process.returncode

            await self.send_final_output(chat_id)

            # Очистка задач
            if chat_id in self.update_tasks:
                tasks = self.update_tasks[chat_id]
                tasks['update'].cancel()
                del self.update_tasks[chat_id]

            if chat_id in self.running_commands:
                del self.running_commands[chat_id]

        async def check_sudo_prompt(self, chat_id, stderr_text):
            """Проверяет stderr на наличие запроса sudo пароля"""
            if chat_id not in self.running_commands:
                return
                
            cmd_data = self.running_commands[chat_id]
            
            # Проверяем, запрашивает ли sudo пароль
            for pattern in self.PASS_REQ:
                if pattern in stderr_text:
                    if cmd_data['sudo_state'] == 0:
                        # Запрашиваем пароль
                        await self.request_sudo_password(chat_id)
                    return
                    
            # Проверяем на неверный пароль
            for pattern in self.WRONG_PASS:
                if re.search(pattern, stderr_text):
                    if cmd_data['sudo_state'] == 1:
                        await self.handle_wrong_password(chat_id)
                    return
                    
            # Проверяем на слишком много попыток
            for pattern in self.TOO_MANY_TRIES:
                if re.search(pattern, stderr_text):
                    await self.handle_too_many_attempts(chat_id)
                    return

        async def request_sudo_password(self, chat_id):
            """Отправляет запрос на ввод sudo пароля"""
            if chat_id not in self.running_commands:
                return
                
            cmd_data = self.running_commands[chat_id]
            cmd_data['sudo_state'] = 1
            
            # Отправляем сообщение с запросом пароля
            auth_msg = await self.client.send_message(
                'me',  # Отправляем в сохраненные сообщения для безопасности
                f"{CUSTOM_EMOJI['🔐']} <b>Требуется sudo пароль</b>\n"
                f"Команда: <code>{html.escape(cmd_data['command'])}</code>\n\n"
                f"Отредактируйте это сообщение, введя пароль.\n",
                parse_mode='html'
            )
            
            cmd_data['auth_msg_id'] = auth_msg.id
            
            # Отправляем уведомление в чат
            await self.client.send_message(
                chat_id,
                f"{CUSTOM_EMOJI['🔐']} <i>Требуется sudo пароль. Проверьте сохраненные сообщения.</i>",
                parse_mode='html'
            )
            
            # Регистрируем обработчик для редактирования сообщения
            @self.client.on(events.MessageEdited(chats=['me']))
            async def sudo_password_handler(event):
                if event.id == cmd_data['auth_msg_id']:
                    password = event.message.message.strip()
                    
                    # Отправляем пароль в процесс
                    if chat_id in self.running_commands:
                        current_cmd = self.running_commands[chat_id]
                        if current_cmd['process'] and not current_cmd['process'].stdin.is_closing():
                            current_cmd['process'].stdin.write(f"{password}\n".encode())
                            await current_cmd['process'].stdin.drain()
                            
                            # Обновляем состояние
                            current_cmd['sudo_state'] = 2
                            
                            # Удаляем сообщение с паролем
                            await event.delete()
                            
                            # Отправляем подтверждение
                            await self.client.send_message(
                                chat_id,
                                f"{CUSTOM_EMOJI['✅']} <i>Пароль отправлен</i>",
                                parse_mode='html'
                            )
                    
                    # Удаляем обработчик
                    self.client.remove_event_handler(sudo_password_handler)

        async def handle_wrong_password(self, chat_id):
            """Обрабатывает неверный пароль"""
            if chat_id not in self.running_commands:
                return
                
            cmd_data = self.running_commands[chat_id]
            cmd_data['sudo_state'] = 0
            
            await self.client.send_message(
                chat_id,
                f"{CUSTOM_EMOJI['⚠️']} <i>Неверный пароль. Повторите ввод в сохраненных сообщениях.</i>",
                parse_mode='html'
            )
            
            # Повторно запрашиваем пароль
            await self.request_sudo_password(chat_id)

        async def handle_too_many_attempts(self, chat_id):
            """Обрабатывает слишком много неудачных попыток"""
            await self.client.send_message(
                chat_id,
                f"{CUSTOM_EMOJI['⚠️']} <i>Слишком много неудачных попыток. Команда остановлена.</i>",
                parse_mode='html'
            )
            
            # Останавливаем команду
            await self.kill_command(chat_id)

        async def update_output(self, chat_id):
            while chat_id in self.running_commands:
                try:
                    cmd_data = self.running_commands[chat_id]

                    if cmd_data['completed']:
                        break

                    stdout_text = self.format_output(cmd_data['stdout'].decode('utf-8', errors='ignore'))
                    stderr_text = self.format_output(cmd_data['stderr'].decode('utf-8', errors='ignore'))

                    elapsed = time.time() - cmd_data['start_time']

                    # Добавляем информацию о состоянии sudo
                    sudo_status = ""
                    if cmd_data['sudo_state'] == 1:
                        sudo_status = f"{CUSTOM_EMOJI['🔐']} <i>Ожидание sudo пароля...</i>\n\n"

                    output = f"""{sudo_status}{CUSTOM_EMOJI['💻']} <i>системная команда:</i> <code>{html.escape(cmd_data['command'])}</code>

<b>stdout:</b>
<blockquote><code>{stdout_text}</code></blockquote>
<b>stderr:</b>
<blockquote><code>{stderr_text}</code></blockquote>

<blockquote>{CUSTOM_EMOJI['🧮']} <b>выполняется:</b> <mono>{elapsed:.2f} сек.</mono></blockquote>"""

                    try:
                        await client.edit_message(
                            chat_id,
                            cmd_data['message_id'],
                            output,
                            parse_mode='html'
                        )
                    except Exception:
                        pass

                    await asyncio.sleep(3)
                except Exception as e:
                    print(f"Update error: {e}")
                    break

        async def send_final_output(self, chat_id):
            if chat_id not in self.running_commands:
                return

            cmd_data = self.running_commands[chat_id]

            stdout_text = self.format_output(cmd_data['stdout'].decode('utf-8', errors='ignore'))
            stderr_text = self.format_output(cmd_data['stderr'].decode('utf-8', errors='ignore'))

            elapsed = time.time() - cmd_data['start_time']

            output = f"""{CUSTOM_EMOJI['💻']} <i>системная команда:</i> <code>{html.escape(cmd_data['command'])}</code>
{CUSTOM_EMOJI['📰']} <b>код выхода:</b> <mono>{cmd_data['return_code']}</mono>

<b>stdout:</b>
<blockquote><code>{stdout_text}</code></blockquote>
<b>stderr:</b>
<blockquote><code>{stderr_text}</code></blockquote>

<blockquote>{CUSTOM_EMOJI['🧮']} <b>выполнено за</b> <mono>{elapsed:.2f} сек.</mono></blockquote>"""

            try:
                await client.edit_message(
                    chat_id,
                    cmd_data['message_id'],
                    output,
                    parse_mode='html'
                )
            except Exception:
                pass

        async def kill_command(self, chat_id):
            if chat_id not in self.running_commands:
                await client.send_message(chat_id, f"{CUSTOM_EMOJI['🗯']} <i>Нет выполняющихся команд</i>", parse_mode='html')
                return

            cmd_data = self.running_commands[chat_id]

            if cmd_data['completed']:
                await client.send_message(chat_id, f"{CUSTOM_EMOJI['💬']} <i>Команда уже завершена</i>", parse_mode='html')
                return

            try:
                process = cmd_data['process']
                if process and process.returncode is None:
                    # Отправляем SIGTERM
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    await asyncio.sleep(1)
                    
                    # Если процесс еще жив, отправляем SIGKILL
                    if process.returncode is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        await process.wait()

                cmd_data['completed'] = True
                cmd_data['return_code'] = -9

                await self.send_final_output(chat_id)

                if chat_id in self.update_tasks:
                    tasks = self.update_tasks[chat_id]
                    tasks['update'].cancel()
                    del self.update_tasks[chat_id]

                del self.running_commands[chat_id]

                await client.send_message(chat_id, f"{CUSTOM_EMOJI['☑️']} <i>Команда остановлена</i>", parse_mode='html')

            except Exception as e:
                await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['🗯']} <i>Ошибка остановки:</i> <code>{html.escape(str(e))}</code>",
                    parse_mode='html'
                )

    terminal = TerminalModule()

    @kernel.register_command('t')
    # terminal
    async def terminal_handler(event):
        args = event.text.split(maxsplit=1)
        await event.delete()
        command = args[1]
        await terminal.run_command(event.chat_id, command)

    @kernel.register_command('tkill')
    # kill terminal
    async def terminal_kill_handler(event):
        await event.delete()
        await terminal.kill_command(event.chat_id)

    # Алиасы
    @kernel.register_command('pacman')
    # pacman package manager
    async def pacman_handler(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(f"{CUSTOM_EMOJI['📦']} <i>Использование:</i> <code>.pacman опции</code>\n\n"
                           f"{CUSTOM_EMOJI['✏️']} <i>Примеры:</i>\n"
                           "<code>.pacman -Syu</code> - обновить систему\n"
                           "<code>.pacman -S пакет</code> - установить пакет\n"
                           "<code>.pacman -R пакет</code> - удалить пакет",
                           parse_mode='html')
            return
        
        await event.delete()
        # Добавляем --noconfirm для автоматического подтверждения
        options = args[1]
        if not any(opt in options for opt in ['-S', '-R', '-U']):
            command = f"sudo pacman {options}"
        else:
            command = f"sudo pacman {options} --noconfirm"
        await terminal.run_command(event.chat_id, command)

    @kernel.register_command('pip')
    # pip package installer
    async def pip_handler(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(f"{CUSTOM_EMOJI['🐍']} <i>Использование:</i> <code>.pip опции</code>\n\n"
                           f"{CUSTOM_EMOJI['✏️']} <i>Примеры:</i>\n"
                           "<code>.pip install пакет</code> - установить пакет\n"
                           "<code>.pip uninstall пакет</code> - удалить пакет\n"
                           "<code>.pip list</code> - список пакетов",
                           parse_mode='html')
            return
        
        await event.delete()
        options = args[1]
        # Если команда начинается с install, добавляем опции
        if options.startswith('install'):
            command = f"sudo pip {options}"
        else:
            command = f"pip {options}"
        await terminal.run_command(event.chat_id, command)

    @kernel.register_command('apt')
    # apt package manager
    async def apt_handler(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(f"{CUSTOM_EMOJI['🐧']} <i>Использование:</i> <code>.apt опции</code>\n\n"
                           f"{CUSTOM_EMOJI['✏️']} <i>Примеры:</i>\n"
                           "<code>.apt update</code> - обновить список пакетов\n"
                           "<code>.apt install пакет</code> - установить пакет\n"
                           "<code>.apt remove пакет</code> - удалить пакет",
                           parse_mode='html')
            return
        
        await event.delete()
        options = args[1]
        # Если команда начинается с install, добавляем -y для автоматического подтверждения
        if options.startswith('install') or options.startswith('remove'):
            command = f"sudo apt {options} -y"
        else:
            command = f"sudo apt {options}"
        await terminal.run_command(event.chat_id, command)

    @kernel.register_command('dnf')
    # dnf package manager
    async def dnf_handler(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(f"{CUSTOM_EMOJI['🎩']} <i>Использование:</i> <code>.dnf опции</code>\n\n"
                           f"{CUSTOM_EMOJI['✏️']} <i>Примеры:</i>\n"
                           "<code>.dnf install пакет</code> - установить пакет\n"
                           "<code>.dnf remove пакет</code> - удалить пакет\n"
                           "<code>.dnf update</code> - обновить пакеты",
                           parse_mode='html')
            return
        
        await event.delete()
        options = args[1]
        # Если команда начинается с install, добавляем -y
        if options.startswith('install') or options.startswith('remove'):
            command = f"sudo dnf {options} -y"
        else:
            command = f"sudo dnf {options}"
        await terminal.run_command(event.chat_id, command)
