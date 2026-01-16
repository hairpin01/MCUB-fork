
# `MCUB` Module API Documentation `1.0.1.9.2`

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
> 15. [Inline Query Automation Methods](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#inline-query-automation-methods)

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
The Telethon client instance for Telegram API operations.

**Usage:**

```python
await kernel.client.send_message('username', 'Hello')
```

`kernel.custom_prefix`
Command prefix (default: '`.`').

`kernel.config`
Persistent configuration storage.

Usage:
```python
kernel.config['key'] = 'value'
kernel.save_config()
```

`kernel.logger`
Structured logging instance.

**Usage:**

```python
kernel.logger.debug("Debug message")
kernel.logger.info("Info message")
kernel.logger.warning("Warning message")
kernel.logger.error("Error message")
```

Logging Methods

`kernel.log_debug(message)`
Log debug message.

`kernel.log_info(message)`
Log info message.

`kernel.log_warning(message)`
Log warning message.

`kernel.log_error(message)`
Log error message.

**Usage:**

```python
kernel.log_info("Module loaded successfully")
```

### Error Handling

`kernel.handle_error(e, source="module:function", event=None)`
Centralized error handling.

**Usage:**

```python
try:
    await some_operation()
except Exception as e:
    await kernel.handle_error(e, source="module:function", event=event)
```

Registration Methods

`kernel.register_command(pattern, func=None)`
Register a command handler.

`kernel.register_inline_handler(pattern, function)`
Register inline query handler.

`kernel.register_callback_handler(pattern, function)`
Register callback query handler.

**Usage:**

```python
@kernel.register_command('test')
async def test_handler(event):
    await event.edit("Test command")
```

### Utility Properties

`kernel.LOGS_DIR` - Path to logs directory
`kernel.IMG_DIR` - Path to images directory
`kernel.VERSION` - Kernel version string
`kernel.start_time` - Kernel start timestamp



kernel.get_thread_id(event)

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
kernel.cprint("Module loaded successfully", kernel.Colors.GREEN)

# Error message
kernel.cprint("Failed to load module", kernel.Colors.RED)

# Info message
kernel.cprint("Initializing database...", kernel.Colors.CYAN)
```

`kernel.Colors` Class

> Description:
> Static class containing ANSI escape codes for terminal text coloring. Used by kernel.cprint() method.

Class Variables:

· RESET = '\033[0m' - Reset to default terminal color
· RED = '\033[91m' - Bright red
· GREEN = '\033[92m' - Bright green
· YELLOW = '\033[93m' - Bright yellow
· BLUE = '\033[94m' - Bright blue
· PURPLE = '\033[95m' - Bright purple
· CYAN = '\033[96m' - Bright cyan

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

### Message Helpers
`
kernel.send_with_emoji(chat_id, text, **kwargs)`
Send message with custom emoji support.

`kernel.format_with_html(text, entities)`
Format text with Telegram entities to HTML.

`kernel.edit_with_html(event, html_text, **kwargs)`
`kernel.reply_with_html(event, html_text, **kwargs)`
`kernel.send_with_html(chat_id, html_text, **kwargs)`
`kernel.send_file_with_html(chat_id, html_text, file, **kwargs)`

## Database API

MCUB provides a `SQLite` database interface for persistent storage.

**Basic Operations**

`await kernel.db_set(module, key, value)`
Store **key-value** pair for module.

`await kernel.db_get(module, key)`
Retrieve **value** for module.

`await kernel.db_delete(module, key)`
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
Get module-specific configuration.

`await kernel.save_module_config(module_name, config)`
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
Store value in cache.

`kernel.cache.get(key)`
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
    kernel.log_info("Backup completed")

# Run every 5 minutes
await kernel.scheduler.add_interval_task(backup_data, 300)
```

Daily Tasks

`await kernel.scheduler.add_daily_task(func, hour, minute)`
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
    kernel.log_info(f"Message from {event.sender_id}: {event.text[:50]}")
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
    kernel.log_info(f"New message: {event.chat_id} - {event.text[:100]}")

kernel.client.on(events.NewMessage(incoming=True))(message_logger)
```

Edited Message

```python
async def edit_logger(event):
    kernel.log_info(f"Message edited: {event.id}")

kernel.client.on(events.MessageEdited(incoming=True))(edit_logger)
```

Custom Filter

```python
async def keyword_handler(event):
    if "urgent" in event.text.lower():
        await kernel.send_log_message(f"⚠️ Urgent: {event.text[:200]}")

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
    
    # Log module load
    kernel.log_info(f"Module {__name__} loaded with config: {module_config}")
    
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
    
    # Inline handler
    async def weather_inline(event):
        query = event.text.strip()
        if not query:
            return
        
        weather = await fetch_weather(query)
        builder = event.builder.article(
            title=f"Weather in {query}",
            text=f"🌤️ {weather}",
            buttons=[
                [Button.inline('Refresh', f'weather_refresh_{query}'.encode())]
            ]
        )
        await event.answer([builder])
    
    kernel.register_inline_handler('weather', weather_inline)
    
    # Callback handler
    async def weather_callback(event):
        data = event.data.decode()
        if data.startswith('weather_refresh_'):
            city = data.split('_', 2)[2]
            weather = await fetch_weather(city)
            await event.edit(f"🔄 {city}: {weather}")
    
    kernel.register_callback_handler('weather_refresh_', weather_callback)
    
    async def fetch_weather(city):
        # Simulated API call
        await asyncio.sleep(0.5)
        weather_data = {
            'Moscow': '☀️ 22°C',
            'London': '🌧️ 15°C',
            'Tokyo': '⛅ 25°C'
        }
        return weather_data.get(city, '❓ Unknown city')
```

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

## **Inline Query Automation Methods**

`inline_query_and_click()`

Performs an inline query through the specified bot and automatically clicks on the selected result. This method handles the complete workflow from query to message sending with configurable parameters.

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

# With buttons and reply
success, message = await kernel.inline_query_and_click(
    chat_id=event.chat_id,
    query="video meme",
    buttons=[[Button.url("Source", "https://example.com")]],
    reply_to=event.message.id
)
```

`manual_inline_example()`

Provides manual control over inline query execution, returning raw results for custom processing. Useful when you need to implement custom logic for result selection or processing.

`send_inline_from_config()`

Simplified wrapper that uses the bot **username** configured in __config.json__. For quick usage when you don't need to specify a bot username.

---
> [!NOTE]
> All new APIs (_Database, Cache, Scheduler, Middleware_),
> require **MCUB kernel** version `1.0.1.9` or later.
> Check your kernel version with `.info` command.
