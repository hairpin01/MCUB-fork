# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

# requires:
# author: @Hairpin00
# version: 2.0.0
# description: Terminal commands with real-time output streaming
import asyncio
import html
import os
import re
import shlex
import signal
import time

from core.lib.loader.module_config import (
    Boolean,
    Choice,
    ConfigValue,
    Float,
    Integer,
    ModuleConfig,
    String,
)
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

# output filter helpers

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mABCDEFGHJKSTfhilmnprsu]")


def _filter_proxychains_output(text: str) -> str:
    """Remove lines containing [proxychains] markers from output."""
    if not text:
        return text
    return "\n".join(line for line in text.split("\n") if "[proxychains]" not in line)


def _filter_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    if not text:
        return text
    return ANSI_RE.sub("", text)


def _filter_by_pattern(text: str, pattern: str) -> str:
    """Remove lines matching a custom regex pattern."""
    if not text or not pattern:
        return text
    try:
        return "\n".join(
            line for line in text.split("\n") if not re.search(pattern, line)
        )
    except re.error:
        return text


def _strip_trailing_whitespace(text: str) -> str:
    """Strip trailing spaces and tabs from each line."""
    if not text:
        return text
    return "\n".join(line.rstrip(" \t") for line in text.split("\n"))


def _truncate_lines(text: str, max_lines: int) -> str:
    """Return last max_lines lines. If max_lines <= 0, return text unchanged."""
    if max_lines <= 0 or not text:
        return text
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:])


def _apply_output_filters(text: str, cfg) -> str:
    """Apply all configured output filters in order."""
    if cfg.get("filter_ansi", True):
        text = _filter_ansi(text)
    if cfg.get("filter_proxychains", True):
        text = _filter_proxychains_output(text)
    if cfg.get("strip_trailing_whitespace"):
        text = _strip_trailing_whitespace(text)
    pattern = cfg.get("filter_pattern", "")
    if pattern:
        text = _filter_by_pattern(text, pattern)
    return text


# shell helpers


def _get_shell_path(cfg) -> str:
    """Return effective shell path: custom_shell when shell=custom, else shell name."""
    shell = cfg.get("shell") or "bash"
    if shell == "custom":
        return cfg.get("custom_shell") or shell
    return shell


def _get_shell_args(cfg) -> list[str]:
    """Return shell arguments as a list (supports multi-part via shlex.split)."""
    args_str = cfg.get("args") or "-c"
    return shlex.split(args_str)


