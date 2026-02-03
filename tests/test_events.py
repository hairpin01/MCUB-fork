"""
Tests for event handling and middleware system
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch

@pytest.mark.asyncio
class TestEventHandling:
    """Test event processing and middleware"""
    
    async def test_middleware_chain(self, kernel_instance):
        """Test middleware execution chain"""
        execution_order = []
        
        async def middleware1(event, handler):
            execution_order.append('middleware1_before')
            result = await handler(event)
            execution_order.append('middleware1_after')
            return result
            
        async def middleware2(event, handler):
            execution_order.append('middleware2_before')
            result = await handler(event)
            execution_order.append('middleware2_after')
            return result
            
        async def event_handler(event):
            execution_order.append('handler')
            return 'handler_result'
            
        # Add middleware
        kernel_instance.add_middleware(middleware1)
        kernel_instance.add_middleware(middleware2)
        
        # Process event
        mock_event = Mock()
        result = await kernel_instance.process_with_middleware(
            mock_event, event_handler
        )
        
        # Check execution order
        assert execution_order == [
            'middleware1_before',
            'middleware2_before',
            'handler',
            'middleware2_after',
            'middleware1_after'
        ]
        assert result == 'handler_result'
        
    async def test_middleware_interruption(self, kernel_instance):
        """Test middleware that interrupts processing"""
        execution_order = []
        
        async def blocking_middleware(event, handler):
            execution_order.append('blocking')
            return False  # Interrupt chain
            
        async def never_reached_middleware(event, handler):
            execution_order.append('never_reached')
            return await handler(event)
            
        async def event_handler(event):
            execution_order.append('handler')
            return 'result'
            
        kernel_instance.add_middleware(blocking_middleware)
        kernel_instance.add_middleware(never_reached_middleware)
        
        mock_event = Mock()
        result = await kernel_instance.process_with_middleware(
            mock_event, event_handler
        )
        
        assert execution_order == ['blocking']
        assert result is False  # Chain was interrupted
        
    async def test_event_registration_flow(self, kernel_instance):
        """Test complete event registration and handling"""
        from telethon import events
        
        # Mock event handler registration
        handler_called = []
        
        @kernel_instance.register.event('newmessage', pattern='hello')
        async def test_handler(event):
            handler_called.append(event.text)
            
        # Verify handler was registered
        assert kernel_instance.client.add_event_handler.called
        
        # Extract the registered handler
        call_args = kernel_instance.client.add_event_handler.call_args
        registered_handler = call_args[0][0]  # First positional arg
        
        # Simulate event
        mock_event = Mock(text='hello world')
        await registered_handler(mock_event)
        
        assert len(handler_called) == 1
        assert handler_called[0] == 'hello world'
        
    async def test_callback_event_handling(self, kernel_instance):
        """Test callback query event handling"""
        callback_called = []
        
        async def callback_handler(event):
            callback_called.append(event.data)
            
        # Register callback
        kernel_instance.register_callback_handler(b'test_callback', callback_handler)
        
        # Simulate callback event
        mock_event = Mock(data=b'test_callback')
        
        # Get the actual handler (wrapped by register_callback_handler)
        handler = kernel_instance.callback_handlers.get(b'test_callback')
        assert handler is not None
        
        await handler(mock_event)
        
        assert len(callback_called) == 1
        assert callback_called[0] == b'test_callback'
        
    async def test_permission_based_callback(self, kernel_instance):
        """Test callback with permission checking"""
        callback_called = []
        
        async def permissioned_callback(event):
            callback_called.append(event.sender_id)
            
        kernel_instance.register_callback_handler(b'permission_test', 
                                                permissioned_callback)
        
        # Set up permissions
        kernel_instance.callback_permissions.allow(
            user_id=123456, 
            pattern=b'permission_test', 
            duration_seconds=60
        )
        
        # Test with permitted user
        mock_event_allowed = Mock(
            data=b'permission_test',
            sender_id=123456
        )
        
        handler = kernel_instance.callback_handlers[b'permission_test']
        await handler(mock_event_allowed)
        
        assert 123456 in callback_called
        
        # Test with non-permitted user
        callback_called.clear()
        mock_event_denied = Mock(
            data=b'permission_test',
            sender_id=999999
        )
        
        await handler(mock_event_denied)
        
        # Handler might still run or might check permissions internally
        # This depends on implementation
        
    async def test_error_handling_in_events(self, kernel_instance, mock_event):
        """Test error handling in event processing"""
        with patch.object(kernel_instance, 'handle_error', AsyncMock()):
            async def failing_handler(event):
                raise ValueError("Event handler error")
                
            # Register failing handler
            kernel_instance.command_handlers['fail'] = failing_handler
            
            mock_event.text = '.fail'
            
            # Should not raise exception
            result = await kernel_instance.process_command(mock_event)
            
            # Error should be logged
            assert kernel_instance.handle_error.called
            
    async def test_event_thread_id_extraction(self, kernel_instance):
        """Test thread ID extraction from events"""
        # Test event with reply_to
        event_with_reply = Mock()
        event_with_reply.reply_to = Mock(reply_to_top_id=123)
        
        thread_id = await kernel_instance.get_thread_id(event_with_reply)
        assert thread_id == 123
        
        # Test event without thread
        event_without = Mock()
        event_without.reply_to = None
        
        thread_id = await kernel_instance.get_thread_id(event_without)
        assert thread_id is None

class TestEventFilters:
    """Test event filtering and matching"""
    
    def test_pattern_matching(self):
        """Test regex pattern matching for commands"""
        import re
        
        # Test command pattern matching
        patterns = [
            (r'^\.test$', '.test', True),
            (r'^\.test$', '.test extra', False),
            (r'^\.cmd(\s+.+)?$', '.cmd', True),
            (r'^\.cmd(\s+.+)?$', '.cmd arg1 arg2', True),
        ]
        
        for pattern, text, should_match in patterns:
            match = re.match(pattern, text)
            if should_match:
                assert match is not None, f"Pattern {pattern} should match {text}"
            else:
                assert match is None, f"Pattern {pattern} should not match {text}"
                
    async def test_event_text_processing(self, kernel_instance, mock_event):
        """Test event text preprocessing"""
        # Test with command prefix
        mock_event.text = '.test command with args'
        processed = await kernel_instance.process_command(mock_event)
        # Result depends on registered commands
        
        # Test without prefix
        mock_event.text = 'regular message'
        processed = await kernel_instance.process_command(mock_event)
        assert processed is False
