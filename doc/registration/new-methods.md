# New Registration Methods v1.0.3

## Query Registered Handlers

`kernel.register.get_commands()` — Get all registered userbot commands.

```python
commands = kernel.register.get_commands()
for cmd, handler in commands.items():
    print(f"Command: {cmd}")
```

`kernel.register.get_bot_commands()` — Get all registered Telegram bot commands.

```python
bot_cmds = kernel.register.get_bot_commands()
for cmd, (pattern, handler) in bot_cmds.items():
    print(f"Bot command: /{cmd}")
```

`kernel.register.get_watchers()` — Get all registered watchers from all modules.

```python
watchers = kernel.register.get_watchers()
print(f"Active watchers: {len(watchers)}")
```

`kernel.register.get_events()` — Get all registered event handlers.

```python
events = kernel.register.get_events()
print(f"Active event handlers: {len(events)}")
```

`kernel.register.get_loops()` — Get all registered InfiniteLoop objects.

```python
loops = kernel.register.get_loops()
for loop in loops:
    print(f"Loop: {loop.func.__name__}, running: {loop.status}")
```

## Unregister Handlers

`kernel.register.unregister_command(cmd)` — Unregister a userbot command by name.

```python
if kernel.register.unregister_command("ping"):
    print("Command 'ping' removed")
```

`kernel.register.unregister_bot_command(cmd)` — Unregister a Telegram bot command.

```python
if kernel.register.unregister_bot_command("start"):
    print("Bot command '/start' removed")
```

## Bug Fixes in v1.0.3

- **`@register.command`**: Fixed regex escaping for custom prefix characters
- **`@register.command`** and **`@register.bot_command`**: Added duplicate command detection
- **`@register.method`**: Methods are now tracked per-module for proper cleanup on unload
