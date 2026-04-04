# Task Scheduler API

All scheduler methods are available via `kernel.scheduler`.

## Lifecycle Methods

`kernel.scheduler.start()` — Start the task scheduler.

`kernel.scheduler.stop()` — Stop all scheduled tasks and clean up resources.

## Task Management

`kernel.scheduler.add_interval_task(func, interval_seconds, task_id=None)`
Schedule an async function to run at fixed intervals.

```python
async def update_cache():
    kernel.logger.debug("Updating cache...")

await kernel.scheduler.add_interval_task(update_cache, 60)
```

`kernel.scheduler.add_daily_task(func, hour, minute, task_id=None)`
Schedule a function to run daily at a specific time.

```python
async def daily_report():
    await kernel.client.send_message("me", "Daily report ready!")

await kernel.scheduler.add_daily_task(daily_report, hour=9, minute=30)
```

`kernel.scheduler.add_task(func, delay_seconds, task_id=None)`
Schedule a one-shot task to run after a delay. Returns task_id.

```python
async def delayed_alert():
    await kernel.client.send_message("me", "Alert!")

task_id = await kernel.scheduler.add_task(delayed_alert, 300, task_id="my_alert")
```

`kernel.scheduler.cancel_task(task_id)` — Cancel a task by its ID.

`kernel.scheduler.cancel_all_tasks()` — Cancel all tasks and stop the scheduler.

`kernel.scheduler.remove_task(task)` — Remove and cancel a specific asyncio task.

## Query Methods

`kernel.scheduler.get_tasks()` — Get status summary of all scheduled tasks. Returns list of dicts with `name` and `status`.

`kernel.scheduler.get_active_tasks()` — Get all asyncio Task objects.

`kernel.scheduler.get_task_count()` — Get number of scheduled tasks.

---

## Error Handling

Tasks spawned by the scheduler automatically:
- Catch and log exceptions without crashing the task
- Continue running after errors (interval/daily tasks)
- Support graceful cancellation via `asyncio.CancelledError`

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
@kernel.register.command('remind')
async def remind(event):
    args = event.text.split()
    if len(args) < 2:
        await event.edit("Usage: .remind <seconds> <message>")
        return

    seconds = int(args[1])
    message = ' '.join(args[2:])

    async def send_reminder():
        await kernel.client.send_message(event.chat_id, f"⏰ Reminder: {message}")

    await kernel.scheduler.add_task(send_reminder, seconds)
    await event.edit(f"Reminder set for {seconds}s")
```
