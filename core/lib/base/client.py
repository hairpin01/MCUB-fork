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
        from utils.platform import get_platform_name, PlatformDetector
        from telethon.sessions import SQLiteSession

        k = self.k
        platform = PlatformDetector()
        k.logger.info(
            f"Initializing MCUB on {get_platform_name()} "
            f"(Python {sys.version_info.major}.{sys.version_info.minor})..."
        )

        k.client = TelegramClient(
            SQLiteSession("user_session"),
            k.API_ID,
            k.API_HASH,
            proxy=k.config.get("proxy"),
            connection_retries=3,
            request_retries=3,
            flood_sleep_threshold=30,
            device_model=f"MCUB-{platform.detect()}",
            system_version=f"Python {sys.version}",
            app_version=f"MCUB {k.VERSION}",
            lang_code="en",
            system_lang_code="en-US",
            base_logger=None,
            catch_up=False,
        )

        try:
            await k.client.start(phone=k.PHONE, max_attempts=3)

            if not await k.client.is_user_authorized():
                k.logger.error("Authorization failed")
                return False

            me = await k.client.get_me()
            if not me or not hasattr(me, "id"):
                k.logger.error("Invalid user data received")
                return False

            k.ADMIN_ID = me.id
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
        k = self.k
        token = k.config.get("inline_bot_token")
        if not token:
            k.logger.warning("Inline bot not configured (no token)")
            return False

        k.logger.info("Starting inline bot...")
        k.bot_client = TelegramClient(
            "inline_bot_session", k.API_ID, k.API_HASH, timeout=30
        )

        try:
            await asyncio.wait_for(
                k.bot_client.start(bot_token=token),
                timeout=15.0
            )
            bot_me = await k.bot_client.get_me()
            bot_me = await k.bot_client.get_me()
            k.config["inline_bot_username"] = bot_me.username

            with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(k.config, f, ensure_ascii=False, indent=2)

            from core_inline.handlers import InlineHandlers
            handlers = InlineHandlers(k, k.bot_client)
            await handlers.register_handlers()

            task = asyncio.create_task(k.bot_client.run_until_disconnected())
            if not hasattr(k, "_background_tasks"):
                k._background_tasks = []
            k._background_tasks.append(task)

            k.logger.info(f"Inline bot started: @{bot_me.username}")
            return True

        except asyncio.TimeoutError:
            k.logger.error("Inline bot start timeout — check token or network")
            return False

        except Exception as e:
            k.logger.error(f"Inline bot handler registration failed: {e}")
            traceback.print_exc()
            return False

    async def safe_connect(self) -> bool:
        """Attempt to (re-)connect the client with exponential back-off.

        Uses kernel attributes: reconnect_attempts, max_reconnect_attempts,
        reconnect_delay, shutdown_flag.

        Returns:
            True when connected and authorized.
        """
        k = self.k
        while k.reconnect_attempts < k.max_reconnect_attempts:
            if k.shutdown_flag:
                return False
            try:
                if k.client.is_connected():
                    return True
                await k.client.connect()
                if await k.client.is_user_authorized():
                    k.reconnect_attempts = 0
                    return True
            except Exception:
                k.reconnect_attempts += 1
                await asyncio.sleep(k.reconnect_delay * k.reconnect_attempts)
        return False
