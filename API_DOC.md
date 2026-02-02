
# `MCUB` Module API Documentation `1.0.1.9.4`

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
> 12. [Best Practices](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#best-practices)
> 13. [Example Module](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#example-module)
> 14. [Premium Emoji Guide](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#premium-emoji-guide)
> 15. [Inline Query Automation Methods](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#inline-query-automation-methods-and-inline-form)

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
Command prefix (keys `commad_prefix` kernel config) (default: '`.`').

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
await kernel.logger.debug("Debug message")
await kernel.logger.info("Info message")
await kernel.logger.warning("Warning message")
await kernel.logger.error("Error message")
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
Register a command handler.

`kernel.register_inline_handler(pattern, function)`
---
Register inline query handler.

`kernel.register_callback_handler(pattern, function)`
---
Register callback query handler.

**Usage:**

```python
@kernel.register_command('test')
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

    @kernel.register_command('test')
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

### Platform Detection Utility

MCUB includes a comprehensive platform detection utility in `utils.platform` that helps modules adapt to different environments (Termux, WSL, VPS, etc.).

**Importing**
--- 

```python
# Import the entire module
from utils import platform

# Or import specific functions
from utils.platform import get_platform, get_platform_name, is_termux, is_vds
```

**Functions and Classes**

`PlatformDetector`
---
Main class for platform detection. Provides detailed detection capabilities.

`get_platform()`
---
Returns the platform identifier as a string. 

**Possible values:**
- `'termux'` - Android Termux
- `'wsl'` - Windows Subsystem for Linux (v1)
- `'wsl2'` - Windows Subsystem for Linux 2
- `'docker'` - Docker container
- `'vds'` - VDS/VPS server
- `'macos'` - macOS
- `'windows'` - Windows
- `'linux'` - Linux 
- `'linux_desktop'` - Linux Desktop
- `'unknown'` - Unknown platform

`get_platform_info()` / `get_detailed_info()`
---
Returns a dictionary with detailed platform information.

**Example output:**
```python
{
    "platform": "vds",
    "system": "linux",
    "machine": "x86_64",
    "platform_string": "Linux-5.15.0-x86_64-with-glibc2.35",
    "python_version": "3.11.0",
    "hostname": "vps-server-01",
    "processor": "Intel Xeon",
    "release": "5.15.0",
    "version": "#1 SMP Debian 5.15.0-1",
    "architecture": "64bit",
    "is_64bit": True,
    "env_vars": {
        "termux": False,
        "wsl": False,
        "docker": False,
        "display": False,
        "wayland": False
    }
}
```

`get_platform_name()`
---
Returns a human-readable platform name with emoji.

**Examples:**
- `"📱 Termux (Android)"`
- `"🪟 Windows Subsystem for Linux"`
- `"🖥️ VDS/VPS Server"`
- `"🐧 Linux Desktop"`

### Platform Detection Functions
| Function | Returns True for | Description |
|----------|------------------|-------------|
| `is_termux()` | Android Termux | Mobile environment on Android |
| `is_wsl()` | WSL or WSL2 | Windows Subsystem for Linux |
| `is_vds()` | VDS/VPS | Virtual server environment |
| `is_docker()` | Docker | Docker container environment |
| `is_mobile()` | Termux | Mobile platforms only |
| `is_desktop()` | macOS, Windows, Linux Desktop | Desktop operating systems |
| `is_virtualized()` | Termux, WSL, Docker, VDS | Virtualized/containerized environments |

__Usage Examples__

**Basic Platform Detection**
```python
# Get current platform
platform_name = platform.get_platform()
await event.edit(f"Running on: {platform_name}")

# Get human-readable name
friendly_name = platform.get_platform_name()
await event.edit(f"Platform: {friendly_name}")

# Get detailed information
info = platform.get_platform_info()
await event.edit(
    f"System: {info['system']}\n"
    f"Hostname: {info['hostname']}\n"
    f"Python: {info['python_version']}"
)
```

**Conditional Code Based on Platform**
```python
# Termux-specific code
if platform.is_termux():
    # Use Termux-specific paths or commands
    storage_path = "/sdcard"
    await event.edit("Running on Android Termux 📱")

# VPS-specific optimizations
elif platform.is_vds():
    # Disable resource-intensive tasks on VPS
    await event.edit("Running on VPS - limited resources 🖥️")
    # Reduce cache size, disable animations, etc.

# Desktop environment
elif platform.is_desktop():
    # Enable desktop-specific features
    await event.edit("Running on desktop - full features available 💻")

# Virtualized environment check
if platform.is_virtualized():
    # Be conservative with resources
    await event.edit("Running in virtualized environment 🐳")
```

**Module Initialization Based on Platform**
```python
def register(kernel):
    # Check platform during module load
    if platform.is_termux():
        # Load Android-specific configurations
        config = {"notifications": True, "vibrate": False}
    elif platform.is_vds():
        # Load VPS-optimized configurations
        config = {"cache_ttl": 600, "background_tasks": False}
    else:
        # Default configuration for desktops
        config = {"cache_ttl": 300, "notifications": True}
    
    # Platform-aware command registration
    @kernel.register_command('sysinfo')
    async def sysinfo_handler(event):
        info = platform.get_platform_info()
        
        # Format platform-specific information
        if platform.is_termux():
            extra = "📱 Android environment detected"
        elif platform.is_vds():
            extra = "🖥️ Server environment - resource monitoring enabled"
        else:
            extra = "💻 Desktop environment - all features available"
        
        await event.edit(
            f"**System Information**\n"
            f"Platform: {platform.get_platform_name()}\n"
            f"OS: {info['system']} {info['release']}\n"
            f"Architecture: {info['architecture']}\n"
            f"Python: {info['python_version']}\n"
            f"Hostname: {info['hostname']}\n\n"
            f"{extra}"
        )
```

**Platform-Specific File Paths**
```python
# Determine appropriate paths based on platform
def get_config_path():
    if platform.is_termux():
        return "/data/data/com.termux/files/home/.config/mcub"
    elif platform.is_wsl():
        return "/mnt/c/Users/username/.mcub"
    elif platform.is_vds():
        return "/opt/mcub/config"
    else:
        return os.path.expanduser("~/.config/mcub")

# Use in module
config_path = get_config_path()
os.makedirs(config_path, exist_ok=True)
```

**Resource Management by Platform**
```python
async def optimize_for_platform():
    if platform.is_termux():
        # Limit concurrent tasks on mobile
        max_tasks = 2
        cache_size = 100
    elif platform.is_vds():
        # Conservative settings for VPS
        max_tasks = 3
        cache_size = 200
    else:
        # Full resources for desktop
        max_tasks = 10
        cache_size = 1000
    
    return {
        "max_concurrent_tasks": max_tasks,
        "cache_max_size": cache_size,
        "enable_animations": not platform.is_vds()
    }
```

> [!NOTE]
> **Availability:** The utility is available in MCUB kernel version 1.0.1.9.4 and later

> [!TIP]
> **Kernel Integration:** Kernel automatically sets `kernel.platform` and `kernel.platform_name` <br>
</br>**Fallback:** If platform detection fails, returns `'unknown'` platform type <br>
</br>**Detection Methods:** Uses multiple detection methods for accuracy (environment variables, file paths, process inspection)<br>
</br>**Performance:** Detection is lightweight and cached after first call
---

### Language

MCUB provides built-in support for internationalization (i18n) through the kernel configuration system. Modules can support multiple languages by accessing the `language` key in `kernel.config`.

**Language Configuration**

The kernel stores the current language setting in `kernel.config['language']` with possible values:
- `'ru'` - Russian (default)
- `'en'` - English 

**Usage in Modules:**

```python
def register(kernel):
    # Get current language from config
    language = kernel.config.get('language', 'en')
    
    # Define localized strings
    strings = {
        'en': {
            'greeting': 'Hello!',
            'error': 'An error occurred',
            'success': 'Operation completed successfully'
        },
        'ru': {
            'greeting': 'Привет!',
            'error': 'Произошла ошибка',
            'success': 'Операция выполнена успешно'
        }
    }
    
    # Get strings for current language
    lang_strings = strings.get(language, strings['en'])
    
    # Use localized strings
    @kernel.register_command('test')
    async def test_handler(event):
        await event.edit(lang_strings['greeting'])
```

### Bot Client Access

The bot client is directly accessible via `kernel.bot_client` attribute.

Check Availability:
```python
    if kernel.is_bot_available():
        # Use bot_client
```
Direct Access Examples:
```python
    # Send message
    await kernel.bot_client.send_message(chat_id, text)
    
    # Send file
    await kernel.bot_client.send_file(chat_id, file)
    
    # Get bot info
    bot = await kernel.bot_client.get_me()
    
    # Edit message
    await kernel.bot_client.edit_message(chat_id, message_id, new_text)
    
    # Delete messages
    await kernel.bot_client.delete_messages(chat_id, [msg_id1, msg_id2])
```
> [!NOTE]
> Always check availability with `kernel.is_bot_available()` before use.


### Message Helpers
`
kernel.send_with_emoji(chat_id, text, **kwargs)`
Send message with custom emoji support.

`kernel.format_with_html(text, entities)`
---
Format text with Telegram entities to HTML.

`kernel.edit_with_html(event, html_text, **kwargs)`
`kernel.reply_with_html(event, html_text, **kwargs)`
`kernel.send_with_html(chat_id, html_text, **kwargs)`
`kernel.send_file_with_html(chat_id, html_text, file, **kwargs)`

## Database API

MCUB provides a `SQLite` database interface for persistent storage.

**Basic Operations**

`await kernel.db_set(module, key, value)`
---
Store **key-value** pair for module.

`await kernel.db_get(module, key)`
---
Retrieve **value** for module.

`await kernel.db_delete(module, key)`
---
**Delete key** from module storage.

**Usage:**

```python
# Store data
await kernel.db_set('mymodule', 'user_data', '{"name": "John"}')

# Retrieve data
data = await kernel.db_get('mymodule', 'user_data')

# Delete data
await kernel.db_delete('mymodule', 'user_data')
```

## Query Operations
`await kernel.db_query(query, parameters)`
---
Execute **custom** SQL query.

**Usage:**

```python
# Get all keys for module
rows = await kernel.db_query(
    "SELECT key, value FROM module_data WHERE module = ?",
    ('mymodule',)
)
```

## Module Configuration
`await kernel.get_module_config(module_name, default=None)`
---
Get module-specific configuration.

`await kernel.save_module_config(module_name, config)`
---
Save module configuration.

**Usage:**

```python
# Get config
config = await kernel.get_module_config(__name__, {'enabled': True})

# Update config
config['enabled'] = False
await kernel.save_module_config(__name__, config)
```

## Cache API

> TTL-based caching system for performance optimization.

**Basic Usage**

`kernel.cache.set(key, value)`
---
Store value in cache.

`kernel.cache.get(key)`
---
Retrieve value from cache.

**Usage:**

```python
# Cache expensive API call
data = kernel.cache.get('api_data')
if not data:
    data = await fetch_expensive_data()
    kernel.cache.set('api_data', data, ttl=300)  # 5 minutes

return data
```

**Cache with Custom TTL**

```python
# Set with custom TTL (seconds)
kernel.cache.set('key', 'value', ttl=600)

# Get with fallback
value = kernel.cache.get('key') or 'default'
```

## Task Scheduler API

Schedule periodic tasks with the built-in **scheduler**.

**Interval Tasks**

`await kernel.scheduler.add_interval_task(func, interval_seconds)`
Schedule task at fixed intervals.

**Usage:**

```python
async def backup_data():
    await kernel.db_set('backup', 'time', time.time())
    await kernel.log_info("Backup completed")

# Run every 5 minutes
await kernel.scheduler.add_interval_task(backup_data, 300)
```

Daily Tasks

`await kernel.scheduler.add_daily_task(func, hour, minute)`
---
Schedule task at specific time daily.

**Usage:**

```python
async def send_daily_report():
    await kernel.send_log_message("📊 Daily report generated")

# Run at 9:00 AM daily
await kernel.scheduler.add_daily_task(send_daily_report, 9, 0)
```

**One-time Tasks**

`await kernel.scheduler.add_task(func, delay_seconds)`
---
Schedule one-time delayed task.

**Usage:**

```python
async def remind_later():
    await event.reply("Reminder!")

# Remind in 1 hour
await kernel.scheduler.add_task(remind_later, 3600)
```

## Middleware API

Process messages through middleware chain for _filtering/transformation._

**Creating Middleware**

```python
async def spam_filter_middleware(event, next_handler):
    # Skip spam messages
    if "spam" in event.text.lower():
        await event.delete()
        return None
    
    # Pass to next middleware/handler
    return await next_handler(event)

# Register middleware
kernel.add_middleware(spam_filter_middleware)
```

**Multiple Middleware**

```python
async def logging_middleware(event, next_handler):
    await kernel.logger.info(f"Message from {event.sender_id}: {event.text[:50]}")
    return await next_handler(event)

async def rate_limit_middleware(event, next_handler):
    user_id = event.sender_id
    key = f"rate_limit_{user_id}"
    
    last_time = await kernel.db_get('ratelimit', key)
    if last_time and time.time() - float(last_time) < 2:
        await event.reply("⏳ Please wait...")
        return None
    
    await kernel.db_set('ratelimit', key, str(time.time()))
    return await next_handler(event)

# Register in order
kernel.add_middleware(logging_middleware)
kernel.add_middleware(rate_limit_middleware)
```

## Command Registration

**Basic Command**

```python
@kernel.register_command('ping')
# Check bot responsiveness
async def ping_handler(event):
    start = time.time()


    message = await event.edit("Pong!")
    delay = (time.time() - start) * 1000
    await message.edit(f"🏓 Pong! {delay:.2f}ms")
```

**Command with Arguments**

```python
@kernel.register_command('echo')
# Echo back the provided text
async def echo_handler(event):
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.edit("Usage: .echo <text>")
        return
    
    await event.edit(args[1])
```

**Command with Database**

```python
@kernel.register_command('counter')
# Count command invocations
async def counter_handler(event):
    user_id = event.sender_id
    key = f"count_{user_id}"
    
    current = await kernel.db_get('counter', key) or 0
    new_count = int(current) + 1
    
    await kernel.db_set('counter', key, str(new_count))
    await event.edit(f"Count: {new_count}")
```

## Event Handlers

**Message Event**

```python
from telethon import events

async def message_logger(event):
    await kernel.logger.info(f"New message: {event.chat_id} - {event.text[:100]}")

kernel.client.on(events.NewMessage(incoming=True))(message_logger)
```

Edited Message

```python
async def edit_logger(event):
    await kernel.logger.info(f"Message edited: {event.id}")

kernel.client.on(events.MessageEdited(incoming=True))(edit_logger)
```

Custom Filter

```python
async def keyword_handler(event):
    if "urgent" in event.text.lower():
        await kernel.logger.info(f"⚠️ Urgent: {event.text[:200]}")

kernel.client.on(events.NewMessage(
    func=lambda e: e.text and len(e.text) > 10
))(keyword_handler)
```

## Configuration Management

Module Settings

```python
def register(kernel):
    # Set defaults
    defaults = {
        'enabled': True,
        'interval': 60,
        'notify_chat': None
    }
    
    # Merge with existing config
    config = await kernel.get_module_config(__name__, defaults)
    
    # Use configuration
    if config['enabled']:
        await start_module_tasks(config)
```

User Settings

```python
async def user_settings_handler(event):
    user_id = event.sender_id
    user_config = await kernel.get_module_config(f'user_{user_id}', {})
    
    # Update settings
    args = event.text.split()
    if len(args) > 2:
        user_config[args[1]] = args[2]
        await kernel.save_module_config(f'user_{user_id}', user_config)
        await event.edit("✅ Settings updated")
```

## Error Handling

_Network_ Operations

```python
import aiohttp
import asyncio

async def fetch_api(event, url):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    await event.edit(f"API error: {response.status}")
                    return None
    except asyncio.TimeoutError:
        await event.edit("⏰ Request timeout")
    except Exception as e:
        await kernel.handle_error(e, source="fetch_api", event=event)
    return None
```

_File_ Operations

```python
import aiofiles

async def read_large_file(event, filepath):
    if not os.path.exists(filepath):
        await event.edit("❌ File not found")
        return
    
    try:
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            content = await f.read()
            # Process content
            await event.edit(f"📄 {len(content)} characters")
    except Exception as e:
        await kernel.handle_error(e, source="read_large_file", event=event)
```

## Best Practices

* 1. Resource Management

```python
# Use context managers
async def process_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    
    # Clean up resources
    kernel.cache.set('processed_data', data)
```

* 2. Database Optimization

```python
# Batch operations
async def batch_update(users):
    for user in users:
        await kernel.db_set('users', user['id'], json.dumps(user))
    
    # Use transactions for multiple updates
    await kernel.db_query("BEGIN TRANSACTION")
    # Multiple queries
    await kernel.db_query("COMMIT")
```

* 3. Caching Strategies

```python
# Cache with invalidation
async def get_cached_data(key, ttl=300):
    data = kernel.cache.get(key)
    if data:
        return data
    
    data = await fetch_fresh_data(key)
    if data:
        kernel.cache.set(key, data, ttl=ttl)
    
    return data
```

* 4. Error Recovery

```python
async def resilient_operation():
    for attempt in range(3):
        try:
            return await perform_operation()
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(1 * attempt)
```

## Example Module

```python
# requires: aiohttp, aiofiles
# author: Developer
# version: 2.0.0
# description: Advanced module example

import asyncio
import aiohttp
import json
from telethon import events, Button

def register(kernel):
    client = kernel.client
    
    # Module configuration
    module_config = await kernel.get_module_config(__name__, {
        'enabled': True,
        'api_key': '',
        'cache_ttl': 300
    })
    
    
    # Middleware: Rate limiter
    async def rate_limit_middleware(event, next_handler):
        user_id = event.sender_id
        key = f"rl_{user_id}"
        
        last_time = await kernel.db_get('ratelimit', key)
        current_time = time.time()
        
        if last_time and current_time - float(last_time) < 1:
            await event.edit("⏳ Please wait 1 second between commands")
            return None
        
        await kernel.db_set('ratelimit', key, str(current_time))
        return await next_handler(event)
    
    kernel.add_middleware(rate_limit_middleware)
    
    # Scheduled task: Daily summary
    async def daily_summary():
        if not module_config['enabled']:
            return
        
        count = await kernel.db_get('stats', 'command_count') or 0
        await kernel.send_log_message(f"📊 Daily stats: {count} commands")
        await kernel.db_set('stats', 'command_count', '0')
    
    await kernel.scheduler.add_daily_task(daily_summary, 23, 59)
    
    # Command: Weather with caching
    @kernel.register_command('weather')
    # Get weather for city
    async def weather_handler(event):
        if not module_config['enabled']:
            await event.edit("❌ Module disabled")
            return
        
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit("Usage: .weather <city>")
            return
        
        city = args[1]
        cache_key = f"weather_{city}"
        
        # Check cache
        cached = kernel.cache.get(cache_key)
        if cached:
            await event.edit(f"🌤️ {city}: {cached} (cached)")
            return
        
        # Fetch fresh data
        try:
            weather = await fetch_weather(city)
            kernel.cache.set(cache_key, weather, ttl=module_config['cache_ttl'])
            
            # Update stats
            count = int(await kernel.db_get('stats', 'command_count') or 0)
            await kernel.db_set('stats', 'command_count', str(count + 1))
            
            await event.edit(f"🌤️ {city}: {weather}")
        except Exception as e:
            await kernel.handle_error(e, source="weather_handler", event=event)
            await event.edit("❌ Error fetching weather")
    
```
> [!NOTE]
> All new APIs (_Database, Cache, Scheduler, Middleware_),
> require **MCUB kernel** version `1.0.1.9` or later.
> Check your kernel version with `.py print(f"version kernel: {kernel.VERSION}")` command. (or `info` commad)

## Premium Emoji Guide

**Basic Syntax**

```python
CUSTOM_EMOJI = {
    'check': '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    'error': '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
}

await event.edit(
    f"{CUSTOM_EMOJI['check']} <b>Success!</b>",
    parse_mode='html'
)
```

With Message Helpers

```python
await kernel.edit_with_html(
    event,
    f"{CUSTOM_EMOJI['check']} <b>Operation completed</b>"
)
```

**Finding Emoji IDs**

```python
async for message in client.iter_messages('me', limit=10):
    for entity in message.entities:
        if isinstance(entity, MessageEntityCustomEmoji):
            print(f"ID: {entity.document_id}")
```

## **Inline Query Automation Methods and Inline form**

> In MCUB, the bot specified in config.json can operate in two modes:
> 1. Regular bot mode: using the bot_client to send messages as the bot, for example, to send a message to the admin user.
> 2. Inline mode: using the inline_form method to create inline forms with buttons and other elements, or using the inline_query_and_click method to call an inline query from any bot (including third-party bots).


`inline_form()`
---

> Creating and submitting an inline form in one method.

__Args:__
*    chat_id (int): The ID of the chat to send
*    title (str): The title of the form
*    fields (list/dict, optional): Form fields
*    buttons (list, optional): Buttons in the format `{"text": "1", "type": "callback", "data": "main"}`
*    auto_send (bool): Automatically submit the form
*    **kwargs: Additional parameters

**Returns:**
    __tuple:__ (`success`, `message`) or query string
    
**Example:**
```
buttons = [
    {"text": "1", "type": "callback", "data": "menu_page_1"},
    {"text": "2", "type": "callback", "data": "menu_page_2"}
]
success, message = await kernel.inline_form(
    event.chat_id,
    "menu",
    buttons=buttons
)
if success:
    await event.delete()
```
### __Inline practices__
**Menu_buttons**
```
from telethon import events, Button

def register(kernel):
    client = kernel.client # client
    bot = kernel.bot_client # inline bot
    @kernel.register_command('menu_button') # register command: {kernel.custom_prefix}menu_button. '' <- yes. "" <- not usage
    async def menu_cmd(event):
        buttons = [
            {"text": "1", "type": "callback", "data": "menu_page_1"},
            {"text": "2", "type": "callback", "data": "menu_page_2"}
            # text: text msg inline, type: format buttons, data: callback data
        ]
        success, message = await kernel.inline_form(
            event.chat_id, # chat
            "menu", # text
            buttons=buttons # buttons
        )
        if success:
            await event.delete()
            # edit inline msg for 'message'
            # await bot.edit_message(message.peer_id, message.id, "test")


    async def menu_callback_handler(event):
        data = event.data # data buttons callback

        if data == b'menu_page_1':
            buttons = [
                [
                    Button.inline("edit test", b"menu_edit_1")
                ],
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "menu 1",
                buttons=buttons
            )
        elif data == b'menu_page_2':
            buttons = [
                [
                    Button.inline("edit test", b"menu_edit_1")
                ],
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "menu 2",
                buttons=buttons
            )
        elif data == b'menu_edit_1':
            buttons = [
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "hello word",
                buttons=buttons
                )
        elif data == b'menu_edit_2':
            buttons = [
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "Привет мир",
                buttons=buttons
                )

        else:
            buttons = [
            [
                Button.inline("1", b"menu_page_1")
            ],
            [
                Button.inline("2", b"menu_page_2")
            ]
            ]
            await event.edit(
                "menu",
                buttons=buttons
            )
    # register callback
    kernel.register_callback_handler("menu_", menu_callback_handler)

```
**fields**
```
fields = {
    "name": "user",
    "status": "MCUB user",
    "coin": "100 MCUB coin"
}

success, msg = await kernel.inline_form(
    event.chat_id,
    "👤 profile user",
    fields=fields,
    buttons=[
        {"text": "Play", "type": "callback", "data": "casino_play_callback"},
        {"text": "History", "type": "callback", "data": f"casino_{fields[name]}_history"}
    ]
)

```
__output:__
```
👤 profile user
name: user
status: MCUB user
coin: 100 MCUB coin
[
buttons = [
    [
    play
    ],
    [
    History
    ]
]
]
```
> [!NOTE]
> kernel version 1.0.9.5

`inline_query_and_click()`
---

Performs an inline query through the specified bot and automatically clicks on the selected result. This method handles the complete workflow from query to message sending with configurable parameters.
> [!NOTE]
> kernel version `1.0.9.4`

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

```

`manual_inline_example()`
---

Provides manual control over inline query execution, returning raw results for custom processing. Useful when you need to implement custom logic for result selection or processing.

`send_inline_from_config()`
---

Simplified wrapper that uses the bot **username** configured in __config.json__. For quick usage when you don't need to specify a bot username.

---

# Callback Permission Management 

MCUB includes a built-in callback permission manager to control user access to inline button interactions.

> [!TIP]
> By default, everyone does not have the right to press inline buttons (except ADMIN_ID)

## `CallbackPermissionManager` Class

Manages temporary permissions for callback query patterns.

### Initialization

```python
permission_manager = CallbackPermissionManager()
```

### Methods

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

## Usage Example

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
            await event.answer("⏱️ Session expired!", alert=True)
            return
        
        # Process callback
        await event.edit("Game action processed!")
    
    kernel.register_callback_handler('game_', game_callback_handler)
```

> [!NOTE]
> Available in MCUB kernel version 1.0.2 and later.

---

# Enhanced Registration API v1.0.2

MCUB introduces a new `Register` class with decorator-based registration methods for cleaner module syntax.

### Method Registration

`@kernel.Register.method`
---
You can make your register using the @kernel.Register.method decorator-based

**Usage:**
```python
import kernel # without this, method will not work
from telethon import events

@kernel.Register.method
def custom_register(kernel): # or class
    
    @kernel.register.command('version', alias='v')
    async def version_mcub(event)
        await event.edit(f"Kernel version {kernel.VERSION}")
```

### Event Registration

`@kernel.Register.event(event_type, **kwargs)`
---
Register event handlers with cleaner syntax.

**Event types:** `'newmessage'`, `'messageedited'`, `'messagedeleted'`, `'userupdate'`, `'chatupload'`, `'inlinequery'`, `'callbackquery'`, `'raw'`

**Examples:**
```python
@kernel.Register.event('newmessage', pattern='hello')
async def greeting_handler(event):
    await event.reply("Hi!")

@kernel.Register.event('callbackquery', pattern=b'menu_')
async def menu_handler(event):
    await event.answer("Menu clicked")
```

### Command Registration

`@kernel.Register.command(pattern, **kwargs)`
---
Alternative to `kernel.register_command()` with alias support.

**Parameters:**
- `alias` (str/list): Command aliases
- `more` (str): Additional options

**Example:**
```python
@kernel.Register.command('test', alias=['t', 'check'])
async def test_handler(event):
    await event.edit("Test passed")
    
# All work: .test, .t, .check
```

### Bot Command Registration

`@kernel.Register.bot_command(pattern, **kwargs)`
---
Register bot commands (requires bot client).

**Example:**
```python
@kernel.Register.bot_command('start')
async def start_handler(event):
    await event.respond("Bot started!")

# Also works with arguments
@kernel.Register.bot_command('help topic')
async def help_handler(event):
    await event.respond("Help topic details")
```

### Complete Module Example

```python
@kernel.Register.method
def test(kernel):
    
    
    @kernel.register.event('newmessage', pattern='(?i)ping')
    async def ping_handler(event):
        await event.reply("Pong!")
    
    @kernel.register.bot_command('status')
    async def status_cmd(event):
        if kernel.is_bot_available():
            await event.respond("Bot is running")
```

> [!NOTE]
> Available in MCUB kernel version 1.0.2 and later.  
> `Register.command` supports the same alias system as `kernel.register_command()`.

