"""
Mock Telegram client for testing
"""
from unittest.mock import AsyncMock, Mock
import asyncio

class MockTelegramClient:
    """Mock Telethon client for testing"""
    
    def __init__(self, session_name, api_id, api_hash, **kwargs):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.kwargs = kwargs
        self._connected = False
        self._authorized = False
        
        # Mock methods
        self.start = AsyncMock()
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.is_connected = Mock(return_value=False)
        self.is_user_authorized = Mock(return_value=False)
        self.get_me = AsyncMock()
        self.send_message = AsyncMock()
        self.send_file = AsyncMock()
        self.edit_message = AsyncMock()
        self.delete_messages = AsyncMock()
        self.inline_query = AsyncMock()
        
        # Event handler storage
        self._event_handlers = []
        
    def add_event_handler(self, handler, event=None):
        """Mock event handler registration"""
        self._event_handlers.append((handler, event))
        
    def on(self, event):
        """Decorator for event handlers"""
        def decorator(func):
            self.add_event_handler(func, event)
            return func
        return decorator
        
    async def simulate_event(self, event_type, **event_data):
        """Simulate receiving an event"""
        for handler, event_filter in self._event_handlers:
            # Simple filter matching (for testing)
            if event_filter is None or event_type in str(event_filter):
                mock_event = Mock(**event_data)
                mock_event.client = self
                await handler(mock_event)
                
    def __call__(self, *args, **kwargs):
        return self
