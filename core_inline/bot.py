# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import string
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp
from telethon import TelegramClient, events

try:
    from aiogram import Bot as AioBot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.filters import Filter
    from aiogram.types import BotCommand, InlineQuery, CallbackQuery
    from aiogram.methods import (
        AnswerInlineQuery,
        AnswerCallbackQuery,
        SendMessage,
        EditMessageText,
    )
    from aiogram.utils import markdown as md
except Exception:  # pragma: no cover - optional dependency at runtime
    AioBot = None
    Dispatcher = None
    DefaultBotProperties = None
    BotCommand = None
    Filter = None
    InlineQuery = None
    CallbackQuery = None
    AnswerInlineQuery = None
    AnswerCallbackQuery = None
    SendMessage = None
    EditMessageText = None
    md = None


class _InlineQueryFilter(Filter if Filter else object):
    """Filter that passes all inline queries to the handler."""

    async def __call__(self, query: Any) -> bool:
        return True


class _CallbackQueryFilter(Filter if Filter else object):
    """Filter that passes all callback queries to the handler."""

    async def __call__(self, query: Any) -> bool:
        return True


@dataclass(slots=True)
class BotProvisionResult:
    """Result of bot provisioning flow.

    Attributes:
        success: True when bot token/username are ready.
        token: Provisioned token.
        username: Provisioned username without @.
        created: True when a new bot was created via BotFather.
        manual_required: True when user must finish setup manually.
        message: Human readable message for UI/logging.
        error: Error text when success is False.
    """

    success: bool
    token: str | None = None
    username: str | None = None
    created: bool = False
    manual_required: bool = False
    message: str = ""
    error: str | None = None


