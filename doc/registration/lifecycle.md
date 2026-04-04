# Lifecycle Callbacks

← [Index](../../API_DOC.md)

All lifecycle callbacks receive `kernel` as their only argument.

## `@kernel.register.on_load()`

Called after the module is fully registered — on initial startup and on every `reload`.

```python
@kernel.register.on_load()
async def setup(kernel):
    kernel.logger.info("MyModule ready")
    await some_service.connect()
```

## `@kernel.register.on_install()`

Called **only the first time** the module is installed (via `dlm` / `loadera`). Not called on `reload`.

```python
@kernel.register.on_install()
async def first_time(kernel):
    await kernel.client.send_message('me', '✅ MyModule installed!')
    await kernel.save_module_config('mymod', {'enabled': True})
```

## `@kernel.register.uninstall()`

Called when the module is unloaded — via `um`, `reload`, or any loader operation.

```python
@kernel.register.uninstall()
async def cleanup(kernel):
    await some_client.disconnect()
    kernel.logger.info("MyModule unloaded cleanly")
```

## Cleanup Order on Unload

1. All `@register.loop` loops stopped
2. All `@register.watcher` Telethon handlers removed
3. All `@register.event` Telethon handlers removed
4. `@register.uninstall()` callback called
5. Command entries removed from kernel

## Complete Example

```python
import aiohttp

session = None

def register(kernel):
    @kernel.register.loop(interval=600)
    async def refresh(kernel):
        async with session.get("https://api.example.com/data") as r:
            kernel.logger.info(f"refreshed: {r.status}")

    @kernel.register.on_install()
    async def first_run(k):
        await k.client.send_message('me', '✅ module installed')

    @kernel.register.on_load()
    async def on_load(k):
        global session
        session = aiohttp.ClientSession()

    @kernel.register.uninstall()
    async def on_unload(k):
        global session
        if session:
            await session.close()
```
