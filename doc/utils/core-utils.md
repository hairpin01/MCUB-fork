# Utils Package API

← [Index](../../API_DOC.md)

MCUB provides a comprehensive utils package for common operations. Import utilities as needed:

```python
from utils import (
    get_args,
    answer,
    escape_html,
    parse_html,
    restart_kernel,
    get_platform,
    is_docker,
)
```

---

## Argument Parsing

### `get_args(event)`

Extract command arguments split by spaces, respecting quotes.

**How it works:**
1. Gets message text from event
2. Splits off the command prefix
3. Uses `shlex.split()` to parse arguments, handling quoted strings properly

**Parameters:**
- `event` — Message event or Message object

**Returns:** List of string arguments

```python
# .send hello "world test" 123
args = get_args(event)
# ['hello', 'world test', '123']
```

### `get_args_raw(event)`

Return raw argument string (everything after command).

```python
# .send hello world
args = get_args_raw(event)
# 'hello world'
```

### `get_args_html(event)`

Return command arguments with preserved HTML formatting.

**Use case:** Commands that need to accept formatted input like `<b>bold</b>`.

```python
html_args = get_args_html(event)
# Preserves HTML entities from the input
```

---

## Advanced Argument Parser

### `ArgumentParser(text, prefix='.')`

Powerful argument parser supporting flags, named arguments, and positional arguments.

**Features:**
- Long flags: `--flag value` or `--flag=value`
- Short flags: `-f value` or `-fvx` (combined)
- Boolean flags: `--verbose` (sets to True)
- Auto type detection: int, float, bool, list
- Quote handling for complex arguments

```python
from utils import ArgumentParser

@kernel.register.command('deploy')
async def deploy_handler(event):
    parser = ArgumentParser(event.text, kernel.custom_prefix)

    # Get positional arguments
    service = parser.get(0, 'default')

    # Get named arguments
    environment = parser.get_kwarg('env', 'production')
    timeout = parser.get_kwarg('timeout', 60)

    # Check flags
    if parser.get_flag('verbose'):
        await event.edit("Verbose mode")

    # Check if argument exists
    if parser.has('force'):
        await event.edit("Force mode!")
```

### ArgumentParser Methods

| Method | Description |
|--------|-------------|
| `parser.get(index, default)` | Get positional argument by index |
| `parser.get_kwarg(key, default)` | Get named argument value |
| `parser.get_flag(flag)` | Check if flag exists (returns bool) |
| `parser.has(key)` | Check if argument exists |
| `parser.join_args(start, end)` | Join positional arguments into string |
| `parser.require(*names)` | Validate required arguments, returns `(valid, missing)` |
| `parser.remaining(start)` | Get raw args from position |
| `len(parser)` | Get number of positional arguments |

### Parser Examples

**Command:** `.search --limit=10 --verbose "my query"`

```python
parser = ArgumentParser(event.text, '.')

parser.command     # 'search'
parser.args        # ['my query']
parser.kwargs     # {'limit': 10, 'verbose': True}
parser.flags       # {'verbose'}
parser.raw_args    # '--limit=10 --verbose "my query"'
```

**Short flags:** `.cmd -nvf value`

```python
parser.kwargs     # {'n': True, 'v': True, 'f': 'value'}
parser.flags      # {'n', 'v'}
```

**Lists:** `.cmd --items=one,two,three`

```python
parser.kwargs     # {'items': ['one', 'two', 'three']}
```

### Validation Helpers

```python
from utils import ArgumentValidator

validator = ArgumentValidator()

# Check required arguments
if not validator.validate_required(parser, 'name', 'email'):
    await event.edit("Missing required arguments")

# Check argument count
if not validator.validate_count(parser, min_count=1, max_count=3):
    await event.edit("Invalid argument count")

# Check types
if not validator.validate_types(parser, str, int, float):
    await event.edit("Invalid argument types")
```

---

## Message Helpers

### `answer(event, text, **kwargs)`

Universal method to reply/edit/send with auto-detection.

**Features:**
- Auto-detects inline vs regular message
- Supports HTML detection: `<b>`, `<i>`, etc.
- Supports emoji parsing: `<tg-emoji>`
- Auto-forwards kwargs to underlying method

```python
# Reply to regular message
await answer(event, "Hello!")

# With HTML (auto-detected)
await answer(event, "<b>Bold</b> and <i>italic</i>")

# Explicit HTML
await answer(event, "<b>Bold</b>", as_html=True)

# With file
await answer(event, "Check this", file="photo.jpg")

# With buttons
from telethon import Button
buttons = [[Button.inline("Click", b"data")]]
await answer(event, "Choose:", reply_markup=buttons)
```