def register(kernel):
    client = kernel.client
    logger = kernel.logger

    lang = Strings(kernel, {"name": "terminal"})

    # ModuleConfig
    config = ModuleConfig(
        ConfigValue(
            "update_interval",
            3,
            description=lambda: lang["config_update_interval"],
            validator=Integer(default=3, min=1, max=30),
        ),
        ConfigValue(
            "shell",
            "bash",
            description=lambda: "Shell to use for command execution",
            validator=Choice(
                choices=["zsh", "sh", "fish", "dash", "bash", "custom"], default="bash"
            ),
        ),
        ConfigValue(
            "filter_proxychains",
            True,
            description=lambda: "Filter [proxychains] noise from stdout/stderr output",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "custom_shell",
            "",
            description=lambda: "Custom shell path (used when shell=custom)",
            validator=String(default=""),
        ),
        ConfigValue(
            "args",
            "-c",
            description=lambda: "Shell arguments (default: -c)",
            validator=String(default="-c"),
        ),
        # Filters
        ConfigValue(
            "filter_ansi",
            True,
            description=lambda: "Strip ANSI escape codes from output",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "filter_pattern",
            "",
            description=lambda: "Custom regex: remove lines matching this pattern",
            validator=String(default=""),
        ),
        ConfigValue(
            "strip_trailing_whitespace",
            False,
            description=lambda: "Strip trailing whitespace from each output line",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "max_lines",
            0,
            description=lambda: "Truncate output to last N lines (0 = disabled, uses byte limit)",
            validator=Integer(default=0, min=0),
        ),
        ConfigValue(
            "tail_lines",
            0,
            description=lambda: "Show only last N lines in output (0 = disabled)",
            validator=Integer(default=0, min=0),
        ),
        # Process
        ConfigValue(
            "timeout",
            0,
            description=lambda: "Auto-kill process after N seconds (0 = disabled)",
            validator=Integer(default=0, min=0),
        ),
        ConfigValue(
            "cwd",
            "",
            description=lambda: "Working directory for command (empty = bot's cwd)",
            validator=String(default=""),
        ),
        ConfigValue(
            "env_extra",
            "",
            description=lambda: "Extra env vars: KEY=VAL KEY2=VAL2 (space-separated)",
            validator=String(default=""),
        ),
        ConfigValue(
            "stdin_eof",
            False,
            description=lambda: "Close stdin immediately after process start",
            validator=Boolean(default=False),
        ),
        # Display
        ConfigValue(
            "show_stderr_inline",
            False,
            description=lambda: "Merge stderr into stdout in order of arrival",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "show_pid",
            False,
            description=lambda: "Show process PID in command footer",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "compact_mode",
            False,
            description=lambda: "Hide shell/elapsed footer during execution, show on completion",
            validator=Boolean(default=False),
        ),
        # Throttling
        ConfigValue(
            "min_edit_interval",
            1.0,
            description=lambda: "Minimum interval between message edits (seconds)",
            validator=Float(default=1.0),
        ),
        ConfigValue(
            "edit_on_newline_only",
            False,
            description=lambda: "Only edit message when newline arrives in output",
            validator=Boolean(default=False),
        ),
    )

    async def _startup():
        # Register schema FIRST so save_module_config doesn't crash on new keys
        kernel.store_module_config_schema(__name__, config)
        cfg_dict = await kernel.get_module_config(
            __name__,
            {
                "update_interval": 3,
                "shell": "bash",
                "filter_proxychains": True,
                "custom_shell": "",
                "args": "-c",
            },
        )
        config.from_dict(cfg_dict)
        clean = {k: v for k, v in config.to_dict().items() if v is not None}
        if clean:
            await kernel.save_module_config(__name__, clean)

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
            cfg = _get_config()
            line_limit = cfg.get("max_lines") or cfg.get("tail_lines") or 0
            if line_limit > 0:
                lines = text.split("\n")
                if len(lines) > line_limit:
                    text = "...\n" + "\n".join(lines[-line_limit:])
            elif len(text) > max_length:
                text = "...\n" + text[-max_length:]
            return html.escape(text)

        def _build_message(self, cmd_data: dict, *, final: bool = False) -> str:
            stdout_raw = cmd_data["stdout"].decode("utf-8", errors="ignore")
            stderr_raw = cmd_data["stderr"].decode("utf-8", errors="ignore")
            cfg = _get_config()

            stdout_raw = _apply_output_filters(stdout_raw, cfg)
            stderr_raw = _apply_output_filters(stderr_raw, cfg)

            if cfg.get("show_stderr_inline") and stderr_raw.strip():
                stdout_raw = stdout_raw + "\n" + stderr_raw
                stderr_raw = ""

            stdout_block = f"<pre>{self._format_output(stdout_raw)}</pre>"
            stderr_block = (
                f"<pre>{self._format_output(stderr_raw)}</pre>"
                if stderr_raw.strip()
                else ""
            )
            elapsed = time.time() - cmd_data["start_time"]
            cmd_escaped = html.escape(cmd_data["command"])
            shell = html.escape(_get_shell_path(cfg))

            if final:
                time_label = lang["completed_in"]
                extra = f"{CUSTOM_EMOJI['📰']} <b>{lang['exit_code']}</b> <mono>{cmd_data['return_code']}</mono>\n"
                # Build footer parts
                footer_parts = [
                    f"{CUSTOM_EMOJI['🉐']} <b>{lang['shell']}</b> {shell}",
                ]
                if cfg.get("show_pid") and cmd_data.get("pid"):
                    footer_parts.append(f"<b>PID</b> <mono>{cmd_data['pid']}</mono>")
                footer_parts.append(
                    f"{CUSTOM_EMOJI['🧮']} <b>{time_label}</b> <mono>{elapsed:.2f} {lang['seconds']}</mono>"
                )
                footer = f"<blockquote>{' | '.join(footer_parts)}</blockquote>"
            else:
                time_label = lang["running_time"]
                extra = ""
                if cfg.get("compact_mode"):
                    footer = ""
                else:
                    footer_parts = [
                        f"{CUSTOM_EMOJI['🉐']} <b>{lang['shell']}</b> {shell}",
                    ]
                    if cfg.get("show_pid") and cmd_data.get("pid"):
                        footer_parts.append(
                            f"<b>PID</b> <mono>{cmd_data['pid']}</mono>"
                        )
                    footer_parts.append(
                        f"{CUSTOM_EMOJI['🧮']} <b>{time_label}</b> <mono>{elapsed:.2f} {lang['seconds']}</mono>"
                    )
                    footer = f"<blockquote>{' | '.join(footer_parts)}</blockquote>"

            return (
                f"{CUSTOM_EMOJI['💻']} <i>{lang['system_command']}</i> <blockquote><code>{cmd_escaped}</code></blockquote>\n"
                f"{extra}"
                f"{stdout_block}{stderr_block}"
                f"{footer}"
            )

        async def run_command(self, chat_id, command, message_id=None):
            if chat_id in self.running_commands:
                await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_already_running']}</i>",
                    parse_mode="html",
                )
                return

            piped = False

            try:
                data_event = asyncio.Event()
                cmd_data = {
                    "command": command,
                    "stdout": b"",
                    "stderr": b"",
                    "completed": False,
                    "return_code": None,
                    "process": None,
                    "pid": None,
                    "start_time": time.time(),
                    "data_event": data_event,
                    "piped": piped,
                    "timeout_task": None,
                }

                cfg_shell = _get_config()
                shell_path = _get_shell_path(cfg_shell)
                shell_args = _get_shell_args(cfg_shell)

                # cwd
                cwd_val = cfg_shell.get("cwd") or None
                # env_extra
                env_val = None
                env_extra = cfg_shell.get("env_extra", "")
                if env_extra.strip():
                    env_val = os.environ.copy()
                    for pair in shlex.split(env_extra):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            env_val[k] = v

                process = await asyncio.create_subprocess_exec(
                    shell_path,
                    *shell_args,
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd_val,
                    env=env_val,
                    preexec_fn=os.setsid if os.name != "nt" else None,
                )

                cmd_data["process"] = process
                cmd_data["pid"] = process.pid
                self.running_commands[chat_id] = cmd_data

                # stdin_eof: close stdin immediately
                if cfg_shell.get("stdin_eof") and process.stdin:
                    process.stdin.close()

                # timeout: auto-kill after N seconds
                timeout = cfg_shell.get("timeout") or 0
                if timeout > 0:

                    async def _kill_timeout(proc=process):
                        await asyncio.sleep(timeout)
                        if proc.returncode is None:
                            try:
                                proc.kill()
                            except ProcessLookupError:
                                pass

                    timeout_task = asyncio.create_task(_kill_timeout())
                    cmd_data["timeout_task"] = timeout_task

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

        async def run_command_piped(
            self, chat_id, command, message_id=None, quiet=False
        ):
            try:
                cfg_shell = _get_config()
                shell_path = _get_shell_path(cfg_shell)
                shell_args = _get_shell_args(cfg_shell)

                # cwd
                cwd_val = cfg_shell.get("cwd") or None
                # env_extra
                env_val = None
                env_extra = cfg_shell.get("env_extra", "")
                if env_extra.strip():
                    env_val = os.environ.copy()
                    for pair in shlex.split(env_extra):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            env_val[k] = v

                process = await asyncio.create_subprocess_exec(
                    shell_path,
                    *shell_args,
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd_val,
                    env=env_val,
                )

                # stdin_eof: close stdin immediately
                if cfg_shell.get("stdin_eof") and process.stdin:
                    process.stdin.close()

                # timeout: auto-kill
                timeout = cfg_shell.get("timeout") or 0
                if timeout > 0:
                    try:
                        await asyncio.wait_for(process.wait(), timeout=timeout)
                    except TimeoutError:
                        process.kill()
                        stdout, stderr = await process.communicate()
                    else:
                        stdout, stderr = await process.communicate()
                else:
                    stdout, stderr = await process.communicate()

                output = stdout.decode("utf-8", errors="ignore")
                if not quiet:
                    output += stderr.decode("utf-8", errors="ignore")

                output = _apply_output_filters(output, _get_config())
                return output
            except Exception as e:
                return f"Error: {e!s}"

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
                # Cancel timeout task if still running
                timeout_task = cmd_data.get("timeout_task")
                if timeout_task and not timeout_task.done():
                    timeout_task.cancel()
                    try:
                        await timeout_task
                    except asyncio.CancelledError:
                        pass

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
            Edits are throttled to avoid Telegram API flood.
            Only edits when the formatted message actually changed.
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
                except TimeoutError:
                    pass
                except asyncio.CancelledError:
                    break

                cmd_data["data_event"].clear()

                if cmd_data["completed"]:
                    break

                cfg = _get_config()

                # edit_on_newline_only: skip if no newline in new data
                if cfg.get("edit_on_newline_only") and not cmd_data["completed"]:
                    prev_len = cmd_data.get("_prev_stdout_len", 0)
                    new_bytes = cmd_data["stdout"][prev_len:]
                    if b"\n" not in new_bytes:
                        continue
                cmd_data["_prev_stdout_len"] = len(cmd_data["stdout"])

                # Throttling: respect min_edit_interval from config
                now = time.time()
                min_edit = cfg.get("min_edit_interval") or 1.0
                if now - last_edit < min_edit:
                    continue

                # Build message and compare - skip if identical to avoid "not modified"
                new_text = self._build_message(cmd_data)
                if new_text == cmd_data.get("_last_sent_text"):
                    continue
                cmd_data["_last_sent_text"] = new_text

                try:
                    await client.edit_message(
                        chat_id,
                        cmd_data["message_id"],
                        new_text,
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

            piped = cmd_data.get("piped", False)

            try:
                if piped:
                    stdout = cmd_data["stdout"].decode("utf-8", errors="ignore")
                    stdout = _apply_output_filters(stdout, _get_config())
                    output = stdout
                    await client.edit_message(
                        chat_id,
                        cmd_data["message_id"],
                        output,
                    )
                else:
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
                    except TimeoutError:
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
        doc_en="[command] execute shell command",
        doc_ru="[кoмaндa] выпoлнить shell кoмaндy",
    )
    async def terminal_handler(event):
        args = event.text.split(maxsplit=1)
        pipe_input = getattr(event, "pipe_input", None)
        piped = getattr(event, "piped", False)

        if len(args) < 2:
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_not_specified']}</i>",
                parse_mode="html",
            )
            return

        cmd = args[1]
        quiet = False
        if cmd.startswith("-q "):
            quiet = True
            cmd = cmd[3:]

        if pipe_input:
            cmd = f"{pipe_input}\n{cmd}"

        if piped:
            output = await terminal.run_command_piped(
                event.chat_id, cmd, event.id, quiet
            )
            await event.edit(output if output else "done")
        else:
            await terminal.run_command(event.chat_id, cmd, event.id)

    @kernel.register.command(
        "tkill",
        doc_en="stop running terminal command",
        doc_ru="ocтaнoвить выпoлняeмyю кoмaндy тepминaлa",
    )
    async def terminal_kill_handler(event):
        await terminal.kill_command(event.chat_id, event.id)