class InlineBot:
    """Inline bot manager.

    This class handles:
    - Bot provisioning (manual token or BotFather auto-creation).
    - Bot API configuration via aiogram.
    - Runtime Telethon bot client startup for existing inline handlers.
    """

    def __init__(self, kernel: Any | None) -> None:
        """Initialize bot manager.

        Args:
            kernel: MCUB kernel instance or None for standalone WebApp flow.
        """

        self.kernel = kernel
        self.bot_client: TelegramClient | None = None
        self.token: str | None = None
        self.username: str | None = None
        self._aiogram_bot = None
        self._aiogram_dp: Dispatcher | None = None
        self._aiogram_polling_task: asyncio.Task | None = None
        self._telethon_task: asyncio.Task | None = None
        self._inline_handlers_instance = None

        if kernel and getattr(kernel, "logger", None):
            self.logger: logging.Logger = kernel.logger
        else:
            self.logger = logging.getLogger(__name__)

        self.logger.debug("[InlineBot] initialized kernel_bound=%s", bool(kernel))

    async def setup(self) -> None:
        """Run interactive setup flow when token is missing."""

        if not self.kernel:
            self.logger.warning("[InlineBot] setup skipped: kernel is not available")
            return

        self.token = self.kernel.config.get("inline_bot_token")
        self.username = self.kernel.config.get("inline_bot_username")

        self.logger.debug(
            "[InlineBot] setup start token_present=%s username=%s",
            bool(self.token),
            self.username,
        )

        if not self.token:
            await self.create_bot()
            return

        await self.start_bot()
        self.logger.debug("[InlineBot] setup complete")

    async def stop_bot(self) -> None:
        """Disconnect runtime bot client and aiogram runtime if active."""

        await self._stop_aiogram_runtime()

        if self._telethon_task is not None:
            self._telethon_task.cancel()
            try:
                await self._telethon_task
            except (asyncio.CancelledError, Exception):
                pass
            self._telethon_task = None

        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
            self.logger.info("[InlineBot] bot stopped")

    async def create_bot(self) -> None:
        """Interactive CLI flow for creating/configuring inline bot."""

        if not self.kernel:
            self.logger.error("[InlineBot] create_bot requires kernel context")
            return

        self.logger.info("[InlineBot] starting bot setup")
        await self.kernel.db_set("kernel", "HELLO_BOT", "False")

        choice = input(
            f"{self.kernel.Colors.YELLOW}1. Auto create via BotFather\n"
            f"2. Enter token manually\n"
            f"Select (1/2): {self.kernel.Colors.RESET}"
        ).strip()

        if choice == "1":
            await self._auto_create_bot()
            return
        if choice == "2":
            await self._manual_setup()
            return

        self.logger.error("[InlineBot] invalid setup choice")

    async def provision_bot(
        self,
        *,
        mode: Literal["auto", "manual", "config"] = "auto",
        client: Any | None = None,
        token: str | None = None,
        username: str | None = None,
        configure: bool = True,
        persist: bool = True,
        interactive_username: bool = True,
    ) -> BotProvisionResult:
        """Universal bot provisioning method.

        Args:
            mode: Provisioning strategy.
            client: Telethon user client for BotFather dialogs.
            token: Manual token input.
            username: Optional manual username.
            configure: Configure bot profile/commands after provisioning.
            persist: Save token/username to config when kernel is available.
            interactive_username: Ask for username in terminal when auto mode is used.

        Returns:
            BotProvisionResult with details of provisioning outcome.
        """

        self.logger.info("[InlineBot] provision start mode=%s", mode)

        if mode == "config":
            if self.kernel:
                token = token or self.kernel.config.get("inline_bot_token")
                username = username or self.kernel.config.get("inline_bot_username")
            if not token:
                return BotProvisionResult(
                    success=False,
                    error="Token is not configured",
                    message="No bot token in config",
                )

            identity = await self._get_bot_identity(token)
            if not identity.success:
                return identity
            self.token = identity.token
            self.username = identity.username

        elif mode == "manual":
            if not token:
                return BotProvisionResult(
                    success=False,
                    error="Token is required for manual mode",
                )

            identity = await self._get_bot_identity(token)
            if not identity.success:
                return identity

            resolved_username = identity.username
            if (
                username
                and resolved_username
                and username.lower() != resolved_username.lower()
            ):
                self.logger.warning(
                    "[InlineBot] username mismatch provided=%s actual=%s",
                    username,
                    resolved_username,
                )

            self.token = token
            self.username = resolved_username

        else:
            if client is None:
                if self.kernel and getattr(self.kernel, "client", None):
                    client = self.kernel.client
                else:
                    return BotProvisionResult(
                        success=False,
                        error="BotFather client is required for auto mode",
                    )

            auto_result = await self._create_via_botfather(
                client,
                requested_username=username,
                interactive_username=interactive_username,
            )
            if not auto_result.success:
                return auto_result

            self.token = auto_result.token
            self.username = auto_result.username

        if not self.token or not self.username:
            return BotProvisionResult(
                success=False,
                error="Provisioning finished without token/username",
            )

        if configure:
            await self._configure_bot(botfather_client=client)

        if persist and self.kernel:
            self._persist_credentials()

        created = mode == "auto"
        result = BotProvisionResult(
            success=True,
            token=self.token,
            username=self.username,
            created=created,
            message=(
                f"Bot @{self.username} created and configured"
                if created
                else f"Bot @{self.username} configured"
            ),
        )
        self.logger.info(
            "[InlineBot] provision complete mode=%s username=%s",
            mode,
            result.username,
        )
        return result

    async def create_bot_auto_web(self, client: Any) -> dict[str, Any]:
        """Create a bot for WebApp setup flow.

        Args:
            client: Authorized Telethon user client.

        Returns:
            Dict compatible with existing Web API response contract.
        """

        result = await self.provision_bot(
            mode="auto",
            client=client,
            configure=True,
            persist=bool(self.kernel),
            interactive_username=False,
        )
        if not result.success:
            return {
                "error": result.error or "Provision failed",
                "manual": result.manual_required,
            }

        return {
            "success": True,
            "token": result.token,
            "username": result.username,
        }

    async def _auto_create_bot(self) -> None:
        """Create and configure bot automatically via BotFather."""

        if not self.kernel:
            self.logger.error("[InlineBot] auto setup requires kernel")
            return

        result = await self.provision_bot(
            mode="auto",
            client=self.kernel.client,
            configure=True,
            persist=True,
            interactive_username=True,
        )
        if not result.success:
            self.logger.error("[InlineBot] auto setup failed: %s", result.error)
            return

        await self._save_config_and_restart()

    async def _manual_setup(self) -> None:
        """Manual token/username setup flow for terminal users."""

        if not self.kernel:
            self.logger.error("[InlineBot] manual setup requires kernel")
            return

        self.logger.info("[InlineBot] manual setup started")

        while True:
            token = input(
                f"{self.kernel.Colors.YELLOW}Enter bot token: {self.kernel.Colors.RESET}"
            ).strip()
            if not token:
                self.logger.error("[InlineBot] token cannot be empty")
                continue

            username = input(
                f"{self.kernel.Colors.YELLOW}Enter username (without @): {self.kernel.Colors.RESET}"
            ).strip()
            if not username:
                self.logger.error("[InlineBot] username cannot be empty")
                continue

            result = await self.provision_bot(
                mode="manual",
                token=token,
                username=username,
                configure=False,
                persist=True,
            )
            if result.success:
                break

            self.logger.error("[InlineBot] manual setup failed: %s", result.error)

        setup_choice = (
            input(
                f"{self.kernel.Colors.YELLOW}Configure with BotFather? (y/n): {self.kernel.Colors.RESET}"
            )
            .strip()
            .lower()
        )
        if setup_choice == "y":
            await self._configure_bot(botfather_client=self.kernel.client)

        await self.start_bot()

    async def _ask_bot_username(self) -> str:
        """Request and validate desired bot username from CLI."""

        if not self.kernel:
            raise RuntimeError(
                "Kernel context required for interactive username prompt"
            )

        while True:
            username = input(
                f"{self.kernel.Colors.YELLOW}Desired username (without @): {self.kernel.Colors.RESET}"
            ).strip()

            if not username:
                self.logger.error("[InlineBot] username cannot be empty")
                continue

            if not re.match(r"^[a-zA-Z0-9_]{5,32}$", username):
                self.logger.error("[InlineBot] invalid username format: %s", username)
                continue

            if username.lower().endswith("bot"):
                return username

            self.logger.warning(
                "[InlineBot] username should end with 'bot': %s",
                username,
            )
            confirm = (
                input(
                    f"{self.kernel.Colors.YELLOW}Continue with this username? (y/n): {self.kernel.Colors.RESET}"
                )
                .strip()
                .lower()
            )
            if confirm == "y":
                return username

    async def _create_via_botfather(
        self,
        client: Any,
        *,
        requested_username: str | None = None,
        interactive_username: bool = True,
    ) -> BotProvisionResult:
        """Create a new bot through BotFather dialog.

        Args:
            client: Telethon user client.

        Returns:
            Provision result with created credentials.
        """

        try:
            botfather = await client.get_entity("BotFather")
            if not requested_username:
                requested_username = await self._resolve_username_for_creation(
                    interactive=interactive_username
                )

            await client.send_message(botfather, "/newbot")
            await asyncio.sleep(1)
            await client.send_message(botfather, "MCUB Inline Bot")
            await asyncio.sleep(1)
            await client.send_message(botfather, requested_username)

            token, actual_username = await self._wait_for_bot_token(
                botfather=botfather,
                expected_username=requested_username,
                client=client,
            )
            if not token or not actual_username:
                return BotProvisionResult(
                    success=False,
                    error="Could not fetch bot token from BotFather",
                    manual_required=True,
                )

            return BotProvisionResult(
                success=True,
                token=token,
                username=actual_username,
                created=True,
            )
        except asyncio.TimeoutError:
            return BotProvisionResult(
                success=False,
                error="Timed out waiting for BotFather response",
                manual_required=True,
            )
        except Exception as exc:
            self.logger.error("[InlineBot] botfather create failed", exc_info=True)
            return BotProvisionResult(
                success=False, error=str(exc), manual_required=True
            )

    async def _resolve_username_for_creation(self, *, interactive: bool = True) -> str:
        """Get username for bot creation.

        Returns:
            Valid username for BotFather /newbot flow.
        """

        if self.kernel and interactive:
            return await self._ask_bot_username()

        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"mcub_{suffix}_bot"

    async def _wait_for_bot_token(
        self,
        *,
        botfather: Any,
        expected_username: str,
        client: Any,
        timeout: int = 45,
    ) -> tuple[str | None, str | None]:
        """Wait for token and username in recent BotFather replies."""

        start = time.monotonic()
        last_msg_id = 0
        token: str | None = None
        actual_username: str | None = None

        while time.monotonic() - start < timeout:
            messages = await client.get_messages(botfather, limit=8)
            fresh_messages = [msg for msg in messages if msg.id > last_msg_id]

            for msg in fresh_messages:
                last_msg_id = max(last_msg_id, msg.id)
                text = msg.text or ""

                token_match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                if token_match and "token" in text.lower():
                    token = token_match.group(1)

                uname_match = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
                if uname_match:
                    actual_username = uname_match.group(1)
                elif not actual_username:
                    uname_match_at = re.search(r"@([A-Za-z0-9_]+)", text)
                    if uname_match_at:
                        actual_username = uname_match_at.group(1)

                lowered = text.lower()
                if "sorry" in lowered or "invalid" in lowered or "error" in lowered:
                    self.logger.error("[InlineBot] BotFather response: %s", text[:240])
                    return None, None

                if token and actual_username:
                    return token, actual_username

            await asyncio.sleep(2)

        self.logger.error(
            "[InlineBot] BotFather timeout waiting token expected_username=%s",
            expected_username,
        )
        return None, None

    async def _get_bot_identity(self, token: str) -> BotProvisionResult:
        """Validate token and extract bot username via aiogram or Bot API.

        Args:
            token: Bot token.

        Returns:
            Validation result with resolved username.
        """

        masked = self._mask_token(token)
        if AioBot is not None and DefaultBotProperties is not None:
            bot = AioBot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
            try:
                me = await bot.get_me()
                return BotProvisionResult(
                    success=True,
                    token=token,
                    username=me.username,
                    message=f"Token validated ({masked})",
                )
            except Exception as exc:
                self.logger.warning(
                    "[InlineBot] aiogram get_me failed token=%s error=%s",
                    masked,
                    type(exc).__name__,
                )
            finally:
                await bot.session.close()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getMe"
                ) as resp:
                    data = await resp.json()
            if not data.get("ok"):
                return BotProvisionResult(
                    success=False,
                    error=data.get("description", "Invalid token"),
                )

            return BotProvisionResult(
                success=True,
                token=token,
                username=data["result"]["username"],
                message=f"Token validated ({masked})",
            )
        except Exception as exc:
            return BotProvisionResult(
                success=False, error=f"Token validation failed: {exc}"
            )

    async def _configure_bot(self, botfather_client: Any | None = None) -> None:
        """Configure bot profile and commands.

        Uses aiogram/Bot API first, then optional BotFather fallback.
        """

        api_ok = await self._configure_bot_via_api()
        if api_ok:
            return

        if botfather_client is not None:
            await self._configure_bot_via_botfather(botfather_client)

    async def _configure_bot_via_api(self) -> bool:
        """Configure description and commands via aiogram Bot API.

        Returns:
            True when at least base configuration is sent successfully.
        """

        if not self.token:
            return False

        commands_payload = [
            ("start", "start"),
            ("profile", "profile"),
            ("ping", "ping"),
            ("delete_mcub_bot", "remove bot from chat"),
        ]

        if (
            AioBot is not None
            and DefaultBotProperties is not None
            and BotCommand is not None
        ):
            bot = AioBot(
                token=self.token,
                default=DefaultBotProperties(parse_mode="HTML"),
            )
            try:
                await bot.set_my_description(
                    description="MCUB inline bot for automation",
                )
                await bot.set_my_short_description(
                    short_description="MCUB inline assistant",
                )
                commands = [
                    BotCommand(command=c, description=d) for c, d in commands_payload
                ]
                await bot.set_my_commands(commands=commands, language_code="en")
                await bot.set_my_commands(commands=commands, language_code="ru")
                self.logger.info("[InlineBot] bot configured via aiogram Bot API")
                return True
            except Exception:
                self.logger.error("[InlineBot] aiogram configure failed", exc_info=True)
                return False
            finally:
                await bot.session.close()

        session = getattr(self.kernel, "session", None) if self.kernel else None
        external_session = True
        if session is None or session.closed:
            session = aiohttp.ClientSession()
            external_session = False

        try:
            base = f"https://api.telegram.org/bot{self.token}"

            async def post(method: str, payload: dict[str, Any]) -> bool:
                async with session.post(f"{base}/{method}", json=payload) as resp:
                    data = await resp.json()
                if not data.get("ok"):
                    self.logger.warning(
                        "[InlineBot] Bot API %s failed: %s",
                        method,
                        data.get("description"),
                    )
                    return False
                return True

            ok_desc = await post(
                "setMyDescription",
                {"description": "MCUB inline bot for automation"},
            )
            await post(
                "setMyShortDescription",
                {"short_description": "MCUB inline assistant"},
            )
            commands = [{"command": c, "description": d} for c, d in commands_payload]
            await post(
                "setMyCommands",
                {
                    "scope": {"type": "default"},
                    "language_code": "en",
                    "commands": commands,
                },
            )
            await post(
                "setMyCommands",
                {
                    "scope": {"type": "default"},
                    "language_code": "ru",
                    "commands": commands,
                },
            )
            return ok_desc
        except Exception:
            self.logger.error("[InlineBot] fallback configure failed", exc_info=True)
            return False
        finally:
            if not external_session:
                await session.close()

    async def _configure_bot_via_botfather(self, client: Any) -> None:
        """Fallback configuration flow via BotFather chat commands."""

        if not self.username:
            return

        try:
            botfather = await client.get_entity("BotFather")

            await client.send_message(botfather, "/setdescription")
            await asyncio.sleep(1)
            await client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await client.send_message(
                botfather,
                "I'm a bot from MCUB for inline actions.",
            )

            await client.send_message(botfather, "/setinline")
            await asyncio.sleep(1)
            await client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await client.send_message(botfather, "mcub@MCUB~$ ")

            await client.send_message(botfather, "/setinlinefeedback")
            await asyncio.sleep(1)
            await client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await client.send_message(botfather, "Enabled")

            self.logger.info("[InlineBot] fallback BotFather configuration complete")
        except Exception:
            self.logger.error("[InlineBot] BotFather configure failed", exc_info=True)

    async def _save_config_and_restart(self) -> None:
        """Persist config and trigger kernel restart."""

        if not self.kernel:
            return

        self._persist_credentials()
        self.logger.info("[InlineBot] saved credentials username=%s", self.username)
        self.logger.info("[InlineBot] restarting kernel")

        if self.kernel.client and self.kernel.client.is_connected():
            await self.kernel.client.disconnect()

        if (
            hasattr(self.kernel, "bot_client")
            and self.kernel.bot_client
            and self.kernel.bot_client.is_connected()
        ):
            await self.kernel.bot_client.disconnect()

        await self.kernel.restart()

    async def start_bot(self) -> None:
        """Start Telethon runtime bot client and register handlers.

        Returns:
            None.
        """

        if not self.kernel:
            self.logger.error("[InlineBot] start_bot requires kernel context")
            return

        self.token = self.token or self.kernel.config.get("inline_bot_token")
        if not self.token:
            self.logger.error("[InlineBot] cannot start: token is missing")
            return

        session_name = "inline_bot_session"
        self.logger.info("[InlineBot] starting runtime client session=%s", session_name)
        self.bot_client = TelegramClient(
            session_name,
            self.kernel.API_ID,
            self.kernel.API_HASH,
            timeout=30,
        )

        try:
            await self.bot_client.connect()
            if not await self.bot_client.is_user_authorized():
                await self.bot_client.start(bot_token=self.token)

            me = await self.bot_client.get_me()
            self.username = me.username
            self._persist_credentials()

            from .handlers import InlineHandlers

            handlers = InlineHandlers(self.kernel, self.bot_client)
            await handlers.register_handlers()

            self.kernel.bot_client = self.bot_client
            await self._register_module_commands()

            self.logger.info(
                "[InlineBot] runtime client started username=@%s", self.username
            )
            self._telethon_task = asyncio.create_task(
                self.bot_client.run_until_disconnected()
            )

            aiogram_started = await self.start_aiogram_runtime()
            if not aiogram_started:
                self.logger.warning(
                    "[InlineBot] aiogram runtime unavailable, using Telethon-only mode"
                )
        except Exception:
            self.logger.error("[InlineBot] runtime start failed", exc_info=True)

    async def start_aiogram_runtime(self) -> bool:
        """Start aiogram Bot + Dispatcher runtime alongside Telethon.

        Registers aiogram handlers that delegate to InlineHandlers adapter
        methods (process_inline_query / process_callback_query), so the
        same business logic works under both transports.

        Telethon stays active for UpdateBotInlineSend and module-level events.
        Aiogram runs polling for Bot API calls (answerInlineQuery, etc).

        Returns:
            True if aiogram runtime started successfully.
        """

        if AioBot is None or Dispatcher is None:
            self.logger.warning(
                "[InlineBot] aiogram not available, skipping aiogram runtime"
            )
            return False

        if not self.token:
            self.logger.error("[InlineBot] cannot start aiogram runtime: token missing")
            return False

        self.logger.info("[InlineBot] starting aiogram runtime")

        try:
            self._aiogram_bot = AioBot(
                token=self.token,
                default=DefaultBotProperties(parse_mode="HTML"),
            )

            self._aiogram_dp = Dispatcher()

            from .handlers import InlineHandlers

            self._inline_handlers_instance = InlineHandlers(
                self.kernel, self._aiogram_bot
            )

            inline_router = self._aiogram_dp.inline_router
            callback_router = self._aiogram_dp.callback_query_router

            @inline_router.inline_query(_InlineQueryFilter())
            async def _aiogram_inline_handler(query: Any) -> None:
                """Bridge aiogram InlineQuery to the adapter method.

                The adapter (_wrap_aiogram_inline_query) converts aiogram's
                InlineQuery into a Telethon-compatible interface so that
                process_inline_query() logic runs unchanged.
                """
                await self._inline_handlers_instance.process_inline_query(query)

            @callback_router.callback_query(_CallbackQueryFilter())
            async def _aiogram_callback_handler(query: Any) -> None:
                """Bridge aiogram CallbackQuery to the adapter method."""
                await self._inline_handlers_instance.process_callback_query(query)

            self._aiogram_polling_task = asyncio.create_task(
                self._aiogram_dp.start_polling(self._aiogram_bot)
            )

            self.logger.info(
                "[InlineBot] aiogram runtime started username=@%s",
                self.username,
            )
            return True

        except Exception:
            self.logger.error("[InlineBot] aiogram runtime start failed", exc_info=True)
            await self._stop_aiogram_runtime()
            return False

    async def _stop_aiogram_runtime(self) -> None:
        """Stop aiogram polling and close sessions."""

        if self._aiogram_polling_task is not None:
            self._aiogram_polling_task.cancel()
            try:
                await self._aiogram_polling_task
            except (asyncio.CancelledError, Exception):
                pass
            self._aiogram_polling_task = None

        if self._inline_handlers_instance is not None:
            try:
                await self._inline_handlers_instance.close()
            except Exception:
                pass
            self._inline_handlers_instance = None

        if self._aiogram_bot is not None:
            try:
                await self._aiogram_bot.session.close()
            except Exception:
                pass
            self._aiogram_bot = None

        self._aiogram_dp = None
        self.logger.debug("[InlineBot] aiogram runtime stopped")

    def _persist_credentials(self) -> None:
        """Persist bot token/username to kernel config when available."""

        if not self.kernel:
            return

        if self.token:
            self.kernel.config["inline_bot_token"] = self.token
        if self.username:
            self.kernel.config["inline_bot_username"] = self.username
        self._write_config_atomic(self.kernel.CONFIG_FILE, self.kernel.config)

    def _write_config_atomic(self, path: str, data: dict[str, Any]) -> None:
        """Write JSON config atomically to avoid file truncation on crash."""

        fd, tmp_path = tempfile.mkstemp(
            prefix="config_",
            suffix=".json",
            dir=os.path.dirname(path) or ".",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            self.logger.error("[InlineBot] atomic config write failed", exc_info=True)
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
            except Exception:
                self.logger.error(
                    "[InlineBot] fallback config write failed", exc_info=True
                )

    async def _register_module_commands(self) -> None:
        """Attach module command handlers to runtime Telethon bot client."""

        if not self.kernel or not self.bot_client:
            self.logger.warning(
                "[InlineBot] cannot register commands: bot client missing"
            )
            return

        try:
            registered_count = 0
            for _, (pattern, handler) in self.kernel.bot_command_handlers.items():

                async def command_wrapper(
                    event: Any, handler: Any = handler, pattern: str = pattern
                ) -> None:
                    try:
                        self.logger.debug(
                            "[InlineBot] executing bot command pattern=%s", pattern
                        )
                        await handler(event)
                    except Exception as exc:
                        await self.kernel.handle_error(
                            exc,
                            source=f"bot_command:{pattern}",
                            event=event,
                        )

                self.bot_client.add_event_handler(
                    command_wrapper,
                    events.NewMessage(pattern=pattern),
                )
                registered_count += 1

            self.logger.info(
                "[InlineBot] module commands registered total=%s",
                registered_count,
            )
        except Exception:
            self.logger.error("[InlineBot] command registration failed", exc_info=True)

    @staticmethod
    def _mask_token(token: str) -> str:
        """Mask token for safe logging.

        Args:
            token: Raw bot token.

        Returns:
            Masked token string.
        """

        if len(token) <= 10:
            return "***"
        return f"{token[:5]}...{token[-4:]}"
