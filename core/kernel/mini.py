from __future__ import annotations

# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: mini kernel — lightweight build on top of standard
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork

import asyncio
import os
import time
from typing import Any

from .standard import Kernel as _StandardKernel


class Kernel(_StandardKernel):
    """Mini kernel"""

    def __init__(self) -> None:
        super().__init__()
        self._kernel_tag = "MINI"
        self.logger.debug("[MiniKernel] __init__ done")

    async def run(self) -> None:
        """Slimmed startup: skip the web panel & inline-bot unless enabled."""
        import logging

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
            self.cprint(
                f"{self.Colors.YELLOW}Install: pip install aiosqlite{self.Colors.RESET}"
            )
        except Exception as e:
            self.cprint(f"{self.Colors.RED}=X DB init error: {e}{self.Colors.RESET}")
            await self.log_error_async(f"DB init error: {e}")

        if self.config.get("inline_bot_token"):
            await self.setup_inline_bot()

        from ..lib.utils.logger import KernelLogger, setup_telegram_logging

        kernel_logger = KernelLogger(self)
        telegram_handler = setup_telegram_logging(self.logger, kernel_logger)
        await telegram_handler.start()
        self._telegram_handler = telegram_handler
        self._kernel_logger = kernel_logger

        from telethon import events
        import html
        import traceback

        async def message_handler(event):
            _tele = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            _note = '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>'
            msg = getattr(event, "message", event)

            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return

            self._mark_command_event_processed(event)
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)
                from telethon.errors import RPCError

                if isinstance(e, RPCError):
                    try:
                        await event.edit(
                            f"{_tele} <b>RPC error:</b> <code>{html.escape(str(e))}</code>",
                            parse_mode="html",
                        )
                    except Exception:
                        pass
                    return

                tb = traceback.format_exc()
                if len(tb) > 1000:
                    tb = tb[-1000:] + "\n...(truncated)"
                try:
                    await event.edit(
                        f"{_tele} <b>Call <code>{html.escape(event.text or '')}</code> failed!</b>\n"
                        f"{_note} <b><i>Full log:</i></b>\n<pre>{tb}</pre>",
                        parse_mode="html",
                    )
                except Exception:
                    pass

        async def fallback_message_handler(event):
            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return
            self._mark_command_event_processed(event)
            await self.process_command(event)

        self._core_message_handler = message_handler
        self._core_fallback_message_handler = fallback_message_handler
        self.client.add_event_handler(message_handler, events.NewMessage())
        self.client.add_event_handler(message_handler, events.MessageEdited())
        self.client.add_event_handler(fallback_message_handler, events.NewMessage())

        modules_start = time.time()
        await self.load_system_modules()
        if os.path.exists(self.RESTART_FILE):
            try:
                with open(self.RESTART_FILE) as f:
                    data = f.read().split(",")
                if len(data) >= 3:
                    from ..lib.utils.colors import Colors as _Colors

                    restart_chat_id = int(data[0])
                    restart_msg_id = int(data[1])
                    restart_time = float(data[2])
                    total_ms = round(time.time() - restart_time, 2)

                    em_alembic = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
                    lang = self.config.get("language", "ru")
                    _strings = {
                        "ru": {
                            "success": "Перезагрузка <b>успешна!</b>",
                            "loading": "но модули ещё загружаются...",
                        },
                        "en": {
                            "success": "Reboot <b>successful!</b>",
                            "loading": "but modules are still loading...",
                        },
                    }
                    s = _strings.get(lang, _strings["en"])
                    await self.client.edit_message(
                        restart_chat_id,
                        restart_msg_id,
                        f"{em_alembic} {s['success']} (*.*)\n"
                        f"<i>{s['loading']}</i> <b>Kernel boot:</b><code> {total_ms} </code>s",
                        parse_mode="html",
                    )
            except Exception:
                pass

        await self.load_module_sources()
        await self.load_user_modules()
        modules_end = time.time()

        logo = (
            f"\n ___  ___ ___ _  _ ___ \n"
            f"| \\/ |_ _| _ \\ || |_ _|\n"
            f"| |\\/| || ||  / __ || | \n"
            f"|_|  |_|___|_|_|_||_|___|\n"
            f"Mini kernel loaded.\n\n"
            f"• Version:  {self.VERSION}\n"
            f"• Prefix:   {self.custom_prefix}\n"
        )
        if self.error_load_modules:
            logo += f"• Module load errors: {self.error_load_modules}\n"
        print(logo)
        self.logger.info("Start MCUB Mini!")
        del logo

        if os.path.exists(self.RESTART_FILE):
            await self._handle_restart_notification(modules_start, modules_end)

        async def _run_with_reconnect():
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
                    delay = self.reconnect_delay * min(self.reconnect_attempts, 10)
                    if (
                        self.reconnect_attempts <= 3
                        or self.reconnect_attempts % 10 == 0
                    ):
                        self.logger.warning(
                            f"Connection lost, attempt {self.reconnect_attempts}, retrying in {delay}s..."
                        )
                    await asyncio.sleep(delay)
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

    async def _handle_restart_notification(
        self, modules_start: float, modules_end: float
    ) -> None:
        """Post-restart notification — same format as standard kernel.

        The restart.tmp file contains:  chat_id,msg_id,timestamp[,thread_id]
        """
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
                else f"MCUB {self._kernel_tag}"
            )

            em_package = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
            em_error = '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'

            kernel_s = round(modules_start - restart_time, 2)
            mod_s = round(modules_end - modules_start, 2)

            lang = self.config.get("language", "ru")
            _all_strings = {
                "ru": {
                    "loaded": f"Твой <b>{mcub}</b> полностью загрузился!",
                    "errors": f"Твой <b>{mcub}</b> <b>загрузился c ошибками</b> :(",
                },
                "en": {
                    "loaded": f"Your <b>{mcub}</b> is fully loaded!",
                    "errors": f"Your <b>{mcub}</b> <b>loaded with errors</b> :(",
                },
            }
            strings = _all_strings.get(lang, _all_strings["en"])

            if not self.client.is_connected():
                return

            if not self.error_load_modules:
                msg_text = (
                    f"{em_package} {strings['loaded']}\n"
                    f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                    f"<b>Modules:</b><code> {mod_s} </code>s.</blockquote>"
                )
            else:
                msg_text = (
                    f"{em_error} {strings['errors']}\n"
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
            self.logger.error(f"[MiniKernel] Restart file error: {e}")
            if os.path.exists(self.RESTART_FILE):
                try:
                    os.remove(self.RESTART_FILE)
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"[MiniKernel] Unexpected restart handler error: {e}")
