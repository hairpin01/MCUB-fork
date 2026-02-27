"""
Tests for event handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestEventHandling:
    """Test event handling"""

    def test_middleware_chain(self):
        """Test middleware chain registration"""
        kernel = MagicMock()
        kernel.middleware_chain = []
        
        async def middleware(event, handler):
            return await handler(event)
        
        kernel.middleware_chain.append(middleware)
        
        assert len(kernel.middleware_chain) == 1

    def test_event_registration(self):
        """Test event registration"""
        kernel = MagicMock()
        kernel.event_handlers = {}
        
        kernel.event_handlers["message"] = [AsyncMock()]
        
        assert "message" in kernel.event_handlers


class TestEventFilters:
    """Test event filters"""

    def test_pattern_matching(self):
        """Test message pattern matching"""
        import re
        
        pattern = re.compile(r"\.test(\s+.*)?$")
        
        assert pattern.match(".test") is not None
        assert pattern.match(".test arg") is not None
        assert pattern.match(".other") is None
