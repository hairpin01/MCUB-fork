# Introduction

← [Index](../../API_DOC.md)

**MCUB** (`Mitrich UserBot`) is a modular Telegram userbot framework built on [Telethon-MCUB](https://github.com/hairpin01/Telethon-MCUB).

## Features

- **Modules** — create plugins in `modules/` and `modules_loaded/`
- **Commands** — register commands with `@kernel.register.command()`
- **Watchers** — track messages with `@kernel.register.watcher()`
- **Events** — handle events with `@kernel.register.event()`
- **Inline bots** — create inline forms and buttons
- **Scheduler** — schedule tasks with `kernel.scheduler`

## Quick Start

### 1. Create a module

```python
# modules/hello.py
# author: Your Name
# description: Hello module

def register(kernel):
    @kernel.register.command('hello')
    # say hello
    async def hello_handler(event):
        await event.edit("Hello, World!")
```

### 2. Run

```bash
python3 -m core
```

Use `.hello` in any chat.

## Learn More

- [Module Structure](module-structure.md) — module structure, headers, directives
- [Command Registration](../api/commands.md) — command registration
- [Best Practices](../guides/best-practices.md) — recommended patterns
