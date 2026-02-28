"""
Tests for Register class
"""

import pytest
import re
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class TestRegisterClass:
    """Test Register functionality"""

    def test_register_initialization(self):
        """Test Register initialization"""
        kernel = MagicMock()
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        assert register is not None
        assert register.kernel is kernel


class TestCommandPrefixHandling:
    """Test command prefix handling - Bug fix for lstrip regex issue"""

    def test_strips_prefix_correctly(self):
        """Test that prefix is stripped correctly, not via lstrip"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.current_loading_module = "test_module"
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        @register.command("test")
        async def test_handler(event):
            pass
        
        assert "test" in kernel.command_handlers

    def test_strips_prefix_with_anchor(self):
        """Test stripping prefix with ^ anchor"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.current_loading_module = "test_module"
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        @register.command("^.test")
        async def test_handler(event):
            pass
        
        assert "test" in kernel.command_handlers

    def test_strips_escaped_prefix(self):
        """Test stripping escaped prefix"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.current_loading_module = "test_module"
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        @register.command("\\.test")
        async def test_handler(event):
            pass
        
        assert "test" in kernel.command_handlers

    def test_dollar_sign_removed(self):
        """Test that $ is removed from pattern"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.current_loading_module = "test_module"
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        @register.command("test$")
        async def test_handler(event):
            pass
        
        assert "test" in kernel.command_handlers

    def test_special_prefix_characters(self):
        """Test handling of special regex characters in prefix"""
        kernel = MagicMock()
        kernel.custom_prefix = "?"
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.current_loading_module = "test_module"
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        @register.command("test")
        async def test_handler(event):
            pass
        
        assert "test" in kernel.command_handlers


class TestGetOrCreateRegister:
    """Test _get_or_create_register method"""

    def test_creates_register_object(self):
        """Test that register object is created if not exists"""
        from core.lib.loader.register import Register
        
        module = MagicMock()
        del module.register
        
        reg = Register._get_or_create_register(module)
        
        assert hasattr(module, 'register')

    def test_returns_existing_register(self):
        """Test that existing register is returned"""
        from core.lib.loader.register import Register
        
        existing = MagicMock()
        module = MagicMock()
        module.register = existing
        
        reg = Register._get_or_create_register(module)
        
        assert reg is existing


class TestEnsureList:
    """Test _ensure_list method"""

    def test_creates_list_if_not_exists(self):
        """Test that list is created if attribute doesn't exist"""
        from core.lib.loader.register import Register
        
        reg = MagicMock()
        del reg.test_list
        
        result = Register._ensure_list(reg, 'test_list')
        
        assert isinstance(result, list)

    def test_returns_existing_list(self):
        """Test that existing list is returned"""
        from core.lib.loader.register import Register
        
        existing = ['item1', 'item2']
        reg = MagicMock()
        reg.test_list = existing
        
        result = Register._ensure_list(reg, 'test_list')
        
        assert result is existing


class TestInfiniteLoop:
    """Test InfiniteLoop class"""

    @pytest.mark.asyncio
    async def test_loop_starts_and_stops(self):
        """Test loop can be started and stopped"""
        from core.lib.loader.register import InfiniteLoop
        
        async def dummy_func(kernel):
            await asyncio.sleep(0.01)
        
        loop = InfiniteLoop(dummy_func, interval=1, autostart=False, wait_before=False)
        loop._kernel = MagicMock()
        
        loop.start()
        await asyncio.sleep(0.05)
        
        assert loop.status is True
        
        loop.stop()
        assert loop.status is False

    @pytest.mark.asyncio
    async def test_loop_not_started_twice(self):
        """Test that loop doesn't start if already running"""
        from core.lib.loader.register import InfiniteLoop
        
        async def dummy_func(kernel):
            await asyncio.sleep(10)
        
        loop = InfiniteLoop(dummy_func, interval=1, autostart=False, wait_before=False)
        loop._kernel = MagicMock()
        
        loop.start()
        first_task = loop._task
        
        loop.start()
        second_task = loop._task
        
        assert first_task is second_task
        
        loop.stop()

    def test_loop_repr(self):
        """Test loop string representation"""
        from core.lib.loader.register import InfiniteLoop
        
        async def my_func(kernel):
            pass
        
        loop = InfiniteLoop(my_func, interval=60, autostart=True, wait_before=False)
        
        repr_str = repr(loop)
        
        assert "my_func" in repr_str
        assert "60" in repr_str


