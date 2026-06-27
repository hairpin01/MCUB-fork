# InlineManager API

← [Index](../../API_DOC.md)

The `InlineManager` is accessible via `kernel.inline_manager` and via `core/lib/loader/inline.py` (`InlineManager` class). It provides advanced inline form operations beyond the basic `inline_form`.

All methods that return a `message` return an **`InlineMessage`** object with methods:
- `await msg.edit(text, buttons=None, *, parse_mode="html")` - edit the message
- `await msg.answer(text="", alert=False)` - toast/alert popup
- `await msg.delete()` - delete the message
- `msg.data` - callback data (`bytes`)
- `msg.inline_message_id` - inline message ID
- `msg.chat_id`, `msg.sender_id`

---

## `await kernel.inline_manager.inline_form(chat_id, title, fields=None, buttons=None, auto_send=True, ttl=200, reply_to=None, **kwargs)`

Send an inline form message. See [Inline Form](inline-form.md) for full documentation.

---

## `await kernel.inline_manager.inline_query_and_click(chat_id, query, bot_username=None, result_index=0, buttons=None, silent=False, reply_to=None, **kwargs)`

Perform an inline bot query and automatically click (send) the specified result.

**Parameters:**
- `chat_id` (`int`) - Target chat ID
- `query` (`str`) - Inline query text (e.g. `@bot search term`)
- `bot_username` (`str`, optional) - Bot to query (defaults to config `inline_bot_username`)
- `result_index` (`int`, default `0`) - Which result to click (0-based)
- `buttons` (`list`, optional) - Extra buttons to attach to the sent message
- `silent` (`bool`) - Send silently
- `reply_to` (`int`, optional) - Reply-to message ID (supports topics)

**Returns:** `(success: bool, message: InlineMessage | None)`

The returned `InlineMessage` has: `edit(text, buttons)`, `answer(text, alert)`, `delete()`, `data`, `inline_message_id`, `chat_id`, `sender_id`.

```python
success, msg = await kernel.inline_manager.inline_query_and_click(
    event.chat_id,
    "search hello",
    result_index=0,
)
```

```python
success, msg = await kernel.inline_manager.inline_query_and_click(
    event.chat_id,
    "search hello",
    result_index=0,
)
```

---

## `await kernel.inline_manager.gallery(chat_id, title, rows, ttl=200, escape_html=False, **kwargs)`

Send an inline gallery with [\<] [\>] navigation buttons.

**Parameters:**
- `chat_id` (`int`) - Target chat
- `title` (`str`) - Gallery header text
- `rows` (`list`) - List of items. Each item is a dict with:
  - `photo` / `gif` / `video` (`str`): Media URL
  - `text` (`str`): Item description
  - `title` (`str`): Item title
- `ttl` (`int`, default `200`) - Cache TTL for navigation data
- `escape_html` (`bool`) - Escape HTML in titles

**Returns:** `(success, message: InlineMessage)` tuple.

The returned `InlineMessage` has: `edit(text, buttons)`, `answer(text, alert)`, `delete()`, `data`, `inline_message_id`, `chat_id`, `sender_id`.

```python
rows = [
    {"photo": "https://example.com/photo1.jpg", "title": "Photo 1", "text": "Description 1"},
    {"photo": "https://example.com/photo2.jpg", "title": "Photo 2", "text": "Description 2"},
]
success, msg = await kernel.inline_manager.gallery(
    event.chat_id,
    "My Gallery",
    rows,
)
```

Max 10 items. Adds navigation buttons automatically.

---

## `await kernel.inline_manager.list(chat_id, title, items, ttl=200, escape_html=False, **kwargs)`

Send an inline list with pagination [\<] [\>] buttons.

**Parameters:**
- `chat_id` (`int`) - Target chat
- `title` (`str`) - List header
- `items` (`list`) - List of strings to display (each item is one page)
- `ttl` (`int`, default `200`) - Cache TTL
- `escape_html` (`bool`) - Escape HTML in items

**Returns:** `(success, message: InlineMessage)` tuple.

```python
items = ["First page content", "Second page content", "Third page content"]
success, msg = await kernel.inline_manager.list(
    event.chat_id,
    "My List",
    items,
)
```

---

## `await kernel.inline_manager.text(chat_id, title, text, ttl=200, buttons=None, **kwargs)`

Send a paginated inline text message. Splits long text into pages with [\<] [\>] navigation.

**Parameters:**
- `chat_id` (`int`) - Target chat
- `title` (`str`) - Text header
- `text` (`str`) - Full text content (auto-split into pages)
- `ttl` (`int`, default `200`) - Cache TTL
- `buttons` (`list`, optional) - Custom buttons to append after navigation

**Returns:** `(success, message: InlineMessage)` tuple.

```python
long_text = "Very long text..." * 100
success, msg = await kernel.inline_manager.text(
    event.chat_id,
    "Long Document",
    long_text,
    buttons=[{"text": "Close", "type": "callback", "data": "close"}],
)
```

---

## `kernel.inline_manager.get_module_inline_commands(module_name) -> list`

Get all inline command handler names registered by a specific module.

```python
cmds = kernel.inline_manager.get_module_inline_commands("my_module")
# -> ["search", "help", ...]
```

---

## `kernel.inline_manager.register_inline_handler(pattern, handler)`

Register an inline query handler. See [Event Handlers](../api/events.md).

## `kernel.inline_manager.register_callback_handler(pattern, handler)`

Register a callback query handler. See [Inline Callbacks](callbacks.md).