### `answer_file(event, file, caption=None, **kwargs)`

Send file in reply to message.

```python
await answer_file(event, "document.pdf", caption="<b>Report</b>", as_html=True)
await answer_file(event, "photo.jpg", "Look at this!")
```

---

## HTML Parsing

### `parse_html(html_text)`

Parse HTML markup to Telegram text and entities.

**How it works:**
1. Parser scans HTML tags
2. Creates MessageEntity objects with offsets
3. Returns clean text + entity list for Telegram API

```python
from utils import parse_html

html = '<b>Bold</b> and <i>italic</i>'
text, entities = parse_html(html)
# text: 'Bold and italic'
# entities: [MessageEntityBold, MessageEntityItalic]

await event.client.send_message(chat_id, text, formatting_entities=entities)
```

### Supported HTML Tags

| Tag | Result | Example |
|-----|--------|---------|
| `<b>`, `<strong>` | Bold | `<b>text</b>` |
| `<i>`, `<em>` | Italic | `<i>text</i>` |
| `<u>` | Underline | `<u>text</u>` |
| `<s>`, `<del>` | Strikethrough | `<s>text</s>` |
| `<code>` | Monospace | `<code>text</code>` |
| `<pre>` | Code block | `<pre language="python">code</pre>` |
| `<a href="url">` | Link | `<a href="https://...">text</a>` |
| `<blockquote>` | Quote | `<blockquote>text</blockquote>` |
| `<blockquote expandable>` | Expandable quote | `<blockquote expandable>text</blockquote>` |
| `<tg-spoiler>` | Spoiler | `<tg-spoiler>text</tg-spoiler>` |
| `<tg-emoji emoji-id="123">` | Custom emoji | `<tg-emoji emoji-id="...">📌</tg-emoji>` |

### `telegram_to_html(text, entities)`

Convert Telegram text and entities back to HTML markup.

```python
from utils import telegram_to_html

message = await event.get_reply_message()
html = telegram_to_html(message.text, message.entities)
```

### HTML Message Helpers

```python
from utils import edit_with_html, reply_with_html, send_with_html

# Edit with HTML
await edit_with_html(kernel, event, "<b>Updated</b> content")

# Reply with HTML
await reply_with_html(kernel, event, "<code>Result:</code> 42")

# Send with HTML
await send_with_html(kernel, kernel.client, chat_id, "<i>Sent message</i>")

# Send file with HTML caption
await send_file_with_html(kernel, kernel.client, chat_id, "<b>Document</b>", "file.pdf")
```

---

## Text Formatting

### `escape_html(text)`

Escape HTML special characters (`&`, `<`, `>`).

**Use case:** Sanitizing user input before inserting into HTML.

```python
user_input = '<script>alert("xss")</script>'
safe_text = escape_html(user_input)
# '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
```

### `escape_quotes(text)`

Escape double quotes for HTML attributes.

```python
attr_value = escape_quotes(user_input)
html = f'<a href="{attr_value}">Link</a>'
```

---

## Time & Date Formatting

### `format_time(seconds, detailed=False)`

Format seconds into human-readable string.

```python
format_time(3665)           # "1h 1m"
format_time(90)             # "1m 30s"
format_time(7200)           # "2h"
format_time(3665, detailed=True)  # "1h 1m 5s"
format_time(90061, detailed=True) # "1d 1h 1m 1s"
```

### `format_date(timestamp, fmt="%Y-%m-%d %H:%M")`

Format Unix timestamp to date string.

```python
format_date(1704067200)                      # "2024-01-01 00:00"
format_date(1704067200, "%d.%m.%Y")         # "01.01.2024"
format_date(1704067200, "%B %d, %Y")        # "January 01, 2024"
```

### `format_relative_time(timestamp)`

Format as relative time ("5 minutes ago").

```python
format_relative_time(msg_time.timestamp())
# "2 hours ago"
# "just now"
# "3 days ago"
```

---

## Chat Utilities

### `get_chat_id(event)`

Return chat ID (without -100 prefix for channels).

```python
chat_id = get_chat_id(event)
# Works for: users, groups, channels
```

### `get_sender_info(event)`

Return formatted sender info: "Name (@username) [ID]"

```python
sender = await get_sender_info(event)
# "John Doe (@johndoe) [123456789]"
```

### `get_thread_id(event)`

Return thread (topic) ID if in forum.

```python
thread_id = await get_thread_id(event)
if thread_id:
    await event.client.send_message(
        chat_id,
        "Topic reply",
        reply_to=thread_id
    )
```

### `get_admins(event_or_client, chat_id=None)`

Get list of admins in chat.

