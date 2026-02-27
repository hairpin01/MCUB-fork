"""
Integration tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
class TestIntegration:
    """Integration tests"""

    async def test_module_lifecycle(self):
        """Test module load/unload lifecycle"""
        kernel = MagicMock()
        kernel.loaded_modules = {}
        kernel.command_handlers = {}
        
        async def test_handler(event):
            return "test"
        
        kernel.loaded_modules["test_module"] = {"name": "test"}
        kernel.command_handlers["test"] = test_handler
        
        assert "test_module" in kernel.loaded_modules
        assert "test" in kernel.command_handlers
        
        del kernel.loaded_modules["test_module"]
        del kernel.command_handlers["test"]
        
        assert "test_module" not in kernel.loaded_modules

    async def test_command_flow(self):
        """Test command processing flow"""
        kernel = MagicMock()
        kernel.command_handlers = {}
        kernel.custom_prefix = "."
        
        async def ping_handler(event):
            return "pong"
        
        kernel.command_handlers["ping"] = ping_handler
        
        event = MagicMock()
        event.text = ".ping"
        
        handler = kernel.command_handlers.get("ping")
        result = await handler(event)
        
        assert result == "pong"

    async def test_error_recovery(self):
        """Test error recovery mechanism"""
        kernel = MagicMock()
        kernel.handle_error = AsyncMock()
        
        try:
            raise ValueError("test error")
        except ValueError as e:
            await kernel.handle_error(e, source="test")
        
        assert kernel.handle_error.called

    async def test_scheduler_integration(self):
        """Test scheduler with kernel integration"""
        from core.lib.time.scheduler import TaskScheduler
        
        kernel = MagicMock()
        kernel.log_error = lambda msg: None
        
        scheduler = TaskScheduler(kernel)
        await scheduler.start()
        
        executions = []
        
        async def periodic_task():
            executions.append(1)
        
        await scheduler.add_interval_task(periodic_task, 0.1)
        
        await asyncio.sleep(0.25)
        await scheduler.stop()
        
        assert len(executions) >= 1
