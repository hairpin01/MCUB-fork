# Class-Style Modules v1.0.0

← [Index](../../API_DOC.md)

Class-style modules provide an object-oriented approach to module development. Instead of using function-based registration, you inherit from `ModuleBase` and define handlers as class methods.

## Quick Start

```python
from __future__ import annotations

from typing import Any
from telethon import events

from core.lib.loader.module_base import ModuleBase, command, bot_command, owner, event, method

class MyModule(ModuleBase):
    name = "MyModule"
    version = "1.0.0"
    author = "@yourname"
    description: dict[str, str] = {"ru": "Описание", "en": "Description"}
    dependencies: list[str] = ["requests"]

    @command("hello", doc_ru="Приветствие", doc_en="Say hello")
    async def cmd_hello(self, event: events.NewMessage.Event) -> None:
        await event.edit("Hello from class-style module!")

    @bot_command("start", doc_ru="Старт", doc_en="Start")
    async def bot_start(self, event: events.NewMessage.Event) -> None:
        await event.reply("Hello from bot!")

    @command("admin")
    @owner(only_admin=True)
    async def cmd_admin(self, event: events.NewMessage.Event) -> None:
        await event.reply("Admin access granted!")

    @event("chataction", incoming=True)
    async def on_chat_action(self, event: events.ChatAction.Event) -> None:
        if event.user_joined:
            await event.reply("Welcome!")

    @method
    async def setup(self) -> None:
        self.log.info("Module setup complete")

    async def on_load(self) -> None:
        self.log.info("Module loaded!")

    async def on_unload(self) -> None:
        self.log.info("Module unloading...")
```

## Module Metadata

Class attributes define module metadata:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"Unnamed"` | Display name (used as filename) |
| `version` | `str` | `"1.0.0"` | Semantic version |
| `author` | `str` | `"unknown"` | Author identifier |
| `description` | `dict \| str` | `{}` | Localized descriptions (`{"ru": "...", "en": "..."}`) or plain string |
| `dependencies` | `list` | `[]` | Pip packages to install |
| `banner_url` | `str` | `None` | Banner image URL |

> [!NOTE]
> The `name` attribute determines the module filename. If `name = "MyModule"`, the file will be renamed to `MyModule.py`.

> [!NOTE]
> For localized `description` dicts, loader/man pick text by current kernel language (`language` config), then fallback to `en`, then `ru`, then first non-empty value.

## Decorators

### `@command(pattern, *, alias=None, doc=None, doc_ru=None, doc_en=None)`

Register a userbot command. The decorated method receives `self` and the `event`.

```python
@command("ping", alias=["p"], doc_ru="Пинг", doc_en="Ping")
async def cmd_ping(self, event):
    await event.edit("Pong!")
```

**Parameters:**
- `pattern` (str): Command name without prefix
- `alias` (str | list): Alternative triggers
- `doc` (dict): Descriptions like `{"ru": "...", "en": "..."}`
- `doc_ru` (str): Russian description shorthand
- `doc_en` (str): English description shorthand

### `@bot_command(pattern, *, alias=None, doc=None, doc_ru=None, doc_en=None)`

Register a command via bot account (not userbot). The decorated method receives `self` and the `event`.

```python
@bot_command("start", doc_ru="Старт", doc_en="Start")
async def cmd_start(self, event):
    await event.reply("Hello from bot!")
```

> [!NOTE]
> Bot commands are registered on the bot account, while `@command` registers on the userbot.

**Parameters:** Same as `@command`

### `@owner(only_admin=False)`

Decorator for owner/admin permission check. Use after `@command` or `@bot_command`.

```python
@command("admin")
@owner(only_admin=True)
async def cmd_admin(self, event):
    await event.reply("Admin access granted!")
```

> [!IMPORTANT]
> If you override `on_load()` and need `@method` decorators to work, call `await super().on_load()`:
> ```python
> async def on_load(self):
>     await super().on_load()  # calls @method decorated functions
>     # your additional initialization
> ```

**Parameters:**
- `only_admin` (bool): If True, only bot admins can use this command (default: False)

### `@permission(**tags)`

Decorator for applying event filters to handlers, similar to `@watcher`. Can be stacked on commands, bot commands, watchers, and events.

```python
@command("secret")
@permission(only_pm=True, out=True)
async def cmd_secret(self, event):
    await event.reply("Secret!")

