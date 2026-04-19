# Callback Permission Management

← [Index](../../API_DOC.md)

MCUB includes a built-in callback permission manager to control user access to inline button interactions.

> [!TIP]
> By default, only users with ADMIN_ID have the right to press inline buttons.

## CallbackPermissionManager Class

Manages temporary permissions for callback query patterns.

### Methods

`allow(user_id, pattern, duration_seconds=60)` — Grant permission for a user to trigger callbacks.

`is_allowed(user_id, pattern)` — Check if a user has permission for a callback pattern. Returns `bool`.

`prohibit(user_id, pattern=None)` — Revoke permission(s) for a user.

`cleanup()` — Remove expired permissions (automatically called internally).

### Usage

```python
from kernel import CallbackPermissionManager

perm_mgr = CallbackPermissionManager()

@kernel.register.command('start_game')
async def start_handler(event):
    perm_mgr.allow(event.sender_id, 'game_', duration_seconds=300)
    await event.edit("Game started!")

async def game_callback_handler(event):
    if not perm_mgr.is_allowed(event.sender_id, event.data):
        await event.answer("Session expired!", alert=True)
        return
    await event.edit("Game action processed!")

kernel.register_callback_handler('game_', game_callback_handler)
```

---

## InlineManager Class (core_inline)

Manages user permissions for inline bot interactions.

```python
from core_inline.lib.manager import InlineManager

inline_mgr = InlineManager(kernel)
```

### Methods

`is_admin(user_id)` — Check if user is the bot admin.

`is_allowed(user_id, command=None)` — Check if user is allowed to use inline commands.

`allow_user(user_id, command=None)` — Grant permission to a user.

`deny_user(user_id, command=None)` — Revoke permission from a user.

`get_allowed_users(command=None)` — Get list of allowed users.

`clear_all()` — Clear all permissions.

### Auto-generated inline callbacks (token → handler)

You can pass a callable `callback` directly in the button dict. The inline manager generates `callback_data` tokens and stores the mapping in `kernel.inline_callback_map` for the lifetime of the form (TTL). Expired tokens are cleaned automatically when forms are created and on every press.

### Usage

```python
inline_mgr = InlineManager(kernel)

# Check if user can use inline
if await inline_mgr.is_allowed(event.sender_id):
    await event.respond("Allowed!")

# Allow user globally
await inline_mgr.allow_user(123456789)

# Allow user for specific command
await inline_mgr.allow_user(123456789, "search")

# List allowed users
users = await inline_mgr.get_allowed_users()
```

---

## Temporary Inline Commands

MCUB supports temporary inline command handlers via `kernel.register.inline_temp()`.

### Register.register_inline_temp()

```python
form_id = kernel.register.inline_temp(
    handler,              # async callable
    ttl=300,            # time-to-live in seconds
    article=None,        # callable returning article builder
    data=None,           # arbitrary data passed to handler
    allow_user=None,     # int, list[int], or "all"
    allow_ttl=100,      # permission TTL
)
```

**Parameters:**
- `handler`: Async function `async def handler(event, args, data=None)` or `async def handler(event, args)`
- `ttl`: Seconds before handler expires (default: 300)
- `article`: Optional `lambda event: event.builder.article(...)`
- `data`: Any data accessible in handler
- `allow_user`: Restrict to specific user(s) or "all"
- `allow_ttl`: Permission duration in seconds

**Returns:**
- 8-character uuid string used as inline command

### Usage

```python
@kernel.register.method
async def setup(kernel):
    form_id = kernel.register.inline_temp(
        self.handle_search,
        ttl=600,
        article=lambda e: e.builder.article("Search", text="Enter query..."),
        data={"timeout": 30}
    )
    # form_id = "a1b2c3d4"

async def handle_search(self, event, args, data=None):
    # args = "query text" (everything after form_id)
    await event.answer(f"Searching: {args}")
```

### Triggering

1. User types: `@bot <form_id> <args>`
2. Bot shows article
3. User sends article → handler called with `(event, args, data)`

### Class-Style Usage

```python
from core.lib.loader.module_base import ModuleBase, inline_temp

class MyModule(ModuleBase):
    name = "MyModule"

    @inline_temp(ttl=600)
    async def handle_search(self, event, args, data=None):
        await event.answer(f"Result: {args}")

    async def on_load(self):
        form_id = self.get_inline_temp_id("handle_search")
        # Use in buttons:
        await event.edit("Search", buttons=[[self.Button.switch("Search", f"{form_id} ")]])
```
