# `MCUB` Module API Documentation `1.0.2`

__Table of Contents__

> 1. [Introduction](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#introduction)
> 2. [Module Structure](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#module-structure)
> 3. [Kernel API Reference](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#kernel-api-reference)
> 4. [Database API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#database-api)
> 5. [Cache API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#cache-api)
> 6. [Task Scheduler API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#task-scheduler-api)
> 7. [Middleware API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#middleware-api)
> 8. [Command Registration](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#command-registration)
> 9. [Event Handlers](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#event-handlers)
> 10. [Configuration Management](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#configuration-management)
> 11. [Error Handling](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#error-handling)
> 12. [Utils Package API](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#utils-package-api)
> 13. [Best Practices](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#best-practices)
> 14. [Example Module](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#example-module)
> 15. [Premium Emoji Guide](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#premium-emoji-guide)
> 16. [Inline Query Automation Methods](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#inline-query-automation-methods-and-inline-form)

# Introduction

* MCUB (`Mitrich UserBot`) is a modular Telegram **userbot** framework built on Telethon. This documentation describes the extended API for creating modules.

## Module Structure

### Basic Structure:

```python
# requires: library1, library2
# author: Author Name
# version: 1.0.0
# description: Module description here

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

`kernel.start_time` - Kernel start timestamp

`kernel.log_chat_id` - log chat id

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

`kernel.scheduler.schedule_task(func, delay=0, interval=0, name=None)`
---
Schedule task execution.

**Parameters:**
- `func` (callable): Function to execute
- `delay` (int): Initial delay in seconds
- `interval` (int): Repeat interval (0 = run once)
- `name` (str, optional): Task identifier

**Returns:** Task ID

**Usage:**
```python
# Run once after 60 seconds
task_id = kernel.scheduler.schedule_task(
    cleanup_function,
    delay=60
)

# Run every 300 seconds
task_id = kernel.scheduler.schedule_task(
    periodic_check,
    interval=300,
    name="health_check"
)
```

`kernel.scheduler.cancel_task(task_id)`
---
Cancel scheduled task.

**Usage:**
```python
kernel.scheduler.cancel_task(task_id)
```

`kernel.scheduler.cancel_all_tasks()`
---
Cancel all scheduled tasks.

**Usage:**
```python
kernel.scheduler.cancel_all_tasks()
```

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

### Message Events

```python
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

MCUB introduces a new `Register` class with decorator-based registration methods for cleaner module syntax.

### Method Registration

`@kernel.register.method`
---
Register any function as a module setup method. The function will be called during module loading with the kernel as its only argument. You can use any function name.

**Usage:**
```python
from telethon import events

@kernel.register.method
async def setup_commands(kernel):   # function name is arbitrary
    @kernel.register.command('version', alias='v')
    async def version_mcub(event):
        await event.edit(f"Kernel version {kernel.VERSION}")

@kernel.register.method
async def init_stuff(kernel):
    # Another setup method – both will be executed
    kernel.logger.info("Additional initialisation")

### Event Registration

`@kernel.register.event(event_type, **kwargs)`
---
Register event handlers with cleaner syntax.

**Event types:** `'newmessage'`, `'messageedited'`, `'messagedeleted'`, `'userupdate'`, `'chatupload'`, `'inlinequery'`, `'callbackquery'`, `'raw'`

**Examples:**
```python
@kernel.register.event('newmessage', pattern='hello')
async def greeting_handler(event):
    await event.reply("Hi!")

@kernel.register.event('callbackquery', pattern=b'menu_')
async def menu_handler(event):
    await event.answer("Menu clicked")
```

### Command Registration

`@kernel.register.command(pattern, **kwargs)`
---
Alternative to `kernel.register_command()` with alias support.

**Parameters:**
- `alias` (str/list): Command aliases
- `more` (str): Additional options

**Example:**
```python
@kernel.register.command('test', alias=['t', 'check'])
async def test_handler(event):
    await event.edit("Test passed")
    
# All work: .test, .t, .check
```

### Bot Command Registration

`@kernel.register.bot_command(pattern, **kwargs)`
---
Register bot commands (requires bot client).

**Example:**
```python
@kernel.register.bot_command('start')
async def start_handler(event):
    await event.respond("Bot started!")

# Also works with arguments
@kernel.register.bot_command('help topic')
async def help_handler(event):
    await event.respond("Help topic details")
```

### Complete Module Example

```python
@kernel.register.method
def test(kernel):
    
    @kernel.register.event('newmessage', pattern=f'{kernel.custom_prefix}ping')
    async def ping_handler(event):
        await event.reply("Pong!")
    
    @kernel.register.bot_command('status')
    async def status_cmd(event):
        if kernel.is_bot_available():
            await event.respond("Bot is running")
```

> [!NOTE]
> Available in MCUB kernel version 1.0.2 and later.
> `register.command` supports the same alias system as `kernel.register_command()`.