@command("group")
@permission(only_groups=True, contains="!stats")
async def cmd_stats(self, event):
    await event.reply("Stats!")
```

**Available tags:** Same as `@watcher`:
- Direction: `incoming`, `out`
- Chat type: `only_pm`, `no_pm`, `only_groups`, `no_groups`, `only_channels`, `no_channels`
- Content: `only_media`, `no_media`, `only_photos`, `no_videos`, `only_audios`, `only_docs`, `only_stickers`
- Other: `only_forwards`, `no_forwards`, `only_reply`, `no_reply`
- Text matching: `regex="pattern"`, `startswith="text"`, `endswith="text"`, `contains="text"`
- IDs: `from_id=<int>`, `chat_id=<int>`

**Use cases:**
- Filter commands to specific chat types
- Add regex/text matching conditions to commands
- Combine with `@owner` for both permission and chat type filtering

### `@error_handler(*, log_level="error", reraise=False, message=None)`

Decorator for automatic error handling in module methods. Catches exceptions and logs them with optional custom message.

```python
@error_handler(log_level="warning", message="Command {func} failed: {exc}")
async def cmd_risky(self, event):
    await self.process(event)

@error_handler(reraise=True)
async def cmd_critical(self, event):
    await self.critical_operation()
```

**Parameters:**
- `log_level` (str): Logging level — "error", "warning", "info" (default: "error")
- `reraise` (bool): If True, reraise exception after logging (default: False)
- `message` (str): Custom message template with `{exc}`, `{func}`, `{module}` placeholders

**Use cases:**
- Graceful error logging without breaking command flow
- Custom error messages for debugging
- Conditional reraise for critical operations

### `@callback(ttl=900)`

Decorator for inline callback handlers. Generates a uuid and registers the handler in `kernel.inline_callback_map`.

```python
@callback(ttl=300)
async def handle_click(self, event):
    await event.answer("Clicked!", alert=True)
```

**Parameters:**
- `ttl` (int): Time-to-live in seconds (default: 900)

Use with `self.callback_button()` to create buttons.

> [!NOTE]
> When the module is unloaded, all callback tokens are automatically cleaned up from `kernel.inline_callback_map`. This prevents memory leaks.

> [!NOTE]
> `data` is optional for callback handlers. If your handler has `data` parameter (or `**kwargs`), button `data` is passed there; otherwise it is ignored.

### `@inline(pattern)`

Register an inline query handler.

```python
@inline("myquery")
async def inline_handler(self, event):
    article = event.builder.article(
        title="Title",
        text="Content",
        parse_mode="html"
    )
    await event.answer([article])
```

### `@event(event_type, *args, bot_client=False, **kwargs)`

Register a custom Telethon event handler.

```python
@event("chataction", incoming=True)
async def handle_chat_action(self, event):
    await event.reply("Chat action detected!")

@event("newmessage", pattern=r"hello")
async def handle_hello(self, event):
    await event.reply("Hello!")
```

**Available event types:**
`newmessage`, `message`, `messageedited`, `edited`, `messagedeleted`, `deleted`, `messageread`, `read`, `userupdate`, `user`, `chataction`, `action`, `joinrequest`, `request`, `album`, `inlinequery`, `inline`, `callbackquery`, `callback`, `raw`, `custom`

### `@method()`

Register a method called automatically during module load.

```python
@method
async def setup(self):
    await self._connect_service()
    self.log.info("Setup complete")
```

The decorated method is called automatically as part of `on_load()` (via `super().on_load()`).

**When to use `@method` vs `on_load()`:**
- **`@method`**: Use for declarative setup that should be visible in code structure. Multiple `@method` decorators can be stacked and are called in definition order.
- **`on_load()`**: Use for imperative initialization, accessing `self` attributes set by other `@method` methods, or when you need the load state flag (`self._loaded`).

```python
# @method - declarative, called first
@method
async def setup_service(self):
    self._service = await Service.connect()

# on_load - imperative, called after all @method
async def on_load(self):
    await super().on_load()  # calls all @method decorated functions
    self._cache = {}
    self.log.info("Module ready")
```

### `@on_install()`

Register a one-time callback called only on first install (not on reload).

```python
@on_install
async def first_time_setup(self):
    await self.client.send_message("me", "Module installed!")
```

### `@uninstall()`

Register a cleanup callback called when the module is unloaded.

```python
@uninstall
async def cleanup(self):
    await self._close_connections()
