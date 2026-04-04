# Example Module

Complete example demonstrating various features:

```python
# requires: aiohttp
# author: MCUB Developer
# version: 1.0.0
# description: Complete example module with all features

import aiohttp
from utils import get_args, answer, ArgumentParser

def register(kernel):
    @kernel.register.command('hello', alias='hi')
    # Simple command
    async def hello_handler(event):
        try:
            args = get_args(event)
            name = args[0] if args else 'World'
            await answer(event, f"Hello, {name}!")
        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:hello", event=event)


    @kernel.register.command('fetch')
    # Command with API call
    async def fetch_handler(event):
        try:
            await event.edit("Fetching data...")

            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com", timeout=30) as resp:
                    data = await resp.json()

            await answer(event, f'<b>Result:</b>\n<code>{data}</code>', as_html=True)

        except aiohttp.ClientError as e:
            await kernel.logger.error(f"API request failed: {e}")
            await event.edit("Failed to fetch data")
        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:fetch", event=event)


    @kernel.register.command('save')
    # Command with database
    async def save_handler(event):
        try:
            args = get_args(event)
            if len(args) < 2:
                await event.edit("Usage: .save <key> <value>")
                return

            key, value = args[0], ' '.join(args[1:])
            await kernel.db_set(__name__, key, value)
            await event.edit(f"Saved: {key} = {value}")

        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:save", event=event)


    @kernel.register.command('deploy')
    # Command with advanced argument parsing
    async def deploy_handler(event):
        try:
            parser = ArgumentParser(event.text, kernel.custom_prefix)
            service = parser.get(0)
            if not service:
                await event.edit("Usage: .deploy <service> [--env=production]")
                return

            environment = parser.get_kwarg('env', 'production')
            verbose = parser.get_flag('verbose')

            await event.edit(f"Deploying {service} to {environment}...")
            await asyncio.sleep(2)
            await event.edit(f"Deployed {service} to {environment}")

        except Exception as e:
            await kernel.handle_error(e, source=f"{__name__}:deploy", event=event)


    async def example_inline_handler(event):
        builder = event.builder.article(
            title="Example Result",
            text=f"You searched for: {event.text}",
            description="Click to send"
        )
        await event.answer([builder])

    async def example_callback_handler(event):
        data = event.data.decode('utf-8')
        if data == 'btn1':
            await event.edit("Button 1 clicked")
        elif data == 'btn2':
            await event.edit("Button 2 clicked")

    kernel.register_inline_handler('example', example_inline_handler)
    kernel.register_callback_handler('example_', example_callback_handler)
```
