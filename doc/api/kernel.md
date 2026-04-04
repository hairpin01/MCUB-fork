# Kernel API Reference

## Kernel Core Variables

The `Kernel` class exposes the following core variables that can be accessed in your modules:

### Module Registries

| Variable | Type | Description |
|----------|------|-------------|
| `kernel.loaded_modules` | `dict` | Dictionary of all currently loaded user modules. Keys are module names (str), values are the module objects. |
| `kernel.system_modules` | `dict` | Dictionary of all loaded system modules (from `modules/` directory). |
| `kernel.command_handlers` | `dict` | Dictionary mapping command names to their handler functions. |
| `kernel.command_owners` | `dict` | Dictionary mapping command names to the module that owns them. |
| `kernel.bot_command_handlers` | `dict` | Dictionary of registered bot commands (starting with `/`). |
| `kernel.bot_command_owners` | `dict` | Dictionary mapping bot command names to owning modules. |
| `kernel.inline_handlers` | `dict` | Dictionary of registered inline query handlers. |
| `kernel.inline_handlers_owners` | `dict` | Dictionary mapping inline handlers to owning modules. |
| `kernel.callback_handlers` | `dict` | Dictionary of registered callback query handlers. |
| `kernel.aliases` | `dict` | Dictionary of command aliases. |

### Runtime State

| Variable | Type | Description |
|----------|------|-------------|
| `kernel.custom_prefix` | `str` | Command prefix (default: `.`). |
| `kernel.config` | `dict` | Persistent kernel configuration storage. |
| `kernel.client` | `TelethonClient` | The main Telethon client instance for Telegram API operations. |
| `kernel.bot_client` | `TelethonClient` or `None` | The inline bot client (if configured). |
| `kernel.inline_bot` | `TelethonClient` or `None` | Alias for `bot_client`. |
| `kernel.catalog_cache` | `dict` | Cache for module catalogs. |
| `kernel.pending_confirmations` | `dict` | Dictionary for pending confirmation dialogs. |
| `kernel.shutdown_flag` | `bool` | Flag indicating if kernel is shutting down. |
| `kernel.power_save_mode` | `bool` | Power saving mode flag. |
| `kernel.repositories` | `list` | List of configured module repositories. |
| `kernel.scheduler` | `TaskScheduler` or `None` | The task scheduler instance. |

### Paths and Directories

| Variable | Type | Description |
|----------|------|-------------|
| `kernel.MODULES_DIR` | `str` | Path to user modules directory (default: `"modules"`). |
| `kernel.MODULES_LOADED_DIR` | `str` | Path to loaded modules directory (default: `"modules_loaded"`). |
| `kernel.IMG_DIR` | `str` | Path to images directory (default: `"img"`). |
| `kernel.LOGS_DIR` | `str` | Path to logs directory (default: `"logs"`). |
| `kernel.CONFIG_FILE` | `str` | Config file name (default: `"config.json"`). |
| `kernel.MODULES_REPO` | `str` | Default modules repository URL. |
| `kernel.UPDATE_REPO` | `str` | Kernel update repository URL. |
| `kernel.default_repo` | `str` | Default repository URL (alias for `MODULES_REPO`). |

### Core Subsystems

| Variable | Type | Description |
|----------|------|-------------|
| `kernel.cache` | `TTLCache` | TTL cache instance for temporary data storage. |
| `kernel.register` | `Register` | Command/handler registration manager. |
| `kernel.callback_permissions` | `CallbackPermissionManager` | Callback permission manager. |
| `kernel.logger` | `KernelLogger` | Structured logging instance. |
| `kernel.version_manager` | `VersionManager` | Kernel version manager. |
| `kernel.db_manager` | `DatabaseManager` | Database manager instance. |
| `kernel.Colors` | `Colors` | ANSI color codes for terminal output. |

### Version and Time

| Variable | Type | Description |
|----------|------|-------------|
| `kernel.VERSION` | `str` | Kernel version string. |
| `kernel.DB_VERSION` | `int` | Database version number. |
| `kernel.start_time` | `float` | Unix timestamp when kernel started. |

---

## Core Methods

### Executing Userbot Commands Programmatically

```python
# Execute a command by calling its handler directly
if 'ping' in kernel.command_handlers:
    await kernel.command_handlers['ping'](event)
```

### Error Handling

`kernel.handle_error(e, source="module:function", event=None)`
Centralized error handling.

```python
try:
    await some_operation()
except Exception as e:
    await kernel.handle_error(e, source="module:function", event=event)
```

### Utility Methods

`kernel.get_thread_id(event)`
Returns the thread ID (topic ID) for a given event in groups with topics enabled.

```python
thread_id = await kernel.get_thread_id(event)
```

`kernel.get_user_info(user_id)`
Retrieves formatted user information for the given user ID.

```python
user_info = await kernel.get_user_info(event.sender_id)
```

`kernel.is_admin(user_id)`
Checks if the specified user ID matches the admin ID of the userbot.

```python
if kernel.is_admin(event.sender_id):
    await event.edit("Admin command executed")
```

`kernel.cprint(text, color='')`
Prints colored text to the console using ANSI escape codes.

```python
kernel.cprint("Success!", kernel.Colors.GREEN)
```

### Kernel Version API

`kernel.get_thread_id(event)` — Thread ID for topics

`kernel.get_user_info(user_id)` — User info formatting

`kernel.is_admin(user_id)` — Admin check

`kernel.cprint(text, color='')` — Colored console output

`kernel.Colors` — ANSI color codes (RESET, RED, GREEN, YELLOW, BLUE, PURPLE, CYAN)
