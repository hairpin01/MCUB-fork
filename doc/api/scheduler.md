# Task Scheduler API

← [Index](../../API_DOC.md)

All scheduler methods are available via `kernel.scheduler`. Methods that create or wait for
tasks are async and must be awaited.

## Lifecycle Methods

`await kernel.scheduler.start()` - Start the task scheduler and set `running = True`.

`await kernel.scheduler.stop()` - Stop all scheduled tasks, wait for cancellation, and clear the task list.

## Task Management

`await kernel.scheduler.add_interval_task(func, interval_seconds)`
Schedule an async function to run at fixed intervals. The first run happens after
`interval_seconds`; it does not run immediately.

```python
async def update_cache():
    kernel.logger.debug("Updating cache...")

await kernel.scheduler.add_interval_task(update_cache, 60)
```

**Parameters:**
- `func`: async callable with no arguments.
- `interval_seconds` (`float`): delay between task runs, in seconds.

**Returns:** `None`.

`await kernel.scheduler.add_daily_task(func, hour, minute)`
Schedule a function to run daily at a specific time.

```python
async def daily_report():
    await kernel.client.send_message("me", "Daily report ready!")

await kernel.scheduler.add_daily_task(daily_report, hour=9, minute=30)
```

**Parameters:**
- `func`: async callable with no arguments.
- `hour` (`int`): 0-23.
- `minute` (`int`): 0-59.

**Raises:** `ValueError` if `hour` or `minute` is outside the valid range.

**Returns:** `None`.

`await kernel.scheduler.add_task(func, delay_seconds, task_id=None) -> str`
Schedule a one-shot task to run after a delay. Returns task_id.

```python
async def delayed_alert():
    await kernel.client.send_message("me", "Alert!")

task_id = await kernel.scheduler.add_task(delayed_alert, 300, task_id="my_alert")
```

**Parameters:**
- `func`: async callable with no arguments.
- `delay_seconds` (`float`): delay before execution.
- `task_id` (`str | None`): optional ID. If omitted, MCUB generates `once_<func_name>_<id>`.

**Returns:** The task ID string.

`kernel.scheduler.cancel_task(task_id) -> bool` - Cancel a one-shot task registered with `add_task`. Returns `True` if found and cancelled.

`kernel.scheduler.cancel_all_tasks()` - Synchronously cancel all tasks, set `running = False`, clear the task list and one-shot registry. Unlike `stop()`, it does not await task cancellation.

`await kernel.scheduler.remove_task(task) -> bool` - Remove and cancel a specific asyncio task. Returns `True` if it was found.

## Query Methods

`kernel.scheduler.get_tasks() -> list[dict]` - Get status summary of all scheduled tasks. Returns dicts with `name` and `status` (`"running"` or `"stopped"`).

`kernel.scheduler.get_active_tasks() -> list[asyncio.Task]` - Get a copy of all asyncio Task objects.

`kernel.scheduler.get_task_count() -> int` - Get number of scheduled tasks currently tracked.

---

## Error Handling

Tasks spawned by the scheduler automatically:
- Catch and log exceptions without crashing the task
- Continue running after errors (interval/daily tasks)
- Support graceful cancellation via `asyncio.CancelledError`

Interval and one-shot task errors call `kernel.log_error(...)`. Daily task errors call
`kernel.handle_error(error, message="Scheduled task failed")` and then wait 60 seconds before retrying.

---

## Usage Examples

### Periodic Cache Update

```python
def register(kernel):
    async def refresh_data():
        kernel.logger.info("Refreshing data...")
        # ... fetch and cache data

    @kernel.register.loop(interval=600)  # Preferred way for modules
    async def refresher(kernel):
        await refresh_data()
```

### Delayed One-Shot Task

```python
def register(kernel):
    @kernel.register.command('remind')
    async def remind(event):
        args = event.text.split()
        if len(args) < 3:
            await event.edit("Usage: .remind <seconds> <message>")
            return

        seconds = int(args[1])
        message = ' '.join(args[2:])

        async def send_reminder():
            await kernel.client.send_message(event.chat_id, f"⏰ Reminder: {message}")

        await kernel.scheduler.add_task(send_reminder, seconds)
        await event.edit(f"Reminder set for {seconds}s")
```

## Notes and edge cases

- Scheduled callables should be async and take no arguments.
- `add_interval_task()` waits before the first execution. Use `await func()` yourself first if you need an immediate run.
- One-shot tasks run only while `scheduler.running` is still `True` after the delay.
- `cancel_task()` only knows tasks registered by `add_task()`; interval and daily tasks should be cancelled via `remove_task()`, `cancel_all_tasks()`, or `stop()`.
