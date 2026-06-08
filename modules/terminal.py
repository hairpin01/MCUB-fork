# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# name: terminal
from __future__ import annotations

# requires:
# author: @Hairpin00
# version: 3.0.0
# description: Terminal commands with real-time output streaming, parallel slots and stdin input
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
    "✅": '<tg-emoji emoji-id="5332762073388578651">✅</tg-emoji>',
    "loading": '<tg-emoji emoji-id="5310041868191407556">🔘</tg-emoji>',
    "done": '<tg-emoji emoji-id="5332533929020761310">☑️</tg-emoji>',
    "done_error_code": '<tg-emoji emoji-id="5330273431898318607">😖</tg-emoji>',
}

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
        # Invalid regex - return text unchanged; not a runtime error.
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


def _parse_slot(text: str) -> tuple[str, str]:
    """
    Parse optional '@N' slot prefix from command text.

    Examples:
        '@2 ls -la'  → ('2', 'ls -la')
        '@all'       → ('all', '')       ← for tkill @all
        'ls -la'     → ('1', 'ls -la')   ← default slot
        ''           → ('1', '')
    """
    text = text.strip()
    if text.startswith("@"):
        parts = text.split(maxsplit=1)
        slot = parts[0][1:]  # strip leading '@'
        rest = parts[1] if len(parts) > 1 else ""
        return slot, rest
    return "1", text


