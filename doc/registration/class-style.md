# Class-Style Modules v1.0.0

← [Index](../../API_DOC.md)

Class-style modules provide an object-oriented approach to module development. Instead of using function-based registration, you inherit from `ModuleBase` and define handlers as class methods.

## Quick Start

```python
from core.lib.loader.module_base import ModuleBase, command, bot_command, owner, event, method

class MyModule(ModuleBase):
    name = "MyModule"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Описание", "en": "Description"}
    dependencies = ["requests"]

    @command("hello", doc_ru="Приветствие", doc_en="Say hello")
    async def cmd_hello(self, event):
        await event.edit("Hello from class-style module!")

    @bot_command("start", doc_ru="Старт", doc_en="Start")
    async def bot_start(self, event):
        await event.reply("Hello from bot!")

    @command("admin")
    @owner(only_admin=True)
    async def cmd_admin(self, event):
        await event.reply("Admin access granted!")

    @event("chataction", incoming=True)
    async def on_chat_action(self, event):
        if event.user_joined:
            await event.reply("Welcome!")

    @method
    async def setup(self):
        self.log.info("Module setup complete")

    async def on_load(self):
        self.log.info("Module loaded!")

    async def on_unload(self):
        self.log.info("Module unloading...")
```

## Module Metadata

Class attributes define module metadata:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"Unnamed"` | Display name (used as filename) |
| `version` | `str` | `"1.0.0"` | Semantic version |
| `author` | `str` | `"unknown"` | Author identifier |
| `description` | `dict` | `{}` | Localized descriptions `{"ru": "...", "en": "..."}` |
| `dependencies` | `list` | `[]` | Pip packages to install |
| `banner_url` | `str` | `None` | Banner image URL |

> [!NOTE]
> The `name` attribute determines the module filename. If `name = "MyModule"`, the file will be renamed to `MyModule.py`.

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

The decorated method is called automatically after `on_load()`.

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

@command("startcheck")
async def cmd_start(self, event):
    # Find loop by checking self._loops
    for loop in self._loops:
        if getattr(loop, 'func', None).__name__ == 'status_checker':
            loop.start()
```

**Parameters:**
- `interval` (int): Seconds between iterations (default: 60)
- `autostart` (bool): Start automatically on load (default: True)
- `wait_before` (bool): Sleep before first iteration (default: False)

**Instance attribute:** `self._loops` - List of `InfiniteLoop` instances.

```python
# Access loops by index or store reference
@loop(interval=300, autostart=False)
async def heartbeat(self):
    await self.client.send_message("me", "Heartbeat!")

@command("startbeat")
async def cmd_startbeat(self, event):
    self._loops[0].start()  # Start first loop

@command("stopbeat")
async def cmd_stopbeat(self, event):
    self._loops[0].stop()  # Stop first loop
```

## Instance Attributes

The `__init__` method provides convenient access to kernel resources:

| Attribute | Description |
|-----------|-------------|
| `self.kernel` | Kernel instance |
| `self.client` | Userbot client |
| `self._register` | Register instance |
| `self.log` | Logger (`kernel.logger`) |
| `self.db` | Database manager |
| `self.cache` | Cache instance |
| `self._loaded` | Load state flag |
| `self._loops` | List of InfiniteLoop instances |

### Database and Cache Usage

```python
async def on_load(self):
    # Database - persistent storage
    await self.db.set("mymodule", "counter", 0)
    await self.db.set("mymodule", "data", {"key": "value"})

    # Cache - fast in-memory storage
    self.cache.set("temp_data", "quick_value", ttl=60)

async def some_command(self, event):
    # Read from database
    count = await self.db.get("mymodule", "counter")
    if count is None:
        count = 0

    # Read from cache
    cached = self.cache.get("temp_data")
    if cached:
        await event.reply(f"Cached: {cached}")

    # Update database
    await self.db.set("mymodule", "counter", count + 1)
```

## Module Configuration

Class-style modules can define a `config` attribute using `ModuleConfig` from `core.lib.module_config`.

```python
from core.lib.loader.module_config import ModuleConfig, Integer, Boolean, String

class MyModule(ModuleBase):
    name = "MyModule"
    config = ModuleConfig(
        Integer("max_count", default=100, min=1, max=1000),
        Boolean("enabled", default=True),
        String("greeting", default="Hello!"),
    )

    @command("status")
    async def cmd_status(self, event):
        if self.config["enabled"]:
            await event.edit(f"Max: {self.config['max_count']}, Greeting: {self.config['greeting']}")
        else:
            await event.edit("Module disabled")
```

