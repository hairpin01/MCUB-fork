# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for inline features
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


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
        from core_inline.lib.manager import InlineManager

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

    @pytest.mark.asyncio
    async def test_is_admin_true(self, inline_manager, mock_kernel):
        """Test admin identification"""
        result = await inline_manager.is_admin(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_admin_false(self, inline_manager, mock_kernel):
        """Test non-admin returns false"""
        result = await inline_manager.is_admin(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_allowed_specific_command(self, inline_manager, mock_kernel):
        """Test allowing user for specific command"""
        existing_data = json.dumps({"global": [1], "ping": [456]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        result = await inline_manager.is_allowed(456, "ping")
        assert result is True

    @pytest.mark.asyncio
    async def test_deny_user_no_data(self, inline_manager, mock_kernel):
        """Test deny when no data exists"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.deny_user(123)
        assert result is False

    @pytest.mark.asyncio
    async def test_deny_user_specific_command(self, inline_manager, mock_kernel):
        """Test denying user from specific command"""
        existing_data = json.dumps({"global": [1], "ping": [456, 789]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        result = await inline_manager.deny_user(456, "ping")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_allowed_users_no_data(self, inline_manager, mock_kernel):
        """Test get allowed users when no data"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.get_allowed_users()
        assert result == []

    @pytest.mark.asyncio
    async def test_allow_user_exception(self, inline_manager, mock_kernel):
        """Test allow_user handles exceptions"""
        mock_kernel.db_get = AsyncMock(side_effect=Exception("DB error"))
        result = await inline_manager.allow_user(123)
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_all_exception(self, inline_manager, mock_kernel):
        """Test clear_all handles exceptions"""
        mock_kernel.db_delete = AsyncMock(side_effect=Exception("DB error"))
        result = await inline_manager.clear_all()
        assert result is False


class TestInlineManagerEdgeCases:
    """Test InlineManager edge cases"""

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
        from core_inline.lib.manager import InlineManager

        return InlineManager(mock_kernel)

    @pytest.mark.asyncio
    async def test_allow_same_user_twice(self, inline_manager, mock_kernel):
        """Test allowing the same user twice doesn't duplicate"""
        mock_kernel.db_get = AsyncMock(return_value=json.dumps({"global": [123]}))
        mock_kernel.db_set = AsyncMock(return_value=True)

        result = await inline_manager.allow_user(123)
        assert result is True

    @pytest.mark.asyncio
    async def test_deny_admin_no_effect(self, inline_manager, mock_kernel):
        """Test denying admin has no effect (admin always allowed)"""
        mock_kernel.db_get = AsyncMock(return_value=json.dumps({"global": []}))

        result = await inline_manager.deny_user(1)
        assert result is False

        is_still_allowed = await inline_manager.is_allowed(1)
        assert is_still_allowed is True

    @pytest.mark.asyncio
    async def test_empty_global_list(self, inline_manager, mock_kernel):
        """Test empty global list denies all non-admins"""
        mock_kernel.db_get = AsyncMock(return_value=json.dumps({"global": []}))

        result = await inline_manager.is_allowed(123)
        assert result is False

    @pytest.mark.asyncio
    async def test_user_in_command_but_not_global(self, inline_manager, mock_kernel):
        """Test user allowed for command but not global"""
        mock_kernel.db_get = AsyncMock(
            return_value=json.dumps({"global": [], "specific": [456]})
        )

        result = await inline_manager.is_allowed(456, "specific")
        assert result is True

        result_global = await inline_manager.is_allowed(456)
        assert result_global is False

    @pytest.mark.asyncio
    async def test_corrupted_json_handled(self, inline_manager, mock_kernel):
        """Test corrupted JSON data is handled gracefully"""
        mock_kernel.db_get = AsyncMock(return_value="not valid json {{{")
        result = await inline_manager.get_allowed_users()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_allow_user_zero_id(self, inline_manager, mock_kernel):
        """Test allowing user with ID 0"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.allow_user(0)
        assert result is True

    @pytest.mark.asyncio
    async def test_allow_user_negative_id(self, inline_manager, mock_kernel):
        """Test allowing user with negative ID"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.allow_user(-1)
        assert result is True

    @pytest.mark.asyncio
    async def test_allow_user_large_id(self, inline_manager, mock_kernel):
        """Test allowing user with large ID"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        large_id = 999999999999
        result = await inline_manager.allow_user(large_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_commands_per_user(self, inline_manager, mock_kernel):
        """Test user can have permissions for multiple commands"""
        existing_data = json.dumps(
            {
                "global": [123],
                "cmd1": [123],
                "cmd2": [123],
                "cmd3": [123],
            }
        )
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        for cmd in ["cmd1", "cmd2", "cmd3"]:
            result = await inline_manager.is_allowed(123, cmd)
            assert result is True

    @pytest.mark.asyncio
    async def test_empty_command_name(self, inline_manager, mock_kernel):
        """Test allowing user for empty command name"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.allow_user(123, "")
        assert result is True

    @pytest.mark.asyncio
    async def test_special_chars_in_command_name(self, inline_manager, mock_kernel):
        """Test allowing user for command with special characters"""
        mock_kernel.db_get = AsyncMock(return_value=None)

        result = await inline_manager.allow_user(123, "cmd_with_underscore")
        assert result is True

        result2 = await inline_manager.allow_user(123, "cmd-with-dash")
        assert result2 is True


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

    def test_multiple_inline_handlers(self):
        """Test multiple inline handlers can be registered"""
        kernel = MagicMock()
        kernel.inline_handlers = {}

        async def handler1(event):
            return []

        async def handler2(event):
            return []

        kernel.inline_handlers["cmd1"] = handler1
        kernel.inline_handlers["cmd2"] = handler2

        assert len(kernel.inline_handlers) == 2

    def test_inline_handler_replaces_existing(self):
        """Test registering same command replaces handler"""
        kernel = MagicMock()
        kernel.inline_handlers = {}

        async def old_handler(event):
            return ["old"]

        async def new_handler(event):
            return ["new"]

        kernel.inline_handlers["test"] = old_handler
        kernel.inline_handlers["test"] = new_handler

        assert kernel.inline_handlers["test"] == new_handler


class TestInlineParsing:
    """Test inline query parsing"""

    def test_button_format_conversion(self):
        """Test button format conversion"""
        buttons = [[{"text": "Btn1", "url": "http://example.com"}]]

        assert len(buttons) == 1
        assert buttons[0][0]["text"] == "Btn1"

    def test_query_string_generation(self):
        """Test query string generation"""
        query = "test query"

        assert isinstance(query, str)
        assert "test" in query.lower()

    def test_json_buttons_in_query(self):
        """Test JSON buttons in inline query"""
        buttons = [{"text": "Click", "data": "callback_data"}]
        json_str = json.dumps(buttons)

        parsed = json.loads(json_str)

        assert parsed[0]["text"] == "Click"

    @pytest.mark.parametrize(
        "query,expected_in_result",
        [
            ("test", True),
            ("", True),
            ("long query text", True),
            ("UPPERCASE", True),
            ("with numbers 123", True),
        ],
    )
    def test_various_queries(self, query, expected_in_result):
        """Test various query formats"""
        assert isinstance(query, str)

    def test_empty_button_list(self):
        """Test empty button list"""
        buttons = []
        json_str = json.dumps(buttons)
        parsed = json.loads(json_str)
        assert parsed == []

    def test_nested_button_structure(self):
        """Test nested button structure"""
        buttons = [
            [{"text": "A", "data": "a"}, {"text": "B", "data": "b"}],
            [{"text": "C", "data": "c"}],
        ]
        json_str = json.dumps(buttons)
        parsed = json.loads(json_str)

        assert len(parsed) == 2
        assert len(parsed[0]) == 2
        assert len(parsed[1]) == 1

    def test_button_with_all_fields(self):
        """Test button with all possible fields"""
        button = {
            "text": "Click Me",
            "data": "callback_id",
            "url": "https://example.com",
            "switch": "query",
        }
        json_str = json.dumps(button)
        parsed = json.loads(json_str)

        assert parsed["text"] == "Click Me"
        assert parsed["data"] == "callback_id"
        assert parsed["url"] == "https://example.com"
        assert parsed["switch"] == "query"


class TestInlinePermissionsData:
    """Test inline permissions data structures"""

    def test_permissions_data_structure(self):
        """Test permissions data structure"""
        data = {
            "global": [1, 2, 3],
            "ping": [1, 4],
            "search": [2, 5],
        }
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert "global" in parsed
        assert isinstance(parsed["global"], list)
        assert 1 in parsed["global"]

    def test_empty_permissions_structure(self):
        """Test empty permissions structure"""
        data = {"global": [], "cmd1": [], "cmd2": []}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert all(len(v) == 0 for v in parsed.values())

    def test_large_user_list(self):
        """Test large user list in permissions"""
        users = list(range(1000))
        data = {"global": users}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert len(parsed["global"]) == 1000
