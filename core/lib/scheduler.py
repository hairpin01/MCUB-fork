# author: @Hairpin00
# version: 1.0.1
# description: Task scheduler for periodic and time-based tasks

import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, List


class TaskScheduler:
    """
    A scheduler for managing periodic and time-based asynchronous tasks.
    This class provides methods to schedule tasks that run at fixed intervals
    or at specific times daily. It integrates with a kernel for error logging
    and supports graceful shutdown of running tasks.
    Attributes:
        kernel: Reference to the main kernel/application for logging and services
        tasks: List of currently scheduled asyncio tasks
        running: Flag indicating whether the scheduler is active
    """
    def __init__(self, kernel: Any) -> None:
        """
        Initialize the task scheduler.

        Args:
            kernel: The main application kernel providing logging and other services
                    Must have a `log_error` method for error reporting.
        """
        self.kernel = kernel
        self.tasks: List[asyncio.Task] = []
        self.running = False

    async def start(self) -> None:
        """Start the task scheduler and mark it as running."""
        self.running = True

    async def stop(self) -> None:
        """
        Stop all scheduled tasks and clean up resources.

        This method cancels all running tasks and waits for them to complete
        cancellation. It should be called before application shutdown.
        """
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to be cancelled
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.tasks.clear()

    async def add_interval_task(self,
                               func: Callable[[], Any],
                               interval_seconds: float) -> None:
        """
        Schedule a function to run at fixed intervals.

        The function will be called repeatedly, waiting for `interval_seconds`
        between the end of one execution and the start of the next.

        Args:
            func: Async function to execute periodically
            interval_seconds: Time interval between executions in seconds

        Example:
            >>> await scheduler.add_interval_task(update_cache, 60.0)
        """
        async def wrapper() -> None:
            """Wrapper function that handles the interval logic and error catching."""
            while self.running:
                try:
                    await asyncio.sleep(interval_seconds)
                    await func()
                except asyncio.CancelledError:
                    # Task was cancelled, break out of the loop
                    break
                except Exception as e:
                    # Log the error but keep the task running
                    error_msg = f"Interval task error in {func.__name__}: {e}\n"
                    error_msg += traceback.format_exc()
                    self.kernel.log_error(error_msg)

        task = asyncio.create_task(wrapper(), name=f"interval_{func.__name__}")
        self.tasks.append(task)

    async def add_daily_task(self,
                            func: Callable[[], Any],
                            hour: int,
                            minute: int) -> None:
        """
        Schedule a function to run daily at a specific time.

        The function will be called every day at the specified hour and minute.
        If the target time has already passed for today, it will run tomorrow.

        Args:
            func: Async function to execute daily
            hour: Hour of the day (0-23) to run the task
            minute: Minute of the hour (0-59) to run the task

        Raises:
            ValueError: If hour or minute values are out of valid range

        Example:
            >>> await scheduler.add_daily_task(send_daily_report, 9, 30)
        """
        # Validate input parameters
        if not (0 <= hour <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"Minute must be between 0 and 59, got {minute}")

        async def wrapper() -> None:
            """Wrapper function that handles the daily scheduling and error catching."""
            while self.running:
                try:
                    # Calculate time until next execution
                    now = datetime.now()
                    target_time = now.replace(
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0
                    )


                    # If target time has passed today, schedule for tomorrow
                    if now >= target_time:
                        target_time += timedelta(days=1)

                    # Calculate delay in seconds
                    delay_seconds = (target_time - now).total_seconds()

                    # Wait until the target time
                    await asyncio.sleep(delay_seconds)

                    # Execute the scheduled function
                    await func()

                    # After execution, wait for the next day
                    # This prevents multiple executions if the function takes time
                    await asyncio.sleep(1)  # Small delay before recalculating

                except asyncio.CancelledError:
                    # Task was cancelled, break out of the loop
                    break
                except Exception as e:
                    # Log the error but keep the task running
                    error_msg = f"Daily task error in {func.__name__}: {e}\n"
                    error_msg += traceback.format_exc()
                    self.kernel.log_error(error_msg)

                    # Wait a bit before retrying to avoid error loops
                    await asyncio.sleep(60)

        task_name = f"daily_{func.__name__}_{hour:02d}:{minute:02d}"
        task = asyncio.create_task(wrapper(), name=task_name)
        self.tasks.append(task)

    def get_active_tasks(self) -> List[asyncio.Task]:
        """
        Get a list of all currently scheduled tasks.

        Returns:
            List of asyncio.Task objects representing scheduled tasks
        """
        return self.tasks.copy()

    def get_task_count(self) -> int:
        """Return the number of currently scheduled tasks."""
        return len(self.tasks)

    async def remove_task(self, task: asyncio.Task) -> bool:
        """
        Remove and cancel a specific task.

        Args:
            task: The task to remove and cancel

        Returns:
            True if the task was found and cancelled, False otherwise
        """
        if task in self.tasks:
            self.tasks.remove(task)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return True
        return False
