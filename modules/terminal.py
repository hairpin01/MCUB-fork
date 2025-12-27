# requires: telethon>=1.24
# author: @Hairpin00
# version: 1.0.4
# description: выполнить команду в terminal с премиум эмодзи

import asyncio
import subprocess
import time
import html
from pathlib import Path

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
}

def register(kernel):
    client = kernel.client

    class TerminalModule:
        def __init__(self):
            self.running_commands = {}
            self.update_tasks = {}
            self.kernel = kernel
            self.client = kernel.client

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

        async def run_command(self, chat_id, command):
            if chat_id in self.running_commands:
                await client.send_message(chat_id, f"{CUSTOM_EMOJI['🗯']} <i>Уже выполняется команда</i>", parse_mode='html')
                return

            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE
                )

                start_time = time.time()
                self.running_commands[chat_id] = {
                    'process': process,
                    'command': command,
                    'start_time': start_time,
                    'stdout': b'',
                    'stderr': b'',
                    'completed': False,
                    'return_code': None
                }

                msg = await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['💻']} <i>системная команда:</i> <code>{html.escape(command)}</code>\n"
                    f"{CUSTOM_EMOJI['❄️']} <i>выполняется...</i>",
                    parse_mode='html'
                )

                self.running_commands[chat_id]['message_id'] = msg.id

                task = asyncio.create_task(self.update_output(chat_id))
                self.update_tasks[chat_id] = task

                task = asyncio.create_task(self.read_output(chat_id))

            except Exception as e:
                await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['🗯']} <i>Ошибка запуска:</i> <code>{html.escape(str(e))}</code>",
                    parse_mode='html'
                )

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
                except Exception:
                    pass

                if is_stderr:
                    cmd_data['stderr'] = data
                else:
                    cmd_data['stdout'] = data

            await asyncio.gather(
                read_stream(process.stdout, False),
                read_stream(process.stderr, True)
            )

            await process.wait()

            cmd_data['completed'] = True
            cmd_data['return_code'] = process.returncode

            await self.send_final_output(chat_id)

            if chat_id in self.update_tasks:
                self.update_tasks[chat_id].cancel()
                del self.update_tasks[chat_id]

            if chat_id in self.running_commands:
                del self.running_commands[chat_id]

        async def update_output(self, chat_id):
            while chat_id in self.running_commands:
                try:
                    cmd_data = self.running_commands[chat_id]

                    if cmd_data['completed']:
                        break

                    stdout_text = self.format_output(cmd_data['stdout'].decode('utf-8', errors='ignore'))
                    stderr_text = self.format_output(cmd_data['stderr'].decode('utf-8', errors='ignore'))

                    elapsed = time.time() - cmd_data['start_time']

                    output = f"""{CUSTOM_EMOJI['💻']} <i>системная команда:</i> <code>{html.escape(cmd_data['command'])}</code>

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
                except Exception:
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
                cmd_data['process'].terminate()
                await asyncio.sleep(1)
                if cmd_data['process'].returncode is None:
                    cmd_data['process'].kill()

                await cmd_data['process'].wait()

                cmd_data['completed'] = True
                cmd_data['return_code'] = -9

                await self.send_final_output(chat_id)

                if chat_id in self.update_tasks:
                    self.update_tasks[chat_id].cancel()
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
        if len(args) < 2:
            await event.edit(
                f"{CUSTOM_EMOJI['💻']} <i>Использование:</i> <code>.t команда</code>\n\n"
                f"{CUSTOM_EMOJI['✏️']} <i>Примеры:</i>\n"
                "<code>.t pwd</code> - текущая директория\n"
                "<code>.t ls -la</code> - список файлов\n"
                "<code>.t echo 'test'</code> - вывод текста\n"
                "<code>.t python3 -c \"print('hello')\"</code> - Python код",
                parse_mode='html'
            )
            return

        await event.delete()
        command = args[1]
        await terminal.run_command(event.chat_id, command)

    @kernel.register_command('tkill')
    # kill terminal
    async def terminal_kill_handler(event):
        await event.delete()
        await terminal.kill_command(event.chat_id)

