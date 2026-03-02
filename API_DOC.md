# `MCUB` Module API Documentation `1.0.3.9`

__Table of Contents__

> 1. [Introduction](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#introduction)
> 2. [Module Structure](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#module-structure)
> 3. [Kernel API Reference](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#kernel-api-reference)
> 4. [Database API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#database-api)
> 5. [Key-Value Database API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#key-value-database-api)
> 6. [Module Config API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#module-config-api)
> 7. [Cache API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#cache-api)
> 8. [Task Scheduler API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#task-scheduler-api)
> 9. [Middleware API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#middleware-api)
> 10. [Command Registration](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#command-registration)
> 11. [Event Handlers](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#event-handlers)
> 12. [Configuration Management](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#configuration-management)
> 13. [Error Handling](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#error-handling)
> 14. [Utils Package API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#utils-package-api)
> 15. [Best Practices](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#best-practices)
> 16. [Example Module](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#example-module)
> 17. [Premium Emoji Guide](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#premium-emoji-guide)
> 18. [Inline Query Automation Methods](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#inline-query-automation-methods-and-inline-form)
> 19. [Callback Permission Management](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#callback-permission-management)
> 20. [Enhanced Registration API v1.0.2](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#enhanced-registration-api-v102)
> 21. [Watchers](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#watchers)
> 22. [InfiniteLoop](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#infiniteloop)
> 23. [Lifecycle Callbacks](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#lifecycle-callbacks)
> 24. [Custom Core MCUB](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#custom-core-mcub)

# Introduction

* MCUB (`Mitrich UserBot`) is a modular Telegram **userbot** framework built on Telethon. This documentation describes the extended API for creating modules.

## Module Structure

### Basic Structure:

```python
# requires: library1, library2
# author: Author Name
# version: 1.0.0
# description: Module description here
# scop: kernel (min|max|None) v(version|[__lastest__])

def register(kernel):
    # Module code here
```

## Kernel API Reference
Core Properties

`kernel.client`
---
The Telethon client instance for Telegram API operations.

**Usage:**

```python
await kernel.client.send_message('username', 'Hello')
```

`kernel.custom_prefix`
---
Command prefix (keys `command_prefix` kernel config) (default: '`.`').

`kernel.config`
---
Persistent configuration storage.

Usage:
```python
kernel.config['key'] = 'value'
kernel.save_config()
```

`kernel.logger`
---
Structured logging instance.

**Usage:**

```python
# outputs to terminal
kernel.logger.debug("Debug message")
kernel.logger.info("Info message")
kernel.logger.warning("Warning message")
kernel.logger.error("Error message") 
```

Logging Methods for __bot_client:__

`kernel.log_debug(message)`
---
Log debug message.

`kernel.log_info(message)`
---
Log info message.

`kernel.log_warning(message)`
---
Log warning message.

`kernel.log_error(message)`
---
Log error message.

**Usage:**

```python
# outputs to the chat log in telegram
await kernel.log_info("log message")
```
> [!TIP]
> But it's better not to do that.

### Error Handling

`kernel.handle_error(e, source="module:function", event=None)`
---
Centralized error handling.

**Usage:**

```python
try:
    await some_operation()
except Exception as e:
    await kernel.handle_error(e, source="module:function", event=event)
```

### Registration Methods

`kernel.register_command(pattern, func=None)`
---

or:

`kernel.register.command(pattern, func=None)`
---

Register a command handler.

`kernel.register_inline_handler(pattern, function)` 
---
Register inline query handler.

`kernel.register_callback_handler(pattern, function)`
---
Register callback query handler.

**Usage:**

```python
@kernel.register.command('test')
async def test_handler(event):
    await event.edit("Test command")
```
---

**Inline**
```python
async def test_inline_handler(event):
    builder = event.builder.article(
    title="test command",
    text="test command",
    description="test"
    )
    await event.answer([builder])

def register(kernel):

    @kernel.register.command('test')
    async def test_cmd(event):
        try:
            success, result = await kernel.inline_query_and_click(
            event.chat_id,
            "test"
            )
            if success:
                event.delete()
            else:
                event.edit("error test")

        except Exception as e:
            await kernel.handle_error(e, source="test_cmd", event)
            await event.edit("Error, please check log chat")

    # inline team registration (@MCUB_bot test)
    kernel.register_inline_handler("test", test_inline_handler)
```
### Utility Properties

`kernel.LOGS_DIR` - Path to logs directory

`kernel.IMG_DIR` - Path to images directory

`kernel.VERSION` - Kernel version string

**Usage:**
```python
await event.edit(f"Running MCUB kernel v{kernel.VERSION}")
```

`kernel.start_time` - Kernel start timestamp (Unix float from `time.time()`)

**Usage:**
```python
import time
uptime_seconds = int(time.time() - kernel.start_time)
hours, rem = divmod(uptime_seconds, 3600)
minutes, seconds = divmod(rem, 60)
await event.edit(f"Uptime: {hours}h {minutes}m {seconds}s")
```

`kernel.log_chat_id` - log chat id

`kernel.loaded_modules`
---
Dictionary of all currently loaded user modules. Keys are module names (str), values are the module objects.

**Usage:**
```python
# Check if a specific module is loaded
if 'notes' in kernel.loaded_modules:
    await event.edit("notes module is active")

# List all loaded user modules
names = list(kernel.loaded_modules.keys())
await event.edit("Loaded: " + ", ".join(names))
```

`kernel.system_modules`
---
Dictionary of all loaded system modules (same structure as `loaded_modules`). System modules are loaded from the `modules/` directory and cannot be unloaded via `um`.

**Usage:**
```python
all_modules = {**kernel.system_modules, **kernel.loaded_modules}
await event.edit(f"Total modules: {len(all_modules)}")
```

---

`kernel.get_thread_id(event)`
---

> Description:
> Returns the thread ID (topic ID) for a given event in groups with topics enabled.

___Parameters:___

· event (`telethon.events.NewMessage.Event`): The message event object.

Returns:

· int or None: Thread ID if available in the message context, otherwise None.

**Usage:**

```python
thread_id = await kernel.get_thread_id(event)
if thread_id:
    await event.reply(f"This is topic #{thread_id}")
```

`kernel.get_user_info(user_id)`
---

> Description:
> Retrieves formatted user information for the given user ID.

Parameters:

· `user_id` (int): Telegram user ID to query.

Returns:

· str: Formatted string containing user name, username (if available), and ID. Returns fallback format if user cannot be fetched.

**Usage:**

```python
user_info = await kernel.get_user_info(event.sender_id)
await event.edit(f"Message from: {user_info}")
```

`kernel.is_admin(user_id)`
---

> Description:
> Checks if the specified user ID matches the admin ID of the userbot.

___Parameters:___

· `user_id` (int): User ID to verify.

Returns:

· bool: True if user ID matches admin ID, otherwise False.

Usage:

```python
if kernel.is_admin(event.sender_id):
    # Admin-only functionality
    await event.edit("Admin command executed")
else:
    await event.edit("Access denied")
```

`kernel.cprint(text, color='')`
---

> Description:
> Prints colored text to the console using ANSI escape codes.

Parameters:

· `text` (str): Text to print.
· `color` (str, optional): Color code from kernel.Colors class. Default is empty string (system default color).

Available Colors:

```python
kernel.Colors.RESET    # Reset to default
kernel.Colors.RED      # Red text
kernel.Colors.GREEN    # Green text
kernel.Colors.YELLOW   # Yellow text
kernel.Colors.BLUE     # Blue text
kernel.Colors.PURPLE   # Purple text
kernel.Colors.CYAN     # Cyan text
```

**Usage:**

```python
# Success message
kernel.cprint("success message", kernel.Colors.GREEN)


# Error message
kernel.cprint(f"error:{__name__}:{e}", kernel.Colors.RED)

# Info message
kernel.cprint("Initializing database...", kernel.Colors.CYAN)
```

`kernel.Colors` Class
---

> Description:
> Static class containing ANSI escape codes for terminal text coloring. Used by kernel.cprint() method.

Class Variables:

· `RESET = '\033[0m'` - Reset to default terminal color

· `RED = '\033[91m'` - Bright red

· `GREEN = '\033[92m'` - Bright green

· `YELLOW = '\033[93m'` - Bright yellow

· `BLUE = '\033[94m'` - Bright blue

· `PURPLE = '\033[95m'` - Bright purple

· `CYAN = '\033[96m'` - Bright cyan

**Usage:**

```python
# Direct usage
print(f"{kernel.Colors.GREEN}Success!{kernel.Colors.RESET}")

# Through cprint method
kernel.cprint("Warning message", kernel.Colors.YELLOW)
```

---

> [!NOTE]
> These utility methods are available in kernel version 1.0.1.9 and later.

---

## Database API

`kernel.db.execute(query, params=None)`
---
Execute SQL query.

**Parameters:**
- `query` (str): SQL query string
- `params` (tuple, optional): Query parameters

**Returns:** Cursor object

**Usage:**
```python
await kernel.db.execute(
    "INSERT INTO users (id, name) VALUES (?, ?)",
    (user_id, name)
)
```

`kernel.db.fetchone(query, params=None)`
---
Fetch single row from database.

**Returns:** dict or None

**Usage:**
```python
user = await kernel.db.fetchone(
    "SELECT * FROM users WHERE id = ?",
    (user_id,)
)
```

`kernel.db.fetchall(query, params=None)`
---
Fetch all rows matching query.

**Returns:** list of dict

**Usage:**
```python
users = await kernel.db.fetchall("SELECT * FROM users")
```

`kernel.db.commit()`
---
Commit pending transactions.

**Usage:**
```python
await kernel.db.execute("UPDATE users SET active = 1")
await kernel.db.commit()
```

---

## Key-Value Database API

A simpler high-level API built on top of the raw SQL database. Stores arbitrary values under a `(module, key)` pair — no table management required.

`kernel.db_set(module, key, value)`
---
Store a string value.

**Parameters:**
- `module` (str): Namespace — typically your module name
- `key` (str): Key
- `value` (str): Value to store

**Usage:**
```python
await kernel.db_set('mymodule', 'last_run', '2024-01-01')
```

`kernel.db_get(module, key)`
---
Retrieve a stored value.

**Returns:** str | None (via await)

**Usage:**
```python
value = await kernel.db_get('mymodule', 'last_run')
```

`kernel.db_delete(module, key)`
---
Delete a stored value.

**Usage:**
```python
await kernel.db_delete('mymodule', 'last_run')
```

`kernel.db_query(query, parameters)`
---
Execute arbitrary SQL query.

**Returns:** list of rows

**Usage:**
```python
rows = await kernel.db_query("SELECT * FROM module_data WHERE module = ?", ('mymodule',))
```

`kernel.db_conn`
---
Get the raw sqlite3 connection object.

**Returns:** aiosqlite.Connection or None

**Usage:**
```python
conn = kernel.db_conn
```

---

## Module Config API

A structured per-module configuration system backed by the database. Stores and retrieves JSON-serialisable config objects automatically.

`kernel.get_module_config(module_name, default=None)`
---
Retrieve the full config dict for a module.

**Returns:** dict (empty dict if nothing stored and no default given)

**Usage:**
```python
config = await kernel.get_module_config('mymodule')
timeout = config.get('timeout', 30)
```

`kernel.save_module_config(module_name, config_data)`
---
Save the full config dict for a module.

**Returns:** bool

**Usage:**
```python
await kernel.save_module_config('mymodule', {'timeout': 60, 'enabled': True})
```

`kernel.get_module_config_key(module_name, key, default=None)`
---
Retrieve a single key from the module config.

**Usage:**
```python
timeout = await kernel.get_module_config_key('mymodule', 'timeout', 30)
```

`kernel.set_module_config_key(module_name, key, value)`
---
Set a single key in the module config without overwriting other keys.

**Usage:**
```python
await kernel.set_module_config_key('mymodule', 'timeout', 120)
```

`kernel.delete_module_config_key(module_name, key)`
---
Remove a single key from the module config.

**Usage:**
```python
await kernel.delete_module_config_key('mymodule', 'old_setting')
```

`kernel.update_module_config(module_name, updates)`
---
Merge a dict of updates into the module config (shallow merge).

**Usage:**
```python
await kernel.update_module_config('mymodule', {'timeout': 90, 'retries': 3})
```

`kernel.delete_module_config(module_name)`
---
Delete the entire config for a module.

**Usage:**
```python
await kernel.delete_module_config('mymodule')
```

**Full example:**
```python
MODULE = 'myplugin'

def register(kernel):

    @kernel.register.on_load()
    async def setup(k):
        # Set defaults on first load
        cfg = await k.get_module_config(MODULE)
        if not cfg:
            await k.save_module_config(MODULE, {'enabled': True, 'limit': 10})

    @kernel.register.command('cfg')
    async def cfg_handler(event):
        args = event.text.split()
        if len(args) == 3:
            _, key, value = args
            await kernel.set_module_config_key(MODULE, key, value)
            await event.edit(f"Set {key} = {value}")
        else:
            cfg = await kernel.get_module_config(MODULE)
            await event.edit(str(cfg))
```

---

## Cache API

`kernel.cache.set(key, value, ttl=None)`
---
Store value in cache.

**Parameters:**
- `key` (str): Cache key
- `value` (any): Value to store
- `ttl` (int, optional): Time to live in seconds

**Usage:**
```python
kernel.cache.set('user_data', {'name': 'John'}, ttl=3600)
```

`kernel.cache.get(key, default=None)`
---
Retrieve value from cache.

**Returns:** Cached value or default

**Usage:**
```python
data = kernel.cache.get('user_data')
```

`kernel.cache.delete(key)`
---
Remove key from cache.

**Usage:**
```python
kernel.cache.delete('user_data')
```

`kernel.cache.clear()`
---
Clear all cache entries.

**Usage:**
```python
kernel.cache.clear()
```

---

## Task Scheduler API

`kernel.scheduler.add_interval_task(func, interval_seconds, task_id=None)`
---
Schedule a task to run repeatedly at a fixed interval.

**Parameters:**
- `func` (callable): Async function to execute
- `interval_seconds` (int): Interval between executions in seconds
- `task_id` (str, optional): Custom task identifier (auto-generated if omitted)

**Returns:** `task_id` (str)

**Usage:**
```python
async def check_updates():
    await kernel.client.send_message('me', 'ping')

task_id = await kernel.scheduler.add_interval_task(check_updates, 300)
```

`kernel.scheduler.add_daily_task(func, hour, minute, task_id=None)`
---
Schedule a task to run once every day at a specific time.

**Parameters:**
- `func` (callable): Async function to execute
- `hour` (int): Hour (0–23)
- `minute` (int): Minute (0–59)
- `task_id` (str, optional): Custom task identifier

**Returns:** `task_id` (str)

**Usage:**
```python
async def daily_report():
    await kernel.client.send_message('me', 'Daily report')

task_id = await kernel.scheduler.add_daily_task(daily_report, hour=9, minute=0)
```

`kernel.scheduler.add_task(func, delay_seconds, task_id=None)`
---
Schedule a one-shot task to run once after a delay.

**Parameters:**
- `func` (callable): Async function to execute
- `delay_seconds` (int): Delay before execution in seconds
- `task_id` (str, optional): Custom task identifier

**Returns:** `task_id` (str)

**Usage:**
```python
# Run once after 60 seconds
task_id = await kernel.scheduler.add_task(cleanup_function, delay_seconds=60)
```

`kernel.scheduler.cancel_task(task_id)`
---
Cancel a scheduled task by its ID.

**Usage:**
```python
kernel.scheduler.cancel_task(task_id)
```

`kernel.scheduler.cancel_all_tasks()`
---
Cancel all currently scheduled tasks.

**Usage:**
```python
kernel.scheduler.cancel_all_tasks()
```

`kernel.scheduler.get_tasks()`
---
Get a list of all registered tasks with their status.

**Returns:** List of dicts with keys `id`, `type`, `status`

**Usage:**
```python
for task in kernel.scheduler.get_tasks():
    print(f"{task['id']} [{task['type']}]: {task['status']}")
```

> [!TIP]
> Always cancel interval/daily tasks in `@kernel.register.uninstall()` to avoid orphaned tasks after module reload. For new modules, consider `@kernel.register.loop()` instead — it starts and stops automatically with the module lifecycle.

---

## Middleware API

`kernel.add_middleware(middleware_func)`
---
Add middleware to process events before handlers.

**Parameters:**
- `middleware_func` (callable): Async function receiving (event, handler)

**Usage:**
```python
async def auth_middleware(event, handler):
    if not kernel.is_admin(event.sender_id):
        await event.reply("Access denied")
        return
    return await handler(event)

kernel.add_middleware(auth_middleware)
```

---

## Command Registration

### Standard Registration

```python
@kernel.register.command('example')
async def example_handler(event):
    await event.edit("Example command")
```

### Registration with Aliases

```python
@kernel.register.command('example', alias=['ex', 'e'])
async def example_handler(event):
    await event.edit(f"Works with {kernel.custom_prefix}example, {kernel.custom_prefix}ex, or {kernel.custom_prefix}e")
```

### Multiple Commands

```python
def register(kernel):
    @kernel.register.command('cmd1')
    async def handler1(event):
        await event.edit("Command 1")
    
    @kernel.register.command('cmd2')
    async def handler2(event):
        await event.edit("Command 2")
```

---

## Event Handlers

> [!TIP]
> Prefer `@kernel.register.event(...)` over `@kernel.client.on(...)` in modules. The register version tracks the handler per-module and removes it automatically on unload. See [Enhanced Registration API](#enhanced-registration-api-v102) for full reference.

### Message Events

```python
# Preferred — auto-removed on module unload
@kernel.register.event('newmessage', pattern=r'keyword')
async def keyword_handler(event):
    await event.reply("Keyword detected")

# Raw Telethon — use only outside of modules
from telethon import events
@kernel.client.on(events.NewMessage(pattern='keyword'))
async def keyword_handler(event):
    await event.reply("Keyword detected")
```

### Callback Query Events

```python
async def button_handler(event):
    data = event.data.decode('utf-8')
    await event.answer(f"Button {data} clicked")
kernel.register_callback_handler('button_', button_handler)
```

### Inline Query Events

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

---

## Configuration Management

### Reading Configuration

```python
# Get value with default
api_key = kernel.config.get('api_key', 'default_key')

# Direct access
timeout = kernel.config['timeout']
```

### Writing Configuration

```python
# Set value
kernel.config['new_setting'] = 'value'

# Save to disk
kernel.save_config()
```

### Configuration Structure

```json
{
    "command_prefix": ".",
    "log_chat_id": 0,
    "bot_username": "MCUB_bot",
    // ...
}
```

---

## Error Handling

### Basic Error Handling

```python
@kernel.register.command('risky')
async def risky_handler(event):
    try:
        result = await risky_operation()
        await event.edit(f"Success: {result}")
    except Exception as e:
        await kernel.handle_error(e, source="risky_handler", event=event)
        await event.edit("Operation failed")
```

### Error Logging

```python
try:
    await operation()
except ValueError as e:
    await kernel.logger.error(f"Value error in module: {e}")
except Exception as e:
    await kernel.logger.critical(f"Critical error: {e}")
```

---

## Utils Package API

MCUB provides a comprehensive utils package for common operations. Import utilities as needed:

```python
from utils import (
    get_args,
    answer,
    escape_html,
    parse_html,
    restart_kernel
)
```

### Argument Parsing

`get_args(event)`
---
Extract command arguments split by spaces, respecting quotes.

**Parameters:**
- `event` (Message or Event): Message event object

**Returns:** List of string arguments

**Usage:**
```python
@kernel.register.command('echo')
async def echo_handler(event):
    args = get_args(event)
    if args:
        await event.edit(f"Echo: {' '.join(args)}")
```

`get_args_raw(event)`
---
Return raw argument string (everything after command).

**Returns:** String of arguments

**Usage:**
```python
args = get_args_raw(event)
await event.edit(f"Raw args: {args}")
```

`get_args_html(event)`
---
Return command arguments with preserved HTML formatting.

**Returns:** HTML string with entities

**Usage:**
```python
html_args = get_args_html(event)
await event.reply(html_args, parse_mode='html')
```

### Advanced Argument Parser

`ArgumentParser(text, prefix='.')`
---
Advanced command argument parser supporting flags, named arguments, and positional arguments.

**Features:**
- Long flags: `--flag value` or `--flag=value`
- Short flags: `-f value` or `-fvx` (multiple)
- Boolean flags: `--verbose` (sets to True)
- Type detection: automatic int, float, bool parsing
- List support: comma-separated values

**Usage:**
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
        await event.edit("Verbose mode enabled")
    
    # Join remaining arguments
    message = parser.join_args(start=1)
```

**Class Methods:**

`parser.get(index, default=None)` - Get positional argument by index

`parser.get_kwarg(key, default=None)` - Get named argument value

`parser.get_flag(flag)` - Check if flag exists (returns bool)

`parser.has(key)` - Check if argument exists

`parser.join_args(start=0, end=None)` - Join positional arguments into string

**Properties:**

`parser.command` - Extracted command name

`parser.args` - List of positional arguments

`parser.kwargs` - Dictionary of named arguments

`parser.flags` - Set of flag names

`parser.raw_args` - Original argument string

**Helper Functions:**

`parse_arguments(text, prefix='.')` - Create ArgumentParser instance

`extract_command(text, prefix='.')` - Extract command and args from text

`split_args(args_string)` - Split argument string respecting quotes

`parse_kwargs(args_string)` - Parse argument string into key-value dictionary

**Validator Class:**

```python
from utils import ArgumentValidator

validator = ArgumentValidator()

# Validate required arguments
if not validator.validate_required(parser, 'name', 'email'):
    await event.edit("Missing required arguments")
    return

# Validate argument count
if not validator.validate_count(parser, min_count=1, max_count=3):
    await event.edit("Invalid argument count")
    return

# Validate types
if not validator.validate_types(parser, str, int, float):
    await event.edit("Invalid argument types")
    return

# Validate named argument type
if not validator.validate_kwarg_type(parser, 'port', int):
    await event.edit("Port must be a number")
    return
```

### Message Sending

`answer(event, text, **kwargs)`
---
Universal method to reply to message, edit inline message, or send file.

**Parameters:**
- `event` (Message or Event): Original event
- `text` (str): Text to send
- `reply_markup` (optional): Inline keyboard
- `file` (optional): File to attach
- `as_html` (bool): Force HTML parsing
- `as_emoji` (bool): Force emoji parsing
- `caption` (str): Caption for file
- `**kwargs`: Additional arguments for send/edit method

**Usage:**
```python
from utils import answer, answer_file
# Simple reply
await answer(event, "Response text")

# With HTML formatting
await answer(event, "<b>Bold</b> text", as_html=True)

# With file
await answer(event, "Check this file", file="document.pdf")

# With inline keyboard
from telethon import Button
buttons = [[Button.inline("Click", b"callback_data")]]
await answer(event, "Choose option", buttons=buttons) 
```

`answer_file(event, file, caption=None, **kwargs)`
---
Send file in reply to message.

**Parameters:**
- `event`: Original event
- `file`: File path, URL, bytes, or InputDocument
- `caption` (str, optional): File caption
- `as_html` (bool): Treat caption as HTML
- `as_emoji` (bool): Treat caption as emoji text
- `**kwargs`: Additional arguments for send_file

**Usage:**
```python
await answer_file(event, "photo.jpg", caption="<b>Photo</b>", as_html=True)
```

### HTML Parsing

`parse_html(html_text)`
---
Parse HTML markup to Telegram text and entities.

**Parameters:**
- `html_text` (str): HTML string

**Returns:** Tuple of (text, entities)

**Supported Tags:**
- `<b>`, `<strong>` - Bold
- `<i>`, `<em>` - Italic
- `<u>` - Underline
- `<s>`, `<del>`, `<strike>` - Strikethrough
- `<code>` - Monospace
- `<pre>` - Preformatted block
- `<pre language="python">` - Syntax highlighting
- `<a href="url">` - Text URL
- `<tg-spoiler>`, `<spoiler>` - Spoiler
- `<blockquote>` - Quote
- `<blockquote expandable>` - Expandable quote
- `<tg-emoji emoji-id="123">` - Custom emoji

**Usage:**
```python
from utils import parse_html

html = '<b>Bold</b> and <i>italic</i> text'
text, entities = parse_html(html)
await event.client.send_message(chat_id, text, formatting_entities=entities)
```

`telegram_to_html(text, entities)`
---
Convert Telegram text and entities back to HTML markup.

**Parameters:**
- `text` (str): Message text
- `entities` (list): Telegram entities

**Returns:** HTML string

**Usage:**
```python
from utils import telegram_to_html

message = await event.get_reply_message()
html = telegram_to_html(message.text, message.entities)
await event.edit(f"Formatted: {html}")
```

### Raw HTML Extraction

`message_to_html(message, detailed=False)`
---
Extract full HTML markup from Telegram message.

**Parameters:**
- `message`: Telegram message object
- `detailed` (bool): Include metadata in output

**Returns:** HTML string

**Usage:**
```python
from utils import message_to_html

msg = await event.get_reply_message()
html = message_to_html(msg, detailed=True)
with open('message.html', 'w') as f:
    f.write(html)
```

`event_to_html(event, detailed=False)`
---
Convert event to HTML representation.

**Usage:**
```python
from utils import event_to_html

html = event_to_html(event)
await event.edit(html, parse_mode='html')
```

`extract_raw_html(message, escape=False)`
---
Extract raw HTML from message.

**Parameters:**
- `message`: Message object
- `escape` (bool): Escape HTML special characters

**Returns:** HTML string

`debug_entities(message)`
---
Debug message entities structure.

**Returns:** List of entity info dictionaries

**Usage:**
```python
from utils import debug_entities

entities_info = debug_entities(message)
for ent in entities_info:
    print(f"{ent['type']}: {ent['text']} (offset={ent['offset']}, length={ent['length']})")
```

### Message Helpers with HTML

`edit_with_html(kernel, event, html_text, truncate=True, **kwargs)`
---
Edit message with HTML markup.

**Parameters:**
- `kernel`: Kernel instance
- `event`: Event object
- `html_text` (str): HTML text
- `truncate` (bool): Truncate to Telegram limits (default: True)
- `**kwargs`: Additional arguments for event.edit

**Usage:**
```python
from utils import edit_with_html

html = '<b>Updated</b> content with <i>formatting</i>'
await edit_with_html(kernel, event, html)
```

`reply_with_html(kernel, event, html_text, truncate=True, **kwargs)`
---
Reply to message with HTML markup.

**Usage:**
```python
from utils import reply_with_html

html = '<code>Code block</code> with <a href="https://example.com">link</a>'
await reply_with_html(kernel, event, html)
```

`send_with_html(kernel, client, chat_id, html_text, truncate=True, **kwargs)`
---
Send message with HTML markup.

**Usage:**
```python
from utils import send_with_html

html = '<b>Notification:</b> System updated'
await send_with_html(kernel, kernel.client, chat_id, html)
```

`send_file_with_html(kernel, client, chat_id, html_text, file, truncate=True, **kwargs)`
---
Send file with HTML caption.

**Parameters:**
- `html_text` (str): HTML caption (max 1024 characters for files)
- `file`: File to send

**Usage:**
```python
from utils import send_file_with_html

caption = '<b>Document:</b> <i>Important file</i>'
await send_file_with_html(kernel, kernel.client, chat_id, caption, 'file.pdf')
```

### Text Formatting

`escape_html(text)`
---
Escape HTML special characters (&, <, >).

**Usage:**
```python
from utils import escape_html

user_input = '<script>alert("xss")</script>'
safe_text = escape_html(user_input)
await event.edit(safe_text)
```

`escape_quotes(text)`
---
Escape double quotes for HTML attributes.

**Usage:**
```python
from utils import escape_quotes

attr_value = escape_quotes(user_input)
html = f'<a href="{attr_value}">Link</a>'
```

### Chat Information

`get_chat_id(event)`
---
Return chat ID without -100 prefix for channels.

**Returns:** int

**Usage:**
```python
from utils import get_chat_id

chat_id = get_chat_id(event)
```

`get_sender_info(event)`
---
Return formatted string with sender information.

**Returns:** String like "John Doe (@johndoe) [123456]"

**Usage:**
```python
from utils import get_sender_info

sender = await get_sender_info(event)
await event.edit(f"Message from: {sender}")
```

`get_thread_id(event)`
---
Return thread (topic) ID if message is in forum.

**Returns:** int or None

**Usage:**
```python
from utils import get_thread_id

thread_id = await get_thread_id(event)
if thread_id:
    await event.client.send_message(
        chat_id,
        "Topic reply",
        reply_to=thread_id
    )
```

### Entity Manipulation

`relocate_entities(entities, offset, text=None)`
---
Shift message entities by offset and clamp to text length.

**Parameters:**
- `entities` (list): List of MessageEntity objects
- `offset` (int): Character offset to shift (can be negative)
- `text` (str, optional): Text to clamp entities to

**Returns:** List of adjusted entities

**Usage:**
```python
from utils import relocate_entities

# Extract substring with entities
full_text = "Command: Hello world"
command_end = 9
substring = full_text[command_end:]
adjusted_entities = relocate_entities(
    event.message.entities,
    -command_end,
    substring
)
```

### Kernel Control

`restart_kernel(kernel, chat_id=None, message_id=None)`
---
Restart userbot process with optional post-restart notification.

**Parameters:**
- `kernel`: Kernel instance
- `chat_id` (int, optional): Chat ID for notification
- `message_id` (int, optional): Message ID to edit after restart

**Usage:**
```python
from utils import restart_kernel

@kernel.register.command('restart')
async def restart_handler(event):
    msg = await event.edit("Restarting...")
    await restart_kernel(kernel, event.chat_id, msg.id)
```

---

### Time & Date Formatting

`format_time(seconds, detailed=False)`
---
Format seconds into human-readable time string.

**Parameters:**
- `seconds` (int/float): Number of seconds
- `detailed` (bool): Show weeks/days separately

**Returns:** str like "1h 30m" or "1w 2d 3h"

**Usage:**
```python
from utils import format_time

uptime = 3665
await event.edit(format_time(uptime))  # "1h 1m"
await event.edit(format_time(uptime, detailed=True))  # "1h 1m 5s"
```

---

`format_date(timestamp, fmt="%Y-%m-%d %H:%M")`
---
Format Unix timestamp to date string.

**Parameters:**
- `timestamp` (int/float/datetime): Unix timestamp or datetime object
- `fmt` (str): strftime format string

**Usage:**
```python
from utils import format_date

ts = 1704067200
await event.edit(format_date(ts))  # "2024-01-01 00:00"
await event.edit(format_date(ts, "%d.%m.%Y"))  # "01.01.2024"
```

---

`format_relative_time(timestamp)`
---
Format timestamp as relative time ("5 minutes ago").

**Usage:**
```python
from utils import format_relative_time

msg_time = message.date.timestamp()
await event.edit(format_relative_time(msg_time))  # "2 hours ago"
```

---

### Chat Utilities

`get_admins(event_or_client, chat_id=None)`
---
Get list of admins in a chat.

**Returns:** List of dicts with keys: `id`, `name`, `username`, `is_creator`, `is_admin`

**Usage:**
```python
from utils import get_admins

admins = await get_admins(event)
for admin in admins:
    if admin['is_creator']:
        await event.edit(f"Owner: {admin['name']}")
```

---

`resolve_peer(client, identifier)`
---
Resolve username, phone, or link to user ID.

**Parameters:**
- `identifier` (str/int): Username (with/without @), phone, or numeric ID

**Returns:** int or None

**Usage:**
```python
from utils import resolve_peer

user_id = await resolve_peer(kernel.client, "@username")
user_id = await resolve_peer(kernel.client, "+79991234567")
user_id = await resolve_peer(kernel.client, 123456789)
```

---

### Button Helpers

`make_button(text, data=None, url=None, switch=None, same_peer=False)`
---
Create a single Telethon Button with less boilerplate.

**Usage:**
```python
from utils import make_button

# Callback button
btn1 = make_button("Click me", data="click")

# URL button
btn2 = make_button("Open", url="https://example.com")

# Switch inline
btn3 = make_button("Search", switch="query", same_peer=True)
```

---

`make_buttons(buttons, cols=2)`
---
Create multiple buttons from a flat list.

**Parameters:**
- `buttons`: List of button dicts with keys: `text`, `data`/`url`/`switch`
- `cols`: Buttons per row (default 2)

**Usage:**
```python
from utils import make_buttons

buttons = [
    {"text": "Edit", "data": "edit_1"},
    {"text": "Delete", "data": "delete_1"},
    {"text": "Link", "url": "https://example.com"},
    {"text": "Search", "switch": "query"},
]
rows = make_buttons(buttons, cols=2)
# Result: [[btn1, btn2], [btn3, btn4]]

await event.edit("Choose:", buttons=rows)
```

### Platform Detection

```python
from utils import (
    get_platform,
    is_termux,
    is_wsl,
    is_docker,
    is_mobile,
    is_desktop
)

# Get platform name
platform = get_platform()  # Returns: 'linux', 'windows', 'darwin', etc.

# Check specific environments
if is_termux():
    await event.edit("Running on Termux")
elif is_docker():
    await event.edit("Running in Docker")
elif is_wsl():
    await event.edit("Running on WSL")
```

---

## Best Practices

### Module Organization

```python
# requires: aiohttp, pillow
# author: Developer Name
# version: 1.0.0
# description: Example module with best practices

import asyncio
from telethon import Button

def register(kernel):
    # Configuration
    CONFIG_KEY = 'example_module'
    
    # Initialize module config
    if CONFIG_KEY not in kernel.config:
        kernel.config[CONFIG_KEY] = {
            'enabled': True,
            'timeout': 30
        }
    
    # Command handlers
    @kernel.register.command('example', alias='ex')
    async def example_handler(event):
        try:
            # Get configuration
            config = kernel.config[CONFIG_KEY]
            if not config['enabled']:
                await event.edit("Module disabled")
                return
            
            # Process command
            result = await process_command(event, config)
            await event.edit(result)
            
        except Exception as e:
            await kernel.handle_error(e, source="example_handler", event=event)
            await event.edit("Command failed")
    
    async def process_command(event, config):
        # Implementation
        return "Success"
```

### Error Handling Pattern

```python
@kernel.register.command('safe')
async def safe_handler(event):
    try:
        # Main logic
        result = await risky_operation()
        await event.edit(f"Result: {result}")
        
    except ValueError as e:
        # Specific error handling
        await kernel.logger.warning(f"Invalid value: {e}")
        await event.edit("Invalid input")
        
    except ConnectionError as e:
        # Network error handling
        await kernel.logger.error(f"Connection failed: {e}")
        await event.edit("Network error")
        
    except Exception as e:
        # Generic error handling
        await kernel.handle_error(e, source="safe_handler", event=event)
        await event.edit("Unexpected error occurred")
```

### Resource Management

```python
def register(kernel):
    # Store resources in module-level variables
    module_cache = {}
    
    @kernel.register.command('resource')
    async def resource_handler(event):
        # Use module cache
        if 'data' not in module_cache:
            module_cache['data'] = await load_data()
        
        data = module_cache['data']
        await event.edit(f"Cached data: {data}")
    
    # Cleanup on module reload (if needed)
    async def cleanup():
        module_cache.clear()
```

### Asynchronous Operations

```python
@kernel.register.command('parallel')
async def parallel_handler(event):
    try:
        # Execute operations in parallel
        results = await asyncio.gather(
            operation1(),
            operation2(),
            operation3(),
            return_exceptions=True
        )
        
        # Process results
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        await event.edit(f"Completed: {success_count}/3")
        
    except Exception as e:
        await kernel.handle_error(e, source="parallel_handler", event=event)
```

### Database Operations

```python
@kernel.register.command('dbsave')
async def dbsave_handler(event):
    try:
        # Get arguments
        args = get_args(event)
        if len(args) < 2:
            await event.edit("Usage: .dbsave <key> <value>")
            return
        
        key, value = args[0], ' '.join(args[1:])
        
        # Save to database
        await kernel.db.execute(
            "INSERT OR REPLACE INTO storage (key, value) VALUES (?, ?)",
            (key, value)
        )
        await kernel.db.commit()
        
        await event.edit(f"Saved: {key} = {value}")
        
    except Exception as e:
        await kernel.handle_error(e, source="dbsave_handler", event=event)
```

---

## Example Module

Complete example demonstrating various features:

```python
# requires: aiohttp
# author: MCUB Developer
# version: 1.0.0
# description: Complete example module with all features

import aiohttp
from utils import get_args, answer, parse_html, ArgumentParser

def register(kernel):
    # Module configuration
    MODULE_NAME = 'example'
    
    # Initialize config
    if MODULE_NAME not in kernel.config:
        kernel.config[MODULE_NAME] = {
            'api_url': 'https://api.example.com',
            'timeout': 30,
            'cache_enabled': True
        }
    
    
    @kernel.register.command('hello', alias='hi')
    # Simple command
    async def hello_handler(event):
        try:
            args = get_args(event)
            name = args[0] if args else 'World'
            await answer(event, f"Hello, {name}!")
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:hello", event=event)
    
    
    @kernel.register.command('fetch')
    # Command with API call
    async def fetch_handler(event):
        try:
            config = kernel.config[MODULE_NAME]
            
            # Show loading message
            await event.edit("Fetching data...")
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config['api_url'],
                    timeout=config['timeout']
                ) as response:
                    data = await response.json()
            
            # Format response with HTML
            html = f'<b>Result:</b>\n<code>{data}</code>'
            await answer(event, html, as_html=True)
            
        except aiohttp.ClientError as e:
            await kernel.logger.error(f"API request failed: {e}")
            await event.edit("Failed to fetch data")
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:fetch", event=event)
    
    
    @kernel.register.command('save')
    # Command with database
    async def save_handler(event):
        try:
            args = get_args(event)
            if len(args) < 2:
                await event.edit("Usage: .save <key> <value>")
                return
            
            key, value = args[0], ' '.join(args[1:])
            
            await kernel.db.execute(
                f"INSERT OR REPLACE INTO {MODULE_NAME}_data (key, value) VALUES (?, ?)",
                (key, value)
            )
            await kernel.db.commit()
            
            await event.edit(f"Saved: {key}")
            
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:save", event=event)
    
    
    @kernel.register.command('deploy')
    # Command with advanced argument parsing
    async def deploy_handler(event):
        try:
            parser = ArgumentParser(event.text, kernel.custom_prefix)
            
            # Get positional arguments
            service = parser.get(0)
            if not service:
                await event.edit("Usage: .deploy <service> [--env=production] [--verbose]")
                return
            
            # Get named arguments
            environment = parser.get_kwarg('env', 'production')
            timeout = parser.get_kwarg('timeout', 60)
            
            # Check flags
            verbose = parser.get_flag('verbose')
            
            # Execute deployment
            await event.edit(f"Deploying {service} to {environment}...")
            
            # Simulate deployment
            import asyncio
            await asyncio.sleep(2)
            
            message = f"Deployed {service} to {environment}"
            if verbose:
                message += f"\nTimeout: {timeout}s"
            
            await event.edit(message)
            
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:deploy", event=event)
    
    
    async def example_inline_handler(event):
    # Inline handler
        try:
            query = event.text.lower()
            
            results = []
            builder = event.builder.article(
                title="Example Result",
                text=f"You searched for: {query}",
                description="Click to send"
            )
            results.append(builder)
            
            await event.answer(results)
            
        except Exception as e:
            await kernel.logger.error(f"Inline handler error: {e}")
    
    # Callback handler
    async def example_callback_handler(event):
        try:
            data = event.data.decode('utf-8')
            
            if data == 'example_button1':
                await event.edit("Button 1 clicked")
            elif data == 'example_button2':
                await event.edit("Button 2 clicked")
            else:
                await event.answer("Unknown button")
                
        except Exception as e:
            await kernel.logger.error(f"Callback handler error: {e}")
    
    # Register inline and callback handlers
    kernel.register_inline_handler('example', example_inline_handler)
    kernel.register_callback_handler('example_', example_callback_handler)
```

---

## Premium Emoji Guide

### Using Custom Emojis

MCUB supports Telegram premium custom emojis through the emoji parser.

**Basic Usage:**

```python
from utils import emoji_parser

# Send message with custom emoji
text = emoji_parser.add_emoji("Hello", emoji_id=5368324170671202286)
await event.reply(text)
```

**Multiple Emojis:**

```python
# Add multiple custom emojis
text = "Start"
text = emoji_parser.add_emoji(text, emoji_id=5368324170671202286)
text += " Middle "
text = emoji_parser.add_emoji(text, emoji_id=5370869711888194012)
text += " End"

await event.reply(text)
```

**Parse Emoji Tags:**

```python
# Check if text contains emoji tags
if emoji_parser.is_emoji_tag(text):
    parsed_text, entities = emoji_parser.parse_to_entities(text)
    await event.client.send_message(chat_id, parsed_text, entities=entities)
```

**Alternative Format (telethon-mcub only):**

MCUB also supports a simplified emoji format when using **telethon-mcub**:

```html
<emoji document_id=5253884036924844372>📌</emoji>
```

This format works directly in messages and is automatically parsed by telethon-mcub. The `document_id` is the custom emoji ID from Telegram.

**Finding Emoji IDs:**

1. Use [@ShowJsonBot](https://t.me/ShowJsonBot) to forward messages with custom emojis
2. Look for `custom_emoji_id` in the JSON response
3. Use the numeric ID in your code
or:
1. write .py print(r_text) in response to premium emoji
---

## Inline Query Automation Methods and Inline Form

### `inline_form()`

Sends an inline message with formatted fields and buttons. Supports two ways of specifying buttons: a simplified dictionary format or ready-made Telethon button objects.

---

**Parameters:**
- `chat_id` (int): Target chat ID.
- `title` (str): Form title.
- `fields` (dict | list, optional): Data to display. If a dict, shows `key: value` pairs; if a list, shows numbered items.
- `buttons` (list, optional): Button configuration. See **Button Configuration** below.
- `auto_send` (bool, default=True): If `True`, sends the form immediately and returns `(bool, Message)`. If `False`, returns the `form_id` string for later use.
- `ttl` (int, default=200): Time-to-live for the form in the cache (seconds).
- `**kwargs`: Additional arguments passed to `inline_query_and_click` (e.g., `reply_to`, `silent`).

---

**Button Configuration**

You can provide buttons in two formats:

1. **Simplified format** – a list of rows, each row is a list of button descriptions (dictionaries or tuples).  
   Each button description can be:
   - **Dictionary**:  
     ```python
     {"text": "Label", "type": "callback", "data": "callback_data"}
     {"text": "Label", "type": "url", "url": "https://..."}
     {"text": "Label", "type": "switch", "query": "inline query", "hint": True}
     ```
   - **Tuple/list** (shorter):  
     ```python
     ("Label", "callback", "data")
     ("Label", "url", "https://...")
     ("Label", "switch", "query", hint)   # hint is optional
     ```

2. **Ready‑made Telethon buttons** – a list of lists containing actual `Button` objects from Telethon:  
   ```python
   [
       [Button.inline("Edit", b"edit_data")],
       [Button.url("Site", "https://...")],
       [Button.switch_inline("Search", query="search", same_peer=True)]
   ]
   ```

**Returns:**
- If `auto_send=True`: `(bool, Message or None)` – success flag and the sent message (or `None` on failure).
- If `auto_send=False`: `str` – the form ID that can be used later in an inline query.

---

**Usage Examples**

#### Basic form (no fields, no buttons)
```python
success, msg = await kernel.inline_form(event.chat_id, "User Profile")
```

#### Form with fields
```python
fields = {
    "Name": "John Doe",
    "Status": "Active",
    "Balance": "100 coins"
}
success, msg = await kernel.inline_form(
    event.chat_id,
    "User Profile",
    fields=fields
)
```

#### Form with simplified buttons
```python
buttons = [
    {"text": "Edit", "type": "callback", "data": "profile_edit"},
    {"text": "Website", "type": "url", "url": "https://example.com"}
]
success, msg = await kernel.inline_form(
    event.chat_id,
    "User Profile",
    fields=fields,
    buttons=buttons
)
```

#### Form with ready‑made Telethon buttons
```python
from telethon import Button

buttons = [
    [Button.inline("Edit", b"profile_edit")],
    [Button.url("Website", "https://example.com")],
    [Button.switch_inline("Search", query="search", same_peer=True)]
]
success, msg = await kernel.inline_form(
    event.chat_id,
    "User Profile",
    fields=fields,
    buttons=buttons
)
```

#### Get form ID only (for later use)
```python
form_id = await kernel.inline_form(
    event.chat_id,
    "My Form",
    auto_send=False
)
# later, send it manually:
await kernel.inline_query_and_click(event.chat_id, query=form_id)
```

---

**Complete Example with Callback Handling**

```python
@kernel.register.command('profile')
async def profile_handler(event):
    fields = {
        "name": "user",
        "status": "MCUB user",
        "coin": "100 MCUB coin"
    }
    buttons = [
        {"text": "Play", "type": "callback", "data": "casino_play"},
        {"text": "History", "type": "callback", "data": "casino_history"}
    ]
    success, msg = await kernel.inline_form(
        event.chat_id,
        "User Profile",
        fields=fields,
        buttons=buttons
    )
    if success:
        await event.delete()
    else:
        await event.edit("Failed to create profile")

# Callback handler
async def casino_callback_handler(event):
    data = event.data.decode('utf-8')
    if data == 'casino_play':
        await event.edit("Starting game...")
    elif data == 'casino_history':
        await event.edit("Loading history...")

kernel.register_callback_handler('casino_', casino_callback_handler)
```

**Field Output Format:**

```
Title
field_name: field_value
another_field: another_value
```

> [!NOTE]
> Available in kernel version 1.0.2.2.5 and later.

---

### `inline_query_and_click()`
---

Performs an inline query through the specified bot and automatically clicks on the selected result. This method handles the complete workflow from query to message sending with configurable parameters.

**Parameters:**
- `chat_id` (int): Target chat ID
- `query` (str): Inline query text
- `bot_username` (str, optional): Bot username (uses config if not specified)
- `result_index` (int): Result index to click (default: 0)
- `timeout` (int): Operation timeout in seconds (default: 10)

**Returns:** Tuple of (bool, Message or None)

> [!NOTE]
> Available in kernel version 1.0.9.4 and later.

**Usage Examples:**

```python
# Basic usage with configured bot
success, message = await kernel.inline_query_and_click(
    chat_id=event.chat_id,
    query="gif cat"
)

# With custom bot and specific result
success, message = await kernel.inline_query_and_click(
    chat_id=event.chat_id,
    query="sticker hello",
    bot_username="StickersBot",
    result_index=2  # Click third result
)

# With timeout
success, message = await kernel.inline_query_and_click(
    chat_id=event.chat_id,
    query="search term",
    timeout=15
)
```

**Complete Example:**

```python
@kernel.register.command('gif')
async def gif_handler(event):
    try:
        args = get_args(event)
        if not args:
            await event.edit("Usage: .gif <search query>")
            return
        
        query = ' '.join(args)
        await event.edit(f"Searching for: {query}...")
        
        success, message = await kernel.inline_query_and_click(
            event.chat_id,
            f"gif {query}",
            bot_username="gif"
        )
        
        if success:
            await event.delete()
        else:
            await event.edit("Failed to find GIF")
            
    except Exception as e:
        await kernel.handle_error(e, source="gif_handler", event=event)
```

---

### `manual_inline_example()`
---

Provides manual control over inline query execution, returning raw results for custom processing. Useful when you need to implement custom logic for result selection or processing.

**Usage:**

```python
# Get inline results manually
results = await kernel.client.inline_query(
    bot_username,
    query
)

# Process results
for i, result in enumerate(results):
    print(f"Result {i}: {result.title}")

# Click specific result
if results:
    message = await results[0].click(
        chat_id,
        reply_to=reply_to_id
    )
```

---

### `send_inline_from_config()`
---

Simplified wrapper that uses the bot username configured in `config.json`. For quick usage when you don't need to specify a bot username.

**Usage:**

```python
success, message = await kernel.send_inline_from_config(
    event.chat_id,
    "search query"
)
```

---

## Callback Permission Management

MCUB includes a built-in callback permission manager to control user access to inline button interactions.

> [!TIP]
> By default, only users with ADMIN_ID have the right to press inline buttons.

### `CallbackPermissionManager` Class

Manages temporary permissions for callback query patterns.

**Initialization:**

```python
from kernel import CallbackPermissionManager
permission_manager = CallbackPermissionManager()
```

**Methods:**

`allow(user_id, pattern, duration_seconds=60)`
---
Grant permission for a user to trigger callbacks starting with the specified pattern.

**Parameters:**
- `user_id` (int): Telegram user ID
- `pattern` (str/bytes): Callback data pattern
- `duration_seconds` (int): Permission duration (default: 60s)

`is_allowed(user_id, pattern)`
---
Check if a user has permission for a callback pattern.

**Returns:** bool - True if allowed

`prohibit(user_id, pattern=None)`
---
Revoke permission(s) for a user.
- If `pattern` specified: revokes only that pattern
- If `pattern` is None: revokes all permissions for user

`cleanup()`
---
Remove expired permissions (automatically called internally).

**Usage Example:**

```python
def register(kernel):
    # Create permission manager
    perm_mgr = CallbackPermissionManager()
    
    # Grant permission when user starts interaction
    @kernel.register.command('start_game')
    async def start_handler(event):
        user_id = event.sender_id
        perm_mgr.allow(user_id, 'game_', duration_seconds=300)
        await event.edit("Game started! You have 5 minutes.")
    
    # Check permission in callback handler
    async def game_callback_handler(event):
        user_id = event.sender_id
        
        if not perm_mgr.is_allowed(user_id, event.data):
            await event.answer("Session expired!", alert=True)
            return
        
        # Process callback
        await event.edit("Game action processed!")
    
    kernel.register_callback_handler('game_', game_callback_handler)
```

> [!NOTE]
> Available in MCUB kernel version 1.0.2 and later.

---

## Enhanced Registration API v1.0.2

MCUB introduces a `Register` class with decorator-based registration. All handlers registered through it are tracked per-module and removed automatically on unload — no zombie handlers after `um` or `reload`.

### Method Registration

`@kernel.register.method`
---
Register any function as a module setup method. Called during loading with the kernel as argument. Any function name is accepted.

**Usage:**
```python
@kernel.register.method
async def setup(kernel):
    kernel.logger.info("module initialised")
```

### Command Registration

`@kernel.register.command(pattern, alias=None, more=None)`
---
Register a userbot command. Prefix and regex anchors are stripped automatically.

**Parameters:**
- `pattern` (str): Command name
- `alias` (str or list): Alternative trigger names
- `more` (any): Arbitrary metadata stored in `kernel.command_metadata`

**Example:**
```python
@kernel.register.command('ping', alias=['p'])
async def ping(event):
    await event.edit("Pong!")

# All work: .ping  .p
```

### Bot Command Registration

`@kernel.register.bot_command(pattern)`
---
Register a Telegram native `/command` (requires bot client).

**Example:**
```python
@kernel.register.bot_command('start')
async def start(event):
    await event.respond("Hello!")
```

### Event Registration

`@kernel.register.event(event_type, **kwargs)`
---
Register a Telethon event handler. Unlike raw `client.add_event_handler`, handlers are stored in `module.register.__event_handlers__` and removed automatically when the module is unloaded.

**Event types:**

| Argument | Telethon class |
|---|---|
| `newmessage` / `message` | `events.NewMessage` |
| `messageedited` / `edited` | `events.MessageEdited` |
| `messagedeleted` / `deleted` | `events.MessageDeleted` |
| `userupdate` / `user` | `events.UserUpdate` |
| `inlinequery` / `inline` | `events.InlineQuery` |
| `callbackquery` / `callback` | `events.CallbackQuery` |
| `raw` / `custom` | `events.Raw` |

**Examples:**
```python
@kernel.register.event('newmessage', pattern=r'hello')
async def hello(event):
    await event.reply("Hi!")

@kernel.register.event('callbackquery', pattern=b'menu_')
async def menu_cb(event):
    await event.answer("Menu clicked")
```

> [!WARNING]
> Do **not** mix `@kernel.register.event` with raw `@kernel.client.on(...)` in the same module. The raw form bypasses the tracker and will leak a handler after unload.

---

## Watchers

`@kernel.register.watcher(**tags)`
---
Register a passive message watcher. Fires on every new message (incoming and outgoing) and is cleaned up automatically on module unload.

Filters are declared as keyword arguments — no `if` branches needed inside the handler.

**Both syntaxes are valid:**
```python
@kernel.register.watcher            # no filters
@kernel.register.watcher()         # no filters
@kernel.register.watcher(only_pm=True, no_media=True)   # with filters
```

**Available tags:**

| Tag | Effect |
|---|---|
| `out=True` | Only outgoing messages |
| `incoming=True` | Only incoming messages |
| `only_pm=True` | Private chats only |
| `no_pm=True` | Exclude private chats |
| `only_groups=True` | Groups/supergroups only |
| `no_groups=True` | Exclude groups |
| `only_channels=True` | Channels only |
| `no_channels=True` | Exclude channels |
| `only_media=True` | Messages with any media |
| `no_media=True` | Text-only messages |
| `only_photos=True` | Photos only |
| `only_videos=True` | Videos only |
| `only_audios=True` | Audio files only |
| `only_docs=True` | Documents only |
| `only_stickers=True` | Stickers only |
| `no_photos/videos/audios/docs/stickers=True` | Exclude that media type |
| `only_forwards=True` | Forwarded messages only |
| `no_forwards=True` | Exclude forwards |
| `only_reply=True` | Replies only |
| `no_reply=True` | Exclude replies |
| `regex="pattern"` | Text matches regex |
| `startswith="text"` | Text starts with value |
| `endswith="text"` | Text ends with value |
| `contains="text"` | Text contains value |
| `from_id=<int>` | From specific user ID |
| `chat_id=<int>` | In specific chat ID |

**Examples:**

```python
def register(kernel):

    # Fire on every message (no filter)
    @kernel.register.watcher
    async def log_all(event):
        kernel.logger.debug(f"msg: {event.text[:50]}")

    # Only my outgoing messages in PM, no media
    @kernel.register.watcher(out=True, only_pm=True, no_media=True)
    async def pm_watcher(event):
        kernel.logger.info(f"sent in PM: {event.text}")

    # React to any message containing a word
    @kernel.register.watcher(contains="купи слона")
    async def elephant(event):
        await event.reply("А у нас есть слоны!")

    # Regex filter
    @kernel.register.watcher(regex=r"^\d{4,}$")
    async def numbers(event):
        await event.reply("That's a long number.")
```

> [!TIP]
> Watcher errors are caught and logged automatically — a crash in one watcher never affects others.

---

## InfiniteLoop

`@kernel.register.loop(interval, autostart=True, wait_before=False)`
---
Declare a managed background loop. The kernel starts it after the module loads and stops it on unload — no `on_load` / `uninstall` boilerplate.

The decorated function receives `kernel` as its only argument. The decorator returns an `InfiniteLoop` object that can be used for manual control.

**Parameters:**
- `interval` (int): Seconds between iterations
- `autostart` (bool): Start automatically after load (default: `True`)
- `wait_before` (bool): Sleep *before* the first iteration instead of after (default: `False`)

**`InfiniteLoop` attributes and methods:**

| | |
|---|---|
| `loop.status` | `True` while running |
| `loop.start()` | Start the loop (no-op if already running) |
| `loop.stop()` | Stop the loop gracefully |

**Examples:**

```python
def register(kernel):

    # Simple autostarting loop — no cleanup needed
    @kernel.register.loop(interval=300)
    async def heartbeat(kernel):
        await kernel.client.send_message('me', '💓 alive')


    # Manual control via commands
    @kernel.register.loop(interval=60, autostart=False)
    async def checker(kernel):
        data = await kernel.db_get('mymod', 'watch_target')
        if data:
            kernel.logger.info(f"checking: {data}")

    @kernel.register.command('startcheck')
    async def start_cmd(event):
        checker.start()
        await event.edit("Checker started")

    @kernel.register.command('stopcheck')
    async def stop_cmd(event):
        checker.stop()
        await event.edit("Checker stopped")

    @kernel.register.command('checkstatus')
    async def status_cmd(event):
        await event.edit(f"Running: {checker.status}")
```

> [!NOTE]
> Loops are stopped before `@register.uninstall()` is called, so you can safely read `loop.status` in the uninstall callback.

> [!TIP]
> Use `wait_before=True` for loops that should delay their first run (e.g. wait for external service to be ready).

---

## Lifecycle Callbacks

All lifecycle callbacks receive `kernel` as their only argument. Both `async` and regular functions are accepted. All support both `@decorator` and `@decorator()` syntax.

### `@kernel.register.on_load()`

Called after the module is fully registered — on initial startup and on every `reload`. Use for post-registration initialisation: cache warm-up, external connections, etc.

```python
@kernel.register.on_load()
async def setup(kernel):
    kernel.logger.info("MyModule ready")
    await some_service.connect()
```

### `@kernel.register.on_install()`

Called **only the first time** the module is installed (via `dlm` / `loadera`). Not called on `reload`. The kernel stores a persistent flag in the DB so subsequent loads skip it automatically.

Use for welcome messages, first-run migrations, one-time setup.

```python
@kernel.register.on_install()
async def first_time(kernel):
    await kernel.client.send_message('me', '✅ MyModule installed!')
    await kernel.save_module_config('mymod', {'enabled': True})
```

### `@kernel.register.uninstall()`

Called when the module is unloaded — via `um`, `reload`, or any loader operation. Use to close external connections, cancel non-loop tasks, free resources.

The kernel calls this **after** stopping all `@register.loop` loops and removing all `@register.event` / `@register.watcher` handlers, so cleanup order is guaranteed.

```python
@kernel.register.uninstall()
async def cleanup(kernel):
    await some_client.disconnect()
    kernel.logger.info("MyModule unloaded cleanly")
```

**Cleanup order on unload:**
1. All `@register.loop` loops stopped
2. All `@register.watcher` Telethon handlers removed
3. All `@register.event` Telethon handlers removed
4. `@register.uninstall()` callback called
5. Command entries removed from kernel

---

### Complete lifecycle example

```python
# author: @hairpin01
# version: 1.0.0
# description: Demonstrates full lifecycle API

import aiohttp

session = None

def register(kernel):
    global session
    k = kernel

    # background loop 
    @kernel.register.loop(interval=600)
    async def refresh(kernel):
        """Refresh data every 10 minutes."""
        async with session.get("https://api.example.com/data") as r:
            kernel.logger.info(f"refreshed: {r.status}")

    # passive watcher
    @kernel.register.watcher(only_pm=True, contains="status")
    async def status_watcher(event):
        await event.reply(f"Loop running: {refresh.status}")

    # commands 
    @kernel.register.command('pause')
    async def pause(event):
        refresh.stop()
        await event.edit("Loop paused")

    @kernel.register.command('resume')
    async def resume(event):
        refresh.start()
        await event.edit("Loop resumed")

    # lifecycle 
    @kernel.register.on_install()
    async def first_run(k):
        await k.client.send_message('me', '✅ example module installed')
        await k.save_module_config('example', {'interval': 600})

    @kernel.register.on_load()
    async def on_load(k):
        global session
        session = aiohttp.ClientSession()
        k.logger.info("HTTP session opened")

    @kernel.register.uninstall()
    async def on_unload(k):
        global session
        if session:
            await session.close()
        k.logger.info("HTTP session closed")
```

> [!NOTE]
> Available in MCUB kernel version `1.0.2.9` and later.
> `register.command` supports the same alias system as `kernel.register_command()`.

---

## New Registration Methods v1.0.3

### Query Registered Handlers

`kernel.register.get_commands()`
---
Get all registered userbot commands.

**Returns:** Dict mapping command names to handler functions.

**Usage:**
```python
commands = kernel.register.get_commands()
for cmd, handler in commands.items():
    await event.edit(f"Command: {cmd}")
```

---

`kernel.register.get_bot_commands()`
---
Get all registered Telegram bot commands.

**Returns:** Dict mapping command names to `(pattern, handler)` tuples.

**Usage:**
```python
bot_cmds = kernel.register.get_bot_commands()
for cmd, (pattern, handler) in bot_cmds.items():
    await event.edit(f"Bot command: /{cmd}")
```

---

`kernel.register.get_watchers()`
---
Get all registered watchers from all modules.

**Returns:** List of `(wrapper_func, event_obj, client)` tuples.

**Usage:**
```python
watchers = kernel.register.get_watchers()
await event.edit(f"Active watchers: {len(watchers)}")
```

---

`kernel.register.get_events()`
---
Get all registered event handlers from all modules.

**Returns:** List of `(handler, event_obj, client)` tuples.

**Usage:**
```python
events = kernel.register.get_events()
await event.edit(f"Active event handlers: {len(events)}")
```

---

`kernel.register.get_loops()`
---
Get all registered InfiniteLoop objects from all modules.

**Returns:** List of InfiniteLoop instances.

**Usage:**
```python
loops = kernel.register.get_loops()
for loop in loops:
    await event.edit(f"Loop: {loop.func.__name__}, running: {loop.status}")
```

---

### Unregister Handlers

`kernel.register.unregister_command(cmd)`
---
Unregister a userbot command by name.

**Parameters:**
- `cmd` (str): Command name to unregister.

**Returns:** `bool` - True if removed, False if not found.

**Usage:**
```python
if kernel.register.unregister_command("ping"):
    await event.edit("Command 'ping' removed")
else:
    await event.edit("Command not found")
```

---

`kernel.register.unregister_bot_command(cmd)`
---
Unregister a Telegram bot command by name.

**Parameters:**
- `cmd` (str): Command name to unregister (without `/`).

**Returns:** `bool` - True if removed, False if not found.

**Usage:**
```python
if kernel.register.unregister_bot_command("start"):
    await event.edit("Bot command '/start' removed")
```

---

### Bug Fixes in v1.0.3

- **`@register.command`**: Fixed regex escaping for custom prefix characters
- **`@register.command`** and **`@register.bot_command`**: Added duplicate command detection with clear error messages
- **`@register.method`**: Methods are now tracked per-module for proper cleanup on unload

---

## Custom Core MCUB

MCUB supports multiple interchangeable kernel cores. Each core is a `.py` file placed in `core/kernel/` that exposes a single `Kernel` class. The launcher (`__main__.py`) discovers cores automatically and loads the selected one at startup.

### How the Loader Works

`__main__.py` scans `core/kernel/` for `.py` files (excluding `_`-prefixed ones), then does:

```python
from importlib import import_module
Kernel = import_module(f"core.kernel.{selected_core}").Kernel
kernel = Kernel()
await kernel.run()
```

Your custom core just needs to satisfy this contract:
- file lives at `core/kernel/<your_core_name>.py`
- the file exports a class named `Kernel`
- the class has an `async def run(self)` method

### Minimal Custom Core

The simplest possible core — inherits everything from `standard` and only overrides what you need:

```python
# core/kernel/mycore.py
# author: @you
# description: My custom MCUB kernel core

from .standard import Kernel as _StandardKernel


class Kernel(_StandardKernel):
    """Custom core — based on standard, with tweaks."""

    async def run(self):
        # Custom pre-start logic here
        self.logger.info("mycore: starting up")
        await super().run()
```

Activate it:
```bash
python3 -m core --core mycore
# or set as default
python3 -m core --set-default-core mycore
```

### Overriding Kernel Behaviour

Common extension points when subclassing `standard.Kernel`:

| Method | When to override |
|--------|-----------------|
| `__init__` | Add new state, change default paths/repos |
| `run` | Change startup sequence, add pre/post hooks |
| `load_system_modules` | Load extra built-in modules or skip certain ones |
| `process_command` | Intercept or transform commands before dispatch |
| `handle_error` | Custom error reporting (e.g. send to external service) |

**Example — custom error handler:**

```python
class Kernel(_StandardKernel):

    async def handle_error(self, e, source="unknown", event=None):
        # Call the original handler first
        await super().handle_error(e, source=source, event=event)
        # Then push to your own monitoring
        await my_monitoring.send(f"[{source}] {e}")
```

**Example — extra startup step:**

```python
class Kernel(_StandardKernel):

    async def run(self):
        # Run before anything else
        await self._preload_external_config()
        await super().run()

    async def _preload_external_config(self):
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get("https://example.com/config.json") as r:
                data = await r.json()
        self.config.update(data)
        self.logger.info("External config loaded")
```

### Full Custom Core (from scratch)

If you need full control and don't want to inherit from `standard`, implement the interface manually. The only hard requirement is `async def run(self)`:

```python
# core/kernel/mycore.py
# author: @you
# description: Fully custom lightweight core

import asyncio
import logging
from telethon import TelegramClient, events

logger = logging.getLogger("mycore")


class Kernel:
    """Minimal custom kernel — no standard inheritance."""

    CORE_NAME = "mycore"  # set by __main__.py, but good to declare

    def __init__(self):
        import json
        with open("config.json") as f:
            self.config = json.load(f)

        self.client = TelegramClient(
            "session",
            self.config["api_id"],
            self.config["api_hash"],
        )
        self.command_handlers = {}
        self.start_time = __import__("time").time()
        self.logger = logger
        self.custom_prefix = self.config.get("command_prefix", ".")

    def register_command(self, pattern, func):
        self.command_handlers[pattern] = func

    async def run(self):
        await self.client.start(phone=self.config["phone"])
        logger.info(f"mycore started. Prefix: {self.custom_prefix!r}")

        @self.client.on(events.NewMessage(outgoing=True))
        async def _dispatch(event):
            for pat, handler in self.command_handlers.items():
                if event.text and event.text.startswith(self.custom_prefix + pat):
                    await handler(event)
                    break

        await self.client.run_until_disconnected()
```

> [!NOTE]
> A from-scratch core won't have the `Register`, `ModuleLoader`, `DatabaseManager`, or other subsystems from `standard`. Modules that rely on `kernel.db_get`, `kernel.register.loop`, etc. will fail to load against it. Use a from-scratch core only if you're building a radically different runtime.

### Distributing a Core

To ship your core as a drop-in file (like the built-in `zen` core):

1. Place the file as `core/kernel/mycore.py` (active) or `core/kernel/mycore.py.off` (disabled by default).
2. Users activate it with:
   ```bash
   mv core/kernel/mycore.py.off core/kernel/mycore.py
   python3 -m core --set-default-core mycore
   ```
3. Document any extra `pip` dependencies in your file header using the standard convention:
   ```python
   # requires: aiohttp, some-lib
   ```

### Core Naming Conventions

| Name | Intended meaning |
|------|-----------------|
| `standard` | Default, frequently updated |
| `zen` | Stable branch, updated less often |
| `micro` / `lite` | Stripped-down, low-resource variant |
| `dev` / `nightly` | Experimental, may be unstable |

> [!TIP]
> Prefix your core file with your username to avoid conflicts: `core/kernel/hairpin_custom.py`.
