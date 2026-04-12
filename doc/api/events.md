# Event Handlers

← [Index](../../API_DOC.md)

> [!TIP]
> Prefer `@kernel.register.event(...)` over `@kernel.client.on(...)` in modules. The register version tracks the handler per-module and removes it automatically on unload.

## Message Events

```python
# Preferred — auto-removed on module unload
@kernel.register.event('newmessage', pattern=r'keyword')
async def keyword_handler(event):
    await event.reply("Keyword detected")

# Raw Telethon — use only outside of modules
@kernel.client.on(events.NewMessage(pattern='keyword'))
async def keyword_handler(event):
    await event.reply("Keyword detected")
```

## Callback Query Events

```python
async def button_handler(event):
    data = event.data.decode('utf-8')
    await event.answer(f"Button {data} clicked")
kernel.register_callback_handler('button_', button_handler)
```

## Inline Query Events

```python
async def search_handler(event):
    results = []
    builder = event.builder.article(
        title="Result",
        text="Result text"
    )
    results.append(builder)
    await event.answer(results)
kernel.register_inline_handler('search', search_handler)
```

## Event Types

| Argument | Telethon class |
|---|---|
| `newmessage` / `message` | `events.NewMessage` |
| `messageedited` / `edited` | `events.MessageEdited` |
| `messagedeleted` / `deleted` | `events.MessageDeleted` |
| `userupdate` / `user` | `events.UserUpdate` |
| `inlinequery` / `inline` | `events.InlineQuery` |
| `callbackquery` / `callback` | `events.CallbackQuery` |
| `raw` / `custom` | `events.Raw` |
