# Example class-style module with localization (strings)

from __future__ import annotations

from typing import Any
from telethon import events

from core.lib.loader.module_base import ModuleBase, command


class GreetingModule(ModuleBase):
    name = "Greeting"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Модуль приветствий", "en": "Greeting module"}

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "greet": "Привет, {name}!",
            "bye": "Пока, {name}! Хорошего дня!",
            "unknown": "Привет! Я не знаю твоего имени.",
            "help": "Команды: hello, bye",
            "saved_name": "Имя сохранено: {name}",
            "no_name": "Сначала представься: setname <имя>",
            "name_cleared": "Имя очищено",
        },
        "en": {
            "greet": "Hello, {name}!",
            "bye": "Goodbye, {name}! Have a nice day!",
            "unknown": "Hi there! I don't know your name.",
            "help": "Commands: hello, bye",
            "saved_name": "Name saved: {name}",
            "no_name": "Introduce yourself first: setname <name>",
            "name_cleared": "Name cleared",
        },
    }

    @command("hello", doc_ru="Поприветствовать", doc_en="Say hello")
    async def cmd_hello(self, event: events.NewMessage.Event) -> None:
        name: str | None = await self.db.db_get(self.name, "name")
        if name:
            await event.edit(self.strings("greet", name=name))
        else:
            await event.edit(self.strings["unknown"])

    @command("bye", doc_ru="Попрощаться", doc_en="Say goodbye")
    async def cmd_bye(self, event: events.NewMessage.Event) -> None:
        name: str | None = await self.db.db_get(self.name, "name")
        if name:
            await event.edit(self.strings("bye", name=name))
        else:
            await event.edit(self.strings["unknown"])

    @command("setname", doc_ru="<имя> Сохранить имя", doc_en="<name> Save your name")
    async def cmd_setname(self, event: events.NewMessage.Event) -> None:
        args: list[str] = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(self.strings["no_name"])
            return

        name: str = args[1].strip()
        await self.db.db_set(self.name, "name", name)
        await event.edit(self.strings("saved_name", name=name))

    @command("clearname", doc_ru="Очистить имя", doc_en="Clear saved name")
    async def cmd_clearname(self, event: events.NewMessage.Event) -> None:
        await self.db.db_set(self.name, "name", None)
        await event.edit(self.strings["name_cleared"])

    @command("help")
    async def cmd_help(self, event: events.NewMessage.Event) -> None:
        await event.edit(self.strings["help"])

    async def on_load(self) -> None:
        self.log.info(f"{self.name} loaded, locale: {self.strings.locale}")