def register(kernel):
    client = kernel.client
    logger = kernel.logger

    lang = Strings(kernel, {"name": "terminal"})

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
            # Keys are (chat_id, slot) tuples to support parallel execution.
            # slot is a string, default "1".
            self.running_commands: dict = {}
            self.update_tasks: dict = {}

        def _format_output(self, text: str, max_length: int = 2000) -> str:
            """Escape and truncate output. Shows tail - it's more recent."""
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
            """Build the Telegram message for a running/completed command."""
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

            # Slot label - shown only when not the default slot.
            slot = cmd_data.get("slot", "1")
            slot_label = f"| <code>@{html.escape(slot)}</code>" if slot != "1" else ""

            if final:
                time_label = lang["completed_in"]
                extra = f"{CUSTOM_EMOJI['📰']} <b>{lang['exit_code']}</b> <mono>{cmd_data['return_code']}</mono>\n"
                footer_parts = [
                    f"{CUSTOM_EMOJI['🉐']} <b>{lang['shell']}</b> {shell}",
                ]
                if cfg.get("show_pid") and cmd_data.get("pid"):
                    footer_parts.append(f"<b>PID</b> <mono>{cmd_data['pid']}</mono>")
                footer_parts.append(
                    f"{CUSTOM_EMOJI['🧮']} <b>{time_label}</b> <mono>{elapsed:.2f} {lang['seconds']}</mono>"
                )
                footer = f"<blockquote>{' | '.join(footer_parts)}</blockquote>"

                final_emoji = (
                    CUSTOM_EMOJI["done"]
                    if cmd_data["return_code"] == 0
                    else CUSTOM_EMOJI["done_error_code"]
                )
            else:
                time_label = lang["running_time"]
                extra = ""
                final_emoji = CUSTOM_EMOJI["loading"]
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
                f"{final_emoji} {'<b>' if final else '<i>'}{lang['system_command']}{'</b>' if final else '</i>'} {slot_label}"
                f" <blockquote><code>{cmd_escaped}</code></blockquote>\n"
                f"{extra}"
                f"{stdout_block}{stderr_block}"
                f"{footer}"
            )

        async def _build_process(
            self,
            command: str,
            cfg,
            *,
            use_setsid: bool = True,
        ):
            """
            Build and launch a subprocess.

            stdin is always PIPE so that `ti` can send input later.
            `use_setsid=True`  → wrap in a new process group (interactive mode).
            `use_setsid=False` → flat process (piped/one-shot mode).
            """
            shell_path = _get_shell_path(cfg)
            shell_args = _get_shell_args(cfg)

            cwd_val = cfg.get("cwd") or None

            env_val = None
            env_extra = cfg.get("env_extra", "")
            if env_extra.strip():
                env_val = os.environ.copy()
                for pair in shlex.split(env_extra):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        env_val[k] = v

            kwargs: dict = {
                "stdin": asyncio.subprocess.PIPE,
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "cwd": cwd_val,
                "env": env_val,
            }
            if use_setsid and os.name != "nt":
                kwargs["preexec_fn"] = os.setsid

            return await asyncio.create_subprocess_exec(
                shell_path, *shell_args, command, **kwargs
            )

        async def run_command(
            self,
            chat_id,
            command,
            message_id=None,
            slot: str = "1",
        ):
            """Launch a shell command in the given slot with live streaming output."""
            key = (chat_id, slot)
            if key in self.running_commands:
                slot_label = f" (@{slot})" if slot != "1" else ""
                await client.send_message(
                    chat_id,
                    f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_already_running']}{slot_label}</i>",
                    parse_mode="html",
                )
                return

            piped = False

            try:
                data_event = asyncio.Event()
                cmd_data = {
                    "command": command,
                    "slot": slot,
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
                process = await self._build_process(command, cfg_shell, use_setsid=True)

                cmd_data["process"] = process
                cmd_data["pid"] = process.pid
                self.running_commands[key] = cmd_data

                # stdin_eof: close stdin immediately (opt-in; ti won't work then)
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
                                # Process already gone - acceptable.
                                pass

                    timeout_task = asyncio.create_task(_kill_timeout())
                    cmd_data["timeout_task"] = timeout_task

                if message_id:
                    cmd_data["message_id"] = message_id
                    await client.edit_message(
                        chat_id,
                        message_id,
                        self._build_message(cmd_data),
                        parse_mode="html",
                    )
                else:
                    slot_label = (
                        f" <code>@{html.escape(slot)}</code>" if slot != "1" else ""
                    )
                    msg = await client.send_message(
                        chat_id,
                        f"{CUSTOM_EMOJI['loading']} <i>{lang['system_command']}</i>{slot_label} "
                        f"<blockquote><code>{html.escape(command)}</code></blockquote>\n"
                        f"{CUSTOM_EMOJI['❄️']} <i>{lang['executing']}</i>",
                        parse_mode="html",
                    )
                    cmd_data["message_id"] = msg.id

                update_task = asyncio.create_task(self._update_loop(key))
                read_task = asyncio.create_task(self._read_output(key))
                self.update_tasks[key] = {"update": update_task, "read": read_task}

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
                self.running_commands.pop(key, None)
                await kernel.handle_error(e, message="Terminal command failed")

        async def run_command_piped(
            self,
            chat_id,
            command,
            message_id=None,
            quiet=False,
        ):
            """Run a command and return its output as a string (pipe mode)."""
            try:
                cfg_shell = _get_config()
                process = await self._build_process(
                    command, cfg_shell, use_setsid=False
                )

                # stdin_eof
                if cfg_shell.get("stdin_eof") and process.stdin:
                    process.stdin.close()

                # timeout
                timeout = cfg_shell.get("timeout") or 0
                if timeout > 0:
                    try:
                        await asyncio.wait_for(process.wait(), timeout=timeout)
                    except TimeoutError:
                        # Timeout expired - kill and collect what we have.
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
                logger.error(f"terminal: piped command error: {e}")
                await kernel.handle_error(e, message="Terminal piped command failed")
                return f"Error: {e!s}"

        async def send_stdin(
            self,
            chat_id,
            slot: str,
            text: str,
        ) -> tuple[bool, str | None]:
            """
            Write *text* (+ newline) to the stdin of a running slot.
            Returns (True, None) on success, (False, reason) on failure.
            """
            key = (chat_id, slot)
            if key not in self.running_commands:
                return False, "no_running"
            cmd_data = self.running_commands[key]
            if cmd_data["completed"]:
                return False, "completed"
            process = cmd_data["process"]
            if not process or not process.stdin or process.stdin.is_closing():
                return False, "no_stdin"
            try:
                process.stdin.write((text + "\n").encode())
                await process.stdin.drain()
                return True, None
            except Exception as e:
                logger.error(f"terminal: stdin write error (slot {slot}): {e}")
                return False, str(e)

        async def _read_output(self, key: tuple):
            """Reads stdout/stderr in chunks and signals update_loop about new data."""
            if key not in self.running_commands:
                return

            cmd_data = self.running_commands[key]
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
                await kernel.handle_error(e, message="Terminal output read failed")
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
                tasks = self.update_tasks.pop(key, None)
                if tasks:
                    t = tasks["update"]
                    if not t.done():
                        t.cancel()
                        try:
                            await t
                        except asyncio.CancelledError:
                            pass

                # Send final output and clean state
                if key in self.running_commands:
                    await self._send_final(key)
                    del self.running_commands[key]

        async def _update_loop(self, key: tuple):
            """
            Update message in real-time:
            - on each new chunk (data_event) or
            - on timeout (update_interval from config).
            Edits are throttled to avoid Telegram API flood.
            Only edits when the formatted message actually changed.
            """
            last_edit = 0.0

            while key in self.running_commands:
                cmd_data = self.running_commands[key]

                if cmd_data["completed"]:
                    break

                interval = _get_config().get("update_interval") or 3
                try:
                    await asyncio.wait_for(
                        asyncio.shield(cmd_data["data_event"].wait()),
                        timeout=float(interval),
                    )
                except TimeoutError:
                    # Normal poll timeout - continue loop.
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
                wait_time = min_edit - (now - last_edit)
                if wait_time > 0:
                    try:
                        await asyncio.sleep(wait_time)
                    except asyncio.CancelledError:
                        break

                # Build message and compare - skip if identical
                new_text = self._build_message(cmd_data)
                if new_text == cmd_data.get("_last_sent_text"):
                    continue
                cmd_data["_last_sent_text"] = new_text

                chat_id = key[0]
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
                    # Ignore "message not modified" and other temporary Telegram errors.
                    pass

        async def _send_final(self, key: tuple):
            """Edit the message one last time with final output + exit code."""
            if key not in self.running_commands:
                return
            cmd_data = self.running_commands[key]
            chat_id = key[0]

            piped = cmd_data.get("piped", False)

            try:
                if piped:
                    stdout = cmd_data["stdout"].decode("utf-8", errors="ignore")
                    stdout = _apply_output_filters(stdout, _get_config())
                    await client.edit_message(
                        chat_id,
                        cmd_data["message_id"],
                        stdout,
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

        async def kill_command(
            self,
            chat_id,
            slot: str = "1",
            message_id=None,
        ):
            """Kill slot *slot* or all slots in the chat when slot='all'."""
            if slot == "all":
                keys = [k for k in self.running_commands if k[0] == chat_id]
                if not keys:
                    msg_text = (
                        f"{CUSTOM_EMOJI['🗯']} <i>{lang['no_running_commands']}</i>"
                    )
                    if message_id:
                        await client.edit_message(
                            chat_id, message_id, msg_text, parse_mode="html"
                        )
                    else:
                        await client.send_message(chat_id, msg_text, parse_mode="html")
                    return
                # Kill every running slot concurrently.
                await asyncio.gather(
                    *[self._kill_one(chat_id, k[1]) for k in keys],
                    return_exceptions=True,
                )
                if message_id:
                    count = len(keys)
                    await client.edit_message(
                        chat_id,
                        message_id,
                        f"{CUSTOM_EMOJI['☑️']} <i>{lang['command_stopped']} ({count})</i>",
                        parse_mode="html",
                    )
                return

            await self._kill_one(chat_id, slot, message_id)

        async def _kill_one(
            self,
            chat_id,
            slot: str,
            message_id=None,
        ):
            """Kill a single slot."""
            key = (chat_id, slot)
            if key not in self.running_commands:
                msg_text = f"{CUSTOM_EMOJI['🗯']} <i>{lang['no_running_commands']}</i>"
                if message_id:
                    await client.edit_message(
                        chat_id, message_id, msg_text, parse_mode="html"
                    )
                else:
                    await client.send_message(chat_id, msg_text, parse_mode="html")
                return

            cmd_data = self.running_commands[key]

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
                            # Process already gone - acceptable.
                            pass

                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except TimeoutError:
                        # Process didn't exit within 5 s - give up waiting.
                        pass

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
                await kernel.handle_error(e, message="Terminal kill command failed")

    terminal = TerminalModule()

    @kernel.register.command(
        "t",
        doc_en="[@N] [command] execute shell command (optional slot @1-@N)",
        doc_ru="[@N] [кoмaндa] выпoлнить shell кoмaндy (cлoт @1-@N нeoбязaтeлeн)",
    )
    async def terminal_handler(event):
        """Execute a shell command. Prefix with @N to use a named parallel slot."""
        args = event.text.split(maxsplit=1)
        pipe_input = getattr(event, "pipe_input", None)
        piped = getattr(event, "piped", False)

        if len(args) < 2:
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_not_specified']}</i>",
                parse_mode="html",
            )
            return

        slot, cmd = _parse_slot(args[1])

        quiet = False
        if cmd.startswith("-q "):
            quiet = True
            cmd = cmd[3:]

        if pipe_input:
            cmd = f"{pipe_input}\n{cmd}"

        if not cmd.strip():
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_not_specified']}</i>",
                parse_mode="html",
            )
            return

        if piped:
            output = await terminal.run_command_piped(
                event.chat_id, cmd, event.id, quiet
            )
            await event.edit(output if output else "done")
        else:
            await terminal.run_command(event.chat_id, cmd, event.id, slot=slot)

    @kernel.register.command(
        "tkill",
        doc_en="[@N|@all] stop running terminal command(s)",
        doc_ru="[@N|@all] ocтaнoвить выпoлняeмyю кoмaндy тepминaлa",
    )
    async def terminal_kill_handler(event):
        """Kill a slot (@N) or all slots (@all). Defaults to slot @1."""
        args = event.text.split(maxsplit=1)
        rest = args[1].strip() if len(args) > 1 else ""
        slot, _ = _parse_slot(rest) if rest else ("1", "")
        await terminal.kill_command(event.chat_id, slot=slot, message_id=event.id)

    @kernel.register.command(
        "ti",
        doc_en="[@N] <text> send text to stdin of a running command",
        doc_ru="[@N] <тeкcт> oтпpaвить тeкcт в stdin зaпyщeннoй кoмaнды",
    )
    async def terminal_input_handler(event):
        """Write text to the stdin of a running process (useful for interactive programs)."""
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>{lang['command_not_specified']}</i>",
                parse_mode="html",
            )
            return

        slot, text = _parse_slot(args[1])

        ok, err = await terminal.send_stdin(event.chat_id, slot, text)

        slot_label = f" <code>@{html.escape(slot)}</code>" if slot != "1" else ""

        if ok:
            await event.edit(
                f"{CUSTOM_EMOJI['☑️']} <i>stdin{slot_label} ← </i>"
                f"<code>{html.escape(text)}</code>",
                parse_mode="html",
            )
        elif err == "no_running":
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>{lang['no_running_commands']}{slot_label}</i>",
                parse_mode="html",
            )
        elif err == "completed":
            await event.edit(
                f"{CUSTOM_EMOJI['💬']} <i>{lang['already_completed']}{slot_label}</i>",
                parse_mode="html",
            )
        elif err == "no_stdin":
            await event.edit(
                f"{CUSTOM_EMOJI['⚠️']} <i>stdin{slot_label} closed "
                f"(stdin_eof enabled?)</i>",
                parse_mode="html",
            )
        else:
            await event.edit(
                f"{CUSTOM_EMOJI['🗯']} <i>stdin error{slot_label}:</i> "
                f"<code>{html.escape(str(err))}</code>",
                parse_mode="html",
            )
