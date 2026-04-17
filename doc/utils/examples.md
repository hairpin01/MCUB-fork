# Example Module (Function-Style)

← [Index](../../API_DOC.md)

Complete example demonstrating function-style module with typing:

```python
from typing import Any
from telethon import events
from utils import Strings, get_args, answer, reply_with_html, ArgumentParser

def register(kernel: Any) -> None:
    strings = Strings(
        kernel,
        {
            "ru": {
                "hello": "Привет, {name}!",
                "no_args": "Укажите аргумент",
                "saved": "Сохранено: {key} = {value}",
            },
            "en": {
                "hello": "Hello, {name}!",
                "no_args": "Please provide an argument",
                "saved": "Saved: {key} = {value}",
            },
        },
    )

    @kernel.register.command("hello", doc_ru="<имя> Приветствие", doc_en="<name> Greeting")
    async def hello_handler(event: events.NewMessage.Event) -> None:
        try:
            args: list[str] = get_args(event)
            if not args:
                await event.edit(strings["no_args"])
                return

            name: str = args[0]
            await answer(event, strings("hello", name=name))

        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:hello", event=event)


    @kernel.register.command("echo", doc_ru="<текст> Повторить", doc_en="<text> Echo")
    async def echo_handler(event: events.NewMessage.Event) -> None:
        try:
            args: list[str] = get_args(event)
            text: str = " ".join(args)
            await reply_with_html(kernel, event, f"<b>{text}</b>")

        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:echo", event=event)


    @kernel.register.command("save", doc_ru="<ключ> <значение> Сохранить", doc_en="<key> <value> Save")
    async def save_handler(event: events.NewMessage.Event) -> None:
        try:
            args: list[str] = get_args(event)
            if len(args) < 2:
                await event.edit("Usage: .save <key> <value>")
                return

            key: str = args[0]
            value: str = " ".join(args[1:])
            await kernel.db_manager.db_set(__name__, key, value)
            await answer(event, strings("saved", key=key, value=value))

        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:save", event=event)


    @kernel.register.command("deploy", doc_ru="<сервис> Деплой", doc_en="<service> Deploy")
    async def deploy_handler(event: events.NewMessage.Event) -> None:
        try:
            parser: ArgumentParser = ArgumentParser(event.text, kernel.custom_prefix)
            service: str | None = parser.get(0)

            if not service:
                await event.edit("Usage: .deploy <service> [--env=production]")
                return

            env: str = parser.get_kwarg("env", "production")
            await event.edit(f"Deploying {service} to {env}...")

        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:deploy", event=event)


    @kernel.register.loop(interval=300, autostart=True)
    async def heartbeat_loop(kernel: Any) -> None:
        """Autostarting background loop."""
        kernel.logger.debug("Heartbeat")


    async def inline_handler(event: events.InlineQuery.Event) -> None:
        builder = event.builder.article(
            title="Example",
            text=f"Query: {event.text}",
        )
        await event.answer([builder])

    kernel.register_inline_handler("example", inline_handler)
```
