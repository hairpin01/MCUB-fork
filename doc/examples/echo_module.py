# Example: Echo module with configuration

from __future__ import annotations

from telethon import events

from core.lib.loader.module_base import ModuleBase, command
from core.lib.loader.module_config import Boolean, Integer, ModuleConfig, String


class EchoModule(ModuleBase):
    name = "Echo"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Эхо-модуль", "en": "Echo module"}
    dependencies: list[str] = []

    config = ModuleConfig(
        String("prefix", default=">>>"),
        Boolean("uppercase", default=False),
        Boolean("reverse", default=False),
        Integer("repeat", default=1, min=1, max=10),
    )

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "echo_help": "Использование: echo <текст>",
            "no_text": "Укажите текст после команды",
            "result": "{prefix} {text}",
        },
        "en": {
            "echo_help": "Usage: echo <text>",
            "no_text": "Please specify text after the command",
            "result": "{prefix} {text}",
        },
    }

    @command("echo", doc_ru="<текст> Повторить текст", doc_en="<text> Echo text")
    async def cmd_echo(self, event: events.NewMessage.Event) -> None:
        args: list[str] = event.text.split(maxsplit=1)

        if len(args) < 2:
            await event.edit(self.strings["echo_help"])
            return

        text: str = args[1].strip()

        if self.config["uppercase"]:
            text = text.upper()

        if self.config["reverse"]:
            text = text[::-1]

        repeat: int = self.config["repeat"]
        prefix: str = self.config["prefix"]

        results: list[str] = [self.strings("result", prefix=prefix, text=text)] * repeat
        await event.edit("\n".join(results))
