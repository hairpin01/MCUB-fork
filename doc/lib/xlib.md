# xlib - MCUB Utility Library

← [Index](../API_DOC.md)

xlib is a comprehensive utility library providing common formatting, keyboard generation, and text manipulation functions for MCUB modules.

## Installation

xlib is hosted in the MCUB repository. Import it in your class-style module:

```python
class MyModule(ModuleBase):
    xlib = None

    async def startup(self):
        # Import from MCUB repo
        self.xlib = await self.import_lib("https://raw.githubusercontent.com/hairpin01/repo-MCUB-fork/refs/heads/main/lib/xlib.py")
```

Or import from any URL:

```python
self.xlib = await self.import_lib("https://example.com/path/to/mylib.py")
```

---

## Formatting Functions

### `format_size(bytes, locale="en")`

Format bytes to human-readable size.

```python
self.xlib.format_size(1024)
# -> "1 KB"

self.xlib.format_size(1536)
# -> "1.50 KB"

self.xlib.format_size(1048576)
# -> "1 MB"

self.xlib.format_size(1048576, "ru")
# -> "1 МБ"
```

### `format_num(value, sep=" ")`

Format number with thousands separator.

```python
self.xlib.format_num(1234567)
# -> "1 234 567"

self.xlib.format_num(1234567.89)
# -> "1 234 567.89"
```

### `format_duration(seconds, short=False, locale="en")`

Format duration to human-readable string.

```python
self.xlib.format_duration(3661)
# -> "1 hour 1 minute 1 second"

self.xlib.format_duration(3661, short=True)
# -> "1h 1m 1s"

self.xlib.format_duration(3661, locale="ru")
# -> "1 час 1 минута 1 секунда"
```

### `format_date(timestamp, fmt="%d %b %Y", locale="en")`

Format timestamp to date string.

```python
self.xlib.format_date(1234567890)
# -> "14 Feb 2009"

self.xlib.format_date(1234567890, "%d %B %Y")
# -> "14 February 2009"

self.xlib.format_date(1234567890, "%d %b %Y", "ru")
# -> "14 фев 2009"
```

### `format_delta(timestamp, locale="en", short=False)`

Format time delta (relative time).

```python
self.xlib.format_delta(time.time() - 300)
# -> "5 minutes ago"

self.xlib.format_delta(time.time() - 300, "ru")
# -> "5 мин назад"
```

### `format_percent(value, total, decimals=1)`

Format percentage.

```python
self.xlib.format_percent(25, 100)
# -> "25.0%"

self.xlib.format_percent(1, 3, 0)
# -> "33%"
```

### `format_list(items, sep=", ", last=" and ")`

Format list with separator before last item.

```python
self.xlib.format_list(["a", "b", "c"])
# -> "a, b and c"
```

---

## Text Functions

### `truncate(text, max_len, suffix="...")`

Truncate text to maximum length.

```python
self.xlib.truncate("hello world", 8)
# -> "hello..."
```

### `plural(n, one, few, many)`

Pluralize word based on number (Russian style).

```python
self.xlib.plural(1, "яблоко", "яблока", "яблок")
# -> "яблоко"

self.xlib.plural(2, "яблоко", "яблока", "яблок")
# -> "яблока"

self.xlib.plural(5, "яблоко", "яблока", "яблок")
# -> "яблок"
```

### `num_word(n, one, few, many)`

Alias for `plural()`.

### `emoji_count(n, item=" item")`

Format number with emoji suffix.

```python
self.xlib.emoji_count(5, " apple")
# -> "5 apple"
```

---

## Button Functions

### `grid(buttons, cols=2)`

Arrange buttons in grid (returns telethon Button objects).

```python
buttons = [btn1, btn2, btn3, btn4]
self.xlib.grid(buttons, 2)
# -> [[btn1, btn2], [btn3, btn4]]
```

### `confirm(yes_text="Yes", no_text="No", yes_data=b"yes", no_data=b"no")`

Create confirm keyboard (telethon Button objects).

```python
self.xlib.confirm()
# -> [[Button.inline("Yes", b"yes"), Button.inline("No", b"no")]]
```

### `pagination(current, total, prefix="page")`

Create pagination keyboard (telethon Button objects).

```python
self.xlib.pagination(2, 5)
# -> [[Button.inline("page:1", b"page:1"), Button.inline("page:3", b"page:3")]]
```

### `url_button(text, url, new_tab=False)`

Create URL button (telethon Button.url).

```python
self.xlib.url_button("Google", "https://google.com")
# -> Button.url

self.xlib.url_button("Open", "https://example.com", new_tab=True)
# -> Button.url with new_tab=True
```