```

The decorated method is called automatically during `on_unload()`.

### `@watcher(bot_client=False, **tags)`

Register a message watcher that filters events declaratively.

```python
@watcher(only_pm=True)
async def pm_watcher(self, event):
    await event.reply("Got your message!")

@watcher(only_groups=True, only_media=True)
async def group_media_watcher(self, event):
    await event.reply("Photo received!")

@watcher(regex=r"hello", incoming=True)
async def hello_watcher(self, event):
    await event.reply("Hi there!")
```

**Available tags:**
- Direction: `incoming`, `out`
- Chat type: `only_pm`, `no_pm`, `only_groups`, `no_groups`, `only_channels`, `no_channels`
- Content: `only_media`, `no_media`, `only_photos`, `only_videos`, `only_audios`, `only_docs`, `only_stickers`
- Other: `only_forwards`, `no_forwards`, `only_reply`, `no_reply`
- Text matching: `regex="pattern"`, `startswith="text"`, `endswith="text"`, `contains="text"`
- IDs: `from_id=<int>`, `chat_id=<int>`
- `bot_client` (bool): Register on bot_client instead of client

### `@loop(interval=60, autostart=True, wait_before=False)`

Register a background loop that runs periodically.

```python
@loop(interval=300, autostart=True)
async def heartbeat(self):
    await self.client.send_message("me", "Still alive!")

@loop(interval=60, autostart=False)
async def status_checker(self):
    # Manual start via button
    ...

# Loop is automatically bound to instance as attribute
@command("startcheck")
async def cmd_start(self, event):
    self.status_checker.start()  # Start the loop by name

@command("stopcheck")
async def cmd_stop(self, event):
    self.status_checker.stop()  # Stop the loop
```

**Parameters:**
- `interval` (int): Seconds between iterations (default: 60)
- `autostart` (bool): Start automatically on load (default: True)
- `wait_before` (bool): Sleep before first iteration (default: False)

**Loop Instance Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `loop.start()` | method | Start the loop |
| `loop.stop()` | method | Stop the loop gracefully |
| `loop.restart()` | method | Restart (stop + start) |
| `loop.is_running` | property | True if loop is active |
| `loop.interval` | int | Seconds between iterations |
| `loop.status` | bool | Loop running state |
| `loop.last_run` | float | Timestamp of last iteration |
| `loop.last_error` | Exception | Last exception raised |
| `loop.fail_count` | int | Consecutive failure count |

```python
@loop(interval=60, autostart=True)
async def worker(self):
    try:
        await self.do_work()
    except Exception as e:
        self.log.error(f"Work failed: {e}")

@command("status")
async def cmd_status(self, event):
    w = self.worker  # Access loop by method name
    await event.edit(
        f"Worker: running={w.is_running}, "
        f"last_run={w.last_run}, "
        f"failures={w.fail_count}"
    )

@command("restart_worker")
async def cmd_restart(self, event):
    self.worker.restart()
    await event.edit("Worker restarted!")
```

> [!TIP]
> Loops are bound to the instance automatically. Use `self.loop_name` to access loop control methods.

**Instance attribute:** `self._loops` - List of `InfiniteLoop` instances.

## Instance Attributes

The `__init__` method provides convenient access to kernel resources:

| Attribute | Description |
|-----------|-------------|
| `self.kernel` | Kernel instance |
| `self.client` | Userbot client |
| `self._register` | Register instance |
| `self.log` | Logger with module name prefix (`[ModuleName] message`) |
| `self.db` | Database manager |
| `self.cache` | Cache instance |
| `self._loaded` | Load state flag |
| `self._loops` | List of InfiniteLoop instances |

### Logger with Module Prefix

The `self.log` attribute automatically adds the module name as a prefix to all log messages.

```python
class MyModule(ModuleBase):
    name = "MyModule"

    async def on_load(self):
        # Output: [MyModule] Module initialized
        self.log.info("Module initialized")

    @command("test")
    async def cmd_test(self, event):
        # Output: [MyModule] Command executed
        self.log.debug("Command executed")
