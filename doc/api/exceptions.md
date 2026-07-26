# Exception Reference

← [Index](../../API_DOC.md)

Custom exceptions used throughout the MCUB kernel.

```python
from core.lib.utils.exceptions import CommandConflictError, McubTelethonError, CallInsecure
```

---

## `CommandConflictError`

Raised when a command or alias is already registered by another module.

```python
from core.lib.utils.exceptions import CommandConflictError

try:
    @kernel.register.command("ping")
    async def ping(event):
        await event.edit("Pong!")
except CommandConflictError as e:
    kernel.logger.warning(f"Command conflict: {e}")
    # e.conflict_type - 'command' or 'alias'
    # e.command - the conflicting command name
```

**Attributes:**
- `conflict_type` (`str | None`) - `"command"` or `"alias"`
- `command` (`str | None`) - The conflicting command name

**Raised by:**
- `@kernel.register.command()` - if command or alias already exists
- `@kernel.register.bot_command()` - if bot command already exists
- `kernel.register.unregister_command()` - if the command is not registered

---

## `McubTelethonError`

Raised when Telethon-MCUB is not installed or has an installation issue.

```python
from core.lib.utils.exceptions import McubTelethonError

# Typically raised during kernel startup:
# "YOU is not install telethon-mcub, please run:
#  'pip install -U telethon-mcub' and 'pip uninstall telethon -y'!"
```

Causes the kernel to crash immediately with a clear installation instruction.

---

## `CallInsecure`

Raised when a module attempts to access protected kernel internals, preventing security bypasses.

```python
from core.lib.utils.exceptions import CallInsecure

try:
    # Module tries to access something it shouldn't
    result = kernel._some_private_attr
except CallInsecure as e:
    print(e)  # "Module 'MyModule' attempted insecure access to '_some_private_attr'"
```

**Attributes:**
- `name` (`str`) - The attribute name that was accessed
- `module_name` (`str | None`) - The module that attempted the access

---

## Error Handling Patterns

### Catching and handling errors in modules:

```python
@kernel.register.command("safe_cmd")
async def safe_handler(event):
    try:
        result = await risky_operation()
        await event.edit(f"Result: {result}")

    except CommandConflictError as e:
        await kernel.logger.warning(f"Command conflict: {e}")
        await event.edit(f"❌ Conflict: {e.command}")

    except CallInsecure as e:
        await kernel.logger.error(f"Security violation: {e}")
        await event.edit("❌ Security error")

    except Exception as e:
        await kernel.handle_error(e, message="Unexpected error", event=event)
        await event.edit("❌ An error occurred")
```

### Using `kernel.handle_error()`:

```python
try:
    await operation()
except Exception as e:
    await kernel.handle_error(
        e,
        message="MyModule: operation failed",
        event=event,
    )
```
> [!TIP]
> See [Error Handling](errors.md) for more details on `kernel.handle_error()`.
