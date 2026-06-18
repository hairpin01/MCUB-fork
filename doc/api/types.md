# Type Protocols

← [Index](../../API_DOC.md)

MCUB provides structural type protocols (`typing.Protocol`) for the core objects that modules interact with - `Kernel`, `Event`, `Message`, `Client`, and `Register`.

Using these types instead of `Any` gives you **IDE autocompletion**, **static type checking** (mypy / pyright), and **self-documenting code**.

```python
from core.lib.types import Kernel, Event

@kernel.register.command("hello")
async def hello_handler(event: Event, kernel: Kernel) -> None:
    await event.edit("Hello!")
```

---

## Where to Import From

```python
from core.lib.types import Kernel, Event, Client, Message, Register
```

All protocols are exported from the single `core.lib.types` package.

---

## Protocols

### `Kernel`

The kernel is the central orchestrator. Modules receive a `ModuleKernelProxy` that safely delegates to the real kernel while blocking dangerous attributes.

```python
from core.lib.types import Kernel

async def setup(k: Kernel) -> None:
    k.logger.info("kernel v%s", k.VERSION)
    cfg = await k.get_module_config("my_mod")
```

**Key members:**

| Member | Type | Description |
|--------|------|-------------|
| `VERSION` | `str` | Kernel version string |
| `CORE_NAME` | `str` | Kernel variant name (set by `__main__`) |
| `logger` | `logging.Logger` | Logger instance |
| `custom_prefix` | `str` | Command prefix (e.g. `"."`) |
| `client` | `Client` | Telegram client (safe proxy) |
| `bot_client` | `Client \| None` | Bot client (if available) |
| `config` | `dict` | Kernel configuration |
| `cache` | `Any` | TTL cache |
| `inline_manager` | `Any` | Inline manager instance |
| `register` | `Register` | Command/watcher/event registration |
| `module_name` | `str` | Current module name |
| `loaded_modules_view` | `MappingProxyType` | Read-only loaded modules |
| `system_modules_view` | `MappingProxyType` | Read-only system modules |

**Methods:**

| Method | Signature |
|--------|-----------|
| `shutdown` | `async () -> None` |
| `restart` | `async (chat_id=None, message_id=None) -> None` |
| `process_command` | `async (event, depth=0) -> bool` |
| `process_bot_command` | `async (event) -> bool` |
| `should_process_command_event` | `(event) -> bool` |
| `get_module_config` | `async (name, default=None) -> Any` |
| `save_module_config` | `async (name, data) -> bool` |
| `get_prefix_for_sender` | `(sender_id) -> str` |
| `store_inline_callback` | `(token, data) -> None` |
| `remove_inline_callback_tokens` | `(tokens) -> None` |
| `allow_inline_callback_user` | `(user_id, token, ttl) -> None` |
| `is_admin` | `(user_id) -> bool` |
| `get_thread_id` | `async (event) -> int \| None` |
| `handle_error` | `async (error, source, message, event) -> None` |
| `log_module` | `async (message) -> None` |
| `lookup_module` | `(name, all_loaded=False) -> Any` |
| `get_loaded_module` | `(name, all_loaded=False) -> Any` |
| `raw_text` | `(source) -> str` |
| `format_with_html` | `(text, entities) -> str` |
| `pipe_interpolate` | `(text, pipe_input="") -> str` |
| `async_pipe_interpolate` | `async (text, pipe_input, event, active_prefix) -> str` |
| `send_to_topic` | `async (entity, topic, message, ...) -> Any` |
| `send_file_to_topic` | `async (entity, topic, file, ...) -> Any` |
| `is_bot_available` | `() -> bool` |
| `send_with_emoji` | `async (chat_id, text, ...) -> Any` |

---

### `Event`

Describes the Telegram event as seen by command handlers, watchers, and event handlers.

```python
from core.lib.types import Event

@kernel.register.command("ping")
async def ping(event: Event) -> None:
    await event.edit("Pong!")
    chat_id = event.chat_id
    sender_id = event.sender_id
```

**Key attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Message text |
| `raw_text` | `str` | Text without command prefix |
| `chat_id` | `int` | Chat ID |
| `sender_id` | `int` | Sender user ID |
| `message_id` | `int` | Message ID |
| `id` | `int` | Alias for `message_id` |
| `client` | `Client` | Safe client proxy |
| `message` | `Message` | The underlying message |
| `is_private` | `bool` | True if private chat |
| `is_group` | `bool` | True if group chat |
| `is_channel` | `bool` | True if channel |
| `is_admin` | `bool` | True if sender is admin |
| `pattern_match` | `Any` | Regex match from `@command` |

