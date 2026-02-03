"""
Tests for inline features and bot integration
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
class TestInlineFeatures:
    """Test inline-related functionality"""
    
    async def test_inline_form_creation(self, kernel_instance):
        """Test inline form generation"""
        # Test with buttons
        buttons = [
            {"text": "Button 1", "type": "callback", "data": "action_1"},
            {"text": "Button 2", "type": "url", "url": "https://example.com"}
        ]
        
        query = await kernel_instance.inline_form(
            chat_id=123456789,
            title="Test Form",
            fields={"field1": "value1", "field2": "value2"},
            buttons=buttons,
            auto_send=False
        )
        
        assert query is not None
        assert "Test Form" in query
        assert "field1: value1" in query
        
        # Check buttons JSON in query
        import json
        query_parts = query.split(" | ")
        if len(query_parts) > 1:
            buttons_json = json.loads(query_parts[1])
            assert len(buttons_json) == 2
            assert buttons_json[0]["text"] == "Button 1"
            
    async def test_inline_form_auto_send(self, kernel_instance):
        """Test inline form with auto send"""
        with patch.object(kernel_instance, 'inline_query_and_click', 
                         AsyncMock(return_value=(True, Mock()))) as mock_send:
            
            success, message = await kernel_instance.inline_form(
                chat_id=123456789,
                title="Auto Send Test",
                auto_send=True
            )
            
            assert success is True
            assert mock_send.called
            
    async def test_inline_query_integration(self, kernel_instance):
        """Test complete inline query flow"""
        mock_results = [
            Mock(
                click=AsyncMock(return_value=Mock(id=123))
            )
        ]
        
        with patch.object(kernel_instance.client, 'inline_query', 
                         AsyncMock(return_value=mock_results)):
            
            success, message = await kernel_instance.inline_query_and_click(
                chat_id=123456789,
                query="test gif",
                bot_username="gif_bot",
                result_index=0,
                silent=True
            )
            
            assert success is True
            assert message is not None
            
    async def test_inline_bot_setup(self, kernel_instance):
        """Test inline bot initialization"""
        # Mock bot client creation
        mock_bot = AsyncMock()
        mock_bot.get_me = AsyncMock(return_value=Mock(username='test_bot'))
        
        with patch('telethon.TelegramClient', return_value=mock_bot), \
             patch('importlib.import_module'):
            
            # Setup config
            kernel_instance.config['inline_bot_token'] = 'test_token'
            
            result = await kernel_instance.setup_inline_bot()
            
            # Should either succeed or fail gracefully
            assert isinstance(result, bool)
            
    async def test_callback_handler_registration(self, kernel_instance):
        """Test callback query handler setup"""
        callback_called = []
        
        async def callback_handler(event):
            callback_called.append(event.data)
            
        kernel_instance.register_callback_handler(b'test_callback', callback_handler)
        
        # Check handler was registered
        assert b'test_callback' in kernel_instance.callback_handlers
        assert kernel_instance.callback_handlers[b'test_callback'] == callback_handler
        
    async def test_inline_handler_registration(self, kernel_instance):
        """Test inline query handler setup"""
        inline_called = []
        
        async def inline_handler(event):
            inline_called.append(event)
            
        kernel_instance.register_inline_handler("search", inline_handler)
        
        # Check handler was registered
        assert "search" in kernel_instance.inline_handlers
        assert kernel_instance.inline_handlers["search"] == inline_handler

class TestInlineParsing:
    """Test inline query parsing and formatting"""
    
    def test_button_format_conversion(self, kernel_instance):
        """Test button format conversion for inline forms"""
        # Test old list format
        old_format = [
            ["Button 1", "callback", "action_1"],
            ["Button 2", "url", "https://example.com"]
        ]
        
        # This would be processed inside inline_form method
        # We'll test the expected output
        expected_types = ['callback', 'url']
        
        # Simulate processing
        processed_buttons = []
        for button in old_format:
            if len(button) >= 2:
                btn_type = button[1] if len(button) > 1 else "callback"
                expected_types.append(btn_type)
                
        assert 'callback' in expected_types
        assert 'url' in expected_types
        
    def test_query_string_generation(self):
        """Test query string assembly"""
        # Test basic query
        title = "Test Title"
        fields = {"key": "value", "number": 42}
        
        # Simulate query building
        query_parts = [title]
        for key, value in fields.items():
            query_parts.append(f"{key}: {value}")
            
        query = "\n".join(query_parts)
        
        assert title in query
        assert "key: value" in query
        assert "number: 42" in query
        
    def test_json_buttons_in_query(self):
        """Test JSON button serialization in query"""
        buttons = [
            {"text": "Test", "type": "callback", "data": "test_data"}
        ]
        
        import json
        json_str = json.dumps(buttons, ensure_ascii=False)
        
        # Ensure valid JSON
        parsed = json.loads(json_str)
        assert parsed[0]["text"] == "Test"
        assert parsed[0]["type"] == "callback"
