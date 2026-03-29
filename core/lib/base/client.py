import asyncio
import json
import sys
import traceback
from typing import TYPE_CHECKING

from telethon import TelegramClient

if TYPE_CHECKING:
    from kernel import Kernel


class ClientManager:
    """Manages the user Telegram client and the optional inline bot."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

    async def init_client(self) -> bool:
        """Create, configure, and authorize the main TelegramClient.

        Returns:
            True when the client is authorized and ready.
        """
        from telethon.sessions import SQLiteSession

        from utils.platform import PlatformDetector, get_platform_name
        from utils.security import ensure_locked_after_write

        k = self.k
        platform = PlatformDetector()
        detected_platform = platform.detect()
        proxy_enabled = bool(k.config.get("proxy"))
        k.logger.info(
            f"Initializing MCUB on {get_platform_name()} "
            f"(Python {sys.version_info.major}.{sys.version_info.minor})..."
        )
        k.logger.debug(
            "Preparing Telegram client session=%r platform=%r proxy_enabled=%s version=%s",
            "user_session",
            detected_platform,
            proxy_enabled,
            k.VERSION,
        )

        k.client = TelegramClient(
            SQLiteSession("user_session"),
            k.API_ID,
            k.API_HASH,
            proxy=k.config.get("proxy"),
            connection_retries=999999,
            request_retries=3,
            flood_sleep_threshold=30,
            device_model=f"MCUB-{detected_platform}",
            system_version=f"Python {sys.version}",
            app_version=f"MCUB {k.VERSION}",
            lang_code="en",
            system_lang_code="en-US",
            base_logger=None,
            catch_up=False,
            auto_reconnect=True,
        )

        try:
            k.logger.debug("Starting Telegram client authorization phone=%r", k.PHONE)
            await k.client.start(phone=k.PHONE, max_attempts=3)

            # Lock the session file right after Telethon creates/writes it
            ensure_locked_after_write("user_session.session", k.logger)

            authorized = await k.client.is_user_authorized()
            k.logger.debug("Telegram client authorized=%s", authorized)
            if not authorized:
                k.logger.error("Authorization failed")
                return False

            me = await k.client.get_me()
            if not me or not hasattr(me, "id"):
                k.logger.error("Invalid user data received")
                return False

            k.ADMIN_ID = me.id
            k.logger.debug(
                "Telegram client ready admin_id=%s first_name=%r",
                me.id,
                getattr(me, "first_name", None),
            )
            k.logger.info(f"Authorized as: {me.first_name} (ID: {me.id})")
            return True

        except Exception as e:
            k.logger.error(f"Client init error: {e}")
            traceback.print_exc()
            return False

    async def setup_inline_bot(self) -> bool:
        """Start the inline bot client if a token is configured.

        Registers InlineHandlers and schedules the bot as a background task.

        Returns:
            True when the bot started successfully.
        """
        from utils.security import ensure_locked_after_write

        k = self.k
        token = k.config.get("inline_bot_token")
        if not token:
            k.logger.warning("Inline bot not configured (no token)")
            return False

        k.logger.info("Starting inline bot...")
        k.logger.debug(
            "Preparing inline bot session=%r token_present=%s",
            "inline_bot_session",
            True,
        )
        k.bot_client = TelegramClient(
            "inline_bot_session", k.API_ID, k.API_HASH, timeout=30
        )

        try:
            k.logger.debug("Authorizing inline bot client")
            await k.bot_client.start(bot_token=token)

            # Lock the bot session file right after creation
            ensure_locked_after_write("inline_bot_session.session", k.logger)

            bot_me = await k.bot_client.get_me()
            k.config["inline_bot_username"] = bot_me.username
            k.logger.debug(
                "Inline bot authorized username=%r id=%r",
                getattr(bot_me, "username", None),
                getattr(bot_me, "id", None),
            )

            with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(k.config, f, ensure_ascii=False, indent=2)
            ensure_locked_after_write(k.CONFIG_FILE, k.logger)
            k.logger.debug("Inline bot config persisted file=%r", k.CONFIG_FILE)

            from core_inline.handlers import InlineHandlers

            handlers = InlineHandlers(k, k.bot_client)
            await handlers.register_handlers()
            k.logger.debug("Inline bot handlers registered")

            task = asyncio.create_task(k.bot_client.run_until_disconnected())
            if not hasattr(k, "_background_tasks"):
                k._background_tasks = []
            k._background_tasks.append(task)
            k.logger.debug(
                "Inline bot background task added total_tasks=%d",
                len(k._background_tasks),
            )

            k.logger.info(f"Inline bot started: @{bot_me.username}")
            return True

        except Exception as e:
            k.logger.error(f"Inline bot handler registration failed: {e}")
            traceback.print_exc()
            return False

    async def safe_connect(self) -> bool:
        """Attempt to (re-)connect the client with exponential back-off.

        Uses kernel attributes: reconnect_attempts, max_reconnect_attempts,
        reconnect_delay, shutdown_flag. Set max_reconnect_attempts=-1 for infinite.

        Returns:
            True when connected and authorized.
        """
        k = self.k
        infinite = k.max_reconnect_attempts < 0

        while infinite or k.reconnect_attempts < k.max_reconnect_attempts:
            if k.shutdown_flag:
                k.logger.debug("safe_connect aborted: shutdown flag is set")
                return False
            try:
                if k.client.is_connected():
                    k.logger.debug("safe_connect skipped: client already connected")
                    return True
                k.logger.debug(
                    "safe_connect attempt=%d max_attempts=%s",
                    k.reconnect_attempts + 1,
                    "infinite" if infinite else k.max_reconnect_attempts,
                )
                await k.client.connect()
                authorized = await k.client.is_user_authorized()
                k.logger.debug(
                    "safe_connect post-connect connected=%s authorized=%s",
                    k.client.is_connected(),
                    authorized,
                )
                if authorized:
                    k.reconnect_attempts = 0
                    if hasattr(k, "_log") and k._log:
                        await k._log.log_network("Client reconnected successfully")
                    return True
                k.logger.debug("safe_connect connected but authorization missing")
            except Exception as e:
                k.reconnect_attempts += 1
                if hasattr(k, "_log") and k._log:
                    if k.reconnect_attempts <= 3 or k.reconnect_attempts % 10 == 0:
                        await k._log.log_network(
                            f"Connection attempt {k.reconnect_attempts} failed: {type(e).__name__}: {e}"
                        )
                    elif k.reconnect_attempts == 4:
                        await k._log.log_network(
                            "⚠️ Connection unstable - reconnection attempts will continue silently (logged every 10 attempts)"
                        )
                delay = k.reconnect_delay * min(k.reconnect_attempts, 10)
                k.logger.debug(
                    "safe_connect failed attempt=%d error=%s delay=%s",
                    k.reconnect_attempts,
                    type(e).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
        k.logger.debug(
            "safe_connect exhausted attempts total_attempts=%d max_attempts=%s",
            k.reconnect_attempts,
            "infinite" if infinite else k.max_reconnect_attempts,
        )
        return False
