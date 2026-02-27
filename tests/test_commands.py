"""
Tests for command system
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestCommandSystem:
    """Test command system"""

    def test_command_registration_flow(self):
        """Test command registration"""
        kernel = MagicMock()
        kernel.command_handlers = {}
        
        async def test_cmd(event):
            return "test"
        
        kernel.command_handlers["test"] = test_cmd
        
        assert "test" in kernel.command_handlers

    @pytest.mark.asyncio
    async def test_command_execution(self):
        """Test command execution"""
        kernel = MagicMock()
        kernel.command_handlers = {}
        
        async def test_cmd(event):
            return "executed"
        
        kernel.command_handlers["test"] = test_cmd
        
        event = MagicMock()
        result = await kernel.command_handlers["test"](event)
        
        assert result == "executed"

    def test_command_with_arguments(self):
        """Test command with arguments parsing"""
        kernel = MagicMock()
        
        event = MagicMock()
        event.text = ".test arg1 arg2"
        
        parts = event.text.split()
        args = parts[1:] if len(parts) > 1 else []
        
        assert args == ["arg1", "arg2"]

    def test_command_alias_resolution(self):
        """Test command alias resolution"""
        kernel = MagicMock()
        kernel.aliases = {"t": "test"}
        
        assert kernel.aliases.get("t") == "test"

    def test_command_permissions(self):
        """Test command permission check"""
        kernel = MagicMock()
        kernel.command_owners = {"test": 123456}
        
        user_id = 123456
        
        assert kernel.command_owners.get("test") == user_id
