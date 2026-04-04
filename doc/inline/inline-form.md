# Inline Form

← [Index](../../API_DOC.md)

## `kernel.inline_form()`

Sends an inline message with formatted fields and buttons.

### Parameters

- `chat_id` (int): Target chat ID
- `title` (str): Form title
- `fields` (dict | list, optional): Data to display
- `buttons` (list, optional): Button configuration
- `auto_send` (bool, default=True): If `True`, sends immediately
- `ttl` (int, default=200): Cache TTL for form (seconds)

### Button Configuration

**Simplified format:**
```python
buttons = [
    {"text": "Edit", "type": "callback", "data": "profile_edit"},
    {"text": "Link", "type": "url", "url": "https://..."}
]
```

**Ready-made Telethon buttons:**
```python
from telethon import Button

buttons = [
    [Button.inline("Edit", b"edit_data")],
    [Button.url("Site", "https://...")]
]
```

### Usage Examples

```python
# Basic form
success, msg = await kernel.inline_form(event.chat_id, "User Profile")

# Form with fields
fields = {"Name": "John", "Status": "Active"}
success, msg = await kernel.inline_form(event.chat_id, "Profile", fields=fields)

# Form with buttons
buttons = [{"text": "Edit", "type": "callback", "data": "edit"}]
success, msg = await kernel.inline_form(event.chat_id, "Profile", buttons=buttons)
```

---

## `kernel._inline.gallery()`

Sends an inline gallery with navigation buttons `[◀] [🔄] [▶]`.

```python
rows = [
    {"photo": "https://example.com/photo1.jpg", "text": "Item 1"},
    {"photo": "https://example.com/photo2.jpg", "text": "Item 2"},
]
success, msg = await kernel._inline.gallery(event.chat_id, "Gallery", rows=rows)
```

---

## `kernel._inline.list()`

Sends an inline list with pagination `[◀] [🔄] [▶]`.

```python
items = ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]
success, msg = await kernel._inline.list(event.chat_id, "List", items=items)
```

---

## `kernel.inline_query_and_click()`

Performs an inline query through a bot and clicks on the selected result.

```python
success, message = await kernel.inline_query_and_click(
    chat_id=event.chat_id,
    query="gif cat",
    bot_username="gif"
)
```

---

## Complete Example with Callbacks

```python
@kernel.register.command('profile')
async def profile_handler(event):
    fields = {"name": "user", "status": "Active"}
    buttons = [{"text": "Play", "type": "callback", "data": "casino_play"}]

    success, msg = await kernel.inline_form(
        event.chat_id, "User Profile", fields=fields, buttons=buttons
    )
    if success:
        await event.delete()

async def casino_callback_handler(event):
    data = event.data.decode('utf-8')
    if data == 'casino_play':
        await event.edit("Starting game...")

kernel.register_callback_handler('casino_', casino_callback_handler)
```
