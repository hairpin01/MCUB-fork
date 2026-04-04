# Middleware API

`kernel.add_middleware(middleware_func)`
Add middleware to process events before handlers.

```python
async def auth_middleware(event, handler):
    if not kernel.is_admin(event.sender_id):
        await event.reply("Access denied")
        return
    return await handler(event)

kernel.add_middleware(auth_middleware)
```

## Middleware Chain

Middleware functions are executed in order before the command handler is called. You can add multiple middlewares.

```python
def register(kernel):
    @kernel.middleware
    async def auth_middleware(event, handler):
        if not kernel.is_admin(event.sender_id):
            await event.reply("Access denied")
            return
        return await handler(event)
```

## Usage Example

```python
def register(kernel):
    @kernel.middleware
    async def logging_middleware(event, handler):
        kernel.logger.debug(f"Command from {event.sender_id}: {event.text}")
        return await handler(event)

    @kernel.register.command('test')
    async def test_handler(event):
        await event.edit("Test command executed")
```
