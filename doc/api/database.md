# Database API

← [Index](../../API_DOC.md)

MCUB uses SQLite for module data storage. Access via `self.db` (class-style) or `kernel.db_manager` (function-style).

> [!TIP]
> For class-style modules, see [Class-Style Modules](../registration/class-style.md) for complete examples.

## Key-Value Storage

Simple `(module, key)` storage — module manages its own data.

### `db.db_set(module, key, value)`

Store a value.

```python
await self.db.db_set("mymodule", "counter", 0)
await self.db.db_set("mymodule", "data", {"key": "value"})
```

**Parameters:**
- `module` (str): Namespace (usually `self.name`)
- `key` (str): Key
- `value` (Any): Any value (converted to string)

### `db.db_get(module, key)`

Retrieve a value.

```python
value = await self.db.db_get("mymodule", "counter")
# value = "0" (string!) or None
```

**Returns:** `str | None`

### `db.db_delete(module, key)`

Delete a value.

```python
await self.db.db_delete("mymodule", "counter")
```

## Raw SQL (read-only)

### `db.db_query(query, parameters)`

Execute SQL query (SELECT/PRAGMA/EXPLAIN only).

```python
rows = await self.db.db_query(
    "SELECT key, value FROM module_data WHERE module = ?",
    ("mymodule",),
)
```

> [!CAUTION]
> Write operations `INSERT`, `UPDATE`, `DELETE`, `DROP` are blocked for security.

## Module-Level Access

For function-style modules use `kernel.db_manager`:

```python
from typing import Any
from telethon import events

def register(kernel: Any) -> None:
    @kernel.register.command("save")
    async def save_cmd(event: events.NewMessage.Event) -> None:
        await kernel.db_manager.db_set("mymodule", "key", "value")

    @kernel.register.command("load")
    async def load_cmd(event: events.NewMessage.Event) -> None:
        value: str | None = await kernel.db_manager.db_get("mymodule", "key")
        await event.edit(f"Value: {value}")
```

## Examples

### Persistent Counter (class-style)

```python
from typing import Self
from telethon import events
from core.lib.loader.module_base import ModuleBase, command

class CounterModule(ModuleBase):
    name = "Counter"

    @command("count")
    async def cmd_count(self, event: events.NewMessage.Event) -> None:
        count: int = 0
        saved: str | None = await self.db.db_get(self.name, "count")
        if saved:
            count = int(saved)
        count += 1
        await self.db.db_set(self.name, "count", count)
        await event.edit(f"Count: {count}")
```

### Storing Complex Data (class-style)

```python
import json
from telethon import events
from core.lib.loader.module_base import ModuleBase, command

class RememberModule(ModuleBase):
    name = "Remember"

    @command("remember")
    async def cmd_remember(self, event: events.NewMessage.Event) -> None:
        args: list[str] = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit("Usage: remember <text>")
            return

        saved: str | None = await self.db.db_get(self.name, "memory")
        memory: list[str] = json.loads(saved) if saved else []
        memory.append(args[1])
        await self.db.db_set(self.name, "memory", json.dumps(memory))
        await event.edit(f"Saved! Total: {len(memory)}")
```
```
