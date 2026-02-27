"""
Tests for task scheduler
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock


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
