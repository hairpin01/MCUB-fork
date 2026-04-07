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
