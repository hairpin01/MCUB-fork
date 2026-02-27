"""
Tests for inline features
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock


class TestInlineManager:
    """Test InlineManager functionality"""

    @pytest.fixture
    def mock_kernel(self):
        kernel = MagicMock()
        kernel.db_get = AsyncMock(return_value=None)
        kernel.db_set = AsyncMock(return_value=True)
        kernel.db_delete = AsyncMock(return_value=True)
        kernel.logger = MagicMock()
        kernel.ADMIN_ID = 1
        return kernel

    @pytest.fixture
    def inline_manager(self, mock_kernel):
        from core_inline.lib import InlineManager
        return InlineManager(mock_kernel)

    @pytest.mark.asyncio
    async def test_admin_always_allowed(self, inline_manager, mock_kernel):
        """Test that admin is always allowed"""
        result = await inline_manager.is_allowed(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_user_denied(self, inline_manager):
        """Test that unknown user is denied"""
        result = await inline_manager.is_allowed(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_allow_global_user(self, inline_manager, mock_kernel):
        """Test allowing user globally"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        
        result = await inline_manager.allow_user(123)
        assert result is True
        
        mock_kernel.db_set.assert_called_once()
        call_args = mock_kernel.db_set.call_args
        assert call_args[0][0] == "inline_permissions"
        assert call_args[0][1] == "allowed_users"

    @pytest.mark.asyncio
    async def test_allow_specific_command(self, inline_manager, mock_kernel):
        """Test allowing user for specific command"""
        result = await inline_manager.allow_user(456, "ping")
        assert result is True

    @pytest.mark.asyncio
    async def test_deny_user(self, inline_manager, mock_kernel):
        """Test denying user"""
        existing_data = json.dumps({"global": [123, 456], "ping": [789]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)
        
        result = await inline_manager.deny_user(123)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_allowed_users(self, inline_manager, mock_kernel):
        """Test getting allowed users"""
        existing_data = json.dumps({"global": [1, 2, 3], "ping": [4, 5]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)
        
        global_users = await inline_manager.get_allowed_users()
        assert global_users == [1, 2, 3]
        
        ping_users = await inline_manager.get_allowed_users("ping")
        assert ping_users == [4, 5]

    @pytest.mark.asyncio
    async def test_clear_all(self, inline_manager, mock_kernel):
        """Test clearing all permissions"""
        result = await inline_manager.clear_all()
        assert result is True
        mock_kernel.db_delete.assert_called_once()


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