**Methods:**

| Method | Signature |
|--------|-----------|
| `edit` | `async (text, ...) -> Any` |
| `reply` | `async (text, ...) -> Any` |
| `delete` | `async () -> Any` |
| `respond` | `async (text, ...) -> Any` |
| `answer` | `async (text=None, ...) -> Any` |
| `get_reply_message` | `async () -> Message \| None` |
| `get_chat` | `async () -> Any` |
| `get_sender` | `async () -> Any` |
| `get_thread_id` | `async () -> int \| None` |
| `format_with_html` | `(text, ...) -> str` |

---

### `Message`

Describes a Telegram message object.

```python
from core.lib.types import Message

async def process(msg: Message) -> None:
    print(msg.text, msg.sender_id)
```

| Member | Type | Description |
|--------|------|-------------|
| `id` | `int` | Message ID |
| `text` | `str` | Message text |
| `raw_text` | `str` | Raw text |
| `sender_id` | `int` | Sender user ID |
| `chat_id` | `int` | Chat ID |
| `reply_to_msg_id` | `int \| None` | Replied message ID |
| `media` | `Any` | Attached media |

---

### `Client`

Safe subset of `TelegramClient`. Dangerous methods (`disconnect`, `log_out`, `on`, `add_event_handler`, …) are blocked by `ClientProxy`.

```python
from core.lib.types import Client

async def send(c: Client) -> None:
    msg = await c.send_message("me", "Hello")
    await c.edit_message("me", msg.id, "Updated")
```

**Key methods:**

| Method | Description |
|--------|-------------|
| `send_message(entity, text, ...)` | Send a message |
| `edit_message(entity, msg, text, ...)` | Edit a message |
| `delete_messages(entity, ids)` | Delete messages |
| `forward_messages(entity, msgs)` | Forward messages |
| `send_file(entity, file, ...)` | Send a file |
| `send_photo(entity, file, ...)` | Send a photo |
| `send_video(entity, file, ...)` | Send a video |
| `send_audio(entity, file, ...)` | Send audio |
| `send_document(entity, file, ...)` | Send document |
| `send_voice(entity, file, ...)` | Send voice |
| `send_sticker(entity, file, ...)` | Send sticker |
| `get_entity(...)` | Get entity by ID/username |
| `get_me()` | Get current user |
| `get_messages(entity, ...)` | Get messages |
| `get_dialogs(...)` | Get dialogs |

---

### `Register`

Registration API - used to declare commands, watchers, loops, events, lifecycle hooks, and inline handlers.

```python
from core.lib.types import Register

def setup(r: Register) -> None:
    @r.command("ping")
    async def handler(event): ...
```

**Methods:**

| Method | Signature |
|--------|-----------|
| `method` | `(func) -> Callable` |
| `event` | `(type, *args, bot_client=False, module=None, **kwargs) -> Callable` |
| `command` | `(pattern, **kwargs) -> Callable` |
| `bot_command` | `(pattern, **kwargs) -> Callable` |
| `watcher` | `(func=None, bot_client=False, module=None, **tags) -> Callable` |
| `loop` | `(interval=60, autostart=True, wait_before=False, module=None) -> Callable` |
| `on_load` | `(func=None) -> Callable` |
| `on_install` | `(func=None) -> Callable` |
| `uninstall` | `(func=None) -> Callable` |
| `inline_temp` | `(func, ttl=300, ...) -> str` |
| `invoke` | `async (cmd, args, chat_id, ...) -> Any` |
| `get_commands` | `() -> dict` |
| `get_command` | `(cmd) -> dict` |
| `get_bot_commands` | `() -> dict` |
| `get_watchers` | `() -> list` |
| `get_events` | `() -> list` |
| `get_loops` | `() -> list` |
| `unregister_command` | `(cmd) -> bool` |
| `unregister_bot_command` | `(cmd) -> bool` |

---

## Type Checking

Run static analysis on your module with:

```bash
# mypy
mypy --strict my_module.py

# pyright (VSCode / command line)
pyright my_module.py
```

Protocols use structural subtyping - your code doesn't need to import or inherit from the protocol classes at runtime. The annotations are only used by type checkers and IDEs.

```python
# Runtime: no overhead
# mypy/pyright: knows event has .edit(), .reply(), .text, etc.
async def handler(self, event: Event) -> None:
    await event.edit("OK")
```
