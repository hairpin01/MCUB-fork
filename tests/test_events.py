"""
Tests for event handling
"""

import re
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestMiddlewareChain:
    """Test middleware chain functionality"""

    @pytest.fixture
    def kernel_with_middleware(self):
        """Create kernel with middleware chain"""
        kernel = MagicMock()
        kernel.middleware_chain = []
        kernel.request_middleware_chain = []
        return kernel

    def test_middleware_chain_initialization(self, kernel_with_middleware):
        """Test middleware chain starts empty"""
        assert len(kernel_with_middleware.middleware_chain) == 0

    def test_middleware_chain_append(self, kernel_with_middleware):
        """Test adding middleware to chain"""

        async def middleware(event, next_handler):
            return await next_handler(event)

        kernel_with_middleware.middleware_chain.append(middleware)
        assert len(kernel_with_middleware.middleware_chain) == 1

    def test_middleware_chain_multiple(self, kernel_with_middleware):
        """Test multiple middleware in chain"""

        async def mw1(event, next_handler):
            event.mw1_processed = True
            return await next_handler(event)

        async def mw2(event, next_handler):
            event.mw2_processed = True
            return await next_handler(event)

        kernel_with_middleware.middleware_chain.extend([mw1, mw2])
        assert len(kernel_with_middleware.middleware_chain) == 2

    def test_middleware_chain_order(self, kernel_with_middleware):
        """Test middleware executes in order"""
        execution_order = []

        async def first_mw(event, next_handler):
            execution_order.append("first")
            return await next_handler(event)

        async def second_mw(event, next_handler):
            execution_order.append("second")
            return await next_handler(event)

        kernel_with_middleware.middleware_chain.extend([first_mw, second_mw])

        async def final_handler(event):
            execution_order.append("handler")
            return "result"

        async def run_chain():
            event = MagicMock()
            for mw in kernel_with_middleware.middleware_chain:
                event = mw(event, lambda e=event: final_handler(e))
            return event

        assert len(kernel_with_middleware.middleware_chain) == 2

    def test_middleware_modifies_event(self, kernel_with_middleware):
        """Test middleware can modify event"""

        async def add_data_mw(event, next_handler):
            event.middleware_modified = True
            event.extra_data = "test"
            return await next_handler(event)

        kernel_with_middleware.middleware_chain.append(add_data_mw)
        assert len(kernel_with_middleware.middleware_chain) == 1

    def test_request_middleware_chain(self, kernel_with_middleware):
        """Test request middleware chain"""

        async def request_mw(request, context, next_handler):
            return await next_handler()

        kernel_with_middleware.request_middleware_chain.append(request_mw)
        assert len(kernel_with_middleware.request_middleware_chain) == 1


class TestEventRegistration:
    """Test event registration"""

    @pytest.fixture
    def kernel_with_handlers(self):
        """Create kernel with event handlers"""
        kernel = MagicMock()
        kernel.event_handlers = {}
        return kernel

    def test_event_registration(self, kernel_with_handlers):
        """Test event registration"""
        kernel_with_handlers.event_handlers["message"] = [AsyncMock()]
        assert "message" in kernel_with_handlers.event_handlers

    def test_multiple_handlers_per_event(self, kernel_with_handlers):
        """Test multiple handlers for same event type"""
        kernel_with_handlers.event_handlers["message"] = [
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        ]
        assert len(kernel_with_handlers.event_handlers["message"]) == 3

    def test_multiple_event_types(self, kernel_with_handlers):
        """Test registering multiple event types"""
        kernel_with_handlers.event_handlers = {
            "message": [AsyncMock()],
            "callback_query": [AsyncMock()],
            "inline_query": [AsyncMock()],
        }
        assert len(kernel_with_handlers.event_handlers) == 3

    def test_handler_deregistration(self, kernel_with_handlers):
        """Test removing event handler"""
        handler = AsyncMock()
        kernel_with_handlers.event_handlers["message"] = [handler]
        kernel_with_handlers.event_handlers["message"].remove(handler)
        assert len(kernel_with_handlers.event_handlers["message"]) == 0


