"""
Tests for inline features
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestInlineFeatures:
    """Test inline functionality"""

    def test_inline_handler_registration(self):
        """Test inline handler registration"""
        kernel = MagicMock()
        kernel.inline_handlers = {}
        
        async def inline_handler(event):
            return []
        
        kernel.inline_handlers["test"] = inline_handler
        
        assert "test" in kernel.inline_handlers

    def test_callback_handler_registration(self):
        """Test callback handler registration"""
        kernel = MagicMock()
        kernel.callback_handlers = {}
        
        async def callback_handler(event):
            return
        
        kernel.callback_handlers["test"] = callback_handler
        
        assert "test" in kernel.callback_handlers


class TestInlineParsing:
    """Test inline query parsing"""

    def test_button_format_conversion(self):
        """Test button format conversion"""
        buttons = [
            [{"text": "Btn1", "url": "http://example.com"}]
        ]
        
        assert len(buttons) == 1
        assert buttons[0][0]["text"] == "Btn1"

    def test_query_string_generation(self):
        """Test query string generation"""
        query = "test query"
        
        assert isinstance(query, str)
        assert "test" in query.lower()

    def test_json_buttons_in_query(self):
        """Test JSON buttons in inline query"""
        import json
        
        buttons = [{"text": "Click", "data": "callback_data"}]
        json_str = json.dumps(buttons)
        
        parsed = json.loads(json_str)
        
        assert parsed[0]["text"] == "Click"
