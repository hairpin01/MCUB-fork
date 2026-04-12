# InfiniteLoop

← [Index](../../API_DOC.md)

`@kernel.register.loop(interval, autostart=True, wait_before=False)`
Declare a managed background loop. The kernel starts it after the module loads and stops it on unload.

## Parameters

- `interval` (int): Seconds between iterations
- `autostart` (bool): Start automatically after load (default: `True`)
- `wait_before` (bool): Sleep *before* the first iteration (default: `False`)

## InfiniteLoop Attributes

| | |
|---|---|
| `loop.status` | `True` while running |
| `loop.start()` | Start the loop |
| `loop.stop()` | Stop the loop gracefully |

## Examples

### Simple autostarting loop

```python
def register(kernel):
    @kernel.register.loop(interval=300)
    async def heartbeat(kernel):
        await kernel.client.send_message('me', '💓 alive')
```

### Manual control via commands

```python
def register(kernel):
    @kernel.register.loop(interval=60, autostart=False)
    async def checker(kernel):
        data = await kernel.db_get('mymod', 'watch_target')
        if data:
            kernel.logger.info(f"checking: {data}")

    @kernel.register.command('startcheck')
    async def start_cmd(event):
        checker.start()
        await event.edit("Checker started")

    @kernel.register.command('stopcheck')
    async def stop_cmd(event):
        checker.stop()
        await event.edit("Checker stopped")

    @kernel.register.command('checkstatus')
    async def status_cmd(event):
        await event.edit(f"Running: {checker.status}")
```

> [!NOTE]
> Loops are stopped before `@register.uninstall()` is called, so you can safely read `loop.status` in the uninstall callback.

> [!TIP]
> Use `wait_before=True` for loops that should delay their first run.