```

This helps identify which module produced log entries when troubleshooting.

### Runtime Helpers

Class-style modules provide convenient runtime helpers for common tasks.

#### Text and Arguments

```python
@command("demo")
async def cmd_demo(self, event):
    # Parse arguments from event text
    parser = self.args(event)
    # parser.command - command name (without prefix)
    # parser.args - list of positional arguments
    # parser.get(0, default) - get positional arg by index
    # parser.get_flag("flag") - check if flag exists
    # parser.get_kwarg("key") - get named argument
    # parser.kwargs - dict of all kwargs

    # Raw argument string
    raw = self.args_raw(event)

    # Arguments preserving HTML formatting
    html = self.args_html(event)
```

#### Prefix and Language

```python
@command("test")
async def cmd_test(self, event):
    # Get current command prefix
    prefix = self.get_prefix()  # e.g., "."

    # Get current language
    lang = self.get_lang()  # e.g., "ru" or "en"
```

#### Message Helpers

```python
@command("reply")
async def cmd_reply(self, event):
    # Unified answer - detects edit/reply/send automatically
    await self.answer(event, "Hello!")

    # Edit existing message (or send if not editable)
    await self.edit(event, "Updated!")

    # Reply to message
    await self.reply(event, "Replied!")

# All helpers support HTML and buttons
await self.answer(event, "<b>Bold</b>", as_html=True)
await self.edit(event, "Text", reply_markup=[[btn]], as_html=True)
```

#### Module Lookup

```python
@command("call")
async def cmd_call(self, event):
    # Lookup another loaded module by name (returns None if not found)
    notes = self.lookup_module("Notes")
    if notes:
        await notes.add_note(event, "text")

    # Require a module (raises LookupError if not found)
    notes = self.require_module("Notes")
    # Use the required module's methods
    await notes.add_note(event, "text")
```

**Lookup methods:**

| Method | Description |
|--------|-------------|
| `self.lookup_module(name)` | Find module by name, returns `None` if not found |
| `self.require_module(name)` | Find module or raise `LookupError` if not found |
| `self.get_prefix()` | Current command prefix |
| `self.get_lang()` | Current language |

**Helper methods:**

| Method | Description |
|--------|-------------|
| `self.args(event)` | Returns `ArgumentParser` for command arguments |
| `self.args_raw(event)` | Raw argument string after command |
| `self.args_html(event)` | Arguments with HTML preserved |
| `self.get_prefix()` | Current command prefix (e.g., `.`) |
| `self.get_lang()` | Current language code |
| `self.answer(event, text, **kwargs)` | Universal send/edit/reply |
| `self.edit(event, text, **kwargs)` | Edit or send message |
| `self.reply(event, text, **kwargs)` | Reply to message |
| `self.inline(chat_id, title, ...)` | Send inline form message |

### Database and Cache Usage

```python
async def on_load(self):
    # Database - persistent storage
    await self.db.db_set("mymodule", "counter", 0)
    await self.db.db_set("mymodule", "data", {"key": "value"})

    async def some_command(self, event):
    # Read from database
    count = await self.db.db_get("mymodule", "counter")
    if count is None:
        count = 0

    # Read from cache
    cached = self.cache.get("temp_data")
    if cached:
        await event.reply(f"Cached: {cached}")

    # Update database
    await self.db.db_set("mymodule", "counter", count + 1)
```

### Localization (strings)

Class-style modules support built-in localization via the `strings` class attribute.

```python
class MyModule(ModuleBase):
    name = "MyModule"
    strings = {
        "ru": {
            "greet": "Привет, {name}!",
            "bye": "Пока!",
            "counter": "Счётчик: {count}",
        },
        "en": {
            "greet": "Hello, {name}!",
            "bye": "Goodbye!",
            "counter": "Counter: {count}",
        },
    }

    @command("hello")
    async def cmd_hello(self, event):
        # Get string by key
        await event.edit(self.strings["greet"])

        # Get string with formatting
        await event.edit(self.strings("greet", name="World"))

        # Check if key exists
        if self.strings.has("greet"):
            ...
```

**Key features:**
- Locale is automatically detected from kernel config (`language`)
- Fallback to `ru` if key not found in current locale
- Formatting via `self.strings("key", var=value)`
- Attribute access via `self.strings["key"]`
- **Flat mode**: Simple strings auto-expand to all locales

**Flat Mode:**

For simple modules, you can use flat string dictionaries without nested locale:

```python
class MyModule(ModuleBase):
    name = "MyModule"
    # Flat mode - auto-expands to all locales
    strings = {
        "hello": "Hello {name}!",
        "bye": "Goodbye!",
    }

    @command("hi")
    async def cmd_hi(self, event):
        await self.edit(self.strings("hello", name="World"))
