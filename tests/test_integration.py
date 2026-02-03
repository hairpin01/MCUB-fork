"""
Integration tests for complete MCUB system
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import sys

@pytest.mark.integration
@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for MCUB components"""
    
    async def test_complete_command_flow(self, kernel_instance, mock_event):
        """Test complete command flow from registration to execution"""
        from kernel import Register
        
        # Setup
        register = Register(kernel_instance)
        kernel_instance.current_loading_module = 'integration_test'
        
        execution_trace = []
        
        # Register a command
        @register.command('integrate', alias=['int'])
        async def integrated_command(event):
            execution_trace.append('command_executed')
            
            # Use kernel features within command
            await kernel_instance.handle_error(
                ValueError("Test error from command"),
                source="integrated_command",
                event=event
            )
            
            # Use database
            await kernel_instance.db_set(
                'integration', 
                'last_executed', 
                str(mock_event.sender_id)
            )
            
            await event.edit("Integration complete")
            
        # Execute command
        mock_event.text = '.integrate'
        
        # Mock database
        with patch.object(kernel_instance, 'db_set', AsyncMock()), \
             patch.object(kernel_instance, 'handle_error', AsyncMock()):
            
            result = await kernel_instance.process_command(mock_event)
            
            assert result is True
            assert 'command_executed' in execution_trace
            assert kernel_instance.db_set.called
            assert kernel_instance.handle_error.called
            
    async def test_module_lifecycle(self, kernel_instance, tmp_path):
        """Test complete module lifecycle"""
        # Create a test module
        module_code = '''
# author: Integration Test
# version: 1.0.0
# description: Test complete lifecycle

def register(kernel):
    """Register module with all features"""
    
    # Register command
    @kernel.register.command('lifecycle')
    async def lifecycle_cmd(event):
        # Use kernel's database
        await kernel.db_set('lifecycle', 'executions', '1')
        await event.edit("Lifecycle test")
        
    # Register bot command
    @kernel.register.bot_command('start')
    async def start_cmd(event):
        await event.respond("Started lifecycle module")
        
    # Return module info
    return {
        'name': 'lifecycle_module',
        'version': '1.0.0'
    }
'''
        
        module_file = tmp_path / 'lifecycle_module.py'
        module_file.write_text(module_code)
        
        # Mock all dependencies
        with patch('importlib.util.spec_from_file_location'), \
             patch('importlib.util.module_from_spec'), \
             patch.object(sys, 'modules', {}), \
             patch.object(kernel_instance, 'db_set', AsyncMock()):
            
            # Load module
            success, message = await kernel_instance.load_module_from_file(
                str(module_file), 'lifecycle_module', False
            )
            
            # Module should be loaded
            assert 'lifecycle_module' in kernel_instance.loaded_modules
            
            # Commands should be registered
            assert 'lifecycle' in kernel_instance.command_handlers
            assert 'start' in kernel_instance.bot_command_handlers
            
    async def test_error_recovery_flow(self, kernel_instance, mock_event):
        """Test error recovery and continuity"""
        # Setup a command that fails
        fail_count = 0
        
        async def flaky_command(event):
            nonlocal fail_count
            fail_count += 1
            
            if fail_count <= 2:
                raise RuntimeError(f"Flaky failure #{fail_count}")
            else:
                await event.edit(f"Success on attempt {fail_count}")
                
        kernel_instance.command_handlers['flaky'] = flaky_command
        
        # Mock error handling
        with patch.object(kernel_instance, 'handle_error', AsyncMock()):
            # First attempt - should fail but be handled
            mock_event.text = '.flaky'
            
            result = await kernel_instance.process_command(mock_event)
            assert result is True
            assert kernel_instance.handle_error.called
            
            # Reset mock
            kernel_instance.handle_error.reset_mock()
            
            # Second attempt - should also fail
            result = await kernel_instance.process_command(mock_event)
            assert result is True
            assert kernel_instance.handle_error.called
            
    async def test_concurrent_operations(self, kernel_instance):
        """Test concurrent operations (database, cache, commands)"""
        import asyncio
        
        # Setup concurrent tasks
        async def db_operation(task_id):
            # Simulate DB operation
            await asyncio.sleep(0.01)
            await kernel_instance.db_set('concurrent', f'task_{task_id}', 'done')
            return task_id
            
        async def cache_operation(task_id):
            # Simulate cache operation
            kernel_instance.cache.set(f'cache_{task_id}', f'value_{task_id}')
            await asyncio.sleep(0.005)
            return kernel_instance.cache.get(f'cache_{task_id}')
            
        # Run concurrent operations
        db_tasks = [db_operation(i) for i in range(5)]
        cache_tasks = [cache_operation(i) for i in range(5)]
        
        # Mock DB connection
        with patch.object(kernel_instance, 'db_set', AsyncMock()):
            # Execute concurrently
            db_results = await asyncio.gather(*db_tasks)
            cache_results = await asyncio.gather(*cache_tasks)
            
            assert len(db_results) == 5
            assert len(cache_results) == 5
            
            # All cache operations should succeed
            assert all(r is not None for r in cache_results)
            
    async def test_scheduler_integration(self, kernel_instance):
        """Test scheduler integration with other components"""
        await kernel_instance.init_scheduler()
        
        # Track executions
        executions = []
        db_calls = []
        
        async def scheduled_task():
            executions.append(time.time())
            
            # Use kernel features in scheduled task
            # (mocked since we're testing integration)
            db_calls.append('scheduled_db_call')
            
        # Schedule task
        task_id = await kernel_instance.scheduler.add_interval_task(
            scheduled_task, interval_seconds=0.1
        )
        
        # Let it run a couple times
        await asyncio.sleep(0.25)
        
        # Cancel
        kernel_instance.scheduler.cancel_task(task_id)
        
        # Should have executed multiple times
        assert len(executions) >= 2
        
    async def test_complete_bot_flow(self, kernel_instance):
        """Test complete bot message flow"""
        # Setup command that uses inline features
        async def inline_command(event):
            # Use inline form
            success, message = await kernel_instance.inline_form(
                event.chat_id,
                "Test Form",
                buttons=[
                    {"text": "Option 1", "type": "callback", "data": "opt1"},
                    {"text": "Option 2", "type": "callback", "data": "opt2"}
                ],
                auto_send=True
            )
            
            if success:
                await event.edit("Form sent!")
            else:
                await event.edit("Failed to send form")
                
        kernel_instance.command_handlers['inlineflow'] = inline_command
        
        # Mock inline form
        with patch.object(kernel_instance, 'inline_form', 
                         AsyncMock(return_value=(True, Mock()))):
            
            mock_event = AsyncMock()
            mock_event.chat_id = 123456789
            mock_event.text = '.inlineflow'
            mock_event.edit = AsyncMock()
            
            await kernel_instance.process_command(mock_event)
            
            assert kernel_instance.inline_form.called
            assert mock_event.edit.called
            
    async def test_config_persistence_flow(self, kernel_instance):
        """Test configuration persistence across operations"""
        # Set module config
        initial_config = {
            'enabled': True,
            'count': 0,
            'last_user': None
        }
        
        # Mock DB operations
        with patch.object(kernel_instance, 'db_set', AsyncMock()) as mock_set, \
             patch.object(kernel_instance, 'db_get', 
                         AsyncMock(side_effect=[
                             None,  # First call returns no config
                             '{"enabled": true, "count": 1, "last_user": "test"}'
                         ])):
            
            # Save initial config
            await kernel_instance.save_module_config('persistence_test', initial_config)
            
            # Update config (simulate module operation)
            updated_config = initial_config.copy()
            updated_config['count'] = 1
            updated_config['last_user'] = 'test'
            
            # Save updated config
            await kernel_instance.save_module_config('persistence_test', updated_config)
            
            # Load config
            loaded_config = await kernel_instance.get_module_config('persistence_test')
            
            # Should have saved twice
            assert mock_set.call_count == 2
            
            # Last save should have updated values
            last_call_args = mock_set.call_args_list[-1][0]
            last_saved_config = json.loads(last_call_args[2])
            assert last_saved_config['count'] == 1
