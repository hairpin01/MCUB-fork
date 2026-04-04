# Database API

← [Index](../../API_DOC.md)

> [!IMPORTANT]
> There is no `kernel.db` object in current kernels. Use the methods below.

## Query Methods

`kernel.db_query(query, parameters)`
Execute a read-only SQL query.

**Parameters:**
- `query` (str): SQL query (`SELECT`, `PRAGMA`, or `EXPLAIN`)
- `parameters` (tuple): Query parameters

**Returns:** list of rows

**Security notes:**
- Only `SELECT` / `PRAGMA` / `EXPLAIN` are allowed.
- Write operations like `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, etc. are blocked.

**Usage:**
```python
rows = await kernel.db_query(
    "SELECT module, key, value FROM module_data WHERE module = ?",
    ("mymodule",),
)
```

`kernel.db_conn`
Get the raw database connection.

**Returns:** `aiosqlite.Connection | None`

**Usage:**
```python
conn = kernel.db_conn
```

---

## Key-Value Database API

A simpler high-level API built on top of the raw SQL database. Stores arbitrary values under a `(module, key)` pair — no table management required.

### `kernel.db_set(module, key, value)`

Store a value.

**Parameters:**
- `module` (str): Namespace — typically your module name
- `key` (str): Key
- `value` (Any): Will be stored as string (`str(value)`)

**Notes:**
- `module` and `key` must match `^[a-zA-Z0-9_-]+$`
- Max length for `module`/`key`: 64
- Raises `ValueError` on invalid identifiers

**Usage:**
```python
await kernel.db_set('mymodule', 'last_run', '2024-01-01')
```

### `kernel.db_get(module, key)`

Retrieve a stored value.

**Returns:** str | None (via await)

**Usage:**
```python
value = await kernel.db_get('mymodule', 'last_run')
```

### `kernel.db_delete(module, key)`

Delete a stored value.

**Usage:**
```python
await kernel.db_delete('mymodule', 'last_run')
```

---

## Usage Examples

### Storing User Data

```python
@kernel.register.command('remember')
async def remember(event):
    args = event.text.split()
    if len(args) < 2:
        await event.edit("Usage: .remember <key> <value>")
        return

    key = args[1]
    value = ' '.join(args[2:])
    await kernel.db_set('mymodule', key, value)
    await event.edit(f"Saved: {key} = {value}")

@kernel.register.command('recall')
async def recall(event):
    args = event.text.split()
    if len(args) < 2:
        await event.edit("Usage: .recall <key>")
        return

    key = args[1]
    value = await kernel.db_get('mymodule', key)
    if value:
        await event.edit(f"{key} = {value}")
    else:
        await event.edit("Key not found")
```
