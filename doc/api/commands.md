# Command Registration

← [Index](../../API_DOC.md)

## Standard Registration

```python
@kernel.register.command('example')
async def example_handler(event):
    await event.edit("Example command")
```

## Registration with Aliases

```python
@kernel.register.command('example', alias=['ex', 'e'])
async def example_handler(event):
    await event.edit(f"Works with {kernel.custom_prefix}example")
```

## Multiple Commands

```python
def register(kernel):
    @kernel.register.command('cmd1')
    async def handler1(event):
        await event.edit("Command 1")

    @kernel.register.command('cmd2')
    async def handler2(event):
        await event.edit("Command 2")
```

## Owner-Only Commands

```python
@kernel.register.command('admincmd')
@kernel.register.owner(only_admin=True)
async def admin_only_handler(event):
    await event.edit("Admin only!")

@kernel.register.command('trustedcmd')
@kernel.register.owner()
async def trusted_handler(event):
    await event.edit("Admin or trusted user!")
```

## Decorators

`kernel.register.owner(only_admin=False)` — Decorator to restrict a handler to the bot owner (admin) or trusted users.

```python
@kernel.register.owner()
async def owner_or_trusted(event):
    await event.reply("Hello, owner!")

@kernel.register.owner(only_admin=True)
async def admin_only(event):
    await event.reply("Admin only!")
```

## Command Aliases Management

```python
aliases = kernel.register.get_all_aliases()
# {'ex': 'example', 'p': 'ping'}

cmd_alias = kernel.register.get_command_alias('ping')
# 'p' or None
```

`kernel.register.get_all_aliases()` — Get all registered command aliases.

`kernel.register.get_command_alias(command)` — Get the alias for a specific command.

## Inline Bot Information

```python
bot_info = kernel.register.get_use_bot()
# {'available': True, 'connected': True, 'username': 'MCUB_bot'}
```

`kernel.register.get_use_bot()` — Get information about inline bot usage.