### `callback_button(text, data)`

Create callback button (telethon Button.inline).

```python
self.xlib.callback_button("Click", b"action:click")
# -> Button.inline
```

---

## Markdown Functions

### `bold(text)`

Format text as bold.

```python
self.xlib.bold("hello")
# -> "<b>hello</b>"
```

### `italic(text)`

Format text as italic.

```python
self.xlib.italic("hello")
# -> "<i>hello</i>"
```

### `code(text, lang=None)`

Format text as code.

```python
self.xlib.code("print('hello')")
# -> "<code>print('hello')</code>"

self.xlib.code("print('hello')", "python")
# -> '<code language="python">print(\'hello\')</code>'
```

### `link(url, text)`

Create HTML link.

```python
self.xlib.link("https://google.com", "Google")
# -> '<a href="https://google.com">Google</a>'
```

### `button(text, data=None, url=None)`

Create button (telethon Button - auto-detects callback or URL).

```python
self.xlib.button("Click", data=b"action:click")
# -> Button.inline

self.xlib.button("Google", url="https://google.com")
# -> Button.url
```

### `pre(text)`

Format text as preformatted.

```python
self.xlib.pre("code here")
# -> "<pre>code here</pre>"
```

---

## Full Example

```python
from core.lib.loader.module_base import ModuleBase, command

class MyModule(ModuleBase):
    name = "MyModule"
    xlib = None

    async def startup(self):
        self.xlib = await self.import_lib(
            "https://raw.githubusercontent.com/hairpin01/MCUB-fork/main/xlib.py"
        )

    @command("test")
    async def cmd_test(self, event):
        size = self.xlib.format_size(1024 * 1024)
        await event.respond(
            f"Size: {size}\n"
            f"Plural: {self.xlib.plural(5, 'файл', 'файла', 'файлов')}",
            buttons=self.xlib.grid([
                self.xlib.button("Click", data="test:click"),
                self.xlib.button("Link", url="https://example.com"),
            ], 2)
        )
```

---

## Locale Support

Most functions support locale parameter:

- `"en"` - English (default)
- `"ru"` - Russian

```python
self.xlib.format_size(1024, "ru")  # "1 КБ"
self.xlib.format_duration(3600, locale="ru")  # "1 час"
self.xlib.format_delta(time.time() - 300, "ru")  # "5 мин назад"
```

---

## Menu Class

Hierarchical inline menu with callback binding.

### `Menu(module, title="", cols=2, show_back=True)`

Create menu instance.

```python
menu = Menu(self, "Main Menu")
```

### `menu.add(label, callback)`

Add action item.

```python
menu.add("Settings", self.show_settings)
menu.add("Profile", self.show_profile)  # callback = callable
```

### `menu.add_submenu(label, submenu)`

Add submenu.

```python
profile_menu = Menu(self, "Profile")
menu.add_submenu("Profile", profile_menu)
```

### `menu.add_url(label, url)`

Add URL button.

```python
menu.add_url("Help", "https://example.com")
```

### `await menu.show(event, edit=True)`

Show menu. Use `edit=True` for `event.edit()`, `False` for `event.reply()`.

```python
await menu.show(event)
```

### Callback Handling

In your callback handler, call `menu.handle_callback()`:

```python
@kernel.register.event("callbackquery")
async def on_callback(event):
    data = event.data.decode()
    if data.startswith("menu:"):
        await self.main_menu.handle_callback(event, data)
```

---

## Paginator Class

Customizable pagination.

### `Paginator(module, items, per_page=10)`

Create paginator.

```python
paginator = Paginator(self, items, per_page=10)
```

### `paginator.format_item(item, index)` (override)

Custom item format.

```python
paginator.format_item = lambda item, i: f"{i+1}. {item['name']}"
```

### `paginator.get_buttons(page, total)` (override)

Custom buttons.

```python
paginator.get_buttons = lambda p, page: [
    [Button.inline("◀", f"prev:{page-1}"), Button.inline("▶", f"next:{page+1}")]
]
]
```

### `await paginator.show(event, edit=True)`

Show current page.

```python
await paginator.show(event)
```

---

## ask Function

Wait for user answer AFTER you've sent the question.

Does NOT send message - you must send the question manually first.

### `await ask(module, event, timeout=60, cancel_word="cancel")`

Returns:
    asyncio.Future - await this to get the event, or None if cancel/timeout.

```python
# 1. Send question manually
await event.edit("Your name?")

# 2. Wait for answer
msg_event = await ask(self, event)

if msg_event:
    # msg_event is the message event from user
    await event.respond(f"Hello, {msg_event.raw_text}!")
# If user typed "cancel" or timeout -> msg_event is None
```
