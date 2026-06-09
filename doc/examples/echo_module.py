# Example: Echo module with configuration

from __future__ import annotations

from core.lib.loader.module_base import ModuleBase, command
from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    Integer,
    ModuleConfig,
    String,
)
from core.lib.types import Event


class EchoModule(ModuleBase):
    name = "Echo"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Эxo-мoдyль", "en": "Echo module"}
    dependencies: list[str] = []

    config = ModuleConfig(
        ConfigValue(
            "prefix",
            ">>>",
            description="Text prefix before echoed message",
            validator=String(default=">>>"),
        ),
        ConfigValue(
            "uppercase",
            False,
            description="Convert text to uppercase",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "reverse",
            False,
            description="Reverse text",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "repeat",
            1,
            description="Number of times to repeat (1-10)",
            validator=Integer(default=1, min=1, max=10),
        ),
    )

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "echo_help": "Иcпoльзoвaниe: echo <тeкcт>",
            "no_text": "Укaжитe тeкcт пocлe кoмaнды",
            "result": "{prefix} {text}",
        },
        "en": {
            "echo_help": "Usage: echo <text>",
            "no_text": "Please specify text after the command",
            "result": "{prefix} {text}",
        },
    }

    @command("echo", doc_ru="<тeкcт> Пoвтopить тeкcт", doc_en="<text> Echo text")
    async def cmd_echo(self, event: Event) -> None:
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
