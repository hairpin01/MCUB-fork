# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for task scheduler
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestScheduler:
    """Test task scheduler functionality"""

    async def test_scheduler_initialization(self):
        """Test scheduler setup"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        assert scheduler is not None
        assert scheduler.running is True
        await scheduler.stop()

    async def test_interval_task(self):
        """Test interval task scheduling"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        executions = []

        async def interval_task():
            executions.append(time.time())

        await scheduler.add_interval_task(interval_task, 0.1)

        await asyncio.sleep(0.25)
        await scheduler.stop()

        assert len(executions) >= 1

    async def test_one_time_task(self):
        """Test delayed one-time task"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        task_executed = []

        async def one_time_task():
            task_executed.append(time.time())

        task_id = await scheduler.add_task(one_time_task, delay_seconds=0.1)

        assert task_id is not None
        assert task_id.startswith("once_")

        await asyncio.sleep(0.15)

        assert len(task_executed) == 1
        await scheduler.stop()

    async def test_scheduler_shutdown(self):
        """Test scheduler graceful shutdown"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        task_ran = []

        async def running_task():
            task_ran.append(time.time())
            await asyncio.sleep(0.05)

        await scheduler.add_interval_task(running_task, 0.1)

        await asyncio.sleep(0.15)
        await scheduler.stop()

        initial_run_count = len(task_ran)
        await asyncio.sleep(0.2)

        assert len(task_ran) == initial_run_count


@pytest.mark.asyncio
class TestSchedulerEdgeCases:
    """Test scheduler edge cases"""

    async def test_multiple_interval_tasks(self):
        """Test multiple interval tasks run independently"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        exec_count1 = []
        exec_count2 = []

        async def task1():
            exec_count1.append(1)

        async def task2():
            exec_count2.append(1)

        await scheduler.add_interval_task(task1, 0.1)
        await scheduler.add_interval_task(task2, 0.15)

        await asyncio.sleep(0.35)
        await scheduler.stop()

        assert len(exec_count1) >= 2
        assert len(exec_count2) >= 1

    async def test_one_time_task_with_zero_delay(self):
        """Test one-time task with zero delay executes immediately"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        executed = []

        async def immediate_task():
            executed.append(1)

        await scheduler.add_task(immediate_task, delay_seconds=0)

        await asyncio.sleep(0.01)
        await scheduler.stop()

        assert len(executed) == 1

    async def test_one_time_task_does_not_repeat(self):
        """Test one-time task only executes once"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        executed = []

        async def single_task():
            executed.append(1)

        await scheduler.add_task(single_task, delay_seconds=0.05)

        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert len(executed) == 1

    async def test_interval_task_with_long_interval(self):
        """Test interval task with long interval doesn't execute immediately"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        executed = []

        async def slow_task():
            executed.append(1)

        await scheduler.add_interval_task(slow_task, 1.0)

        await asyncio.sleep(0.05)
        await scheduler.stop()

        assert len(executed) == 0

    async def test_scheduler_double_stop(self):
        """Test scheduler handles double stop gracefully"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        await scheduler.stop()
        await scheduler.stop()

        assert scheduler.running is False

    async def test_multiple_one_time_tasks(self):
        """Test multiple one-time tasks execute independently"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        results = {"task1": [], "task2": [], "task3": []}

        async def make_task(name):
            async def task():
                results[name].append(1)

            return task

        await scheduler.add_task(await make_task("task1"), delay_seconds=0.05)
        await scheduler.add_task(await make_task("task2"), delay_seconds=0.10)
        await scheduler.add_task(await make_task("task3"), delay_seconds=0.15)

        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert len(results["task1"]) == 1
        assert len(results["task2"]) == 1
        assert len(results["task3"]) == 1

    async def test_task_with_exception_does_not_crash_scheduler(self):
        """Test scheduler handles task exceptions gracefully"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = MagicMock()

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        async def failing_task():
            raise ValueError("test error")

        await scheduler.add_task(failing_task, delay_seconds=0.05)
        await scheduler.add_interval_task(failing_task, 0.1)

        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert scheduler.running is False

    async def test_task_with_async_sleep(self):
        """Test task that performs async sleep"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        executed = []

        async def sleeping_task():
            await asyncio.sleep(0.1)
            executed.append(1)

        await scheduler.add_task(sleeping_task, delay_seconds=0)

        await asyncio.sleep(0.15)
        await scheduler.stop()

        assert len(executed) == 1


@pytest.mark.asyncio
class TestSchedulerTiming:
    """Test scheduler timing accuracy"""

    async def test_one_time_task_timing(self):
        """Test one-time task executes at correct time"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        start_time = time.time()

        async def timed_task():
            return time.time()

        await scheduler.add_task(timed_task, delay_seconds=0.1)

        await asyncio.sleep(0.15)
        await scheduler.stop()

        assert time.time() - start_time >= 0.1

    async def test_interval_task_regular_execution(self):
        """Test interval task executes regularly"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        timings = []

        async def timed_interval():
            timings.append(time.time())

        await scheduler.add_interval_task(timed_interval, 0.1)

        await asyncio.sleep(0.35)
        await scheduler.stop()

        if len(timings) >= 2:
            intervals = [timings[i + 1] - timings[i] for i in range(len(timings) - 1)]
            for interval in intervals:
                assert 0.08 <= interval <= 0.2


class TestSchedulerState:
    """Test scheduler state management"""

    @pytest.mark.asyncio
    async def test_scheduler_initial_state(self):
        """Test scheduler initial state"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_scheduler_after_start(self):
        """Test scheduler state after start"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        assert scheduler.running is True
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_after_stop(self):
        """Test scheduler state after stop"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()
        await scheduler.stop()

        assert scheduler.running is False