class TestWatcherFilters:
    """Test _watcher_passes_filters function"""

    def test_out_filter_true(self):
        """Test outgoing message filter with out=True"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = True
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = ""
        event.message = msg
        
        assert _watcher_passes_filters(event, {"out": True}) is True

    def test_out_filter_true_rejects_incoming(self):
        """Test that out=True rejects incoming messages"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = False
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = ""
        event.message = msg
        
        assert _watcher_passes_filters(event, {"out": True}) is False

    def test_incoming_filter_true(self):
        """Test incoming message filter with incoming=True"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = False
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = ""
        event.message = msg
        
        assert _watcher_passes_filters(event, {"incoming": True}) is True

    def test_incoming_filter_true_rejects_outgoing(self):
        """Test that incoming=True rejects outgoing messages"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = True
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = ""
        event.message = msg
        
        assert _watcher_passes_filters(event, {"incoming": True}) is False

    def test_regex_filter(self):
        """Test regex text filter"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = False
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = "Hello world"
        event.message = msg
        
        assert _watcher_passes_filters(event, {"regex": r"Hello"}) is True
        assert _watcher_passes_filters(event, {"regex": r"goodbye"}) is False

    def test_startswith_filter(self):
        """Test startswith text filter"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = False
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = "Hello world"
        event.message = msg
        
        assert _watcher_passes_filters(event, {"startswith": "Hello"}) is True
        assert _watcher_passes_filters(event, {"startswith": "world"}) is False

    def test_endswith_filter(self):
        """Test endswith text filter"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = False
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = "Hello world"
        event.message = msg
        
        assert _watcher_passes_filters(event, {"endswith": "world"}) is True
        assert _watcher_passes_filters(event, {"endswith": "Hello"}) is False

    def test_contains_filter(self):
        """Test contains text filter"""
        from core.lib.loader.register import _watcher_passes_filters
        
        event = MagicMock()
        msg = MagicMock()
        msg.out = False
        msg.media = None
        msg.fwd_from = None
        msg.reply_to = None
        msg.text = "Hello world"
        event.message = msg
        
        assert _watcher_passes_filters(event, {"contains": "lo"}) is True
        assert _watcher_passes_filters(event, {"contains": "xyz"}) is False


class TestUnregisterCommand:
    """Test unregister_command method"""

    def test_unregister_existing_command(self):
        """Test unregistering existing command"""
        kernel = MagicMock()
        kernel.command_handlers = {"test": MagicMock()}
        kernel.command_owners = {"test": "module1"}
        kernel.command_metadata = {"test": {}}
        kernel.aliases = {"t": "test"}
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        result = register.unregister_command("test")
        
        assert result is True
        assert "test" not in kernel.command_handlers

    def test_unregister_nonexistent_command(self):
        """Test unregistering non-existent command"""
        kernel = MagicMock()
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.command_metadata = {}
        kernel.aliases = {}
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        result = register.unregister_command("nonexistent")
        
        assert result is False

    def test_unregister_removes_aliases(self):
        """Test that aliases are removed when command is unregistered"""
        kernel = MagicMock()
        kernel.command_handlers = {"test": MagicMock()}
        kernel.command_owners = {"test": "module1"}
        kernel.command_metadata = {"test": {}}
        kernel.aliases = {"t": "test", "tt": "test"}
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        
        register.unregister_command("test")
        
        assert "t" not in kernel.aliases
        assert "tt" not in kernel.aliases


class TestGetRegisteredMethods:
    """Test get_registered_methods method"""

    def test_returns_copy_of_methods(self):
        """Test that a copy is returned"""
        kernel = MagicMock()
        
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        register._methods = {"method1": lambda: None}
        
        result = register.get_registered_methods()
        
        assert "method1" in result
        assert result is not register._methods
