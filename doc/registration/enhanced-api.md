# Enhanced Registration API v1.0.2

MCUB introduces a `Register` class with decorator-based registration. All handlers registered through it are tracked per-module and removed automatically on unload — no zombie handlers after `um` or `reload`.

## Decorators

### `@kernel.register.method`

Register any function as a module setup method.

```python
@kernel.register.method
async def setup(kernel):
    kernel.logger.info("module initialised")
```

### `@kernel.register.command(pattern, alias=None, more=None)`

Register a userbot command.

```python
@kernel.register.command('ping', alias=['p'])
async def ping(event):
    await event.edit("Pong!")
```

### `@kernel.register.bot_command(pattern)`

Register a Telegram native `/command` (requires bot client).

```python
@kernel.register.bot_command('start')
async def start(event):
    await event.respond("Hello!")
```

### `@kernel.register.event(event_type, *args, bot_client=False, **kwargs)`

Register a Telethon event handler. Auto-removed on unload.

| Argument | Telethon class |
|---|---|
| `newmessage` / `message` | `events.NewMessage` |
| `messageedited` / `edited` | `events.MessageEdited` |
| `messagedeleted` / `deleted` | `events.MessageDeleted` |
| `userupdate` / `user` | `events.UserUpdate` |
| `inlinequery` / `inline` | `events.InlineQuery` |
| `callbackquery` / `callback` | `events.CallbackQuery` |
| `raw` / `custom` | `events.Raw` |

**Key parameter:**
- `bot_client` (bool): Register on `kernel.bot_client` instead of `kernel.client`

```python
@kernel.register.event('newmessage', pattern=r'hello')
async def hello(event):
    await event.reply("Hi!")

# CallbackQuery MUST use bot_client=True
@kernel.register.event('callbackquery', bot_client=True, pattern=b'menu_')
async def menu_cb(event):
    await event.answer("Menu clicked")
```

> [!IMPORTANT]
> `callbackquery` handlers **must** use `bot_client=True`. Callback queries from inline buttons are routed through the Telegram Bot API.
