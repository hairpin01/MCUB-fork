from __future__ import annotations

# requires:
# author: @Hairpin00
# version: 2.0.0
# description: Terminal commands with real-time output streaming / Терминал с потоковым выводом

import asyncio
import html
import os
import signal
import time

from core.lib.loader.module_config import ConfigValue, Integer, ModuleConfig
from utils.strings import Strings

CUSTOM_EMOJI = {
    "💻": '<tg-emoji emoji-id="5472111548572900003">💻</tg-emoji>',
    "📔": '<tg-emoji emoji-id="5334882760735598374">📔</tg-emoji>',
    "🧮": '<tg-emoji emoji-id="5472404950673791399">🧮</tg-emoji>',
    "🔎": '<tg-emoji emoji-id="5377844313575150051">🔎</tg-emoji>',
    "📕": '<tg-emoji emoji-id="5433653135799228968">📕</tg-emoji>',
    "📰": '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
    "📚": '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    "⌨️": '<tg-emoji emoji-id="5472111548572900003">⌨️</tg-emoji>',
    "💼": '<tg-emoji emoji-id="5359785904535774578">💼</tg-emoji>',
    "🖨": '<tg-emoji emoji-id="5386494631112353009">🖨</tg-emoji>',
    "☑️": '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    "➕": '<tg-emoji emoji-id="5226945370684140473">➕</tg-emoji>',
    "➖": '<tg-emoji emoji-id="5229113891081956317">➖</tg-emoji>',
    "💬": '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    "💭": '<tg-emoji emoji-id="5465143921912846619">💭</tg-emoji>',
    "🗯": '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    "✏️": '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    "🉐": '<tg-emoji emoji-id="5470088387048266598">🉐</tg-emoji>',
    "🢂": '<tg-emoji emoji-id="5350813992732338949">🢂</tg-emoji>',
    "🧊": '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
    "❄️": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "🔔": '<tg-emoji emoji-id="5413720894091851002">🔔</tg-emoji>',
    "⚠️": '<tg-emoji emoji-id="5453943626921666997">⚠️</tg-emoji>',
    "✅": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
}

# Minimum interval between edits (Telegram flood protection)
_MIN_EDIT_INTERVAL = 1.0


