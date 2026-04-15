# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Stress tests for scheduler
"""

import asyncio
import time as sync_time
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestSchedulerStress:
    """Stress tests for scheduler module"""

    async def test_schedule_many_tasks(self):
        """Test scheduling many tasks"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            loop = asyncio.get_running_loop()
            start = loop.time()

            for i in range(100):

                async def dummy_task():
                    pass

                await scheduler.add_interval_task(dummy_task, 60.0)

            elapsed = loop.time() - start
            assert elapsed < 2.0, f"Scheduling 100 tasks took {elapsed}s"
            assert len(scheduler.tasks) == 100
        finally:
            await scheduler.stop()

    async def test_scheduler_many_executing_tasks(self):
        """Test many tasks executing simultaneously"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            results = []

            for i in range(20):

                async def task():
                    results.append(i)

                await scheduler.add_interval_task(task, 0.05)

            await asyncio.sleep(0.3)

            assert len(results) >= 10, f"Only {len(results)} tasks executed"
        finally:
            await scheduler.stop()

    async def test_concurrent_task_addition(self):
        """Test concurrently adding tasks from multiple coroutines"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:

            async def add_tasks(start, count):
                for i in range(count):

                    async def dummy_task():
                        pass

                    await scheduler.add_interval_task(dummy_task, 60.0)

            loop = asyncio.get_running_loop()
            start = loop.time()

            await asyncio.gather(
                add_tasks(0, 25),
                add_tasks(25, 25),
                add_tasks(50, 25),
                add_tasks(75, 25),
            )

            elapsed = loop.time() - start
            assert elapsed < 3.0, f"Concurrent task addition took {elapsed}s"
            assert len(scheduler.tasks) == 100
        finally:
            await scheduler.stop()

    async def test_many_rapid_tasks(self):
        """Test scheduling many tasks with short intervals"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            results = []

            for i in range(50):

                async def task():
                    results.append(i)

                await scheduler.add_interval_task(task, 0.01)

            await asyncio.sleep(0.3)

            assert len(results) >= 30, f"Only {len(results)} tasks executed"
        finally:
            await scheduler.stop()


@pytest.mark.asyncio
class TestSchedulerPerformance:
    """Performance tests for scheduler"""

    async def test_task_execution_timing(self):
        """Test that tasks execute with correct timing and intervals"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            execution_times = []

            async def timed_task():
                execution_times.append(sync_time.time())

            await scheduler.add_interval_task(timed_task, 0.1)
            start_time = sync_time.time()
            await asyncio.sleep(0.35)

            assert len(execution_times) >= 2, f"Task should execute at least 2 times"

            if len(execution_times) >= 2:
                intervals = [
                    execution_times[i] - execution_times[i - 1]
                    for i in range(1, len(execution_times))
                ]
                avg_interval = sum(intervals) / len(intervals)
                assert (
                    0.08 <= avg_interval <= 0.15
                ), f"Interval {avg_interval}s is too far from 0.1s"
        finally:
            await scheduler.stop()

    async def test_scheduler_start_stop_performance(self):
        """Test scheduler start/stop performance"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        loop = asyncio.get_running_loop()
        start = loop.time()

        for _ in range(10):
            scheduler = TaskScheduler(kernel)
            await scheduler.start()
            await scheduler.stop()

        elapsed = loop.time() - start
        assert elapsed < 4.0, f"10 start/stop cycles took {elapsed}s"


@pytest.mark.asyncio
class TestSchedulerReliability:
    """Reliability tests for scheduler"""

    async def test_task_exception_handling(self):
        """Test that task exceptions don't break scheduler"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:

            async def failing_task():
                raise ValueError("Test error")

            async def good_task():
                pass

            await scheduler.add_interval_task(failing_task, 0.05)
            await scheduler.add_interval_task(good_task, 0.05)

            await asyncio.sleep(0.2)

            assert len(scheduler.tasks) == 2
        finally:
            await scheduler.stop()

    async def test_multiple_tasks(self):
        """Test that multiple tasks can run"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            results = []

            async def task_with_name():
                results.append(1)

            for i in range(5):
                await scheduler.add_interval_task(task_with_name, 0.1)

            await asyncio.sleep(0.25)

            assert (
                len(results) >= 5
            ), f"Expected at least 5 executions, got {len(results)}"
        finally:
            await scheduler.stop()

    async def test_cancel_all_tasks(self):
        """Test that cancel_all_tasks actually cancels all tasks"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            for i in range(10):

                async def dummy_task():
                    await asyncio.sleep(10)

                await scheduler.add_interval_task(dummy_task, 60.0)

            assert len(scheduler.tasks) == 10

            scheduler.cancel_all_tasks()

            await asyncio.sleep(0.1)

            assert len(scheduler.tasks) == 0, "All tasks should be cancelled"
        finally:
            await scheduler.stop()

    async def test_cleanup_after_stop(self):
        """Test that tasks are cleaned up after stop"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        for i in range(5):

            async def dummy_task():
                pass

            await scheduler.add_interval_task(dummy_task, 60.0)

        assert len(scheduler.tasks) == 5

        await scheduler.stop()

        assert len(scheduler.tasks) == 0, "Tasks should be empty after stop"
        assert scheduler.running is False


@pytest.mark.asyncio
class TestSchedulerConcurrency:
    """Concurrency stress tests for scheduler"""

    async def test_concurrent_writes(self):
        """Test concurrent writes to scheduler"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:

            async def writer(batch_start, count):
                for i in range(count):

                    async def dummy_task():
                        pass

                    await scheduler.add_interval_task(dummy_task, 60.0)

            loop = asyncio.get_running_loop()
            start = loop.time()

            await asyncio.gather(
                writer(0, 50),
                writer(1, 50),
                writer(2, 50),
                writer(3, 50),
            )

            elapsed = loop.time() - start
            assert elapsed < 3.0, f"Concurrent writes took {elapsed}s"
            assert len(scheduler.tasks) == 200
        finally:
            await scheduler.stop()

    async def test_many_rapid_writes(self):
        """Test many rapid writes to scheduler"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            loop = asyncio.get_running_loop()
            start = loop.time()

            for i in range(200):

                async def dummy_task():
                    pass

                await scheduler.add_interval_task(dummy_task, 60.0)

            elapsed = loop.time() - start
            assert elapsed < 2.0, f"200 rapid writes took {elapsed}s"
            assert len(scheduler.tasks) == 200
        finally:
            await scheduler.stop()


@pytest.mark.asyncio
class TestSchedulerWorkload:
    """Stress tests with actual workload"""

    async def test_tasks_with_sleep(self):
        """Test tasks that perform actual async work"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            results = []

            async def task_with_work():
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                results.append(1)

            for i in range(10):
                await scheduler.add_interval_task(task_with_work, 0.05)

            await asyncio.sleep(0.3)

            assert len(results) >= 5, f"Only {len(results)} tasks completed"
        finally:
            await scheduler.stop()

    async def test_tasks_with_computation(self):
        """Test tasks that perform computation"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            results = []

            def compute():
                total = 0
                for i in range(1000):
                    total += i * i
                return total

            async def task_with_compute():
                compute()
                results.append(1)

            for i in range(10):
                await scheduler.add_interval_task(task_with_compute, 0.05)

            await asyncio.sleep(0.3)

            assert len(results) >= 5, f"Only {len(results)} tasks completed"
        finally:
            await scheduler.stop()

    async def test_heavy_concurrent_workload(self):
        """Test scheduler under heavy concurrent workload"""
        from core.lib.time.scheduler import TaskScheduler

        kernel = MagicMock()
        kernel.log_error = lambda msg: None

        scheduler = TaskScheduler(kernel)
        await scheduler.start()

        try:
            counter = 0

            async def heavy_task():
                nonlocal counter
                for _ in range(5):
                    await asyncio.sleep(0)
                counter += 1

            for i in range(20):
                await scheduler.add_interval_task(heavy_task, 0.1)

            await asyncio.sleep(0.5)

            assert counter >= 50, f"Expected at least 50 executions, got {counter}"
        finally:
            await scheduler.stop()