```python
admins = await get_admins(event)
for admin in admins:
    print(f"{admin['name']} - Creator: {admin['is_creator']}")
```

### `resolve_peer(client, identifier)`

Resolve username/phone/ID to user ID.

```python
user_id = await resolve_peer(kernel.client, "@username")
user_id = await resolve_peer(kernel.client, "+79991234567")
user_id = await resolve_peer(kernel.client, 123456789)
```

### `relocate_entities(entities, offset, text=None)`

Shift message entities by offset and clamp to text length.

**Use case:** Extracting substring with preserved formatting.

```python
# Original message: "Command: Hello world"
# Extract "Hello world" with entities

full_text = "Command: Hello world"
command_end = 9
substring = full_text[command_end:]
adjusted = relocate_entities(event.message.entities, -command_end, substring)
# Entities now point to correct positions in substring
```

---

## Button Helpers

### `make_button(text, data=None, url=None, switch=None, same_peer=False)`

Create a single button.

```python
from utils import make_button

# Callback button
btn1 = make_button("Click me", data="click")

# URL button
btn2 = make_button("Open site", url="https://example.com")

# Switch inline query
btn3 = make_button("Search", switch="query", same_peer=True)
```

### `make_buttons(buttons, cols=2)`

Create buttons from dict list.

```python
from utils import make_buttons

# Flat list (auto-split into rows)
buttons = [
    {"text": "Edit", "data": "edit_1"},
    {"text": "Delete", "data": "delete_1"},
    {"text": "Link", "url": "https://..."},
]
rows = make_buttons(buttons, cols=2)
# Result: [[btn1, btn2], [btn3]]

# Pre-grouped rows
buttons = [
    [{"text": "A", "data": "a"}, {"text": "B", "data": "b"}],
    [{"text": "C", "data": "c"}],
]
rows = make_buttons(buttons)
# Result: [[btnA, btnB], [btnC]]
```

---

## Platform Detection

### `get_platform()`

Returns platform name: `termux`, `wsl`, `docker`, `vds`, `linux`, `macos`, `windows`, `unknown`.

### Platform Check Functions

```python
from utils import (
    get_platform,
    get_platform_name,
    get_platform_info,
    is_termux,
    is_wsl,
    is_docker,
    is_vds,
    is_mobile,
    is_desktop,
    is_virtualized,
)

# Quick check
if is_docker():
    await event.edit("Running in Docker!")

# Get detailed info
info = get_platform_info()
# {
#     "platform": "docker",
#     "system": "linux",
#     "machine": "x86_64",
#     "python_version": "3.11.0",
#     "hostname": "container-id",
#     ...
# }
```

### Platform Detection Methods

| Function | Description |
|----------|-------------|
| `is_termux()` | Running in Termux on Android |
| `is_wsl()` | Running in WSL (1 or 2) |
| `is_docker()` | Running in Docker container |
| `is_vds()` | Running on VDS/VPS server |
| `is_mobile()` | Mobile platform (Termux) |
| `is_desktop()` | Desktop platform |
| `is_virtualized()` | Any virtualization |

### `PlatformDetector` Class

```python
from utils import PlatformDetector

detector = PlatformDetector()
platform = detector.detect()           # 'docker'
friendly = detector.get_friendly_name() # '🐳 Docker Container'
details = detector.get_detailed_info() # Full info dict
```

---

## Kernel Control

### `restart_kernel(kernel, chat_id=None, message_id=None)`

Restart userbot with optional notification.

```python
from utils import restart_kernel

@kernel.register.command('restart')
async def restart_handler(event):
    msg = await event.edit("Restarting...")
    await restart_kernel(kernel, event.chat_id, msg.id)
```

---

## Availability Flags

Check if optional modules are available:

```python
from utils import (
    HTML_PARSER_AVAILABLE,
    EMOJI_PARSER_AVAILABLE,
    MESSAGE_HELPERS_AVAILABLE,
    ARG_PARSER_AVAILABLE,
    RAW_HTML_AVAILABLE,
)

if HTML_PARSER_AVAILABLE:
    from utils import parse_html
```

---

## Quick Reference

```python
# Core imports
from utils import get_args, get_args_raw, answer, answer_file

# HTML & formatting
from utils import escape_html, parse_html, telegram_to_html
from utils import edit_with_html, reply_with_html, send_with_html

# Time
from utils import format_time, format_date, format_relative_time

# Chat
from utils import get_chat_id, get_sender_info, get_thread_id
from utils import get_admins, resolve_peer

# Buttons
from utils import make_button, make_buttons

# Platform
from utils import get_platform, is_docker, is_termux

# Advanced parsing
from utils import ArgumentParser, parse_arguments, extract_command
```
