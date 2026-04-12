# Best Practices

← [Index](../../API_DOC.md)

This section covers recommended patterns and modern APIs for writing MCUB modules.

---

## Module Structure

### Required Header Fields

Every module should include these header comments:

```python
# author: Your Name
# version: 1.0.0
# description: Brief description of what the module does
```

### Optional Header Fields

```python
# requires: aiohttp, requests    # pip dependencies
# banner_url: https://example.com/banner.png
# scop: inline                    # requires inline bot
# scop: kernel min v1.0.2        # minimum kernel version
```

### Recommended Structure

```python
# author: Your Name
# version: 1.0.0
# description: Module description
# requires: aiohttp

import asyncio
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Boolean, String

def register(kernel):
    # 1. Define configuration
    config = ModuleConfig(...)

    # 2. Define commands
    @kernel.register.command('cmd')
    async def handler(event):
        ...

    # 3. Define background tasks
    @kernel.register.loop(interval=300)
    async def background_task(kernel):
        ...

    # 4. Lifecycle callbacks
    @kernel.register.on_load()
    async def init(k):
        ...
```

---

## Modern Module Configuration

Use `ModuleConfig` for declarative configuration with validation and UI support:

```python
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Boolean, String, Choice, Integer

def register(kernel):
    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable module",
            validator=Boolean(default=True)
        ),
        ConfigValue(
            "api_url",
            "https://api.example.com",
            description="API endpoint URL",
            validator=String(default="https://api.example.com")
        ),
        ConfigValue(
            "timeout",
            30,
            description="Request timeout (seconds)",
            validator=Integer(default=30, min=1, max=300)
        ),
        ConfigValue(
            "mode",
            "default",
            description="Operation mode",
            validator=Choice(choices=["default", "fast", "safe"], default="default")
        )
    )

    async def startup():
        config_dict = await kernel.get_module_config(__name__, {
            "enabled": True,
            "api_url": "https://api.example.com",
            "timeout": 30,
            "mode": "default"
        })
        config.from_dict(config_dict)
        await kernel.save_module_config(__name__, config.to_dict())
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(startup())

    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        return live_cfg if live_cfg else config
```

---

## Error Handling Pattern

Always wrap async operations in try-except blocks:

```python
@kernel.register.command('safe')
async def safe_handler(event):
    try:
        result = await risky_operation()
        await event.edit(f"Result: {result}")

    except ValueError as e:
        await kernel.logger.warning(f"Invalid value: {e}")
        await event.edit("Invalid input")

    except ConnectionError as e:
        await kernel.logger.error(f"Connection failed: {e}")
        await event.edit("Network error")

    except Exception as e:
        await kernel.handle_error(e, source="safe_handler", event=event)
        await event.edit("Unexpected error occurred")
```

### Error Logging Levels

| Level | When to use |
|-------|-------------|
| `debug` | Detailed debugging info (dev only) |
| `info` | Normal operation events |
| `warning` | Recoverable issues |
| `error` | Failed operations |
| `critical` | System-level failures |

---

## Async Best Practices

### Use asyncio.gather for Parallel Operations

```python
@kernel.register.command('parallel')
async def parallel_handler(event):
    results = await asyncio.gather(
        operation1(),
        operation2(),
        operation3(),
        return_exceptions=True  # Don't let one failure cancel all
    )
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    await event.edit(f"Completed: {success_count}/3")
```

### Proper Cleanup with asyncio Tasks

```python
def register(kernel):
    tasks = []

    @kernel.register.on_load()
    async def init(k):
        # Start background task
        task = asyncio.create_task(background_loop())
        tasks.append(task)

    @kernel.register.uninstall()
    async def cleanup(k):
        # Cancel all tasks
        for task in tasks:
            task.cancel()
```

### Avoid Blocking Operations

```python
# BAD - blocks event loop
@kernel.register.command('bad')
async def bad_handler(event):
    time.sleep(5)  # Don't do this!

# GOOD - async sleep
@kernel.register.command('good')
async def good_handler(event):
    await asyncio.sleep(5)  # Non-blocking
```

---

## Resource Management with Cache

Use the built-in cache to avoid repeated API calls:

```python
@kernel.register.command('cached')
async def cached_handler(event):
    cache_key = f"{__name__}_data"

    data = kernel.cache.get(cache_key)
    if data is None:
        data = await fetch_data()
        kernel.cache.set(cache_key, data, ttl=300)  # 5 min TTL

    await event.edit(f"Cached data: {data}")
```

### Cache TTL Guidelines

| Data Type | Recommended TTL |
|-----------|----------------|
| User data | 300-600 seconds |
| API responses | 60-300 seconds |
| Static data | 3600+ seconds |
| Real-time data | No cache |

---

## Database Best Practices

### Use Module-Scoped Keys

```python
# Good - module-scoped
await kernel.db_set(__name__, 'counter', '1')
value = await kernel.db_get(__name__, 'counter')

# Avoid - global keys
await kernel.db_set('counter', 'user1', '1')  # Namespace collision
```

### Key Naming Convention

```python
# Use descriptive keys
await kernel.db_set(__name__, 'last_fetch_time', timestamp)
await kernel.db_set(__name__, 'user_count', count)

# Avoid abbreviated keys
await kernel.db_set(__name__, 'lft', timestamp)  # Hard to understand
```

---

## Security Best Practices

### Never Log Sensitive Data

```python
# BAD
kernel.logger.info(f"API Key: {api_key}")

# GOOD
kernel.logger.debug("API request sent")
```

### Validate User Input

```python
@kernel.register.command('div')
async def div_handler(event):
    args = get_args(event)
    if len(args) < 2:
        await event.edit("Usage: .div <a> <b>")
        return

    try:
        a, b = float(args[0]), float(args[1])
        if b == 0:
            await event.edit("Cannot divide by zero")
            return
    except ValueError:
        await event.edit("Invalid numbers")
        return
```

### Use Secrets for API Keys

```python
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Secret

config = ModuleConfig(
    ConfigValue(
        "api_key",
        "",
        description="API Key (keep secret)",
        validator=Secret(default="")
    )
)
```

---

## Performance Tips

### Batch Database Operations

```python
# Instead of multiple writes
for item in items:
    await kernel.db_set(__name__, item.key, item.value)

# Use a single transaction if possible
```

### Limit Response Size

```python
@kernel.register.command('large')
async def large_handler(event):
    # Limit output to prevent message truncation
    results = await fetch_all()
    truncated = results[:100]  # Telegram limit is ~4096 chars
    await event.edit(f"First 100 of {len(results)}: ...")
```

### Use Pagination for Large Lists

```python
@kernel.register.command('users')
async def users_handler(event):
    all_users = await fetch_users()
    # Display in chunks
    chunk_size = 10
    for i in range(0, min(len(all_users), 50), chunk_size):
        chunk = all_users[i:i+chunk_size]
        await event.edit('\n'.join(chunk))
        await asyncio.sleep(1)  # Rate limit
```

---

## Command Design

### Keep Commands Simple

```python
# Good - single responsibility
@kernel.register.command('ping')
async def ping(event):
    await event.edit("Pong!")

# Avoid - too much in one command
@kernel.register.command('doeverything')
async def bad_handler(event):
    # 500 lines of code
    ...
```

### Use Aliases for Common Commands

```python
@kernel.register.command('hello', alias=['hi', 'hey'])
async def hello_handler(event):
    await event.edit("Hello!")
```

### Document Commands with Comments

```python
@kernel.register.command('stats')
# show user statistics
async def stats_handler(event):
    ...
```