def register(kernel):
    client = kernel.client
    logger = kernel.logger

    lang = Strings(
        kernel,
        {
            "ru": {
                "empty": "пусто",
                "command_already_running": "Уже выполняется команда",
                "system_command": "системная команда:",
                "executing": "выполняется...",
                "launch_error": "Ошибка запуска:",
                "already_completed": "Команда уже завершена",
                "running_time": "выполняется:",
                "seconds": "сек.",
                "exit_code": "код выхода:",
                "completed_in": "выполнено за",
                "command_stopped": "Команда остановлена",
                "stop_error": "Ошибка остановки:",
                "no_running_commands": "Нет выполняющихся команд",
                "stdout": "stdout:",
                "stderr": "stderr:",
                "command_not_specified": "Команда не указана",
                "config_update_interval": "Интервал обновления вывода терминала (сек., 1-30). Обновление также происходит при появлении новых данных.",
            },
            "en": {
                "empty": "empty",
                "command_already_running": "Command already running",
                "system_command": "system command:",
                "executing": "executing...",
                "launch_error": "Launch error:",
                "already_completed": "Command already completed",
                "running_time": "running:",
                "seconds": "sec.",
                "exit_code": "exit code:",
                "completed_in": "completed in",
                "command_stopped": "Command stopped",
                "stop_error": "Stop error:",
                "no_running_commands": "No running commands",
                "stdout": "stdout:",
                "stderr": "stderr:",
                "command_not_specified": "Command not specified",
                "config_update_interval": "Terminal output update interval (sec, 1-30). Update also happens when new data arrives.",
            },
        },
    )

    # ModuleConfig
    config = ModuleConfig(
        ConfigValue(
            "update_interval",
            3,
            description=lambda: lang["config_update_interval"],
            validator=Integer(default=3, min=1, max=30),
        ),
    )

    async def _startup():
        cfg_dict = await kernel.get_module_config(__name__, {"update_interval": 3})
        config.from_dict(cfg_dict)
        clean = {k: v for k, v in config.to_dict().items() if v is not None}
        if clean:
            await kernel.save_module_config(__name__, clean)
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(_startup())

    def _get_config() -> ModuleConfig:
        """Always get the live config if available."""
        live = getattr(kernel, "_live_module_configs", {}).get(__name__)
        return live if live else config

    class TerminalModule:
        def __init__(self):
            self.running_commands: dict = {}
            self.update_tasks: dict = {}

        def _format_output(self, text: str, max_length: int = 2000) -> str:
            """Escape and truncate output. Show tail - it's more recent."""
            if not text:
                return lang["empty"]
            text = str(text)
            if len(text) > max_length:
                text = "...\n" + text[-max_length:]
            return html.escape(text)

        def _build_message(self, cmd_data: dict, *, final: bool = False) -> str:
            stdout_raw = cmd_data["stdout"].decode("utf-8", errors="ignore")
            stderr_raw = cmd_data["stderr"].decode("utf-8", errors="ignore")

            stdout_block = f"<pre>{self._format_output(stdout_raw)}</pre>"
            stderr_block = (
                f"<pre>{self._format_output(stderr_raw)}</pre>"
                if stderr_raw.strip()
                else ""
            )

            elapsed = time.time() - cmd_data["start_time"]
            cmd_escaped = html.escape(cmd_data["command"])

            if final:
                time_label = lang["completed_in"]
                extra = f"{CUSTOM_EMOJI['📰']} <b>{lang['exit_code']}</b> <mono>{cmd_data['return_code']}</mono>\n"
            else:
                time_label = lang["running_time"]
                extra = ""

            return (
                f"{CUSTOM_EMOJI['💻']} <i>{lang['system_command']}</i> <blockquote><code>{cmd_escaped}</code></blockquote>\n"
                f"{extra}"
                f"{stdout_block}{stderr_block}"
                f"<blockquote>{CUSTOM_EMOJI['🧮']} <b>{time_label}</b> "
                f"<mono>{elapsed:.2f} {lang['seconds']}</mono></blockquote>"
            )

        async def run_command(self, chat_id, command, message_id=None):
            if chat_id in self.running_commands:
                await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_already_running']}</i>",
                    parse_mode="html",
                )
                return

            try:
                data_event = asyncio.Event()
                cmd_data = {
                    "command": command,
                    "stdout": b"",
                    "stderr": b"",
                    "completed": False,
                    "return_code": None,
                    "process": None,
                    "start_time": time.time(),
                    "data_event": data_event,  # signal about new data
                }

                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    preexec_fn=os.setsid if os.name != "nt" else None,
                )  # noqa: S602, S607, B606

                cmd_data["process"] = process
                self.running_commands[chat_id] = cmd_data

                if message_id:
                    cmd_data["message_id"] = message_id
                else:
                    msg = await client.send_message(
                        chat_id,
                        f"{CUSTOM_EMOJI['💻']} <i>{lang['system_command']}</i> "
                        f"<blockquote><code>{html.escape(command)}</code></blockquote>\n"
                        f"{CUSTOM_EMOJI['❄️']} <i>{lang['executing']}</i>",
                        parse_mode="html",
                    )
                    cmd_data["message_id"] = msg.id

                update_task = asyncio.create_task(self._update_loop(chat_id))
                read_task = asyncio.create_task(self._read_output(chat_id))
                self.update_tasks[chat_id] = {"update": update_task, "read": read_task}

            except Exception as e:
                error_msg = (
                    f"{CUSTOM_EMOJI['🗯']} <i>{lang['launch_error']}</i> "
                    f"<code>{html.escape(str(e))}</code>"
                )
                if message_id:
                    await client.edit_message(
                        chat_id, message_id, error_msg, parse_mode="html"
                    )
                else:
                    await client.send_message(chat_id, error_msg, parse_mode="html")
                self.running_commands.pop(chat_id, None)
                await kernel.handle_error(e, source="terminal:run_command")

        async def _read_output(self, chat_id):
            """Reads stdout/stderr in chunks and signals update_loop about new data."""
            if chat_id not in self.running_commands:
                return

            cmd_data = self.running_commands[chat_id]
            process = cmd_data["process"]

            async def _read_stream(stream, is_stderr: bool):
                try:
                    while True:
                        chunk = await stream.read(4096)
                        if not chunk:
                            break
                        if is_stderr:
                            cmd_data["stderr"] += chunk
                        else:
                            cmd_data["stdout"] += chunk
                        # Notify update_loop: new data arrived
                        cmd_data["data_event"].set()
                except Exception as e:
                    logger.error(f"terminal: stream read error: {e}")

            try:
                await asyncio.gather(
                    _read_stream(process.stdout, False),
                    _read_stream(process.stderr, True),
                )
                await process.wait()

                cmd_data["completed"] = True
                cmd_data["return_code"] = process.returncode
                cmd_data["data_event"].set()  # final signal

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"terminal: read_output error: {e}")
                await kernel.handle_error(e, source="terminal:read_output")
            finally:
                # Stop update_loop
                tasks = self.update_tasks.pop(chat_id, None)
                if tasks:
                    t = tasks["update"]
                    if not t.done():
                        t.cancel()
                        try:
                            await t
                        except asyncio.CancelledError:
                            pass

                # Send final output and clean state
                if chat_id in self.running_commands:
                    await self._send_final(chat_id)
                    del self.running_commands[chat_id]

        async def _update_loop(self, chat_id):
            """
            Update message in real-time:
            - on each new chunk (data_event) or
            - on timeout (update_interval from config).
            Edits are throttled to 1/sec to avoid Telegram API flood.
            """
            last_edit = 0.0

            while chat_id in self.running_commands:
                cmd_data = self.running_commands[chat_id]

                if cmd_data["completed"]:
                    break

                # Wait for new data or timeout
                interval = _get_config().get("update_interval") or 3
                try:
                    await asyncio.wait_for(
                        asyncio.shield(cmd_data["data_event"].wait()),
                        timeout=float(interval),
                    )
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    break

                cmd_data["data_event"].clear()

                if cmd_data["completed"]:
                    break

                # Throttling: not more than 1 time in _MIN_EDIT_INTERVAL sec
                now = time.time()
                if now - last_edit < _MIN_EDIT_INTERVAL:
                    continue

                try:
                    await client.edit_message(
                        chat_id,
                        cmd_data["message_id"],
                        self._build_message(cmd_data),
                        parse_mode="html",
                    )
                    last_edit = time.time()
                except asyncio.CancelledError:
                    break
                except Exception:
                    # Ignore "message not modified" and other temporary errors
                    pass

        async def _send_final(self, chat_id):
            if chat_id not in self.running_commands:
                return
            cmd_data = self.running_commands[chat_id]
            try:
                await client.edit_message(
                    chat_id,
                    cmd_data["message_id"],
                    self._build_message(cmd_data, final=True),
                    parse_mode="html",
                )
            except Exception as e:
                logger.error(f"terminal: final edit error: {e}")

        async def kill_command(self, chat_id, message_id=None):
            if chat_id not in self.running_commands:
                msg_text = f"{CUSTOM_EMOJI['🗯']} <i>{lang['no_running_commands']}</i>"
                if message_id:
                    await client.edit_message(
                        chat_id, message_id, msg_text, parse_mode="html"
                    )
                else:
                    await client.send_message(chat_id, msg_text, parse_mode="html")
                return

            cmd_data = self.running_commands[chat_id]

            if cmd_data["completed"]:
                msg_text = f"{CUSTOM_EMOJI['💬']} <i>{lang['already_completed']}</i>"
                if message_id:
                    await client.edit_message(
                        chat_id, message_id, msg_text, parse_mode="html"
                    )
                else:
                    await client.send_message(chat_id, msg_text, parse_mode="html")
                return

            try:
                process = cmd_data["process"]
                if process and process.returncode is None:
                    if os.name == "nt":
                        process.terminate()
                        await asyncio.sleep(1)
                        if process.returncode is None:
                            process.kill()
                    else:
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                            await asyncio.sleep(1)
                            if process.returncode is None:
                                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except (ProcessLookupError, OSError):
                            pass

                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass

                # Process killed - read_output will catch EOF, send final
                # output to cmd_data["message_id"] and clean state.
                # Here we only edit .tkill message (separate message_id).
                if message_id:
                    await client.edit_message(
                        chat_id,
                        message_id,
                        f"{CUSTOM_EMOJI['☑️']} <i>{lang['command_stopped']}</i>",
                        parse_mode="html",
                    )

            except Exception as e:
                error_msg = (
                    f"{CUSTOM_EMOJI['🗯']} <i>{lang['stop_error']}</i> "
                    f"<pre>{html.escape(str(e))}</pre>"
                )
                if message_id:
                    await client.edit_message(
                        chat_id, message_id, error_msg, parse_mode="html"
                    )
                else:
                    await client.send_message(chat_id, error_msg, parse_mode="html")
                await kernel.handle_error(e, source="terminal:kill_command")

    terminal = TerminalModule()

    @kernel.register.command(
        "t",
        doc_en="execute shell command with real-time output",
        doc_ru="выполнить shell команду с выводом в реальном времени",
    )
    async def terminal_handler(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_not_specified']}</i>",
                parse_mode="html",
            )
            return
        await terminal.run_command(event.chat_id, args[1], event.id)

    @kernel.register.command(
        "tkill",
        doc_en="stop running terminal command",
        doc_ru="остановить выполняемую команду терминала",
    )
    async def terminal_kill_handler(event):
        await terminal.kill_command(event.chat_id, event.id)