```

This automatically expands to:
```python
strings = {
    "ru": {"hello": "Hello {name}!", "bye": "Goodbye!"},
    "en": {"hello": "Hello {name}!", "bye": "Goodbye!"},
    # ... other locales
}
```

**Methods:**

| Method | Description |
|--------|-------------|
| `self.strings["key"]` | Get string by key |
| `self.strings("key", **kwargs)` | Get string with formatting |
| `self.strings.get("key")` | Get string or None |
| `self.strings.has("key")` | Check if key exists |
| `self.strings.locale` | Current locale code |

> [!TIP]
> See `doc/examples/greeting_module.py` for a complete example.

## Module Configuration

Class-style modules can define a `config` attribute using `ModuleConfig` from `core.lib.module_config`.

See [ModuleConfig API](../api/module-config.md) for detailed documentation.

```python
from __future__ import annotations

from typing import Any
from telethon import events

from core.lib.loader.module_config import ModuleConfig, ConfigValue, Integer, Boolean, String, Choice
from core.lib.loader.module_base import ModuleBase, command

class MyModule(ModuleBase):
    name = "MyModule"
    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable module",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "max_count",
            100,
            description="Maximum count",
            validator=Integer(default=100, min=1, max=1000),
        ),
        ConfigValue(
            "greeting",
            "Hello!",
            description="Greeting message",
            validator=String(default="Hello!"),
        ),
        ConfigValue(
            "mode",
            "default",
            description="Operation mode",
            validator=Choice(choices=["default", "fast", "safe"], default="default"),
        ),
    )

    @command("status")
    async def cmd_status(self, event: events.NewMessage.Event) -> None:
        if self.config["enabled"]:
            await event.edit(f"Max: {self.config['max_count']}, Greeting: {self.config['greeting']}")
        else:
            await event.edit("Module disabled")
```

**Key points:**
- Config is automatically loaded from database on module load
- Changes via `self.config["key"] = value` are saved automatically
- Kernel UI (`config` command) displays config schema and allows editing
- Use `ConfigValue` with validator for type-safe configuration |

## Lifecycle Methods

### `async def on_load()`

Called after the module is fully loaded and commands are registered. This method calls all `@method` decorated functions via `super().on_load()`.

```python
async def on_load(self) -> None:
    self.counter = 0
    self.log.info("Module initialized")
```

> [!IMPORTANT]
> If you override `on_load()`, call `await super().on_load()` to invoke `@method` decorated functions:
> ```python
> async def on_load(self) -> None:
>     await super().on_load()  # calls @method decorated functions
>     self._initialized = True
> ```

### `async def on_unload()`

Called before the module is unloaded. Use for cleanup.

```python
async def on_unload(self) -> None:
    self.log.info("Cleanup complete")
```

If you use `@uninstall`, call `await super().on_unload()` inside your override.

### `async def on_install()`

Called only on first installation (not on reload). Use for one-time setup.

```python
async def on_install(self) -> None:
    await self.db.db_set("module", "installed", True)
```

If you use `@on_install`, call `await super().on_install()` inside your override.

### `async def on_reload()`

Called after the module is reloaded via the `reload` command (but not on initial load).

```python
async def on_reload(self) -> None:
    self.log.info("Module reloaded, refreshing state...")
    # Re-initialize any runtime state
```

**When to use:**
- Reset transient state that doesn't persist across reloads
- Refresh cached data from database
- Log reload events for debugging

> [!NOTE]
> `on_reload` is only called during `.reload` command execution, not during initial module load. Use `on_load` for initial setup.

### `async def on_config_update(key, old_value, new_value)`

Called when kernel config is updated at runtime.

```python
async def on_config_update(self, key: str, old_value: Any, new_value: Any) -> None:
    self.log.info(f"Config {key} changed: {old_value} -> {new_value}")
    if key == "prefix":
        self._prefix = new_value
```

**Parameters:**
- `key`: Config key that changed
- `old_value`: Previous value
- `new_value`: New value

### `async def on_language_change(new_lang)`

Called when the bot language changes.

```python
async def on_language_change(self, new_lang: str) -> None:
    self.log.info(f"Language switched to: {new_lang}")
    # Refresh any cached strings
