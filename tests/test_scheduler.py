"""
Tests for task scheduler and async task management
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
class TestScheduler:
    """Test task scheduler functionality"""
    
    async def test_scheduler_initialization(self, kernel_instance):
        """Test scheduler setup"""
        await kernel_instance.init_scheduler()
        
        assert kernel_instance.scheduler is not None
        assert kernel_instance.scheduler.running is True
        assert hasattr(kernel_instance.scheduler, 'task_registry')
        
    async def test_interval_task(self, kernel_instance):
        """Test interval task scheduling"""
        await kernel_instance.init_scheduler()
        
        executions = []
        
        async def interval_task():
            executions.append(time.time())
            
        task_id = await kernel_instance.scheduler.add_interval_task(
            interval_task, interval_seconds=0.1
        )
        
        assert task_id is not None
        assert task_id in kernel_instance.scheduler.task_registry
        
        # Wait for at least one execution
        await asyncio.sleep(0.15)
        
        # Cancel to prevent further executions
        kernel_instance.scheduler.cancel_task(task_id)
        
        assert len(executions) >= 1
        
    async def test_daily_task(self, kernel_instance):
        """Test daily task scheduling"""
        await kernel_instance.init_scheduler()
        
        executions = []
        
        async def daily_task():
            executions.append(datetime.now())
            
        # Schedule for next minute (to test logic without waiting a day)
        now = datetime.now()
        next_minute = (now + timedelta(minutes=1)).time()
        
        task_id = await kernel_instance.scheduler.add_daily_task(
            daily_task, 
            hour=next_minute.hour,
            minute=next_minute.minute
        )
        
        assert task_id is not None
        assert task_id.startswith('daily_')
        
        # Task should be in registry
        assert task_id in kernel_instance.scheduler.task_registry
        
    async def test_one_time_task(self, kernel_instance):
        """Test delayed one-time task"""
        await kernel_instance.init_scheduler()
        
        task_executed = []
        
        async def one_time_task():
            task_executed.append(time.time())
            
        task_id = await kernel_instance.scheduler.add_task(
            one_time_task, delay_seconds=0.1
        )
        
        assert task_id is not None
        assert task_id.startswith('once_')
        
        # Wait for execution
        await asyncio.sleep(0.15)
        
        assert len(task_executed) == 1
        
        # Task should auto-remove after execution
        assert task_id not in kernel_instance.scheduler.task_registry
        
    async def test_task_cancellation(self, kernel_instance):
        """Test task cancellation"""
        await kernel_instance.init_scheduler()
        
        task_ran = []
        
        async def task_to_cancel():
            task_ran.append(True)
            
        task_id = await kernel_instance.scheduler.add_interval_task(
            task_to_cancel, interval_seconds=0.1
        )
        
        # Cancel immediately
        result = kernel_instance.scheduler.cancel_task(task_id)
        assert result is True
        
        # Wait to ensure task doesn't run
        await asyncio.sleep(0.15)
        
        assert len(task_ran) == 0
        assert task_id not in kernel_instance.scheduler.task_registry
        
    async def test_cancel_nonexistent_task(self, kernel_instance):
        """Test cancellation of non-existent task"""
        await kernel_instance.init_scheduler()
        
        result = kernel_instance.scheduler.cancel_task('nonexistent_id')
        assert result is False
        
    async def test_get_tasks_list(self, kernel_instance):
        """Test task listing functionality"""
        await kernel_instance.init_scheduler()
        
        async def sample_task():
            pass
            
        # Add multiple tasks
        task1 = await kernel_instance.scheduler.add_interval_task(
            sample_task, 60, task_id='test_interval'
        )
        task2 = await kernel_instance.scheduler.add_daily_task(
            sample_task, 12, 0, task_id='test_daily'
        )
        
        tasks = kernel_instance.scheduler.get_tasks()
        
        assert len(tasks) == 2
        
        # Check task info structure
        for task_info in tasks:
            assert 'id' in task_info
            assert 'type' in task_info
            assert 'status' in task_info
            assert task_info['id'] in ['test_interval', 'test_daily']
            
    async def test_scheduler_shutdown(self, kernel_instance):
        """Test scheduler graceful shutdown"""
        await kernel_instance.init_scheduler()
        
        task_ran = []
        
        async def running_task():
            task_ran.append(time.time())
            await asyncio.sleep(0.05)
            
        # Add a task
        await kernel_instance.scheduler.add_interval_task(
            running_task, interval_seconds=0.1
        )
        
        # Let it run once
        await asyncio.sleep(0.15)
        
        # Cancel all tasks
        kernel_instance.scheduler.cancel_all_tasks()
        
        initial_run_count = len(task_ran)
        
        # Wait and check no more executions
        await asyncio.sleep(0.2)
        
        assert len(task_ran) == initial_run_count  # No new executions
        
    async def test_task_error_handling(self, kernel_instance):
        """Test error handling in scheduled tasks"""
        await kernel_instance.init_scheduler()
        
        errors_logged = []
        
        # Mock error logging
        original_log_error = kernel_instance.log_error
        kernel_instance.log_error = lambda msg: errors_logged.append(msg)
        
        async def failing_task():
            raise ValueError("Task error")
            
        task_id = await kernel_instance.scheduler.add_interval_task(
            failing_task, interval_seconds=0.1
        )
        
        # Wait for error to occur
        await asyncio.sleep(0.15)
        
        # Cancel to stop further attempts
        kernel_instance.scheduler.cancel_task(task_id)
        
        # Restore original logger
        kernel_instance.log_error = original_log_error
        
        # Error should be caught and logged
        assert len(errors_logged) >= 1
        assert "Task error" in errors_logged[0]
        
    async def test_concurrent_task_management(self, kernel_instance):
        """Test handling multiple concurrent tasks"""
        await kernel_instance.init_scheduler()
        
        execution_counts = {'task1': 0, 'task2': 0, 'task3': 0}
        
        async def counting_task(name):
            execution_counts[name] += 1
            
        # Schedule multiple tasks with different intervals
        tasks = []
        tasks.append(await kernel_instance.scheduler.add_interval_task(
            lambda: counting_task('task1'), 0.1
        ))
        tasks.append(await kernel_instance.scheduler.add_interval_task(
            lambda: counting_task('task2'), 0.15
        ))
        tasks.append(await kernel_instance.scheduler.add_interval_task(
            lambda: counting_task('task3'), 0.2
        ))
        
        # Let them run for a bit
        await asyncio.sleep(0.35)
        
        # Cancel all
        for task_id in tasks:
            kernel_instance.scheduler.cancel_task(task_id)
            
        # All tasks should have run at least once
        assert all(count > 0 for count in execution_counts.values())
        
        # Task1 should have run more times (shortest interval)
        assert execution_counts['task1'] >= execution_counts['task2']
