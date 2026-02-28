"""
TestKernel - тестовое ядро для разработчиков модулей MCUB

Позволяет запускать и отлаживать модули без реального подключения к Telegram.

Использование:
    from core.kernel.test_kernel import TestKernel
    
    test_kernel = TestKernel()
    await test_kernel.setup()
    
    # Симуляция событий
    await test_kernel.send_message(".ping")
    
    # Проверка результатов
    assert test_kernel.last_response is not None
"""

from unittest.mock import AsyncMock, Mock, MagicMock, patch
from typing import Any, Callable, Optional
import asyncio


class MockEvent:
    """Эмуляция события Telegram"""
    
    def __init__(
        self,
        text: str = "",
        chat_id: int = 123456789,
        sender_id: int = 987654321,
        message_id: int = 1,
        **kwargs
    ):
        self.text = text
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.message_id = message_id
        self._kwargs = kwargs
        
        self.client = Mock()
        self.message = Mock(id=message_id)
        self.reply_to = None
        self.edit = AsyncMock()
        self.reply = AsyncMock()
        self.delete = AsyncMock()
        self.respond = AsyncMock()
        
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockCallback:
    """Эмуляция callback-запроса"""
    
    def __init__(
        self,
        query_id: str = "query_123",
        data: str = "callback_data",
        chat_instance: str = "chat_123",
        **kwargs
    ):
        self.query_id = query_id
        self.data = data
        self.chat_instance = chat_instance
        self._kwargs = kwargs
        
        self.message = Mock()
        self.message.chat_id = 123456789
        self.message.message_id = 1
        self.from_user = Mock(id=987654321)
        
        self.answer = AsyncMock()
        self.edit = AsyncMock()
        self.delete = AsyncMock()


class MockInlineQuery:
    """Эмуляция inline-запроса"""
    
    def __init__(
        self,
        query_id: str = "inline_123",
        query: str = "test query",
        offset: str = "",
        **kwargs
    ):
        self.query_id = query_id
        self.query = query
        self.offset = offset
        self._kwargs = kwargs
        
        self.from_user = Mock(id=987654321)
        self.answer = AsyncMock()


class MockTelegramClient:
    """Полный мок TelegramClient для тестирования"""
    
    def __init__(self, session_name: str = "test", api_id: int = 12345, api_hash: str = "hash"):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        
        self.is_connected = Mock(return_value=True)
        self.is_user_authorized = Mock(return_value=True)
        self.get_me = AsyncMock(return_value=Mock(
            id=123456789,
            first_name="Test",
            last_name="User",
            username="testuser"
        ))
        
        self.start = AsyncMock()
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        
        self.send_message = AsyncMock()
        self.send_file = AsyncMock()
        self.edit_message = AsyncMock()
        self.delete_messages = AsyncMock()
        self.get_messages = AsyncMock(return_value=[])
        self.get_entity = AsyncMock()
        
        self._event_handlers = []
        self._bot_token = None
        
    def on(self, event_cls):
        """Декоратор для регистрации обработчиков событий"""
        def decorator(func):
            self._event_handlers.append((event_cls, func))
            return func
        return decorator
    
    async def simulate_message(self, text: str, chat_id: int = 123456789, sender_id: int = 987654321):
        """Симуляция входящего сообщения"""
        event = MockEvent(text=text, chat_id=chat_id, sender_id=sender_id)
        for event_cls, handler in self._event_handlers:
            if hasattr(event_cls, '__name__') and 'Message' in event_cls.__name__:
                await handler(event)
                break
        return event
    
    async def simulate_callback(self, data: str, query_id: str = "query_123"):
        """Симуляция callback-запроса"""
        callback = MockCallback(query_id=query_id, data=data)
        for event_cls, handler in self._event_handlers:
            if hasattr(event_cls, '__name__') and 'Callback' in event_cls.__name__:
                await handler(callback)
                break
        return callback
    
    async def simulate_inline(self, query: str, query_id: str = "inline_123"):
        """Симуляция inline-запроса"""
        inline_query = MockInlineQuery(query_id=query_id, query=query)
        for event_cls, handler in self._event_handlers:
            if hasattr(event_cls, '__name__') and 'Inline' in event_cls.__name__:
                await handler(inline_query)
                break
        return inline_query


class TestKernel:
    """
    Тестовое ядро для отладки модулей MCUB
    
    Позволяет:
        - Запускать модули без реального подключения к Telegram
        - Симулировать события (сообщения, колбэки, инлайн-запросы)
        - Пошагово отлаживать логику модулей
        - Интегрироваться с pytest
    """
    
    Kernel = None  # Alias for compatibility
    
    def __init__(self, module_path: Optional[str] = None):
        self.client = MockTelegramClient()
        self.kernel = None
        self.module_path = module_path
        
        self.last_response: Optional[str] = None
        self.last_event: Optional[MockEvent] = None
        self.response_history = []
        
    async def setup(self):
        """Инициализация тестового ядра"""
        with patch('telethon.TelegramClient', return_value=self.client), \
             patch('core.kernel.setup_logging'), \
             patch('core.kernel.ConfigManager'), \
             patch('core.kernel.DatabaseManager'):
            
            from core.kernel import Kernel
            self.kernel = Kernel()
            self.kernel.client = self.client
            self.kernel.bot_client = AsyncMock()
            
    async def send_message(self, text: str, chat_id: int = 123456789, sender_id: int = 987654321):
        """Симуляция отправки сообщения боту"""
        event = await self.client.simulate_message(text, chat_id, sender_id)
        self.last_event = event
        
        for handler in self.kernel.command_handlers.values():
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event)
                else:
                    result = handler(event)
                self.last_response = result
                self.response_history.append(result)
            except Exception as e:
                self.last_response = f"Error: {e}"
                
        return event
    
    async def send_callback(self, data: str):
        """Симуляция callback-запроса"""
        callback = await self.client.simulate_callback(data)
        
        for handler in self.kernel.callback_handlers.values():
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(callback)
            except Exception as e:
                self.last_response = f"Error: {e}"
                
        return callback
    
    def reset(self):
        """Сброс состояния"""
        self.last_response = None
        self.last_event = None
        self.response_history = []


def create_test_kernel() -> TestKernel:
    """Создание экземпляра TestKernel"""
    return TestKernel()


async def run_module_test(module_handler: Callable, test_cases: list) -> dict:
    """
    Запуск тестов для модуля
    
    Args:
        module_handler: функция-обработчик модуля
        test_cases: список тестовых случаев
        
    Returns:
        dict с результатами тестов
    """
    results = {
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    for i, test_case in enumerate(test_cases):
        try:
            event = MockEvent(**test_case.get("event", {}))
            expected = test_case.get("expected")
            
            if asyncio.iscoroutinefunction(module_handler):
                result = await module_handler(event)
            else:
                result = module_handler(event)
            
            if expected and result == expected:
                results["passed"] += 1
            elif not expected:
                results["passed"] += 1
            else:
                results["failed"] += 1
                
        except Exception as e:
            results["errors"].append({"test": i, "error": str(e)})
            results["failed"] += 1
            
    return results
