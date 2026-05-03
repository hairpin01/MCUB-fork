# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01
# ---- meta data ------ kernel_lifecycle -----------
# author: @Hairpin00
# description: Run, shutdown, restart, command processing
# --- meta data end ---------------------------------
from __future__ import annotations

import asyncio
import gc
import html
import os
import sys
import time
import traceback
from typing import Any

try:
    from utils.html_parser import HTML_PARSER_AVAILABLE
except ImportError:
    HTML_PARSER_AVAILABLE = False
from telethon import events, install_uvloop

from core.lib.utils.logger import KernelLogger, setup_telegram_logging


class KernelLifecycleMixin:
    """Kernel lifecycle mixin — run, shutdown, restart, command processing."""

    async def run(self) -> None:
        """Setup, connect, load modules, and run until disconnected."""
        import logging

        _true = install_uvloop()
        if not _true:
            self.logger.info("failed install uvloop")

        no_web = not getattr(self, "web_enabled", True)

        if not no_web:
            web_via_env = os.environ.get("MCUB_WEB", "0") == "1"
            web_via_config = self.config.get("web_panel_enabled", False)
            from utils.security import session_exists

            api_id = getattr(self, "API_ID", None)
            api_hash = getattr(self, "API_HASH", None)
            no_session = not session_exists(api_id, api_hash)
            no_config = not os.path.exists(self.CONFIG_FILE)

            if web_via_env or web_via_config or no_session or no_config:
                await self.run_panel()

        if not self.load_or_create_config():
            if not self.first_time_setup():
                self.logger.error("Setup failed")
                return
        logging.basicConfig(level=logging.DEBUG)

        self.load_repositories()
        await self.init_scheduler()

        if not await self.init_client():
            return
        try:
            await self.init_db()
        except ImportError:
            self.cprint(f"{Colors.YELLOW}Install: pip install aiosqlite{Colors.RESET}")
            await self.log_error_async("DB init failed: aiosqlite not installed")
        except Exception as e:
            self.cprint(f"{Colors.RED}=X DB init error: {e}{Colors.RESET}")
            await self.log_error_async(f"DB init error: {e}")

        await self.setup_inline_bot()

        if not self.config.get("inline_bot_token"):
            from core_inline.bot import InlineBot

            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()

        kernel_logger = KernelLogger(self)
        telegram_handler = setup_telegram_logging(
            self.logger,
            kernel_logger,
        )
        await telegram_handler.start()

        self._telegram_handler = telegram_handler
        self._kernel_logger = kernel_logger
        strings = self._get_strings()
        from telethon.errors import RPCError

        async def _monitor_connection():
            """Monitor connection state and log events."""
            reconnect_count = 0
            while not self.shutdown_flag:
                try:
                    await self.client.disconnected
                    if not self.shutdown_flag and self.client.is_connected():
                        reconnect_count += 1
                        if reconnect_count <= 3 or reconnect_count % 10 == 0:
                            self.logger.warning("Connection problems detected...")
                        elif reconnect_count == 4:
                            self.logger.warning(
                                "Telegram servers may be experiencing issues"
                            )
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(1)

        self._connection_monitor = asyncio.create_task(_monitor_connection())
        _tele = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
        _note = '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>'

        async def message_handler(event):
            msg = getattr(event, "message", event)

            if not self.should_process_command_event(event):
                self.logger.debug(
                    "[core_handlers] skip-nonoutgoing handler=message_handler "
                    "text=%r sender=%r chat=%r out=%r admin=%r",
                    getattr(msg, "text", None),
                    getattr(event, "sender_id", None),
                    getattr(event, "chat_id", None),
                    getattr(msg, "out", False),
                    self.is_admin(getattr(event, "sender_id", None)),
                )
                return

            if self._is_command_event_processed(event):
                self.logger.debug(
                    "[core_handlers] skip-duplicate handler=message_handler "
                    "text=%r sender=%r chat=%r",
                    getattr(msg, "text", None),
                    getattr(event, "sender_id", None),
                    getattr(event, "chat_id", None),
                )
                return

            self._mark_command_event_processed(event)
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)

                if isinstance(e, RPCError):
                    cmd_text = html.escape(event.text or "")
                    rpc_msg = html.escape(str(e))
                    try:
                        await event.edit(
                            f"{_tele} {strings('call_failed', cmd=cmd_text, rpc_msg=rpc_msg)}",
                            parse_mode="html",
                        )
                    except Exception as edit_err:
                        self.logger.error(
                            f"{strings('could_not_edit', error=edit_err)}"
                        )
                    return

                    tb = traceback.format_exc()
                    if len(tb) > 1000:
                        tb = tb[-1000:] + "\n...(truncated)"
                    safe_cmd = html.escape(event.text or "")
                    try:
                        await event.edit(
                            f"{_tele} {strings('call_failed_traceback', cmd=safe_cmd, traceback=tb)}",
                            parse_mode="html",
                        )
                    except Exception as edit_err:
                        self.logger.error(f"Could not edit error message: {edit_err}")

        async def fallback_message_handler(event):
            msg = getattr(event, "message", event)
            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return
            self.logger.warning(
                "[core_handlers] fallback-dispatch handler=fallback_message_handler "
                "text=%r sender=%r chat=%r out=%r admin=%r",
                getattr(msg, "text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
                getattr(msg, "out", False),
                self.is_admin(getattr(event, "sender_id", None)),
            )
            self._mark_command_event_processed(event)
            await self.process_command(event)

        self._core_message_handler = message_handler
        self._core_fallback_message_handler = fallback_message_handler
        self.client.add_event_handler(message_handler, events.NewMessage())
        self.client.add_event_handler(message_handler, events.MessageEdited())
        self.client.add_event_handler(fallback_message_handler, events.NewMessage())
        self.logger.debug(
            "[core_handlers] registered outgoing handlers builders=%r",
            self._debug_event_builders_snapshot(),
        )

        restart_time = None
        if os.path.exists(self.RESTART_FILE):
            try:
                with open(self.RESTART_FILE) as f:
                    data = f.read().split(",")
                if len(data) >= 2:
                    restart_chat_id = int(data[0])
                    restart_msg_id = int(data[1])
                    if len(data) >= 3:
                        restart_time = float(data[2])

                    em_alembic = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
                    emoji = "(*.*)"
                    total_ms = (
                        round(time.time() - restart_time, 2) if restart_time else 0
                    )

                    await self.client.edit_message(
                        restart_chat_id,
                        restart_msg_id,
                        f"{em_alembic} {strings('success')} {emoji}\n"
                        f"<i>{strings('loading')}</i> <b>Kernel boot:</b><code> {total_ms} </code>s",
                        parse_mode="html",
                    )
            except Exception:
                pass
        self.client.set_protection_mode("safe")
        modules_start = time.time()
        self.load_kernel = "system"
        await self.load_system_modules()
        await self.load_module_sources()
        self.load_kernel = "user"
        await self.load_user_modules()
        modules_end = time.time()

        if hasattr(self, "bot_client") and self.bot_client:

            @self.bot_client.on(events.NewMessage(pattern="/"))
            async def bot_command_handler(event):
                try:
                    await self.process_bot_command(event)
                except Exception as e:
                    await self.handle_error(
                        e, source="bot_command_handler", event=event
                    )

                    if isinstance(e, RPCError):
                        cmd_text = html.escape(event.text or "")
                        rpc_msg = html.escape(str(e))
                        try:
                            await event.edit(
                                f"{_tele} {strings('call_failed', cmd=cmd_text, rpc_msg=rpc_msg)}",
                                parse_mode="html",
                            )
                        except Exception as edit_err:
                            self.logger.error(
                                f"{strings('could_not_edit', error=edit_err)}"
                            )
                        return

                        tb = traceback.format_exc()
                        if len(tb) > 1000:
                            tb = tb[-1000:] + "\n...(truncated)"
                        safe_cmd = html.escape(event.text or "")
                        try:
                            await event.edit(
                                f"{_tele} {strings('call_failed_traceback', cmd=safe_cmd, traceback=tb)}",
                                parse_mode="html",
                            )
                        except Exception as edit_err:
                            self.logger.error(
                                f"Could not edit error message: {edit_err}"
                            )

        logo = (
            f"\n _    _  ____ _   _ ____\n"
            f"| \\  / |/ ___| | | | __ )\n"
            f"| |\\/| | |   | | | |  _ \\\n"
            f"| |  | | |___| |_| | |_) |\n"
            f"|_|  |_|\\____|\\___/|____/\n"
            f"Kernel loaded.\n\n"
            f"• Version: {self.VERSION}\n"
            f"• Prefix: {self.custom_prefix}\n"
        )
        if self.error_load_modules:
            logo += f"• Module load errors: {self.error_load_modules}\n"
        print(logo)
        self.logger.info("Start MCUB!")
        del logo
        self.load_kernel = "full"

        if os.path.exists(self.RESTART_FILE):
            await self._handle_restart_notification(modules_start, modules_end)

        async def _run_with_reconnect():
            """Run client with automatic reconnection and logging."""
            self.reconnect_attempts = 0
            while not self.shutdown_flag:
                try:
                    if self.client.is_connected():
                        await self.client.disconnected
                    else:
                        await self.client.connect()
                        if await self.client.is_user_authorized():
                            await self.log_network("Client reconnected successfully")
                except (KeyboardInterrupt, asyncio.CancelledError):
                    break
                except ConnectionError:
                    self.reconnect_attempts += 1
                    if (
                        self.reconnect_attempts <= 3
                        or self.reconnect_attempts % 10 == 0
                    ):
                        self.logger.warning(
                            f"Connection lost, attempt {self.reconnect_attempts}, retrying..."
                        )
                    elif self.reconnect_attempts == 4:
                        self.logger.warning(
                            "Connection unstable - will continue silently"
                        )
                    await asyncio.sleep(
                        self.reconnect_delay * min(self.reconnect_attempts, 10)
                    )
                except Exception as e:
                    if "failed 5 time" in str(e) or "Task exception" in str(e):
                        continue
                    self.reconnect_attempts += 1
                    self.logger.warning(
                        f"Connection issue ({type(e).__name__}), attempt {self.reconnect_attempts}"
                    )
                    await asyncio.sleep(
                        self.reconnect_delay * min(self.reconnect_attempts, 10)
                    )

        asyncio.get_event_loop().set_exception_handler(lambda loop, ctx: None)

        try:
            await _run_with_reconnect()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully close all sessions and disconnect clients."""
        self.shutdown_flag = True

        if hasattr(self, "_connection_monitor") and self._connection_monitor:
            self._connection_monitor.cancel()
            try:
                await self._connection_monitor
            except asyncio.CancelledError:
                pass

        if self.scheduler:
            try:
                await self.scheduler.stop()
            except Exception:
                pass

        if hasattr(self, "_telegram_handler") and self._telegram_handler:
            try:
                await self._telegram_handler.stop()
            except Exception:
                pass

        if hasattr(self, "bot_client") and self.bot_client:
            try:
                await self.bot_client.disconnect()
            except Exception:
                pass

        try:
            import aiohttp

            for obj in gc.get_objects():
                if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                    try:
                        await obj.close()
                    except Exception:
                        pass
        except Exception:
            pass

        if self.client and self.client.is_connected():
            try:
                await self.client.disconnect()
            except Exception:
                pass

        await asyncio.sleep(0)
        return

    async def _handle_restart_notification(
        self, modules_start: float, modules_end: float
    ) -> None:
        """Read restart.tmp and send a post-restart status message."""
        try:
            with open(self.RESTART_FILE) as f:
                data = f.read().split(",")

            if len(data) < 3:
                os.remove(self.RESTART_FILE)
                return

            chat_id = int(data[0])
            msg_id = int(data[1])
            restart_time = float(data[2])
            thread_id = int(data[3]) if len(data) >= 4 else None

            os.remove(self.RESTART_FILE)

            me = await self.client.get_me()
            mcub = (
                '<tg-emoji emoji-id="5470015630302287916">🕳️</tg-emoji>'
                '<tg-emoji emoji-id="5469945764069280010">Ⓜ️</tg-emoji>'
                '<tg-emoji emoji-id="5469943045354984820">Ⓜ️</tg-emoji>'
                '<tg-emoji emoji-id="5469879466954098867">Ⓜ️</tg-emoji>'
                if me.premium
                else "MCUB"
            )

            em_package = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
            em_error = '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'

            kernel_s = round(modules_start - restart_time, 2)
            mod_s = round(modules_end - modules_start, 2)

            s = self._get_strings()

            if not self.client.is_connected():
                return

            try:
                if not self.error_load_modules:
                    msg_text = (
                        f"{em_package} {s('loaded', mcub=mcub)}\n"
                        f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                        f"<b>Modules:</b><code> {mod_s} </code>s.</blockquote>"
                    )
                else:
                    msg_text = (
                        f"{em_error} {s('errors', mcub=mcub)}\n"
                        f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                        f"<b>Modules Error:</b><code> {int(self.error_load_modules)} </code>s.</blockquote>"
                    )

                try:
                    await self.client.edit_message(
                        chat_id,
                        msg_id,
                        msg_text,
                        parse_mode="html",
                    )
                except Exception:
                    send_kwargs = {"parse_mode": "html"}
                    if thread_id:
                        send_kwargs["reply_to"] = thread_id
                    await self.client.send_message(chat_id, msg_text, **send_kwargs)
            except Exception as e:
                self.logger.error(f"Could not send restart notification: {e}")
                await self.handle_error(e, source="restart")

        except (OSError, FileNotFoundError, ValueError) as e:
            self.logger.error(f"Restart file error: {e}")
            if os.path.exists(self.RESTART_FILE):
                try:
                    os.remove(self.RESTART_FILE)
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"Unexpected restart handler error: {e}")

    async def run_panel(self) -> None:
        """Start web panel. If config.json is missing, run setup wizard first."""
        host = (
            getattr(self, "web_host", None)
            or os.environ.get("MCUB_HOST")
            or (self.config.get("web_panel_host") if self.config else None)
            or "0.0.0.0"
        )
        port = int(
            getattr(self, "web_port", None)
            or os.environ.get("MCUB_PORT")
            or 0
            or (self.config.get("web_panel_port") if self.config else None)
            or 8080
        )

        # Check if we need setup wizard
        needs_setup = not os.path.exists(self.CONFIG_FILE)
        if not needs_setup:
            from utils.security import session_exists

            api_id = getattr(self, "API_ID", None)
            api_hash = getattr(self, "API_HASH", None)
            session_exists = session_exists(api_id, api_hash)
            needs_setup = not session_exists

        # If config.json doesn't exist or session is missing, start the setup wizard
        if needs_setup:
            try:
                from aiohttp import web

                from core.web.app import create_app

                done = asyncio.Event()
                app = create_app(kernel=None, setup_event=done)
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host, port)
                await site.start()
                print(f"  🌐  Setup wizard  →  http://{host}:{port}/", flush=True)
                try:
                    await done.wait()
                finally:
                    await runner.cleanup()
                print("\nStarting kernel…\n", flush=True)
            except Exception as e:
                self.logger.error(f"Setup wizard failed: {e}")
                return

        # Start the actual web panel in the background
        try:
            from core.web.app import start_web_panel

            _task = asyncio.create_task(start_web_panel(self, host, port))
        except Exception as e:
            self.logger.error(f"Failed to start web panel: {e}")
            await self.log_error_async(f"Failed to start web panel: {e}")

    # --- Command processing ---

    async def process_command(self, event: Any, depth: int = 0) -> bool:
        """Match and dispatch an outgoing message event to a command handler.

        Resolves aliases recursively (max depth 5).
        """
        if depth > 5:
            self.logger.error(f"Alias recursion limit reached: {event.text}")
            await self.log_error_async(f"Alias recursion limit reached: {event.text}")
            return False

        text = event.text
        active_prefix = self.get_prefix_for_sender(getattr(event, "sender_id", None))
        self.logger.debug(
            "[process_command] depth=%d text=%r sender=%r chat=%r "
            "handlers=%d aliases=%d",
            depth,
            text,
            getattr(event, "sender_id", None),
            getattr(event, "chat_id", None),
            len(self.command_handlers),
            len(self.aliases),
        )
        if not text or not text.startswith(active_prefix):
            self.logger.debug(
                "[process_command] ignored text=%r reason=no_prefix prefix=%r",
                text,
                active_prefix,
            )
            return False

        try:
            from utils.arg_parser import PipelineParser

            pipeline = PipelineParser(text)
        except ImportError:
            pipeline = None

        piped_enabled = self.config.get("piped", True)
        if pipeline is not None and not pipeline.is_simple() and piped_enabled:
            return await self._execute_pipeline(event, pipeline, depth)
        return await self._dispatch_single_command(event, depth, active_prefix)

    def get_prefix_for_sender(self, sender_id: Any) -> str:
        """Resolve sender prefix with admin fallback and global fallback."""
        owner_prefixes = getattr(self, "owner_prefixes", {}) or {}
        sender_key = str(sender_id) if sender_id is not None else ""
        admin_key = str(getattr(self, "ADMIN_ID", "") or "")

        if sender_key and sender_key in owner_prefixes:
            return owner_prefixes[sender_key]
        if admin_key and admin_key in owner_prefixes:
            return owner_prefixes[admin_key]
        return getattr(self, "custom_prefix", ".") or "."

    async def _dispatch_single_command(
        self, event: Any, depth: int, active_prefix: str
    ) -> bool:
        """Dispatch a single (non-pipeline) command to its handler."""
        text = event.text

        # Guarantee pipeline attributes exist for every handler
        if not hasattr(event, "piped"):
            event.piped = False
        if not hasattr(event, "pipe_input"):
            event.pipe_input = None
        if not hasattr(event, "pipe_output"):
            event.pipe_output = None
        if not hasattr(event, "pipe_exit_code"):
            event.pipe_exit_code = 0
        if not hasattr(event, "no_add_args_to_input"):
            event.no_add_args_to_input = False

        cmd = (
            text[len(active_prefix) :].split()[0]
            if " " in text
            else text[len(active_prefix) :]
        )

        if cmd in self.aliases:
            alias = self.aliases[cmd]
            self.logger.debug(
                "[process_command] alias-hit cmd=%r target=%r text=%r",
                cmd,
                alias,
                text,
            )
            alias_cmd = alias.split()[0] if " " in alias else alias
            if alias_cmd not in self.command_handlers and alias_cmd not in self.aliases:
                self.logger.warning(
                    f"Alias '{cmd}' points to non-existent target '{alias}', "
                    f"executing '{cmd}' directly"
                )
                if cmd in self.command_handlers:
                    await self.command_handlers[cmd](event)
                    return True
                return False
            args = text[len(active_prefix) + len(cmd) :]
            new_text = active_prefix + alias + args
            self._set_event_text(event, new_text)
            return await self.process_command(event, depth + 1)

        if cmd in self.command_handlers:
            handler = self.command_handlers[cmd]
            self.logger.debug(
                "[process_command] dispatch cmd=%r owner=%r handler=%r",
                cmd,
                self.command_owners.get(cmd),
                getattr(handler, "__name__", repr(handler)),
            )
            if not callable(handler):
                self.logger.warning(
                    f"Command handler for '{cmd}' is not callable, skipping"
                )
                return False
            await handler(event)
            return True

        self.logger.debug(
            "[process_command] miss cmd=%r known=%r",
            cmd,
            sorted(self.command_handlers.keys()),
        )
        return False

    async def process_bot_command(self, event: Any) -> bool:
        """Dispatch a bot command event to its registered handler."""
        text = event.text
        if not text or not text.startswith("/"):
            return False

        cmd = text.split()[0][1:] if " " in text else text[1:]
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd in self.bot_command_handlers:
            _, handler = self.bot_command_handlers[cmd]
            await handler(event)
            return True

        return False

    async def _execute_pipeline(self, event: Any, pipeline: Any, depth: int) -> bool:
        """Execute a multi-segment pipeline expression."""
        segments = pipeline.segments
        if not segments:
            return False
        if depth > 5:
            self.logger.error(f"Pipeline recursion limit reached: {event.text}")
            await self.log_error_async(
                f"Pipeline recursion limit reached: {event.text}"
            )
            return False
        if hasattr(event, "no_owner"):
            await event.edit(
                f"ignored pipeline command: {event.no_owner()}", parse_mode="html"
            )
            return False

        original_edit = getattr(event, "edit", None)
        original_text = event.text
        original_piped = getattr(event, "piped", False)
        original_pipe_input = getattr(event, "pipe_input", None)
        chat_id = getattr(event, "chat_id", None)

        current_event = event
        pipe_input = None
        exit_code = 0

        for i, seg in enumerate(segments):
            next_seg = segments[i + 1] if i + 1 < len(segments) else None

            if seg.operator == "||":
                if exit_code == 0:
                    continue
            elif seg.operator == "&&":
                pipe_input = None
                if not chat_id:
                    continue
                try:
                    sent = await self.client.send_message(chat_id, seg.command)
                    if not sent:
                        exit_code = 1
                        continue
                    new_ev = self._make_simple_event(sent, seg.command, chat_id)
                    new_ev.pipe_input = None
                    is_piped = next_seg is not None and next_seg.operator == "|"
                    new_ev.piped = is_piped
                    if is_piped:
                        pipe_input = await self._run_and_capture(new_ev, depth + 1)
                    else:
                        await self.process_command(new_ev, depth=depth + 1)
                    exit_code = getattr(new_ev, "pipe_exit_code", 0) or 0
                    current_event = new_ev
                except Exception:
                    exit_code = 1
                continue

            elif seg.operator == "&":
                pipe_input = None
                self._wrap_edit_with_fallback(current_event, chat_id)

            is_piped = next_seg is not None and next_seg.operator == "|"

            cmd_text = seg.command
            current_event.piped = is_piped
            current_event.pipe_input = pipe_input

            self._set_event_text(current_event, cmd_text)

            if is_piped:
                pipe_input = await self._run_and_capture(current_event, depth)
                exit_code = getattr(current_event, "pipe_exit_code", 0) or 0
            else:
                if current_event is event and original_edit is not None:
                    current_event.edit = original_edit
                await self.process_command(current_event, depth=depth)
                exit_code = getattr(current_event, "pipe_exit_code", 0) or 0
                pipe_input = None

        event.piped = original_piped
        event.pipe_input = original_pipe_input
        if original_edit is not None:
            event.edit = original_edit
        self._set_event_text(event, original_text)
        return True

    def _make_simple_event(self, msg: Any, text: str, chat_id: int) -> Any:
        """Build a lightweight event object wrapping a freshly sent message."""
        kernel = self

        class _SimpleEvent:
            def __init__(inner_self) -> None:
                inner_self.id = getattr(msg, "id", None)
                inner_self.message_id = inner_self.id
                inner_self.chat_id = chat_id
                inner_self.text = text
                inner_self.message = msg
                inner_self.sender_id = getattr(msg, "sender_id", None)
                inner_self.reply_to_msg_id = getattr(msg, "reply_to_msg_id", None)
                inner_self._client = kernel.client
                inner_self.pipe_input = None
                inner_self.pipe_output = None
                inner_self.pipe_exit_code = 0
                inner_self.piped = False
                inner_self.no_add_args_to_input = False

            async def delete(inner_self):
                try:
                    await inner_self._client.delete_messages(
                        inner_self.chat_id, [inner_self.id]
                    )
                except Exception:
                    pass

            async def get_reply_message(inner_self):
                if not inner_self.reply_to_msg_id:
                    return None
                try:
                    return await inner_self._client.get_messages(
                        inner_self.chat_id, ids=inner_self.reply_to_msg_id
                    )
                except Exception:
                    return None

            async def edit(inner_self, new_text, *args, parse_mode=None, **kwargs):
                try:
                    return await inner_self._client.edit_message(
                        inner_self.chat_id,
                        inner_self.id,
                        new_text,
                        parse_mode=parse_mode,
                    )
                except Exception as _err:
                    kernel.logger.debug(
                        "[SimpleEvent.edit] edit failed (%s), falling back to send_message",
                        _err,
                    )
                    try:
                        sent = await inner_self._client.send_message(
                            inner_self.chat_id, new_text, parse_mode=parse_mode
                        )
                        if sent and hasattr(sent, "id"):
                            inner_self.id = sent.id
                            inner_self.message_id = sent.id
                        return sent
                    except Exception:
                        return None

            async def get_sender(inner_self):
                return await inner_self._client.get_entity(inner_self.sender_id)

            async def get_chat(inner_self):
                return await inner_self._client.get_entity(inner_self.chat_id)

        return _SimpleEvent()

    def _wrap_edit_with_fallback(self, ev: Any, chat_id: int) -> None:
        """Wrap ev.edit so that on failure it falls back to send_message."""
        original_edit = getattr(ev, "edit", None)
        kernel = self

        async def _fallback_edit(new_text, *args, parse_mode=None, **kwargs):
            if original_edit is not None:
                try:
                    return await original_edit(
                        new_text, *args, parse_mode=parse_mode, **kwargs
                    )
                except Exception as _err:
                    kernel.logger.debug(
                        "[& edit-fallback] edit failed (%s), sending new message", _err
                    )
            try:
                sent = await kernel.client.send_message(
                    chat_id, new_text, parse_mode=parse_mode
                )
                if sent and hasattr(sent, "id"):
                    ev.id = sent.id
                    ev.message_id = sent.id
                return sent
            except Exception:
                return None
            return None

        ev.edit = _fallback_edit

    async def _run_and_capture(self, ev: Any, depth: int) -> str | None:
        """Run ev through process_command and return the text passed to event.edit."""
        captured = []
        orig_edit = getattr(ev, "edit", None)

        class _FakeMsg:
            async def edit(inner_self, *a, **kw):
                return inner_self

        async def _cap(new_text, *args, **kwargs):
            if isinstance(new_text, str):
                captured.append(new_text)
            return _FakeMsg()

        ev.edit = _cap
        try:
            await self.process_command(ev, depth=depth)
        finally:
            if orig_edit is not None:
                ev.edit = orig_edit
            else:
                try:
                    del ev.edit
                except AttributeError:
                    pass

        explicit = getattr(ev, "pipe_output", None)
        return (
            explicit if explicit is not None else (captured[-1] if captured else None)
        )

    # --- User/Thread utilities ---

    async def get_user_info(self, user_id: int) -> str:
        """Return a formatted string with the user's name and username."""
        try:
            entity = await self.client.get_entity(user_id)
            if hasattr(entity, "first_name") or hasattr(entity, "last_name"):
                name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                return f"{name} (@{entity.username or 'no username'})"
            if hasattr(entity, "title"):
                return f"{entity.title} (chat/channel)"
            return f"ID: {user_id}"
        except Exception:
            return f"ID: {user_id}"

    async def get_thread_id(self, event: Any) -> int | None:
        """Extract the thread/topic ID from an event if present."""
        if not event:
            return None

        thread_id = getattr(event, "reply_to_top_id", None)
        if not thread_id and hasattr(event, "reply_to") and event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None)

        message = getattr(event, "message", None)
        if not thread_id and message:
            thread_id = getattr(message, "reply_to_top_id", None)
        if not thread_id and message:
            reply_to = getattr(message, "reply_to", None)
            thread_id = getattr(reply_to, "reply_to_top_id", None)

        return thread_id

    # --- Emoji support ---

    async def send_with_emoji(self, chat_id: int, text: str, **kwargs):
        """Send a message with custom emoji support."""
        topic = kwargs.pop("topic", None)
        file = kwargs.pop("file", None)
        formatting_entities = kwargs.pop("formatting_entities", None)
        kwargs.pop("entities", None)

        async def send_payload(message_text: str, *, entities=None):
            payload_kwargs = dict(kwargs)
            if entities is not None:
                payload_kwargs["formatting_entities"] = entities

            if topic is not None:
                if file is not None and hasattr(self.client, "send_file_to_topic"):
                    return await self.client.send_file_to_topic(
                        chat_id,
                        topic,
                        file,
                        caption=message_text,
                        **payload_kwargs,
                    )
                if hasattr(self.client, "send_to_topic"):
                    return await self.client.send_to_topic(
                        chat_id,
                        topic,
                        message_text,
                        **payload_kwargs,
                    )

            return await self.client.send_message(
                chat_id,
                message_text,
                file=file,
                topic=topic,
                **payload_kwargs,
            )

        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await send_payload(text, entities=formatting_entities)

        try:
            parsed, emoji_entities = self.emoji_parser.parse_to_entities(text)
            return await send_payload(parsed, entities=emoji_entities)
        except Exception:
            fallback = (
                self.emoji_parser.remove_emoji_tags(text) if self.emoji_parser else text
            )
            return await send_payload(fallback, entities=formatting_entities)