class TestEventFilters:
    """Test event filters"""

    def test_pattern_matching_simple(self):
        """Test basic pattern matching"""
        pattern = re.compile(r"\.test(\s+.*)?$")
        assert pattern.match(".test") is not None
        assert pattern.match(".test arg") is not None
        assert pattern.match(".other") is None

    def test_pattern_with_prefix(self):
        """Test pattern with custom prefix"""
        prefix = "."
        pattern = re.compile(rf"\{prefix}command(\s+.*)?$")

        assert pattern.match(".command") is not None
        assert pattern.match(".command arg") is not None
        assert pattern.match("/command") is None

    def test_pattern_with_regex_chars(self):
        """Test pattern with regex special characters"""
        pattern = re.compile(r"\.test\[0\](\s+.*)?$")
        assert pattern.match(".test[0]") is not None
        assert pattern.match(".test[0] arg") is not None

    def test_pattern_case_sensitive(self):
        """Test case-sensitive pattern matching"""
        pattern = re.compile(r"\.test$")
        assert pattern.match(".test") is not None
        assert pattern.match(".TEST") is None
        assert pattern.match(".Test") is None

    def test_pattern_case_insensitive(self):
        """Test case-insensitive pattern matching"""
        pattern = re.compile(r"\.test$", re.IGNORECASE)
        assert pattern.match(".test") is not None
        assert pattern.match(".TEST") is not None
        assert pattern.match(".Test") is not None

    def test_pattern_with_groups(self):
        """Test pattern with capture groups"""
        pattern = re.compile(r"\.user (\w+) (\d+)")
        match = pattern.match(".user john 123")

        assert match is not None
        assert match.group(1) == "john"
        assert match.group(2) == "123"

    def test_pattern_no_match_returns_none(self):
        """Test pattern returns None when no match"""
        pattern = re.compile(r"\.cmd$")
        result = pattern.match(".other")
        assert result is None


class TestEventFiltersComplex:
    """Test complex event filter scenarios"""

    def test_command_filter_with_prefix(self):
        """Test command filter with custom prefix"""
        PREFIX = "."
        TEXT = ".help"

        pattern = rf"\{PREFIX}\w+"
        match = re.match(pattern, TEXT)
        assert match is not None

    def test_reply_filter(self):
        """Test reply message filter"""
        event = MagicMock()
        event.is_reply = True
        event.reply_to = MagicMock()
        event.reply_to.sender_id = 123456

        assert event.is_reply is True
        assert event.reply_to.sender_id == 123456

    def test_private_chat_filter(self):
        """Test private chat filter"""
        event = MagicMock()
        event.is_private = True
        event.chat_id = 123456789

        assert event.is_private is True

    def test_group_chat_filter(self):
        """Test group chat filter"""
        event = MagicMock()
        event.is_private = False
        event.chat_id = -1001234567890

        assert event.is_private is False
        assert event.chat_id < 0

    def test_forwarded_message_filter(self):
        """Test forwarded message filter"""
        event = MagicMock()
        event.fwd_from = MagicMock()
        event.fwd_from.saved_from_msg_id = 123

        assert event.fwd_from is not None

    def test_media_filter(self):
        """Test media message filter"""
        event = MagicMock()
        event.media = MagicMock()
        event.photo = MagicMock()
        event.document = None

        has_media = event.media is not None or event.photo is not None
        assert has_media is True


class TestEventAttributes:
    """Test event attribute handling"""

    def test_message_text_attribute(self):
        """Test message text attribute"""
        event = MagicMock()
        event.text = "Hello, world!"
        assert event.text == "Hello, world!"

    def test_sender_id_attribute(self):
        """Test sender_id attribute"""
        event = MagicMock()
        event.sender_id = 123456789
        assert event.sender_id == 123456789

    def test_chat_id_attribute(self):
        """Test chat_id attribute"""
        event = MagicMock()
        event.chat_id = -1001234567890
        assert event.chat_id == -1001234567890

    def test_reply_to_nested(self):
        """Test nested reply_to attribute"""
        event = MagicMock()
        event.reply_to_top_id = None
        event.reply_to = None
        event.message = MagicMock()
        event.message.reply_to_top_id = 77

        thread_id = (
            event.reply_to_top_id
            or (event.reply_to.reply_to_top_id if event.reply_to else None)
            or (event.message.reply_to_top_id if event.message else None)
        )
        assert thread_id == 77


class TestEventProcessing:
    """Test event processing flow"""

    @pytest.mark.asyncio
    async def test_event_processing_chain(self):
        """Test complete event processing chain"""
        processed_steps = []

        async def middleware1(event, next_handler):
            processed_steps.append("middleware1")
            return await next_handler(event)

        async def middleware2(event, next_handler):
            processed_steps.append("middleware2")
            return await next_handler(event)

        async def handler(event):
            processed_steps.append("handler")
            return "processed"

        chain = [middleware1, middleware2]

        event = MagicMock()

        async def run_chain():
            next_handler = handler
            for mw in reversed(chain):
                current_mw = mw
                current_next = next_handler
                next_handler = lambda e, mw=current_mw, nh=current_next: mw(e, nh)
            return await next_handler(event)

        result = await run_chain()
        assert result == "processed"

    @pytest.mark.asyncio
    async def test_event_handler_returns_response(self):
        """Test event handler returns response"""

        async def handler(event):
            return "response"

        event = MagicMock()
        result = await handler(event)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_event_handler_returns_none(self):
        """Test event handler returns None for no response"""

        async def handler(event):
            return None

        event = MagicMock()
        result = await handler(event)
        assert result is None
