# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: bot kernel
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork
import asyncio
import html
import os
import time
import traceback
from typing import Any

from .standard import Kernel as _StandardKernel


class Kernel(_StandardKernel):
    """Bot kernel — uses a bot token instead of a user account.

    self.client — the bot's TelegramClient (logged in via bot token)
    self.bot_client — alias to self.client (same object)
    """

    def __init__(self) -> None:
        super().__init__()
        self._bot_token: str | None = None
        self._bot_id: int | None = None
        self._kernel_tag: str = "BOT"
        self.logger.debug("[BotKernel] __init__ done")

    @property  # type: ignore[override]
    def bot_client(self):
        return self.client

    @bot_client.setter
    def bot_client(self, value):
        pass

    async def run(self) -> None:
        """Bot startup: ask for token → connect → load modules → loop."""
        import logging

        self.load_or_create_config()
        logging.basicConfig(level=logging.DEBUG)

        await self._ensure_api_credentials()

        await self._ensure_bot_token()

        self._apply_config()

        self.load_repositories()
        await self.init_scheduler()

        if not await self.init_client():
            return
        try:
            await self.init_db()
        except ImportError:
            self.cprint(
                f"{self.Colors.YELLOW}Install: pip install aiosqlite{self.Colors.RESET}"
            )
        except Exception as e:
            self.cprint(f"{self.Colors.RED}=X DB init error: {e}{self.Colors.RESET}")
            await self.log_error_async(f"DB init error: {e}")

        from ..lib.utils.logger import KernelLogger, setup_telegram_logging

        kernel_logger = KernelLogger(self)
        telegram_handler = setup_telegram_logging(self.logger, kernel_logger)
        await telegram_handler.start()
        self._telegram_handler = telegram_handler
        self._kernel_logger = kernel_logger

        self._register_core_handlers()

        modules_start = time.time()
        await self.load_system_modules()
        if os.path.exists(self.RESTART_FILE):
            await self._send_early_restart_notification()

        await self.load_module_sources()
        await self.load_user_modules()
        modules_end = time.time()

        me = await self.client.get_me()
        bot_name = getattr(me, "username", None) or getattr(me, "first_name", "bot")
        logo = (
            f"\n ___  ___ _____   _  _____ ___ _  _ ___ _    \n"
            f"| _ )/ _ \\_   _| | |/ / __| _ \\ \\| | __| |   \n"
            f"| _ \\ (_) || |   | ' <| _||   / .` | _|| |__ \n"
            f"|___/\\___/ |_|   |_|\\_\\___|_|_\\_|\\_|___|____|\n"
            f"Bot kernel loaded.\n\n"
            f"• Bot:      @{bot_name}\n"
            f"• Version:  {self.VERSION}\n"
            f"• Prefix:   {self.custom_prefix}\n"
        )
        if self.error_load_modules:
            logo += f"• Module load errors: {self.error_load_modules}\n"
        print(logo)
        self.logger.info("Start MCUB Bot!")
        del logo

        if os.path.exists(self.RESTART_FILE):
            await self._handle_restart_notification(modules_start, modules_end)

        await self._connection_loop()

    async def _ensure_api_credentials(self) -> None:
        """Ask for API_ID / API_HASH if they're missing from config."""
        changed = False

        if not self.config.get("api_id"):
            self.cprint(
                "\n[BotKernel] API credentials not found.",
                self.Colors.YELLOW,
            )
            self.cprint(
                "Get them at https://my.telegram.org → API development tools\n",
                self.Colors.CYAN,
            )
            api_id = input("  Enter API_ID  : ").strip()
            api_hash = input("  Enter API_HASH: ").strip()
            self.config["api_id"] = int(api_id)
            self.config["api_hash"] = api_hash
            changed = True

        if changed:
            self.save_config()

    async def _ensure_bot_token(self) -> None:
        """Ask for bot token if not present in config (inline_bot_token key)."""
        token = self.config.get("inline_bot_token", "").strip()
        if not token:
            self.cprint(
                "\n[BotKernel] Bot token not found (inline_bot_token in config).",
                self.Colors.YELLOW,
            )
            self.cprint(
                "Get it from @BotFather → /newbot or /mybots\n",
                self.Colors.CYAN,
            )
            token = input("  Enter bot token: ").strip()
            self.config["inline_bot_token"] = token
            self.save_config()

        self._bot_token = token

    def _apply_config(self) -> None:
        """Map config dict values to kernel attributes (replaces ConfigManager.setup)."""
        cfg = self.config

        self.API_ID = int(cfg.get("api_id", 0))
        self.API_HASH = cfg.get("api_hash", "")

        prefix = cfg.get("command_prefix") or cfg.get("prefix", ".")
        self.custom_prefix = prefix

        lang = cfg.get("language", "ru")
        self.config.setdefault("language", lang)

        log_chat = cfg.get("log_chat_id", 0)
        if log_chat:
            self.log_chat_id = int(log_chat)

    async def init_client(self) -> bool:
        """Connect the Telethon client using the bot token."""
        try:
            from telethon import TelegramClient

            sessions_dir = "sessions"
            os.makedirs(sessions_dir, exist_ok=True)
            session_path = os.path.join(sessions_dir, f"bot_{self.API_ID}")

            self.client = TelegramClient(
                session_path,
                self.API_ID,
                self.API_HASH,
            )

            await self.client.start(bot_token=self._bot_token)

            me = await self.client.get_me()
            self._bot_id = me.id
            self.ADMIN_ID = me.id

            self._sync_client_middlewares()

            getattr(me, "username", None) or str(me.id)
            return True

        except Exception as e:
            tb = traceback.format_exc()
            self.cprint(f"\n=X Bot login failed: {e}\n{tb}", self.Colors.RED)
            self.logger.error(f"[BotKernel] init_client error: {e}")
            return False

    def should_process_command_event(self, event: Any) -> bool:
        """Process only messages sent BY the bot itself (out=True).

        Nobody else's messages trigger commands — only the bot's own outgoing
        messages that start with the command prefix.
        """
        msg = getattr(event, "message", event)
        if getattr(msg, "out", False):
            return True

        sender_id = getattr(event, "sender_id", None)
        if self._bot_id and sender_id == self._bot_id:
            return True
        return False

    def _register_core_handlers(self) -> None:
        """Register outgoing message handlers the same way standard does."""
        from telethon import events

        async def message_handler(event):
            _tele = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            _note = '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>'

            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return

            self._mark_command_event_processed(event)
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="bot_message_handler", event=event)

                from telethon.errors import RPCError

                lang = self.config.get("language", "ru")
                from core.langpacks import get_kernel_strings

                s = get_kernel_strings(lang)

                if isinstance(e, RPCError):
                    try:
                        await event.edit(
                            f"{_tele} {s.get('rpc_error', '').format(error=html.escape(str(e)))}",
                            parse_mode="html",
                        )
                    except Exception:
                        pass
                    return

                tb_str = traceback.format_exc()
                if len(tb_str) > 1000:
                    tb_str = tb_str[-1000:] + "\n...(truncated)"
                try:
                    await event.edit(
                        f"{_tele} {s.get('call_failed_traceback', '').format(cmd=html.escape(event.text or ''), traceback=tb_str)}",
                        parse_mode="html",
                    )
                except Exception:
                    pass

        async def fallback_handler(event):
            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return
            self._mark_command_event_processed(event)
            await self.process_command(event)

        self._core_message_handler = message_handler
        self._core_fallback_message_handler = fallback_handler
        self.client.add_event_handler(message_handler, events.NewMessage())
        self.client.add_event_handler(message_handler, events.MessageEdited())
        self.client.add_event_handler(fallback_handler, events.NewMessage())
        self.logger.debug("[BotKernel] core handlers registered")

    async def _send_early_restart_notification(self) -> None:
        """Edit the restart message right after connect (modules not loaded yet)."""
        try:
            with open(self.RESTART_FILE) as f:
                data = f.read().split(",")
            if len(data) < 3:
                return

            chat_id = int(data[0])
            msg_id = int(data[1])
            restart_time = float(data[2])
            total_ms = round(time.time() - restart_time, 2)

            em_alembic = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
            lang = self.config.get("language", "ru")
            from core.langpacks import get_kernel_strings

            s = get_kernel_strings(lang)

            await self.client.edit_message(
                chat_id,
                msg_id,
                f"{em_alembic} {s.get('success', '')} (*.*)\n"
                f"<i>{s.get('loading', '')}</i> <b>Kernel boot:</b><code> {total_ms} </code>s",
                parse_mode="html",
            )
        except Exception:
            pass

    async def _handle_restart_notification(
        self, modules_start: float, modules_end: float
    ) -> None:
        """Send the final post-restart message (same format as standard kernel).

        restart.tmp format: ``chat_id,msg_id,timestamp[,thread_id]``
        """
        try:
            with open(self.RESTART_FILE) as f:
                data = f.read().split(",")

            if len(data) < 3:
                os.remove(self.RESTART_FILE)
                return

            chat_id = int(data[0])
            msg_id = int(data[1])
            restart_ts = float(data[2])
            thread_id = int(data[3]) if len(data) >= 4 else None

            os.remove(self.RESTART_FILE)

            me = await self.client.get_me()
            getattr(me, "username", None) or "bot"

            mcub_label = (
                '<tg-emoji emoji-id="5470015630302287916">🕳️</tg-emoji>'
                '<tg-emoji emoji-id="5469945764069280010">Ⓜ️</tg-emoji>'
                '<tg-emoji emoji-id="5469943045354984820">Ⓜ️</tg-emoji>'
                '<tg-emoji emoji-id="5469879466954098867">Ⓜ️</tg-emoji>'
                if getattr(me, "premium", False)
                else f"MCUB {self._kernel_tag}"
            )

            em_package = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
            em_error = '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'

            kernel_s = round(modules_start - restart_ts, 2)
            mod_s = round(modules_end - modules_start, 2)

            lang = self.config.get("language", "ru")
            from core.langpacks import get_kernel_strings

            s = get_kernel_strings(lang)

            if not self.client.is_connected():
                return

            if not self.error_load_modules:
                msg_text = (
                    f"{em_package} {s.get('loaded', '').format(mcub=mcub_label)}\n"
                    f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                    f"<b>Modules:</b><code> {mod_s} </code>s.</blockquote>"
                )
            else:
                msg_text = (
                    f"{em_error} {s.get('errors', '').format(mcub=mcub_label)}\n"
                    f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                    f"<b>Modules Error:</b><code> {int(self.error_load_modules)} </code></blockquote>"
                )

            try:
                await self.client.edit_message(
                    chat_id, msg_id, msg_text, parse_mode="html"
                )
            except Exception:
                send_kwargs: dict[str, Any] = {"parse_mode": "html"}
                if thread_id:
                    send_kwargs["reply_to"] = thread_id
                await self.client.send_message(chat_id, msg_text, **send_kwargs)

        except (OSError, FileNotFoundError, ValueError) as e:
            self.logger.error(f"[BotKernel] Restart file error: {e}")
            if os.path.exists(self.RESTART_FILE):
                try:
                    os.remove(self.RESTART_FILE)
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"[BotKernel] Unexpected restart handler error: {e}")

    async def _connection_loop(self) -> None:
        """Keep the bot connected with exponential back-off reconnect."""

        async def _run():
            self.reconnect_attempts = 0
            while not self.shutdown_flag:
                try:
                    if self.client.is_connected():
                        await self.client.disconnected
                    else:
                        await self.client.connect()
                        await self.log_network("Bot reconnected successfully")
                except (KeyboardInterrupt, asyncio.CancelledError):
                    break
                except ConnectionError:
                    self.reconnect_attempts += 1
                    delay = self.reconnect_delay * min(self.reconnect_attempts, 10)
                    if (
                        self.reconnect_attempts <= 3
                        or self.reconnect_attempts % 10 == 0
                    ):
                        self.logger.warning(
                            f"[BotKernel] Connection lost, attempt {self.reconnect_attempts}, "
                            f"retrying in {delay}s..."
                        )
                    await asyncio.sleep(delay)
                except Exception as e:
                    if "failed 5 time" in str(e) or "Task exception" in str(e):
                        continue
                    self.reconnect_attempts += 1
                    self.logger.warning(
                        f"[BotKernel] Connection issue ({type(e).__name__}), "
                        f"attempt {self.reconnect_attempts}"
                    )
                    await asyncio.sleep(
                        self.reconnect_delay * min(self.reconnect_attempts, 10)
                    )

        asyncio.get_event_loop().set_exception_handler(lambda loop, ctx: None)
        try:
            await _run()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.shutdown()
