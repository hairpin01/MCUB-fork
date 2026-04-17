# Example: Welcome module with watcher and loop

from __future__ import annotations

from typing import Any
from telethon import events

from core.lib.loader.module_base import ModuleBase, command, watcher, loop, owner
from core.lib.loader.module_config import ModuleConfig, Boolean


class WelcomeModule(ModuleBase):
    name = "Welcome"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Приветствие новых участников", "en": "Welcome new members"}

    config = ModuleConfig(
        Boolean("enabled", default=True),
    )

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "welcome_msg": "Добро пожаловать, {user}! 🎉",
            "left_msg": "{user} покинул(а) чат",
            "enabled_str": "включены",
            "disabled_str": "выключены",
            "status": "Приветствия: {status}",
            "not_in_chat": "Эта команда работает только в чатах",
        },
        "en": {
            "welcome_msg": "Welcome, {user}! 🎉",
            "left_msg": "{user} left the chat",
            "enabled_str": "enabled",
            "disabled_str": "disabled",
            "status": "Welcome: {status}",
            "not_in_chat": "This command only works in chats",
        },
    }

    @watcher(chataction=True)
    async def on_chat_action(self, event: events.ChatAction.Event) -> None:
        if not self.config["enabled"]:
            return

        if event.user_joined:
            user = await event.get_user()
            if user:
                await event.reply(self.strings("welcome_msg", user=user.first_name))

        if event.user_left:
            user = await event.get_user()
            if user:
                await event.reply(self.strings("left_msg", user=user.first_name))

    @loop(interval=3600, autostart=True)
    async def hourly_check(self) -> None:
        pass

    @command(
        "welcome",
        doc_ru="Включить/выключить приветствия",
        doc_en="Toggle welcome messages",
    )
    @owner(only_admin=True)
    async def cmd_welcome(self, event: events.NewMessage.Event) -> None:
        chat = await event.get_chat()
        if chat.megagroup or chat.broadcast:
            self.config["enabled"] = not self.config["enabled"]
            status: str = (
                self.strings["enabled_str"]
                if self.config["enabled"]
                else self.strings["disabled_str"]
            )
            await event.edit(self.strings("status", status=status))
        else:
            await event.edit(self.strings["not_in_chat"])

    async def on_load(self) -> None:
        self.log.info(f"{self.name} loaded with enabled={self.config['enabled']}")
