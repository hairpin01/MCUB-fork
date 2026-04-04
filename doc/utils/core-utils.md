# Utils Package API

MCUB provides a comprehensive utils package for common operations.

```python
from utils import (
    get_args,
    answer,
    escape_html,
    parse_html,
    restart_kernel
)
```

## Argument Parsing

### `get_args(event)`

Extract command arguments split by spaces, respecting quotes.

```python
args = get_args(event)
# Returns: List of string arguments
```

### `get_args_raw(event)`

Return raw argument string (everything after command).

```python
args = get_args_raw(event)
```

### `get_args_html(event)`

Return command arguments with preserved HTML formatting.

```python
html_args = get_args_html(event)
```

## Advanced Argument Parser

`ArgumentParser(text, prefix='.')` — Advanced command argument parser supporting flags, named arguments, and positional arguments.

```python
from utils import ArgumentParser

@kernel.register.command('deploy')
async def deploy_handler(event):
    parser = ArgumentParser(event.text, kernel.custom_prefix)

    service = parser.get(0, 'default')
    environment = parser.get_kwarg('env', 'production')
    timeout = parser.get_kwarg('timeout', 60)

    if parser.get_flag('verbose'):
        await event.edit("Verbose mode enabled")
```

## Message Sending

### `answer(event, text, **kwargs)`

Universal method to reply to message, edit inline message, or send file.

```python
await answer(event, "Response text")
await answer(event, "<b>Bold</b>", as_html=True)
await answer(event, "Check", file="photo.jpg")
```

### `answer_file(event, file, caption=None, **kwargs)`

Send file in reply to message.

## HTML Parsing

### `parse_html(html_text)`

Parse HTML markup to Telegram text and entities.

```python
from utils import parse_html

html = '<b>Bold</b> and <i>italic</i>'
text, entities = parse_html(html)
```

### Supported Tags

- `<b>`, `<strong>` — Bold
- `<i>`, `<em>` — Italic
- `<u>` — Underline
- `<s>`, `<del>` — Strikethrough
- `<code>` — Monospace
- `<pre>` — Preformatted block
- `<a href="url">` — Text URL
- `<blockquote>` — Quote
- `<tg-emoji emoji-id="123">` — Custom emoji

## Time Formatting

### `format_time(seconds, detailed=False)`

Format seconds into human-readable time string.

```python
await event.edit(format_time(3665))  # "1h 1m"
```

### `format_date(timestamp, fmt="%Y-%m-%d %H:%M")`

Format Unix timestamp to date string.

```python
await event.edit(format_date(ts))  # "2024-01-01 00:00"
```

## Chat Utilities

### `get_admins(event_or_client, chat_id=None)`

Get list of admins in a chat.

### `resolve_peer(client, identifier)`

Resolve username, phone, or link to user ID.

```python
user_id = await resolve_peer(kernel.client, "@username")
```

## Button Helpers

### `make_button(text, data=None, url=None, switch=None)`

Create a single Telethon Button.

```python
btn = make_button("Click me", data="click")
```

### `make_buttons(buttons, cols=2)`

Create multiple buttons from a flat list.

```python
buttons = [
    {"text": "Edit", "data": "edit_1"},
    {"text": "Delete", "data": "delete_1"},
]
rows = make_buttons(buttons, cols=2)
```

## Platform Detection

```python
from utils import get_platform, is_docker, is_wsl, is_termux

if is_docker():
    await event.edit("Running in Docker")
```
