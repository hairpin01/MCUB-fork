# Buttons, Premium Emoji and `convert_emoji`

← [Telethon-MCUB Extensions](index.md)

Telethon-MCUB extends button helpers and HTML emoji handling for MCUB modules.

## Premium emoji on buttons

Button helper methods accept an `icon` argument with a Telegram custom emoji
document id.

```python
from telethon import Button

buttons = [
    [Button.inline("Buy", b"buy", icon=1234567890123456789)],
    [Button.url("Docs", "https://example.com", icon=1234567890123456789)],
]
```

Supported helpers include:

- `Button.inline(...)`
- `Button.switch_inline(...)`
- `Button.url(...)`
- `Button.auth(...)`
- `Button.text(...)`
- `Button.request_location(...)`
- `Button.request_phone(...)`
- `Button.request_poll(...)`
- `Button.buy(...)`
- `Button.game(...)`

## Dict-style inline buttons in MCUB

MCUB also accepts simplified dict buttons in inline forms:

```python
await self.subinline.form(
    m.chat_id,
    "Menu",
    buttons=[
        {"text": "Open", "type": "url", "url": "https://example.com"},
        {"text": "Run", "type": "callback", "data": "run"},
    ],
)
```

Callable callbacks should use MCUB's button factory / callback-token helpers.

## `client.convert_emoji`

Telethon-MCUB can convert Telegram premium emoji HTML tags into emoji links.

```python
client.convert_emoji = True

await client.send_message(
    chat,
    '<tg-emoji emoji-id="123456789">🔥</tg-emoji>',
    parse_mode="html",
)
```

When enabled, `<tg-emoji emoji-id="ID">content</tg-emoji>` is converted to:

```html
<a href="tg://emoji?id=ID">content</a>
```

This helps non-premium accounts avoid some premium emoji send errors. The toggle
is manual; Telethon-MCUB does not enable it automatically.