```

**Parameters:**
- `new_lang`: New language code (e.g., "ru", "en")

## Buttons

> [!IMPORTANT]
> In userbot mode, buttons require an **inline form** message. Use `self.kernel.inline_form()` to create a message with buttons.

### `self.Button` - Button Factory

Class-style modules provide a `Button` factory accessed via `self.Button`. This factory creates various button types with optional `icon` and `style` parameters.

```python
from telethon import events
from core.lib.loader.module_base import ModuleBase, command

class MyModule(ModuleBase):
    @command("menu")
    async def cmd_menu(self, event: events.NewMessage.Event) -> None:
        buttons: list[list[Any]] = [
            [self.Button.inline("Option A", self.handle_a, icon=5325942077639384815)],
            [self.Button.inline("Option B", self.handle_b, icon=5325942077639384816)],
            [self.Button.url("Website", "https://example.com", icon=5325942077639384817)],
            [self.Button.text("Text Only", icon=5325942077639384818)],
        ]
        await self.kernel.inline_form(event.chat_id, "Choose:", buttons=buttons)
```

### Button Types

All buttons support `icon` (int) and `style` parameters:

| Method | Description |
|--------|-------------|
| `Button.inline(text, callback, *, ttl=900, args=(), kwargs=None, data=None, pass_event=True, auto_answer=None, icon=None)` | Callback button |
| `Button.url(text, url, *, new_tab=False, icon=None)` | URL link button |
| `Button.text(text, *, resize=True, selective=False, icon=None)` | Text button |
| `Button.switch(text, query="", *, same_peer=True, icon=None)` | Inline query switch |
| `Button.copy(text="Copy", *, payload=None, icon=None)` | Copy to clipboard |
| `Button.request_phone(text="Share Phone", *, request_title=None, icon=None)` | Request phone |
| `Button.request_location(text="Share Location", *, request_title=None, live_period=None, icon=None)` | Request location |
| `Button.request_poll(text="Create Poll", *, request_title=None, quiz=False, icon=None)` | Request poll |
| `Button.game(text, *, game=None, icon=None)` | Game button |
| `Button.mention(text, user=None, *, icon=None)` | User mention |
| `Button.unknown(data, text="Button", *, icon=None)` | Custom/unknown type |

### Button Helpers

| Method | Description |
|--------|-------------|
| `Button.with_icon(btn, icon)` | Add icon to existing button |
| `Button.style(btn, style)` | Apply style to button |

### Callback Buttons with Data

```python
from typing import Any
from telethon import events
from core.lib.loader.module_base import ModuleBase, command, callback

class MyModule(ModuleBase):
    @command("menu")
    async def cmd_menu(self, event: events.NewMessage.Event) -> None:
        btn: Any = self.Button.inline(
            "Click Me",
            self.handle_click,
            args=(1, 2, 3),           # positional args
            kwargs={"key": "value"},  # keyword args
            data={"extra": "info"},   # stored data
            ttl=300,                   # token lifetime
            auto_answer="Done!"       # auto answer message
        )
        await event.edit("Press the button!", buttons=[[btn]])

    @callback(ttl=300)
    async def handle_click(self, event: events.CallbackQuery.Event, *args: Any, **kwargs: Any) -> None:
        # args = (1, 2, 3)
        # kwargs = {"key": "value"}
        await event.answer(f"Got: {args}, {kwargs}", alert=True)
```

Optional `data` handler variant:
```python
@callback
async def handle_click(self, event: events.CallbackQuery.Event, data: dict[str, Any] | None = None) -> None:
    # data is dict or None
    await event.answer(f"Data: {data}", alert=True)
```

### Icons

Icons use Telegram premade emoji IDs (integers). Example: `5325942077639384815`.

Example:
```python
self.Button.inline("Settings", self.handle_settings, icon=5325942077639384815)
self.Button.url("GitHub", "https://github.com", icon=5325942077639384816)
```

### Example with All Button Types

```python
@command("buttons")
async def cmd_buttons(self, event):
    await self.kernel.inline_form(
        event.chat_id,
        "Button Demo",
        buttons=[
            [self.Button.inline("Callback", self.handle_cb, icon=5325942077639384815)],
            [self.Button.url("URL", "https://example.com", icon=5325942077639384816)],
            [self.Button.text("Text", icon=5325942077639384817)],
            [self.Button.switch("Search", "test query", icon=5325942077639384818)],
            [self.Button.copy("Copy", icon=5325942077639384819)],
            [self.Button.request_phone("Share Phone", icon=5325942077639384820)],
            [self.Button.request_location("Share Location", icon=5325942077639384821)],
            [self.Button.request_poll("Create Poll", icon=5325942077639384822)],
        ]
    )
