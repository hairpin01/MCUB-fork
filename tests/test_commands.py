"""
Tests for command system and bot commands
"""
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
class TestCommandSystem:
    """Test command registration and execution"""
    
    async def test_command_registration_flow(self, kernel_instance):
        """Test complete command registration workflow"""
        from kernel import Register
        register = Register(kernel_instance)
        
        # Set current module
        kernel_instance.current_loading_module = 'test_module'
        
        command_executed = []
        
        @register.command('testcmd', alias=['tc', 'test'])
        async def command_handler(event):
            command_executed.append(event.text)
            await event.edit("Command executed")
            
        # Verify registration
        assert 'testcmd' in kernel_instance.command_handlers
        assert kernel_instance.command_handlers['testcmd'] == command_handler
        
        # Verify aliases
        assert kernel_instance.aliases['tc'] == 'testcmd'
        assert kernel_instance.aliases['test'] == 'testcmd'
        
        # Verify owner
        assert kernel_instance.command_owners['testcmd'] == 'test_module'
        
    async def test_bot_command_registration(self, kernel_instance):
        """Test bot command registration"""
        from kernel import Register
        register = Register(kernel_instance)
        
        kernel_instance.current_loading_module = 'bot_module'
        
        bot_command_executed = []
        
        @register.bot_command('start')
        async def start_handler(event):
            bot_command_executed.append(event.text)
            await event.respond("Bot started")
            
        @register.bot_command('help topic')
        async def help_handler(event):
            bot_command_executed.append('help')
            
        # Verify registration
        assert 'start' in kernel_instance.bot_command_handlers
        assert 'help' in kernel_instance.bot_command_handlers
        
        # Check pattern storage
        pattern, handler = kernel_instance.bot_command_handlers['help']
        assert pattern == '/help topic'
        assert handler == help_handler
        
    async def test_command_execution(self, kernel_instance, mock_event):
        """Test command handler execution"""
        execution_log = []
        
        async def test_handler(event):
            execution_log.append({
                'command': event.text,
                'sender': event.sender_id
            })
            await event.edit("Done")
            
        # Register command
        kernel_instance.command_handlers['run'] = test_handler
        kernel_instance.custom_prefix = '.'
        
        # Execute
        mock_event.text = '.run'
        result = await kernel_instance.process_command(mock_event)
        
        assert result is True
        assert len(execution_log) == 1
        assert execution_log[0]['command'] == '.run'
        assert mock_event.edit.called
        
    async def test_command_with_arguments(self, kernel_instance, mock_event):
        """Test command argument parsing"""
        args_received = []
        
        async def args_handler(event):
            # Simple argument extraction
            parts = event.text.split()
            args_received.append(parts[1:] if len(parts) > 1 else [])
            
        kernel_instance.command_handlers['args'] = args_handler
        kernel_instance.custom_prefix = '!'
        
        # Test with arguments
        mock_event.text = '!args arg1 arg2 arg3'
        await kernel_instance.process_command(mock_event)
        
        assert args_received[0] == ['arg1', 'arg2', 'arg3']
        
        # Test without arguments
        mock_event.text = '!args'
        await kernel_instance.process_command(mock_event)
        
        assert args_received[1] == []
        
    async def test_bot_command_execution(self, kernel_instance):
        """Test bot command handling"""
        from unittest.mock import AsyncMock
        
        bot_command_log = []
        
        async def bot_command_handler(event):
            bot_command_log.append(event.text)
            await event.respond("Response")
            
        # Register bot command
        kernel_instance.bot_command_handlers['test'] = ('/test', bot_command_handler)
        
        # Mock bot client and event
        mock_bot_event = AsyncMock()
        mock_bot_event.text = '/test'
        
        # Mock process_bot_command method behavior
        # (This would normally be called by bot client event handler)
        async def mock_process_bot_command(event):
            if event.text.startswith('/'):
                cmd = event.text.split()[0][1:]
                if cmd in kernel_instance.bot_command_handlers:
                    pattern, handler = kernel_instance.bot_command_handlers[cmd]
                    await handler(event)
                    return True
            return False
            
        result = await mock_process_bot_command(mock_bot_event)
        
        assert result is True
        assert len(bot_command_log) == 1
        assert bot_command_log[0] == '/test'
        assert mock_bot_event.respond.called
        
    async def test_command_alias_resolution(self, kernel_instance, mock_event):
        """Test command alias resolution"""
        execution_count = 0
        
        async def main_handler(event):
            nonlocal execution_count
            execution_count += 1
            
        # Register command with alias
        kernel_instance.command_handlers['main'] = main_handler
        kernel_instance.aliases['m'] = 'main'
        kernel_instance.aliases['primary'] = 'main'
        kernel_instance.custom_prefix = '.'
        
        # Test all variations
        test_cases = ['.main', '.m', '.primary']
        
        for cmd in test_cases:
            mock_event.text = cmd
            await kernel_instance.process_command(mock_event)
            
        assert execution_count == 3
        
    async def test_command_error_handling(self, kernel_instance, mock_event):
        """Test error handling in commands"""
        with patch.object(kernel_instance, 'handle_error', AsyncMock()):
            async def crashing_command(event):
                raise RuntimeError("Command crash")
                
            kernel_instance.command_handlers['crash'] = crashing_command
            kernel_instance.custom_prefix = '.'
            
            mock_event.text = '.crash'
            
            # Should not raise exception
            result = await kernel_instance.process_command(mock_event)
            
            # Error should be logged
            assert kernel_instance.handle_error.called
            assert 'Command crash' in str(kernel_instance.handle_error.call_args)
            
    async def test_command_permissions(self, kernel_instance, mock_event):
        """Test command permission checking"""
        # Mock admin check
        kernel_instance.ADMIN_ID = 123456
        kernel_instance.is_admin = lambda user_id: user_id == 123456
        
        admin_only_called = []
        
        async def admin_command(event):
            if kernel_instance.is_admin(event.sender_id):
                admin_only_called.append(event.sender_id)
                await event.edit("Admin action")
            else:
                await event.edit("Access denied")
                
        kernel_instance.command_handlers['admin'] = admin_command
        kernel_instance.custom_prefix = '.'
        
        # Test as admin
        mock_event.sender_id = 123456
        mock_event.text = '.admin'
        await kernel_instance.process_command(mock_event)
        
        assert len(admin_only_called) == 1
        assert admin_only_called[0] == 123456
        
        # Test as non-admin
        mock_event.sender_id = 999999
        mock_event.text = '.admin'
        await kernel_instance.process_command(mock_event)
        
        # Only one call (from admin)
        assert len(admin_only_called) == 1
        
    async def test_command_conflict_resolution(self, kernel_instance):
        """Test command conflict detection"""
        from kernel import CommandConflictError, Register
        
        register = Register(kernel_instance)
        
        # First registration
        kernel_instance.current_loading_module = 'module1'
        
        @register.command('conflict')
        async def handler1(event):
            pass
            
        # Try to register same command from different module
        kernel_instance.current_loading_module = 'module2'
        
        with pytest.raises(CommandConflictError) as exc_info:
            @register.command('conflict')
            async def handler2(event):
                pass
                
        assert 'conflict' in str(exc_info.value)
        assert exc_info.value.command == 'conflict'
        
        # Original handler should still be registered
        assert kernel_instance.command_handlers['conflict'] == handler1
        assert kernel_instance.command_owners['conflict'] == 'module1'
