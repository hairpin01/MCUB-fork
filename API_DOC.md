# MCUB Module API Documentation

Table of Contents

> 1. [Introduction](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md#introduction)
> 2. [Module Structure]()
> 3. [Kernel API Reference](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#kernel-api-reference)
> 4. [Command Registration](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#command-registration)
> 5. [Event Handlers](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#event-handlers)
> 6. [Configuration Management](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#configuration-management)
> 7. [Error Handling](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#error-handling)
> 8. [Best Practices](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#best-practices)
> 9. [Example Module](https://github.com/hairpin01/MCUB-fork/edit/main/API_DOC.md#example-module)

### Introduction

MCUB (Mitrich UserBot) is a modular Telegram userbot framework built on Telethon. This documentation describes the API for creating modules.
 
## Module Structure

Basic Structure,
Every module must have:

· A `register(kernel)` function as the entry point.
· Proper metadata comments at the beginning.
· Only code inside the register function executes on import.

Metadata Format

```python
# requires: library1, library2
# author: Author Name
# version: 1.0.0
# description: Module description here
```

## Kernel API Reference

`kernel.client`
The Telethon client instance for `Telegram API` operations.

Usage:

```python
client = kernel.client
await client.send_message('username', 'Hello')
```

`kernel.custom_prefix`
The command prefix configured for the userbot.

Usage:

```python
prefix = kernel.custom_prefix  # Returns '.' or configured prefix
```

`kernel.config`
Persistent configuration storage for the module.

Methods:
```python
# Get value with default
value = kernel.config.get('key', default_value)

# Set value
kernel.config['key'] = value

# Set default value
kernel.config.setdefault('key', default_value)

# Save configuration (call after modifications)
kernel.save_config()
```

`kernel.handle_error(e, source="module:function", event=None)`
Centralized error handling and logging.

Parameters:

· `e`: Exception object
· `source`: String identifying error source (format: "module:function")
· `event`: Optional event object for context

Usage:
```python
try:
    # operation
except Exception as e:
    await kernel.handle_error(e, source="module:function", event=event)
```

`kernel.register_inline_handler(pattern, function)`

Register an inline query handler.
Parameters:

· `pattern`: String pattern to match inline queries
· `function`: Async function to handle inline queries

Usage:
```python
async def inline_handler(event):
    # handle inline query
    pass

kernel.register_inline_handler('query_pattern', inline_handler)
```
`kernel.register_callback_handler(pattern, function)`

Register a callback query handler.

Parameters:

· `pattern`: String pattern to match callback data (must start with pattern)
· `function`: Async function to handle callbacks

Usage:
```python
async def callback_handler(event):
    data = event.data.decode()
    # handle callback
    pass

kernel.register_callback_handler('module_prefix_', callback_handler)
```
`
kernel.send_log_message(text, file=None)`
Send message to logs chat.

Parameters:

· `text`: Log message text
· `file`: Optional file to send with log

`kernel.get_module_metadata(code)`
Parse module metadata from source code.

`kernel.LOGS_DIR`

Path to logs directory.

`kernel.IMG_DIR`

Path to images directory.

`kernel.VERSION`

Kernel version string.

`kernel.start_time`

Unix timestamp when kernel started.

# Command Registration

## Basic Command

```python
@kernel.register_command('command_name')
# command description here
async def command_handler(event):
    try:
        # command logic
        await event.edit('Response')
    except Exception as e:
        await kernel.handle_error(e, source="command_handler", event=event)
        await event.edit("Error, check logs", parse_mode='html')
```

Command with Arguments

```python
@kernel.register_command('command')
# command with arguments
async def command_handler(event):
    args = event.text.split()
    if len(args) < 2:
        await event.edit('Usage: .command <argument>')
        return
    # process args
```

## Event Handlers

Message Event Handler

```python
from telethon import events

async def message_handler(event):
    # handle incoming message
    pass

client.on(events.NewMessage(incoming=True))(message_handler)
```

Outgoing Message Handler

```python
client.on(events.NewMessage(outgoing=True))(outgoing_handler)
```

Custom Filter Handler

```python
client.on(events.NewMessage(
    func=lambda e: e.text and 'keyword' in e.text
))(keyword_handler)
```

## Configuration Management

Setting Default Configuration

```python
def register(kernel):
    kernel.config.setdefault('module_option', 'default_value')
    kernel.config.setdefault('module_enabled', False)
```

Using Configuration

```python
enabled = kernel.config.get('module_enabled', False)
if enabled:
    # do something
```

Configuration Persistence

```python
# Save after modification
kernel.config['new_setting'] = 'value'
kernel.save_config()
```

## Error Handling

Standard Error Handling Pattern

```python
try:
    # operation that may fail
    result = await some_async_call()
except asyncio.TimeoutError:
    await event.edit('Timeout error')
except Exception as e:
    await kernel.handle_error(e, source="function_name", event=event)
    await event.edit("Error, check logs", parse_mode='html')
```

Network Operations with Timeout

```python
import aiohttp

async def fetch_data(event):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('https://api.example.com') as resp:
                data = await resp.text()
                await event.edit(f'Data: {data[:100]}')
    except asyncio.TimeoutError:
        await event.edit('Request timeout')
    except Exception as e:
        await kernel.handle_error(e, source="fetch_data", event=event)
        await event.edit("Error, check logs", parse_mode='html')
```

# Best Practices

1. Security

· Never use `eval()` or `exec()` without user confirmation
· Check file existence with `os.path.exists()` before operations
· Validate and sanitize user input

2. Asynchronous Operations

· Use async versions of I/O libraries (`aiofiles`, `aiohttp`)
· Always use timeouts for network operations
· Avoid blocking operations

3. Error Management

· Wrap all operations in `try/except` blocks
· Use `kernel.handle_error()` for centralized logging
· Provide user-friendly error messages

4. Code Organization

· Keep module code inside `register()` function
· Use descriptive function and variable names
· Add comments for complex logic

5. Resource Management

· Close files and network connections properly
· Use context managers (`async with`) when available
· Clean up temporary resources

6. Callback Patterns

· Use unique prefixes for callback patterns (e.g., `module_`)
· Handle callback data safely (decode, validate)

7. File Operations

```python
import aiofiles

async def read_file(event, filepath):
    if not os.path.exists(filepath):
        await event.edit('File not found')
        return
    
    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
        await event.edit(f'Content: {content[:500]}')
```

## Example Module

```python
# requires: aiohttp, aiofiles
# author: Developer Name
# version: 1.0.0
# description: Example module for MCUB

import asyncio
import aiohttp
import aiofiles
import os
from telethon import events

def register(kernel):
    client = kernel.client
    prefix = kernel.custom_prefix
    
    # Configuration defaults
    kernel.config.setdefault('example_enabled', True)
    kernel.config.setdefault('example_api_url', 'https://api.example.com')
    
    @kernel.register_command('example')
    # example command description
    async def example_cmd(event):
        try:
            # Check if module is enabled
            if not kernel.config.get('example_enabled', True):
                await event.edit('Module is disabled')
                return
            
            # Process command with timeout
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = kernel.config.get('example_api_url')
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.text()
                        await event.edit(f'Response: {data[:200]}')
                    else:
                        await event.edit(f'API error: {response.status}')
        except asyncio.TimeoutError:
            await event.edit('Request timeout')
        except Exception as e:
            await kernel.handle_error(e, source="example_cmd", event=event)
            await event.edit("Error, check logs", parse_mode='html')
    
    # Inline handler example
    async def inline_example(event):
        builder = event.builder.article(
            title='Inline Result',
            text='Example inline response',
            buttons=[[Button.inline('Button', b'example_btn')]]
        )
        await event.answer([builder])
    
    kernel.register_inline_handler('example', inline_example)
    
    # Callback handler example
    async def callback_example(event):
        try:
            data = event.data.decode()
            if data == 'example_btn':
                await event.answer('Button clicked')
                await event.edit('Updated message')
        except Exception as e:
            await kernel.handle_error(e, source="callback_example", event=event)
    
    kernel.register_callback_handler('example_', callback_example)
    
    # Event watcher example
    async def message_watcher(event):
        if event.text and 'hello' in event.text.lower():
            await event.reply('Hello there!')
    
    client.on(events.NewMessage(incoming=True))(message_watcher)
```

1. All modules must be self-contained within the register() function
2. Use only the provided kernel API methods
3. Follow the error handling pattern consistently
4. Test modules with various input scenarios
5. Document any external dependencies in the metadata
6. Keep modules focused on a single purpose
7. Update configuration with kernel.save_config() after changes


## How to use Premium Emoji in MCUB Modules
> Premium Emoji Integration Guide for MCUB

Overview:
Telethon v1.24+ supports premium (custom) emoji using HTML-like tags. This guide
explains how to implement them in MCUB modules.

1. BASIC SYNTAX:
   Use `<tg-emoji>` tag with emoji-id attribute:
   
   Format: `<tg-emoji emoji-id="DOCUMENT_ID">PLACEHOLDER</tg-emoji>`
   
   Example: `<tg-emoji emoji-id="5323463142775202324">🔴</tg-emoji>`

2. COMPATIBILITY:
   - Works with HTML parse_mode
   - Telethon v1.24+ required
   - Account must have Telegram Premium
   - Placeholder emoji is shown to non-premium users

3. IMPLEMENTATION STEPS:

   Step 1: Add emoji dictionary at module top:
   ```python
   CUSTOM_EMOJI = {
       'loading': '<tg-emoji emoji-id="5323463142775202324">🔴</tg-emoji>',
       'success': '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
   }
```

Step 2: Use in messages with parse_mode='html':

```python
   await event.edit(
       f'{CUSTOM_EMOJI["success"]} <b>Module loaded!</b>',
       parse_mode='html'
   )
```

Step 3: For editing messages, use kernel's helper:

```python
   if hasattr(kernel, 'edit_with_emoji'):
       await kernel.edit_with_emoji(event, f'{CUSTOM_EMOJI["loading"]} Loading...')
```

1. FINDING EMOJI IDs:
   Method 1: Use official Telegram app
   · Send emoji to "Saved Messages"
   · Fetch with Telethon and inspect message.entities
   · Look for `MessageEntityCustomEmoji.document_id`
   Method 2: Extract from existing message:
   ```python
     async for message in client.iter_messages(chat):
         for entity in message.entities:
             if isinstance(entity, MessageEntityCustomEmoji):
                 print(f"ID: {entity.document_id}")
   ```
2. BEST PRACTICES:
   · Store emoji IDs in configurable dictionary
   · Provide fallback for non-premium users
   · Test with `parse_mode='html'`
   · Use consistent placeholder emoji (same visual meaning)
3. EXAMPLE MODULE STRUCTURE:
   ```python
   CUSTOM_EMOJI = {
       'check': '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
       'error': '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
   }
   
   def register(kernel):
       @kernel.register_command('test')
       async def test_handler(event):
           await event.edit(
               f'{CUSTOM_EMOJI["check"]} <b>Test successful!</b>',
               parse_mode='html'
           )
   ```
4. TROUBLESHOOTING:
   Problem: Emoji not showing
   Solution:
   · Verify Telethon version >= 1.24
   · Check `parse_mode='html'` is set
   · Ensure account has Telegram Premium
   · Verify document_id is correct
   Problem: HTML tags not working
   Solution:
   · Use `<tg-emoji>` not `<emoji>` tag
   · Escape HTML characters with `html.escape()`
   · Test without emoji first
5. ADVANCED USAGE:
   · Combine with buttons and formatting
   · Use in inline mode
   · Cache emoji IDs for performance
   · Create emoji picker module
> [!TIP]
> This documentation is for MCUB v1.0.2+ with Telethon v1.24+.
> For older versions,use the legacy `<emoji document_id=...>` format.




