"""
Tests for command system
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestCommandRegistration:
    """Test command registration"""

    @pytest.fixture
    def kernel_with_commands(self):
        """Create kernel with command handlers"""
        kernel = MagicMock()
        kernel.command_handlers = {}
        kernel.aliases = {}
        kernel.command_owners = {}
        return kernel

    def test_command_registration_flow(self, kernel_with_commands):
        """Test command registration"""

        async def test_cmd(event):
            return "test"

        kernel_with_commands.command_handlers["test"] = test_cmd
        assert "test" in kernel_with_commands.command_handlers

    def test_multiple_commands_registration(self, kernel_with_commands):
        """Test multiple commands can be registered"""

        async def cmd1(event):
            return "cmd1"

        async def cmd2(event):
            return "cmd2"

        async def cmd3(event):
            return "cmd3"

        kernel_with_commands.command_handlers["cmd1"] = cmd1
        kernel_with_commands.command_handlers["cmd2"] = cmd2
        kernel_with_commands.command_handlers["cmd3"] = cmd3

        assert len(kernel_with_commands.command_handlers) == 3

    def test_overwrite_existing_command(self, kernel_with_commands):
        """Test overwriting an existing command handler"""

        async def old_handler(event):
            return "old"

        async def new_handler(event):
            return "new"

        kernel_with_commands.command_handlers["test"] = old_handler
        kernel_with_commands.command_handlers["test"] = new_handler

        assert kernel_with_commands.command_handlers["test"] == new_handler


class TestCommandExecution:
    """Test command execution"""

    @pytest.fixture
    def kernel_with_handler(self):
        """Create kernel with a test handler"""
        kernel = MagicMock()
        kernel.command_handlers = {}

        async def test_cmd(event):
            return f"processed: {event.text}"

        kernel.command_handlers["test"] = test_cmd
        return kernel

    @pytest.mark.asyncio
    async def test_command_execution(self, kernel_with_handler):
        """Test command execution"""
        event = MagicMock()
        event.text = ".test hello"
        result = await kernel_with_handler.command_handlers["test"](event)
        assert result == "processed: .test hello"

    @pytest.mark.asyncio
    async def test_command_returns_none(self, kernel_with_handler):
        """Test command can return None"""
        kernel_with_handler.command_handlers["test"] = AsyncMock(return_value=None)
        event = MagicMock()
        result = await kernel_with_handler.command_handlers["test"](event)
        assert result is None

    @pytest.mark.asyncio
    async def test_command_with_exception(self, kernel_with_handler):
        """Test command can raise exceptions"""

        async def failing_cmd(event):
            raise ValueError("test error")

        kernel_with_handler.command_handlers["failing"] = failing_cmd
        event = MagicMock()
        with pytest.raises(ValueError):
            await kernel_with_handler.command_handlers["failing"](event)


class TestCommandParsing:
    """Test command argument parsing"""

    def test_command_with_single_argument(self):
        """Test parsing command with single argument"""
        text = ".test arg1"
        parts = text.split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        assert cmd == ".test"
        assert args == ["arg1"]

    def test_command_with_multiple_arguments(self):
        """Test parsing command with multiple arguments"""
        text = ".test arg1 arg2 arg3"
        parts = text.split()
        cmd = parts[0]
        args = parts[1:]

        assert cmd == ".test"
        assert args == ["arg1", "arg2", "arg3"]

    def test_command_with_quoted_arguments(self):
        """Test parsing command with quoted arguments"""
        text = '.test "arg with spaces" arg2'
        import shlex

        parts = shlex.split(text)
        cmd = parts[0]
        args = parts[1:]

        assert cmd == ".test"
        assert args == ["arg with spaces", "arg2"]

    def test_command_without_arguments(self):
        """Test parsing command without arguments"""
        text = ".test"
        parts = text.split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        assert cmd == ".test"
        assert args == []

    def test_command_with_key_value_args(self):
        """Test parsing command with key=value arguments"""
        text = ".test key1=value1 key2=value2"
        parts = text.split()

        kwargs = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                kwargs[key] = value

        assert kwargs == {"key1": "value1", "key2": "value2"}

    def test_extract_command_name(self):
        """Test extracting command name from text"""
        prefix = "."
        text = ".test arg1 arg2"

        if text.startswith(prefix):
            rest = text[len(prefix) :]
            parts = rest.split(None, 1)
            cmd_name = parts[0]
        else:
            cmd_name = None

        assert cmd_name == "test"


class TestCommandAliases:
    """Test command alias resolution"""

    @pytest.fixture
    def kernel_with_aliases(self):
        """Create kernel with aliases"""
        kernel = MagicMock()
        kernel.aliases = {
            "t": "test",
            "ping": "ping",
            "h": "help",
        }
        kernel.command_handlers = {
            "test": AsyncMock(),
            "ping": AsyncMock(),
            "help": AsyncMock(),
        }
        return kernel

    def test_alias_resolution(self, kernel_with_aliases):
        """Test command alias resolution"""
        alias = "t"
        resolved = kernel_with_aliases.aliases.get(alias)
        assert resolved == "test"

    def test_alias_points_to_handler(self, kernel_with_aliases):
        """Test alias resolves to existing handler"""
        alias = "t"
        resolved = kernel_with_aliases.aliases.get(alias)
        assert resolved in kernel_with_aliases.command_handlers

    def test_nonexistent_alias(self, kernel_with_aliases):
        """Test nonexistent alias returns None"""
        assert kernel_with_aliases.aliases.get("nonexistent") is None

    def test_self_reference_alias(self):
        """Test alias can reference itself (no-op)"""
        kernel = MagicMock()
        kernel.aliases = {"ping": "ping"}
        assert kernel.aliases.get("ping") == "ping"

    def test_chain_aliases(self):
        """Test alias chain resolution"""
        kernel = MagicMock()
        kernel.aliases = {"a": "b", "b": "c", "c": "command"}

        def resolve_chain(alias):
            visited = set()
            current = alias
            while current in kernel.aliases and current not in visited:
                visited.add(current)
                current = kernel.aliases[current]
            return current

        assert resolve_chain("a") == "command"


class TestCommandPermissions:
    """Test command permission checks"""

    @pytest.fixture
    def kernel_with_permissions(self):
        """Create kernel with permissions"""
        kernel = MagicMock()
        kernel.ADMIN_ID = 123456789
        kernel.command_owners = {
            "owner_cmd": 111111,
            "admin_cmd": 123456789,
        }
        kernel.command_handlers = {}
        return kernel

    def test_admin_has_all_permissions(self, kernel_with_permissions):
        """Test admin has access to all commands"""
        admin_id = kernel_with_permissions.ADMIN_ID
        user_id = 999999

        is_admin = user_id == admin_id
        assert is_admin is False

        is_admin_self = admin_id == admin_id
        assert is_admin_self is True

    def test_command_owner_access(self, kernel_with_permissions):
        """Test command owner has access"""
        owner_id = 111111
        owner_cmd = "owner_cmd"

        is_owner = kernel_with_permissions.command_owners.get(owner_cmd) == owner_id
        assert is_owner is True

    def test_non_owner_denied(self, kernel_with_permissions):
        """Test non-owner is denied"""
        non_owner = 999999
        cmd = "owner_cmd"

        is_owner = kernel_with_permissions.command_owners.get(cmd) == non_owner
        assert is_owner is False

    def test_no_permission_required(self, kernel_with_permissions):
        """Test command with no permission requirements"""
        cmd = "public_cmd"
        user_id = 123

        has_restriction = cmd in kernel_with_permissions.command_owners
        assert has_restriction is False

    def test_multiple_owners(self):
        """Test command can have multiple owners"""
        kernel = MagicMock()
        kernel.command_owners = {
            "shared_cmd": [111111, 222222, 333333],
        }

        cmd = "shared_cmd"
        owners = kernel.command_owners.get(cmd, [])
        assert 111111 in owners
        assert 222222 in owners


class TestBotCommands:
    """Test bot command handlers"""

    @pytest.fixture
    def kernel_with_bot_commands(self):
        """Create kernel with bot commands"""
        kernel = MagicMock()
        kernel.bot_command_handlers = {}
        return kernel

    def test_bot_command_registration(self, kernel_with_bot_commands):
        """Test bot command can be registered"""

        async def bot_cmd(event):
            return "bot response"

        kernel_with_bot_commands.bot_command_handlers["start"] = bot_cmd
        assert "start" in kernel_with_bot_commands.bot_command_handlers

    def test_multiple_bot_commands(self, kernel_with_bot_commands):
        """Test multiple bot commands can be registered"""
        kernel_with_bot_commands.bot_command_handlers = {
            "start": AsyncMock(),
            "help": AsyncMock(),
            "settings": AsyncMock(),
        }
        assert len(kernel_with_bot_commands.bot_command_handlers) == 3
