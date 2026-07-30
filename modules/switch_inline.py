# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import html
import re

import utils
from core.lib.loader.module_base import ModuleBase, command
from core.lib.types import Event
from core_inline.bot import InlineBot
from utils.strings import Strings

CUSTOM_EMOJI = {
    "success": '<tg-emoji emoji-id="5435933711893797296">🎉</tg-emoji>',
    "no_args": '<tg-emoji emoji-id="5260426225599405269">🪄</tg-emoji>',
    "error": '<tg-emoji emoji-id="5370843963559254781">❌</tg-emoji>',
    "creating": '<tg-emoji emoji-id="5375407018418904583">🪩</tg-emoji>',
}


class SwitchInline(ModuleBase):
    name = "switch_inline"
    version = "1.0.0"
    author = "@Hairpin00"
    description = {
        "ru": "Настройка inline-бота MCUB",
        "en": "MCUB inline bot switcher",
        "linux": "Settings inline bot",
        "rofl": "менятор инлайн бота",
    }
    strings: dict | Strings = {"name": "switch_inline"}

    _USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
    _TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$")

    def _emoji(self, name: str) -> str:
        return CUSTOM_EMOJI[name]

    def _s(self, key: str, **kwargs) -> str:
        return self.strings(
            key,
            success=self._emoji("success"),
            no_args=self._emoji("no_args"),
            error=self._emoji("error"),
            creating=self._emoji("creating"),
            **kwargs,
        )

    def _normalize_username(self, username: str) -> str | None:
        username = username.strip()
        if not self._USERNAME_RE.fullmatch(username):
            return None

        username = username.lstrip("@")
        if not username.lower().endswith("bot"):
            return None
        return username

    @command(
        "set_inline_bot",
        doc_ru="<@username> создать нового inline-бота и сохранить его в config",
        doc_en="<@username> create a new inline bot and save it to config",
        doc_linux="<@username> create a new inline bot and save it to /etc/config_inline_bot.cfg",
        doc_rofl="<@username> создать нови инлайн бота и засейвить в cfg",
    )
    async def cmd_set_inline_bot(self, event: Event) -> None:
        username = self._normalize_username(self.args_raw(event))
        if not username:
            await utils.answer(
                event,
                self._s("bot_usage", prefix=self.kernel.custom_prefix),
            )
            return

        await utils.answer(
            event,
            self._s("creating_bot", username=html.escape(username)),
        )

        inline_bot = InlineBot(self.kernel)
        result = await inline_bot.provision_bot(
            mode="auto",
            client=self.client,
            username=username,
            configure=True,
            persist=True,
            interactive_username=False,
        )

        if not result.success:
            error = html.escape(result.error or result.message or "unknown error")
            await utils.answer(
                event,
                self._s("create_error", error_text=error),
            )
            return

        await utils.answer(event, self._s("applied"))

    @command(
        "set_inline_token",
        doc_ru="<BOT_TOKEN> сохранить токен inline-бота в config",
        doc_en="<BOT_TOKEN> save inline bot token to config",
        doc_linux="<BOT_TOKEN> save inline bot token to /etc/config_inline_bot.cfg",
        doc_rofl="<BOT_TOKEN> поменять бот токен инлайн бота, и засейвить в cfg",
    )
    async def cmd_set_inline_token(self, event: Event) -> None:
        token = self.args_raw(event)
        if not token or not self._TOKEN_RE.fullmatch(token):
            await utils.answer(
                event,
                self._s("token_usage", prefix=self.kernel.custom_prefix),
            )
            return

        self.kernel.config["inline_bot_token"] = token
        self.kernel.save_config()

        await utils.answer(event, self._s("applied"))
