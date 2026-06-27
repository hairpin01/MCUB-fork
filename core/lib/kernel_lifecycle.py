# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# ---- meta data ------ kernel_lifecycle -----------
# author: @Hairpin00
# description: Run, shutdown, restart, command processing
# --- meta data end ---------------------------------
from __future__ import annotations

import asyncio
import gc
import html
import os
import secrets
import time
import traceback
from typing import TYPE_CHECKING, Any

from core.lib.types.event import Event

if TYPE_CHECKING:
    from core.lib.types.message import Message

try:
    from utils.html_parser import HTML_PARSER_AVAILABLE
except ImportError:
    HTML_PARSER_AVAILABLE = False
from telethon import events, install_uvloop

from core.lib.loader.kernel_proxy import wrap_event_for_module
from core.lib.utils import purge_caches
from core.lib.utils.colors import Colors
from core.lib.utils.event_helpers import make_simple_event, run_and_capture
from core.lib.utils.logger import KernelLogger, setup_telegram_logging
from utils.restart import read_restart_context


class KernelLifecycleMixin:
    """Kernel lifecycle mixin - run, shutdown, restart, command processing."""

    async def run(self) -> None:
        """Setup, connect, load modules, and run until disconnected."""
        try:
            await self._run_impl()
        except Exception as e:
            import traceback as _tb

            _tb.print_exc()
            msg = f"\033[91m\033[1mKernel crashed:\033[0m\033[91m {e}\033[0m"
            print(msg, flush=True)
            if getattr(self, "logger", None):
                self.logger.critical("Kernel crashed: %s", e, exc_info=True)

    async def _run_impl(self) -> None:
        """Inner startup - wrapped by run() so no crash kills the process."""
        import logging

        try:
            _true = install_uvloop()
            if not _true:
                self._log_if_logger("info", "failed install uvloop")
        except Exception as e:
            self._log_if_logger("info", "uvloop install failed: %s", e)
            await self.handle_error(e, message="uvloop setup failed")

        no_web = not getattr(self, "web_enabled", True)

        if not no_web:
            try:
                web_via_env = os.environ.get("MCUB_WEB", "0") == "1"
                web_via_config = self.config.get("web_panel_enabled", False)
                from utils.security import session_exists

                api_id = getattr(self, "API_ID", None)
                api_hash = getattr(self, "API_HASH", None)
                no_session = not session_exists(api_id, api_hash)
                no_config = not os.path.exists(self.CONFIG_FILE)

                if web_via_env or web_via_config or no_session or no_config:
                    await self.run_panel()
            except Exception as e:
                self._log_if_logger("warning", "web panel setup failed: %s", e)
                await self.handle_error(e, message="Web panel startup failed")

        if not getattr(self, "_config_loaded", False) and not self.first_time_setup():
            self._log_if_logger("error", "Setup failed")
            return
        logging.basicConfig(level=logging.DEBUG)

        try:
            self.load_repositories()
        except Exception as e:
            self._log_if_logger("warning", "load_repositories failed: %s", e)
            await self.handle_error(e, message="Repository loading failed")
        try:
            await self.init_scheduler()
        except Exception as e:
            self._log_if_logger("warning", "init_scheduler failed: %s", e)
            await self.handle_error(e, message="Scheduler initialization failed")

        # Parallel: start client, db, and inline bot concurrently
        async def _init_db_safe():
            try:
                await self.init_db()
            except ImportError:
                self.cprint(
                    f"{Colors.YELLOW}Install: pip install aiosqlite{Colors.RESET}"
                )
                await self.log_error_async("DB init failed: aiosqlite not installed")
            except Exception as e:
                self.cprint(f"{Colors.RED}=X DB init error: {e}{Colors.RESET}")
                await self.log_error_async(f"DB init error: {e}")

        try:
            client_task = asyncio.create_task(self.init_client())
            db_task = asyncio.create_task(_init_db_safe())
            inline_task = asyncio.create_task(self.setup_inline_bot())

            client_ok = await client_task
            if not client_ok:
                db_task.cancel()
                inline_task.cancel()
                return

            await asyncio.gather(db_task, inline_task, return_exceptions=True)
        except Exception as e:
            self._log_if_logger("error", "client/db/inline init failed: %s", e)
            await self.handle_error(e, message="Client/DB/Inline setup failed")
            return

        try:
            if not self.config.get("inline_bot_token"):
                from core_inline.bot import InlineBot

                self.inline_bot = InlineBot(self)
                await self.inline_bot.setup()
        except Exception as e:
            self._log_if_logger("warning", "InlineBot setup failed: %s", e)
            await self.handle_error(e, message="Inline bot setup failed")

        try:
            kernel_logger = KernelLogger(self) if KernelLogger else None
            if setup_telegram_logging:
                telegram_handler = setup_telegram_logging(
                    self.logger,
                    kernel_logger,
                )
                await telegram_handler.start()
                self._telegram_handler = telegram_handler
                self._kernel_logger = kernel_logger
        except Exception as e:
            self._log_if_logger("warning", "telegram logging setup failed: %s", e)
            await self.handle_error(e, message="Telegram logging setup failed")
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

        if self.dispatcher is not None:
            self._core_message_handler = self.dispatcher.watcher_message_handler
            self._core_fallback_message_handler = (
                self.dispatcher.watcher_message_handler
            )
            self.dispatcher.register()
        else:
            self.logger.error(
                "[core_handlers] dispatcher unavailable - no core handlers registered"
            )
        self.logger.debug(
            "[core_handlers] registered outgoing handlers builders=%r",
            self._debug_event_builders_snapshot(),
        )

        restart_time = None
        if os.path.exists(self.RESTART_FILE):
            try:
                restart_ctx = read_restart_context(self.RESTART_FILE)
                restart_chat_id = restart_ctx.chat_id
                restart_msg_id = restart_ctx.message_id
                restart_time = restart_ctx.timestamp
                emojis = [
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
                    ">_<",
                    "0_o",
                ]

                em_alembic = '<tg-emoji emoji-id="5310041868191407556">🔭</tg-emoji>'
                emoji = secrets.choice(emojis)
                total_ms = round(time.time() - restart_time, 2) if restart_time else 0

                await self.client.edit_message(
                    restart_chat_id,
                    restart_msg_id,
                    f"<blockquote>{em_alembic} <b>{strings('success')}</b> <i>{emoji}</i></blockquote>\n"
                    f"<blockquote><i>{strings('loading')}</i> <b>Kernel boot:</b><code> {total_ms} </code>s</blockquote>",
                    parse_mode="html",
                )
            except Exception:
                pass

        self.client.set_protection_mode("safe")
        modules_start = time.time()

        try:
            self.load_kernel = "system"
            await self.load_system_modules()
        except Exception as e:
            self._log_if_logger("error", "load_system_modules failed: %s", e)
            await self.handle_error(e, message="System modules loading failed")
        try:
            await self.load_module_sources()
        except Exception as e:
            self._log_if_logger("warning", "load_module_sources failed: %s", e)
            await self.handle_error(e, message="Module sources loading failed")
        try:
            self.load_kernel = "user"
            await self.load_user_modules()
        except Exception as e:
            self._log_if_logger("error", "load_user_modules failed: %s", e)
            await self.handle_error(e, message="User modules loading failed")
        try:
            if self._loader:
                self._loader.save_persistent_type_cache()
        except Exception as e:
            self._log_if_logger("warning", "save_type_cache failed: %s", e)
            await self.handle_error(e, message="Type cache save failed")

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

        _logo_art = (
            " _    _  ____ _   _ ____\n"
            "| \\  / |/ ___| | | | __ )\n"
            "| |\\/| | |   | | | |  _ \\\n"
            "| |  | | |___| |_| | |_) |\n"
            "|_|  |_|\\____|\\___/|____/"
        )
        _info = (
            f"\nKernel loaded.\n\n"
            f"• Version: {self.VERSION}\n"
            f"• Prefix: {self.custom_prefix}\n"
        )
        if getattr(self, "error_load_modules_name", False):
            modules_items = "\n".join(
                f"- {name}" for name in self.error_load_modules_name
            )
        else:
            modules_items = None

        _errors = (
            Colors.paint(
                f"• Module load errors: {self.error_load_modules}\n" f"{modules_items}",
                Colors.BOLD,
                Colors.BRIGHT_RED,
            )
            if self.error_load_modules
            else ""
        )
        logo = (
            "\n"
            + Colors.gradient_multicolor(
                _logo_art + _info,
                [(200, 0, 0), (230, 60, 0), (255, 140, 0), (220, 220, 220)],
                bold=True,
            )
            + _errors
        )
        print(logo)
        self.logger.info("Start MCUB!")
        del logo
        self.load_kernel = "full"

        async def _memory_monitor():
            """Periodically check RSS vs total RAM and purge caches when memory is high."""
            CHECK_INTERVAL = 30
            PCT_L1 = 0.55  # 55% → L1
            PCT_L2 = 0.70  # 70% → L2
            PCT_L3 = 0.85  # 85% → L3
            RSS_L1 = 600 * 1024 * 1024  # 600 MB absolute → L1
            RSS_L2 = 1200 * 1024 * 1024  # 1.2 GB absolute → L2
            RSS_L3 = 2000 * 1024 * 1024  # 2.0 GB absolute → L3

            def _read_rss_no_psutil():
                try:
                    with open("/proc/self/statm") as f:
                        pages = int(f.read().split()[1])
                        return pages * 4096
                except Exception:
                    return None

            _psutil = None
            try:
                import psutil as _psutil
            except ImportError:
                self.logger.info(
                    "[memmon] psutil not available - using /proc/self/statm"
                )

            while not self.shutdown_flag:
                try:
                    if _psutil is not None:
                        proc = _psutil.Process()
                        rss = proc.memory_info().rss
                    else:
                        rss = _read_rss_no_psutil()
                    if rss is None:
                        await asyncio.sleep(CHECK_INTERVAL)
                        continue

                    if _psutil is not None:
                        total = _psutil.virtual_memory().total
                        ratio = rss / total if total > 0 else 0.0
                    else:
                        ratio = 0.0

                    if ratio >= PCT_L3 or rss >= RSS_L3:
                        level = 3
                    elif ratio >= PCT_L2 or rss >= RSS_L2:
                        level = 2
                    elif ratio >= PCT_L1 or rss >= RSS_L1:
                        level = 1
                    else:
                        level = 0

                    if level:
                        result = purge_caches(self, level=level)
                        cleared = result.get("cleared", [])
                        self.logger.info(
                            "[memmon] RSS %.0f MB (%.1f%%) - " "purge level %d: %s",
                            rss / 1024 / 1024,
                            ratio * 100,
                            level,
                            ", ".join(cleared) if cleared else "nothing",
                        )
                except Exception as exc:
                    self.logger.debug("[memmon] check error: %s", exc)

                try:
                    await asyncio.sleep(CHECK_INTERVAL)
                except asyncio.CancelledError:
                    break

        self._memory_monitor_task = asyncio.create_task(_memory_monitor())

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

    def _log_if_logger(self, level: str, msg: str, *args) -> None:
        """Log if self.logger exists, otherwise print.  Handles degraded mode."""
        logger = getattr(self, "logger", None)
        if logger:
            getattr(logger, level, logger.info)(msg, *args)
        else:
            print(f"[{level}] {msg % args if args else msg}", flush=True)

    async def shutdown(self) -> None:
        """Gracefully close all sessions and disconnect clients."""
        self.shutdown_flag = True

        if hasattr(self, "_connection_monitor") and self._connection_monitor:
            self._connection_monitor.cancel()
            try:
                await self._connection_monitor
            except asyncio.CancelledError:
                pass

        if hasattr(self, "_memory_monitor_task") and self._memory_monitor_task:
            self._memory_monitor_task.cancel()
            try:
                await self._memory_monitor_task
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

        web_runner = getattr(self, "_web_runner", None)
        if web_runner is not None:
            try:
                await web_runner.cleanup()
            except Exception:
                pass
            finally:
                self._web_runner = None

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
            restart_ctx = read_restart_context(self.RESTART_FILE)
            chat_id = restart_ctx.chat_id
            msg_id = restart_ctx.message_id
            restart_time = restart_ctx.timestamp
            thread_id = restart_ctx.thread_id

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
            em_items = '<tg-emoji emoji-id="5375106250449100282">🧳</tg-emoji>'

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
                    modules_items = "\n".join(
                        f"{em_items} <code>{name}</code>"
                        for name in self.error_load_modules_name
                    )
                    msg_text = (
                        f"{em_error} {s('errors', mcub=mcub)}\n"
                        f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                        f"<b>Modules Error:</b><code> {int(self.error_load_modules)}</code></blockquote>"
                        f"<b>{s('modules_not_loaded')}</b>\n"
                        f"<blockquote expandable>{modules_items}</blockquote>"
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
                await self.handle_error(e, message="Restart failed")

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
            except OSError as e:
                import errno as _errno

                if e.errno == _errno.EADDRINUSE:
                    msg = (
                        f"Port {port} is already in use. "
                        "Stop the process occupying it and restart MCUB."
                    )
                    print(f"\n❌  {msg}\n", flush=True)
                    self.logger.error("Setup wizard failed: %s", msg)
                else:
                    self.logger.error("Setup wizard failed: %s", e)
                    await self.handle_error(e, message="Setup wizard failed")
                return
            except Exception as e:
                self.logger.error("Setup wizard failed: %s", e)
                await self.handle_error(e, message="Setup wizard failed")
                return

        # Start the actual web panel in the background
        try:
            from core.web.app import start_web_panel

            self._web_runner = await start_web_panel(self, host, port)
        except Exception as e:
            self.logger.error(f"Failed to start web panel: {e}")
            await self.handle_error(e, message="Web panel start failed")
            await self.log_error_async(f"Failed to start web panel: {e}")

    # Command processing

    async def process_command(self, event: Event, depth: int = 0) -> bool:
        """Proxy to ``dispatcher.process_command``."""
        if self.dispatcher is not None:
            return await self.dispatcher.process_command(event, depth)
        self.logger.error("dispatcher unavailable - cannot process command")
        return False

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

    async def process_bot_command(self, event: Event) -> bool:
        """Dispatch a bot command event to its registered handler."""
        text = event.text
        if not text or not text.startswith("/"):
            return False

        cmd = text.split()[0][1:] if " " in text else text[1:]
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd in self.bot_command_handlers:
            _, handler = self.bot_command_handlers[cmd]
            await handler(wrap_event_for_module(event, "bot_command", self))
            return True

        return False

    def _make_simple_event(self, msg: Message, text: str, chat_id: int) -> Event:
        return make_simple_event(self, msg, text, chat_id)

    async def _run_and_capture(self, ev: Any, depth: int) -> str | None:
        return await run_and_capture(self, ev, depth)

    # User/Thread utilities

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

    async def get_thread_id(self, event: Event) -> int | None:
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

    # Emoji support

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
