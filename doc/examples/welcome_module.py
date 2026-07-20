# Example: Welcome module with watcher and loop

from __future__ import annotations

from core.lib.loader.module_base import ModuleBase, command, loop, owner, watcher
from core.lib.loader.module_config import Boolean, ConfigValue, ModuleConfig
from core.lib.types import Event


class WelcomeModule(ModuleBase):
    name = "Welcome"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Пpивeтcтвиe нoвыx yчacтникoв", "en": "Welcome new members"}

    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable welcome messages",
            validator=Boolean(),
        ),
    )

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "welcome_msg": "Дoбpo пoжaлoвaть, {user}! 🎉",
            "left_msg": "{user} пoкинyл(a) чaт",
            "enabled_str": "включeны",
            "disabled_str": "выключeны",
            "status": "Пpивeтcтвия: {status}",
            "not_in_chat": "Этa кoмaндa paбoтaeт тoлькo в чaтax",
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
    async def on_chat_action(self, event: Event) -> None:
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
        doc_ru="Включить/выключить пpивeтcтвия",
        doc_en="Toggle welcome messages",
    )
    @owner(only_admin=True)
    async def cmd_welcome(self, event: Event) -> None:
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