```

## Full Example

```python
from __future__ import annotations

from typing import Any
from telethon import events

from core.lib.loader.module_base import (
    ModuleBase, command, bot_command, owner, callback, watcher, loop, event, method
)

class CounterModule(ModuleBase):
    name = "Counter"
    version = "1.0.0"
    author = "@you"
    description: dict[str, str] = {"ru": "Счётчик", "en": "Counter"}

    @command("count", doc_ru="Показать счётчик", doc_en="Show counter")
    async def cmd_count(self, event: events.NewMessage.Event) -> None:
        await event.edit(f"Count: {self._counter}")

    @bot_command("count", doc_ru="Показать счётчик (бот)", doc_en="Show counter (бот)")
    async def bot_count(self, event: events.NewMessage.Event) -> None:
        await event.reply(f"Count: {self._counter}")

    @command("admin")
    @owner(only_admin=True)
    async def cmd_admin(self, event: events.NewMessage.Event) -> None:
        await event.reply("Admin panel coming soon!")

    @command("reset", doc_ru="Сбросить", doc_en="Reset counter")
    async def cmd_reset(self, event: events.NewMessage.Event) -> None:
        self._counter = 0
        await event.edit("Counter reset!")

    @command("menu")
    async def cmd_menu(self, event: events.NewMessage.Event) -> None:
        inc_btn: Any = self.Button.inline("+1", self.handle_inc, icon=5325942077639384820)
        dec_btn: Any = self.Button.inline("-1", self.handle_dec, icon=5325942077639384821)
        await self.kernel.inline_form(
            event.chat_id,
            f"Count: {self._counter}",
            buttons=[[inc_btn, dec_btn]]
        )

    @callback(ttl=300)
    async def handle_inc(self, event: events.CallbackQuery.Event) -> None:
        self._counter += 1
        await event.answer(f"+1! Now: {self._counter}")

    @watcher(only_pm=True, incoming=True)
    async def track_pm(self, event: events.NewMessage.Event) -> None:
        self._pm_count += 1
        self.log.debug(f"PM count: {self._pm_count}")

    @event("chataction")
    async def on_join(self, event: events.ChatAction.Event) -> None:
        if event.user_joined:
            await event.reply("Welcome!")

    @loop(interval=300, autostart=True)
    async def heartbeat(self) -> None:
        await self.client.send_message("me", "Heartbeat!")

    @method
    async def init_service(self) -> None:
        self.log.info("Service initialized")

    @on_install
    async def first_run(self) -> None:
        await self.client.send_message("me", "Counter module installed!")

    @uninstall
    async def cleanup(self) -> None:
        self.log.info("Service disconnected")

    async def on_load(self) -> None:
        self._counter = 0
        self._pm_count = 0
        self.log.info("Counter module loaded")

    async def on_unload(self) -> None:
        self.log.info(f"Final counts - msgs: {self._counter}, pms: {self._pm_count}")
```

## Comparison with Other Styles

| Feature | Function-based (`register(kernel)`) | Class-style (`ModuleBase`) |
|---------|------------------------------------|---------------------------|
| State | Global variables | Instance attributes (`self`) |
| Lifecycle | No built-in hooks | `on_load`, `on_unload`, `on_install` |
| Commands | `@kernel.register.command()` | `@command()` decorator |
| Watchers | `@kernel.register.watcher()` | `@watcher()` decorator |
| Loops | `@kernel.register.loop()` | `@loop()` decorator |
| Encapsulation | Manual | Automatic via class |
| Compatibility | Old modules | New modules |

## Best Practices

1. **Use meaningful names**: The `name` attribute determines the module filename
2. **Initialize in `on_load`**: Don't use `__init__` for initialization
3. **Clean up in `on_unload`**: Release resources, stop loops, log final state
4. **Use TTL for callbacks**: Short-lived tokens prevent memory leaks
5. **Store state in attributes**: `self.counter`, `self.data`, etc.
6. **Use watcher tags**: Filter events declaratively instead of with `if` statements
7. **Choose loop intervals wisely**: Too frequent loops strain the system
8. **Start non-autostart loops explicitly**: Call `loop.start()` from a command