**Key points:**
- Config is automatically loaded from database on module load
- Changes via `self.config["key"] = value` are saved automatically
- Kernel UI (`config` command) displays config schema and allows editing
- Supported types: `Integer`, `Boolean`, `String`, `Float`, `Password`, etc.

**Config types available:**

| Type | Description |
|------|-------------|
| `Integer(key, default, min, max)` | Integer with validation |
| `Boolean(key, default)` | True/False toggle |
| `String(key, default)` | Text string |
| `Float(key, default)` | Floating point |
| `Password(key, default)` | Masked password |
| `Choice(key, choices, default)` | Dropdown selection |

## Lifecycle Methods

### `async def on_load()`

Called after the module is fully loaded and commands are registered. Use for initialization.

```python
async def on_load(self):
    self.counter = 0
    self.log.info("Module initialized")
```

### `async def on_unload()`

Called before the module is unloaded. Use for cleanup.

```python
async def on_unload(self):
    self.log.info("Cleanup complete")
```

### `async def on_install()`

Called only on first installation (not on reload). Use for one-time setup.

```python
async def on_install(self):
    await self.db.set("module", "installed", True)
```

## Buttons

> [!IMPORTANT]
> In userbot mode, buttons require an **inline form** message. Use `self.kernel.inline_form()` to create a message with buttons.

### `self.Button` - Button Factory

Class-style modules provide a `Button` factory accessed via `self.Button`. This factory creates various button types with optional `icon` and `style` parameters.

```python
@command("menu")
async def cmd_menu(self, event):
    buttons = [
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
| `Button.inline(text, callback, *, ttl=900, args=(), kwargs={}, data={}, pass_event=True, auto_answer=None, icon=None)` | Callback button |
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
@command("menu")
async def cmd_menu(self, event):
    btn = self.Button.inline(
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
async def handle_click(self, event, *args, **kwargs):
    # args = (1, 2, 3)
    # kwargs = {"key": "value"}
    await event.answer(f"Got: {args}, {kwargs}", alert=True)
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
from core.lib.loader.module_base import (
    ModuleBase, command, bot_command, owner, callback, watcher, loop, event, method
)

class CounterModule(ModuleBase):
    name = "Counter"
    version = "1.0.0"
    author = "@you"
    description = {"ru": "Счётчик", "en": "Counter"}

    @command("count", doc_ru="Показать счётчик", doc_en="Show counter")
    async def cmd_count(self, event):
        await event.edit(f"Count: {self._counter}")

    @bot_command("count", doc_ru="Показать счётчик (бот)", doc_en="Show counter (bot)")
    async def bot_count(self, event):
        await event.reply(f"Count: {self._counter}")

    @command("admin")
    @owner(only_admin=True)
    async def cmd_admin(self, event):
        await event.reply("Admin panel coming soon!")

    @command("reset", doc_ru="Сбросить", doc_en="Reset counter")
    async def cmd_reset(self, event):
        self._counter = 0
        await event.edit("Counter reset!")

    @command("menu")
    async def cmd_menu(self, event):
        inc_btn = self.Button.inline("+1", self.handle_inc, icon=5325942077639384820)
        dec_btn = self.Button.inline("-1", self.handle_dec, icon=5325942077639384821)
        await self.kernel.inline_form(
            event.chat_id,
            f"Count: {self._counter}",
            buttons=[[inc_btn, dec_btn]]
        )

    @callback(ttl=300)
    async def handle_inc(self, event):
        self._counter += 1
        await event.answer(f"+1! Now: {self._counter}")

    @callback(ttl=300)
    async def handle_dec(self, event):
        self._counter -= 1
        await event.answer(f"-1! Now: {self._counter}")

    @watcher(only_pm=True, incoming=True)
    async def track_pm(self, event):
        self._pm_count += 1
        self.log.debug(f"PM count: {self._pm_count}")

    @event("chataction")
    async def on_join(self, event):
        if event.user_joined:
            await event.reply("Welcome!")

    @loop(interval=300, autostart=True)
    async def heartbeat(self):
        await self.client.send_message("me", "Heartbeat!")

    @method
    async def init_service(self):
        await self._service.connect()
        self.log.info("Service connected")

    @on_install
    async def first_run(self):
        await self.client.send_message("me", "Counter module installed!")

    @uninstall
    async def cleanup(self):
        await self._service.disconnect()
        self.log.info("Service disconnected")

    async def on_load(self):
        self._counter = 0
        self._pm_count = 0
        self.log.info("Counter module loaded")

    async def on_unload(self):
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
