# Enhanced Registration API v1.0.2

← [Index](../../API_DOC.md)

MCUB introduces a `Register` class with decorator-based registration. All handlers registered through it are tracked per-module and removed automatically on unload - no zombie handlers after `um` or `reload`.

## Decorators

### `@kernel.register.method`

Register any function as a module setup method.

```python
@kernel.register.method
async def setup(kernel):
    kernel.logger.info("module initialised")
```

### Command decorators

`@kernel.register.command(...)` registers userbot commands and
`@kernel.register.bot_command(...)` registers native Telegram `/commands` on the
bot account.

See [Command Registration](../api/commands.md) for the canonical command syntax,
aliases, documentation metadata, owner-only commands and conflict rules.

### `kernel.register.inline_temp(func, ttl=300, article=None, data=None, allow_user=None, allow_ttl=100)`

Register a temporary inline command handler and return an 8-character form id. This is a normal method, not a decorator: pass the handler callable as the first argument.

```python
async def handle_search(event, args, data=None):
    kernel.logger.info(f'search: {args}')

form_id = kernel.register.inline_temp(
    handle_search,
    ttl=600,
    article=lambda e: e.builder.article("Search", text="Search..."),
    data={"source": "module"},
)
```

When the user enters `@bot <form_id> query` and sends the article, MCUB calls the handler as `(event)`, `(event, args)`, or `(event, args, data)` depending on its signature.

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

### `@kernel.register.watcher(bot_client=False, **tags)`

Register a passive message watcher. Fires on every new message and is cleaned up automatically on module unload.

See [Watchers](watchers.md) for the canonical watcher tags and examples.
