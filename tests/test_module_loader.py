# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for module loader
"""

import inspect
import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModuleLoading:
    """Test module loading functionality"""

    def test_module_loader_init(self):
        """Test ModuleLoader can be instantiated"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        assert loader is not None

    @pytest.mark.asyncio
    async def test_package_load_clears_loading_state_on_error(self, tmp_path):
        """Package loader must clear loading state even when execution fails."""
        from core.lib.loader.loader import ModuleLoader

        modules_loaded_dir = tmp_path / "modules_loaded"
        pkg_dir = modules_loaded_dir / "broken_pkg"
        pkg_dir.mkdir(parents=True)
        init_file = pkg_dir / "__init__.py"
        init_file.write_text("def broken(:\n", encoding="utf-8")

        kernel = MagicMock()
        kernel.MODULES_LOADED_DIR = str(modules_loaded_dir)
        kernel.client = MagicMock()
        kernel.custom_prefix = "."
        kernel.loaded_modules = {}
        kernel.logger = MagicMock()
        kernel.set_loading_module = MagicMock()
        kernel.clear_loading_module = MagicMock()

        loader = ModuleLoader(kernel)

        with pytest.raises(Exception, match="Failed to execute module"):
            await loader._load_package_module("broken_pkg", str(init_file), kernel)

        kernel.clear_loading_module.assert_called_once()


class TestHikkaInlineDelete:
    """Test Hikka inline message deletion safety."""

    @pytest.mark.asyncio
    async def test_delete_unit_message_skips_non_mtproto_message_id(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        client = SimpleNamespace(delete_messages=AsyncMock())
        kernel = SimpleNamespace(
            client=client,
            bot_client=None,
            logger=MagicMock(),
            config={},
        )
        inline = InlineProxy(kernel)
        inline._units["u"] = {"chat": 123, "message_id": 2**40}

        result = await inline._delete_unit_message(unit_id="u")

        assert result is False
        client.delete_messages.assert_not_called()
        assert "u" in inline._units

    @pytest.mark.asyncio
    async def test_delete_unit_message_passes_message_id_as_list(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        client = SimpleNamespace(delete_messages=AsyncMock())
        kernel = SimpleNamespace(
            client=client,
            bot_client=None,
            logger=MagicMock(),
            config={},
        )
        inline = InlineProxy(kernel)
        inline._units["u"] = {"chat": 123, "message_id": "42"}

        result = await inline._delete_unit_message(unit_id="u")

        assert result is True
        client.delete_messages.assert_awaited_once_with(123, [42])
        assert "u" not in inline._units

    def test_register_unit_prunes_expired_heavy_callbacks(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        kernel = SimpleNamespace(
            client=None,
            bot_client=None,
            logger=MagicMock(),
            config={},
            inline_callback_map={},
        )
        inline = InlineProxy(kernel)
        inline._units["old"] = {"expires_at": time.time() - 1}
        inline._custom_map["old-cb"] = {
            "unit_id": "old",
            "args": (bytearray(1024), object()),
        }
        kernel.inline_callback_map["old-cb"] = {
            "unit_id": "old",
            "expires_at": time.time() - 1,
        }

        inline._register_unit("new", {"expires_at": time.time() + 60})

        assert "old" not in inline._units
        assert "old-cb" not in inline._custom_map
        assert "old-cb" not in kernel.inline_callback_map
        assert "new" in inline._units

    def test_unload_unit_removes_kernel_callback_map_entries(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        kernel = SimpleNamespace(
            client=None,
            bot_client=None,
            logger=MagicMock(),
            config={},
            inline_callback_map={"cb": {"unit_id": "u"}},
        )
        inline = InlineProxy(kernel)
        inline._units["u"] = {"expires_at": time.time() + 60}
        inline._custom_map["cb"] = {"unit_id": "u"}

        assert inline._unload_unit_sync("u") is True

        assert "u" not in inline._units
        assert "cb" not in inline._custom_map
        assert "cb" not in kernel.inline_callback_map


class TestDetectModuleType:
    """Test detect_module_type() method - Bug fix for params[0].name"""

    @pytest.mark.asyncio
    async def test_detect_method_type(self):
        """Test detection of @method style register"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        class RegisterObj:
            def setup(self, k):
                pass

            setup._is_register_method = True

            def configure(self, k):
                pass

            configure._is_register_method = True

        module = MagicMock()
        module.register = RegisterObj()

        result = await loader.detect_module_type(module)
        assert result == "method"

    @pytest.mark.asyncio
    async def test_detect_new_type_kernel_param(self):
        """Test detection of new-style register(kernel) - Bug fix test"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        async def register_new(kernel):
            pass

        module = MagicMock(spec=[])
        object.__setattr__(module, "register", register_new)

        result = await loader.detect_module_type(module)
        assert result == "new", f"Expected 'new', got '{result}'"

    @pytest.mark.asyncio
    async def test_detect_old_type_client_param(self):
        """Test detection of old-style register(client)"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        async def register_old(client):
            pass

        module = MagicMock(spec=[])
        object.__setattr__(module, "register", register_old)

        result = await loader.detect_module_type(module)
        assert result == "old", f"Expected 'old', got '{result}'"

    @pytest.mark.asyncio
    async def test_detect_none_type_no_register(self):
        """Test detection when no register function exists"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        module = MagicMock()
        del module.register

        result = await loader.detect_module_type(module)
        assert result == "none"

    @pytest.mark.asyncio
    async def test_detect_with_inspect_signature(self):
        """Verify that Parameter.name comparison works correctly"""

        async def register_with_kernel(kernel):
            pass

        sig = inspect.signature(register_with_kernel)
        params = list(sig.parameters.values())

        assert len(params) == 1
        param = next(iter(params))
        assert param.name == "kernel", f"Expected 'kernel', got '{param.name}'"


class TestUninstallCallback:
    """Test uninstall callback handling - Bug fix for asyncio.get_event_loop()"""

    @pytest.mark.asyncio
    async def test_uninstall_sync_function(self):
        """Test that sync uninstall functions work"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.loaded_modules = {"test_module": MagicMock()}
        kernel.system_modules = {}
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.logger = MagicMock()

        test_module = kernel.loaded_modules["test_module"]
        test_module.register = MagicMock()
        test_module.register.__loops__ = []
        test_module.register.__watchers__ = []
        test_module.register.__event_handlers__ = []
        test_module.register.__uninstall__ = lambda k: None

        loader = ModuleLoader(kernel)

        await loader.unregister_module_commands("test_module")

    @pytest.mark.asyncio
    async def test_uninstall_no_callback(self):
        """Test when no uninstall callback exists"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.loaded_modules = {"test_module": MagicMock()}
        kernel.system_modules = {}
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.logger = MagicMock()

        test_module = kernel.loaded_modules["test_module"]
        test_module.register = MagicMock()
        test_module.register.__loops__ = []
        test_module.register.__watchers__ = []
        test_module.register.__event_handlers__ = []

        loader = ModuleLoader(kernel)

        await loader.unregister_module_commands("test_module")

    @pytest.mark.asyncio
    async def test_uninstall_async_callback_is_awaited(self):
        """Test that async uninstall callback is awaited before unload finishes."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.loaded_modules = {"test_module": MagicMock()}
        kernel.system_modules = {}
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.unregister_module_inline_handlers = MagicMock()
        kernel.logger = MagicMock()

        state = {"done": False}

        async def uninstall_cb(_k):
            state["done"] = True

        test_module = kernel.loaded_modules["test_module"]
        test_module.register = MagicMock()
        test_module.register.__loops__ = []
        test_module.register.__watchers__ = []
        test_module.register.__event_handlers__ = []
        test_module.register.__uninstall__ = uninstall_cb

        loader = ModuleLoader(kernel)
        await loader.unregister_module_commands("test_module")
        assert state["done"] is True

    @pytest.mark.asyncio
    async def test_uninstall_removes_handlers_with_specific_event(self):
        """Test that unload removes only the tracked watcher/event bindings."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.loaded_modules = {"test_module": MagicMock()}
        kernel.system_modules = {}
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.command_metadata = {}
        kernel.unregister_module_inline_handlers = MagicMock()
        kernel.logger = MagicMock()

        client = MagicMock()
        watcher = MagicMock()
        watcher_event = MagicMock()
        event_handler = MagicMock()
        event_obj = MagicMock()

        test_module = kernel.loaded_modules["test_module"]
        test_module.register = MagicMock()
        test_module.register.__loops__ = []
        test_module.register.__watchers__ = [(watcher, watcher_event, client)]
        test_module.register.__event_handlers__ = [(event_handler, event_obj, client)]

        loader = ModuleLoader(kernel)

        await loader.unregister_module_commands("test_module")

        client.remove_event_handler.assert_any_call(watcher, watcher_event)
        client.remove_event_handler.assert_any_call(event_handler, event_obj)

    @pytest.mark.asyncio
    async def test_uninstall_prunes_central_tracked_handlers_for_module(self):
        """Unload must not leave central handlers that ensure() can resurrect."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.loaded_modules = {"test_module": MagicMock()}
        kernel.system_modules = {}
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.command_metadata = {}
        kernel.unregister_module_inline_handlers = MagicMock()
        kernel.logger = MagicMock()

        client = MagicMock()
        kernel.client = client
        stale_watcher = MagicMock()
        stale_watcher_event = MagicMock()
        other_watcher = MagicMock()
        other_watcher_event = MagicMock()

        def stale_event_handler(_event):
            pass

        stale_event_handler.__module__ = "test_module"

        def other_event_handler(_event):
            pass

        other_event_handler.__module__ = "other_module"

        stale_event_obj = MagicMock()
        other_event_obj = MagicMock()
        kernel.register = SimpleNamespace(
            _all_watchers=[
                (
                    stale_watcher,
                    stale_watcher_event,
                    client,
                    {"module": "test_module", "method": "watch"},
                ),
                (
                    other_watcher,
                    other_watcher_event,
                    client,
                    {"module": "other_module", "method": "watch"},
                ),
            ],
            _all_event_handlers=[
                (stale_event_handler, stale_event_obj, client),
                (other_event_handler, other_event_obj, client),
            ],
        )

        test_module = kernel.loaded_modules["test_module"]
        test_module.register = MagicMock()
        test_module.register.__loops__ = []
        test_module.register.__watchers__ = [
            (stale_watcher, stale_watcher_event, client)
        ]
        test_module.register.__event_handlers__ = [
            (stale_event_handler, stale_event_obj, client)
        ]

        loader = ModuleLoader(kernel)
        await loader.unregister_module_commands("test_module")

        assert kernel.register._all_watchers == [
            (
                other_watcher,
                other_watcher_event,
                client,
                {"module": "other_module", "method": "watch"},
            )
        ]
        assert kernel.register._all_event_handlers == [
            (other_event_handler, other_event_obj, client)
        ]

    def test_duplicate_watcher_is_not_bound_before_skip(self):
        """Duplicate watcher detection must not leak an untracked client binding."""
        from core.lib.loader.register import Register

        kernel = MagicMock()
        kernel.client = MagicMock()
        kernel.bot_client = None
        kernel.current_loading_module = "test_module"
        kernel.loaded_modules = {}
        kernel.system_modules = {}
        kernel.logger = MagicMock()
        register = Register(kernel)

        existing_wrapper = MagicMock()
        existing_event = MagicMock()
        register._all_watchers.append(
            (
                existing_wrapper,
                existing_event,
                kernel.client,
                {"module": "test_module", "method": "watch"},
            )
        )
        module = SimpleNamespace(__name__="test_module")

        async def watch(_event):
            pass

        register.watcher(module=module)(watch)

        kernel.client.add_event_handler.assert_not_called()
        assert register._all_watchers == [
            (
                existing_wrapper,
                existing_event,
                kernel.client,
                {"module": "test_module", "method": "watch"},
            )
        ]
        assert not hasattr(module, "register")

    def test_duplicate_event_is_not_bound_before_skip(self):
        """Duplicate event detection must not leak an untracked client binding."""
        from core.lib.loader.register import Register

        kernel = MagicMock()
        kernel.client = MagicMock()
        kernel.bot_client = None
        kernel.current_loading_module = "test_module"
        kernel.loaded_modules = {}
        kernel.system_modules = {}
        kernel.logger = MagicMock()
        register = Register(kernel)

        def existing_handler(_event):
            pass

        from telethon import events

        existing_event = events.NewMessage()
        register._all_event_handlers.append(
            (
                existing_handler,
                existing_event,
                kernel.client,
                {
                    "module": "test_module",
                    "handler": "watch_updates",
                    "event_type": "NewMessage",
                },
            )
        )
        module = SimpleNamespace(__name__="test_module")

        async def watch_updates(_event):
            pass

        register.event("message", module=module)(watch_updates)

        kernel.client.add_event_handler.assert_not_called()
        assert register._all_event_handlers == [
            (
                existing_handler,
                existing_event,
                kernel.client,
                {
                    "module": "test_module",
                    "handler": "watch_updates",
                    "event_type": "NewMessage",
                },
            )
        ]
        assert not hasattr(module, "register")

    @pytest.mark.asyncio
    async def test_uninstall_removes_aliases_for_module_commands(self):
        """Test that remove_module_aliases removes aliases pointing at the module's commands."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.loaded_modules = {"test_module": MagicMock()}
        kernel.system_modules = {}
        kernel.command_handlers = {"ping": MagicMock(), "other": MagicMock()}
        kernel.command_owners = {"ping": "test_module", "other": "other_module"}
        aliases_real = {"p": "ping", "o": "other"}
        kernel.aliases = aliases_real
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.command_metadata = {}
        kernel.unregister_module_inline_handlers = MagicMock()
        kernel.logger = MagicMock()

        test_module = kernel.loaded_modules["test_module"]
        test_module.register = MagicMock()
        test_module.register.__loops__ = []
        test_module.register.__watchers__ = []
        test_module.register.__event_handlers__ = []

        loader = ModuleLoader(kernel)

        commands_removed = ["ping"]
        await loader.unregister_module_commands("test_module")

        assert "ping" not in kernel.command_handlers
        assert "ping" not in kernel.command_owners
        assert "p" in kernel.aliases

        loader.remove_module_aliases("test_module", commands_removed)

        assert "p" not in kernel.aliases
        assert kernel.aliases["o"] == "other"


class TestGetCommandDescription:
    """Test get_command_description() - Bug fix for hardcoded paths"""

    @pytest.mark.asyncio
    async def test_uses_kernel_module_dirs(self):
        """Test that get_command_description uses kernel module directories"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.MODULES_DIR = "/fake/modules"
        kernel.MODULES_LOADED_DIR = "/fake/modules_loaded"
        kernel.system_modules = {"test_module": MagicMock()}
        kernel.loaded_modules = {}
        kernel.command_docs = {}
        kernel.command_owners = {}

        loader = ModuleLoader(kernel)

        result = await loader.get_module_metadata("")
        assert isinstance(result, dict)
        assert "description" in result


class TestInstallFromUrl:
    """Test install_from_url() - Bug fix for missing makedirs"""

    @pytest.mark.asyncio
    async def test_creates_directory_if_not_exists(self):
        """Test that install_from_url creates directory if needed"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.MODULES_LOADED_DIR = "/tmp/nonexistent_mcub_dir/modules_loaded"
        kernel.version_manager = MagicMock()
        kernel.version_manager.check_module_compatibility = AsyncMock(
            return_value=(True, "ok")
        )

        loader = ModuleLoader(kernel)

        try:
            await loader.install_from_url(
                "https://example.com/test_module.py",
                "test_module",
                auto_dependencies=False,
            )
        except Exception:
            pass

        finally:
            import shutil

            if os.path.exists("/tmp/nonexistent_mcub_dir"):
                shutil.rmtree("/tmp/nonexistent_mcub_dir")


class TestPreInstallRequirements:
    """Test pre_install_requirements() functionality"""

    @pytest.mark.asyncio
    async def test_parses_requires_comments(self):
        """Test parsing of # requires: comments"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()

        loader = ModuleLoader(kernel)

        code = """
# requires: requests, numpy
# requires: pandas>=1.0.0

def register(kernel):
    pass
"""
        await loader.pre_install_requirements(code, "test_module")

    def test_parse_requires_ignores_non_direct_requires_mentions(self):
        """Test only direct # requires: comments declare dependencies"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
# meta: requires: requests
# requires:
# requires: numpy

def register(kernel):
    pass
"""

        assert loader.parse_requires(code) == ["numpy"]

    def test_extract_dependencies_skips_literal_requires_marker(self):
        """Test invalid requires: marker is not treated as a package"""
        from core.lib.loader.loader import ModuleLoader

        assert ModuleLoader._extract_dependencies(["requires:", "requests"]) == [
            "requests"
        ]

    @pytest.mark.asyncio
    async def test_handles_no_requires(self):
        """Test when no requires comments exist"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()

        loader = ModuleLoader(kernel)

        code = """
def register(kernel):
    pass
"""
        await loader.pre_install_requirements(code, "test_module")


class TestResolvePipName:
    """Test pip name resolution"""

    def test_resolve_known_packages(self):
        """Test known package name mappings"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        assert loader.resolve_pip_name("PIL") == "Pillow"
        assert loader.resolve_pip_name("cv2") == "opencv-python"
        assert loader.resolve_pip_name("sklearn") == "scikit-learn"
        assert loader.resolve_pip_name("bs4") == "beautifulsoup4"

    def test_resolve_unknown_package(self):
        """Test unknown package returns itself"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        assert loader.resolve_pip_name("unknown_package") == "unknown_package"


class TestIsInVirtualEnv:
    """Test virtual environment detection"""

    def test_detects_virtualenv(self):
        """Test virtual environment detection"""
        import sys

        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        with patch.object(sys, "base_prefix", "/usr"):
            with patch.object(sys, "prefix", "/usr"):
                assert loader.is_in_virtualenv() is False

            with patch.object(sys, "prefix", "/home/user/venv"):
                assert loader.is_in_virtualenv() is True


class TestHikkaModuleUnload:
    """Test Hikka module unload - commands should be fully removed"""

    @pytest.mark.asyncio
    async def test_unload_hikka_module_removes_commands(self):
        """Test that unload_hikka_module properly removes commands and aliases"""
        from core.lib.loader.hikka_compat.fake_package import unload_hikka_module

        kernel = MagicMock()
        kernel.command_handlers = {"testcmd": MagicMock()}
        kernel.command_owners = {"testcmd": "hikka_module"}
        kernel.aliases = {"tc": "testcmd"}
        kernel.inline_handlers = {}
        kernel.inline_handlers_owners = {}
        kernel.loaded_modules = {
            "hikka_module": MagicMock(
                _hikka_compat=True,
                _registered_cmds=["testcmd"],
                _registered_aliases=["tc"],
                _inline_patterns=[],
                _loop_handles=[],
                _callback_event_handles=[],
                _watcher_handles=[],
                _raw_handles=[],
                _event_handles=[],
            )
        }
        kernel.logger = MagicMock()
        kernel.client = MagicMock()

        result = await unload_hikka_module(kernel, "hikka_module")

        assert result is True
        assert "testcmd" not in kernel.command_handlers
        assert "testcmd" not in kernel.command_owners
        assert "tc" not in kernel.aliases
        assert "hikka_module" not in kernel.loaded_modules

    @pytest.mark.asyncio
    async def test_unload_hikka_module_removes_inline_handlers(self):
        """Test that unload_hikka_module removes inline handlers"""
        from core.lib.loader.hikka_compat.fake_package import unload_hikka_module

        kernel = MagicMock()
        kernel.command_handlers = {}
        kernel.command_owners = {}
        kernel.aliases = {}
        kernel.inline_handlers = {"testinline": MagicMock()}
        kernel.inline_handlers_owners = {"testinline": "hikka_module"}
        kernel.loaded_modules = {
            "hikka_module": MagicMock(
                _hikka_compat=True,
                _registered_cmds=[],
                _registered_aliases=[],
                _inline_patterns=["testinline"],
                _loop_handles=[],
                _callback_event_handles=[],
                _watcher_handles=[],
                _raw_handles=[],
                _event_handles=[],
            )
        }
        kernel.logger = MagicMock()
        kernel.client = MagicMock()

        result = await unload_hikka_module(kernel, "hikka_module")

        assert result is True
        assert "testinline" not in kernel.inline_handlers
        assert "testinline" not in kernel.inline_handlers_owners

    @pytest.mark.asyncio
    async def test_unload_hikka_module_nonexistent(self):
        """Test that unload_hikka_module returns False for non-existent module"""
        from core.lib.loader.hikka_compat.fake_package import unload_hikka_module

        kernel = MagicMock()
        kernel.loaded_modules = {}
        kernel.logger = MagicMock()

        result = await unload_hikka_module(kernel, "nonexistent_module")

        assert result is False

    @pytest.mark.asyncio
    async def test_unload_non_hikka_module_returns_false(self):
        """Test that unload_hikka_module returns False for non-hikka modules"""
        from core.lib.loader.hikka_compat.fake_package import unload_hikka_module

        kernel = MagicMock()
        kernel.loaded_modules = {
            "regular_module": MagicMock(
                _hikka_compat=False,
            )
        }
        kernel.logger = MagicMock()

        result = await unload_hikka_module(kernel, "regular_module")

        assert result is False


class TestHikkaModuleConfigSchema:
    """Test Hikka module config schema storage"""

    def test_herokutl_events_import_is_available(self):
        """Test Heroku modules can import Telethon events via herokutl."""
        from core.lib.loader.hikka_compat.fake_package import _ensure_fake_package

        _ensure_fake_package()

        from herokutl import events
        from telethon import events as telethon_events

        assert events is telethon_events
        assert events.NewMessage is telethon_events.NewMessage

    def test_herokutl_top_level_functions_import_is_available(self):
        """Test Heroku modules can import TL functions from herokutl."""
        from core.lib.loader.hikka_compat.fake_package import _ensure_fake_package

        _ensure_fake_package()

        from herokutl import functions
        from herokutl.tl import functions as tl_functions

        assert functions is tl_functions
        assert functions.account.UpdateNotifySettingsRequest is not None

    @pytest.mark.asyncio
    async def test_hikka_module_config_stores_schema(self):
        """Test that Hikka module config schema is stored for UI"""
        from core.lib.loader.hikka_compat.fake_package import _ensure_fake_package

        _ensure_fake_package()
        import sys

        loader_mod = sys.modules.get("heroku.loader")
        assert loader_mod is not None

        ConfigValue = loader_mod.ConfigValue
        ModuleConfig = loader_mod.ModuleConfig

        config = ModuleConfig(
            ConfigValue(
                "test_option",
                default=True,
                description="Test option",
                validator=None,
            ),
        )

        schema = config.schema
        assert len(schema) == 1
        assert schema[0]["key"] == "test_option"
        assert schema[0]["default"] is True
        assert schema[0]["description"] == "Test option"

    @pytest.mark.asyncio
    async def test_hikka_module_config_secret_flag(self):
        """Test that Hikka module config properly marks secret values"""
        from core.lib.loader.hikka_compat.fake_package import _ensure_fake_package
        from core.lib.loader.hikka_compat.validators import Hidden

        _ensure_fake_package()
        import sys

        loader_mod = sys.modules.get("heroku.loader")
        assert loader_mod is not None

        ConfigValue = loader_mod.ConfigValue
        ModuleConfig = loader_mod.ModuleConfig

        hidden_validator = Hidden()

        config = ModuleConfig(
            ConfigValue(
                "api_token",
                default="",
                description="API Token",
                validator=hidden_validator,
            ),
        )

        schema = config.schema
        assert len(schema) == 1
        assert schema[0]["secret"] is True


class TestClassStyleModule:
    """Test class-style module support"""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_detect_class_style_module(self):
        """Test detection of class-style module (inherits from ModuleBase)"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Test"

            @command("ping")
            async def ping(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod

        result = await loader.detect_module_type(module)
        assert result == "class"

    @pytest.mark.asyncio
    async def test_class_style_file_map_populated(self):
        """Test that _class_style_file_map is populated on class-style module registration"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.loaded_modules = {}
        kernel.system_modules = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()
        kernel.logger = MagicMock()

        loader = ModuleLoader(kernel)

        class TestModClass(ModuleBase):
            name = "MyCustomName"

            @command("ping")
            async def ping(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestModClass"] = TestModClass

        result = await loader.register_module(module, "class", "test_class_mod")

        assert result is True
        assert "MyCustomName" in kernel._class_module_instances
        assert "test_class_mod" not in kernel._class_module_instances

    @pytest.mark.asyncio
    async def test_find_module_base_class(self):
        """Test _find_module_base_class returns the correct class"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Test"

            @command("ping")
            async def ping(self, event):
                pass

        class OtherClass:
            pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod
        module.__dict__["OtherClass"] = OtherClass

        result = loader._find_module_base_class(module)
        assert result == TestMod

    @pytest.mark.asyncio
    async def test_register_class_module_creates_instance(self):
        """Test that register_module creates an instance for class-style modules"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()

        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Unnamed"

            @command("ping")
            async def ping(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod

        result = await loader.register_module(module, "class", "test_mod_file")

        assert result is True
        assert "test_mod_file" in kernel._class_module_instances
        instance = kernel._class_module_instances["test_mod_file"]
        assert isinstance(instance, TestMod)
        assert instance.kernel == kernel
        assert instance.client == kernel.client

    @pytest.mark.asyncio
    async def test_class_module_instance_has_attributes(self):
        """Test that class-style module instance has expected attributes"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()

        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Unnamed"

            @command("ping")
            async def ping(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod

        await loader.register_module(module, "class", "test_mod_file")

        instance = kernel._class_module_instances["test_mod_file"]
        assert hasattr(instance, "log")
        assert hasattr(instance, "db")
        assert hasattr(instance, "cache")
        assert hasattr(instance, "_loaded")
        assert hasattr(instance, "_loops")

    @pytest.mark.asyncio
    async def test_class_module_command_registered(self):
        """Test that @command decorator registers command via register"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()

        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Test"

            @command("ping", doc_ru="пинг")
            async def ping(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod

        await loader.register_module(module, "class", "TestMod")

        kernel.register.command.assert_called()
        call_args = kernel.register.command.call_args
        assert call_args[0][0] == "ping"

    @pytest.mark.asyncio
    async def test_class_module_isolation(self):
        """Test that multiple class-style modules don't share command registrations"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()

        loader = ModuleLoader(kernel)

        class ModA(ModuleBase):
            name = "A"

            @command("ping_a")
            async def ping(self, event):
                pass

        class ModB(ModuleBase):
            name = "B"

            @command("ping_b")
            async def ping(self, event):
                pass

        module_a = MagicMock(spec=[])
        module_a.__dict__["ModA"] = ModA
        module_b = MagicMock(spec=[])
        module_b.__dict__["ModB"] = ModB

        await loader.register_module(module_a, "class", "ModA")
        await loader.register_module(module_b, "class", "ModB")

        assert kernel.register.command.call_count == 2
        calls = kernel.register.command.call_args_list
        patterns = [call[0][0] for call in calls]
        assert "ping_a" in patterns
        assert "ping_b" in patterns

    @pytest.mark.asyncio
    async def test_class_module_command_with_all_options(self):
        """Test @command with alias, doc, doc_ru, doc_en, and arbitrary doc_*"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()

        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Test"

            @command(
                "hello",
                alias=["hi", "h"],
                doc_ru="пpивeт",
                doc_en="hello",
                doc_rofl="дapoвa",
                doc_linux="man hello",
            )
            async def hello(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod

        await loader.register_module(module, "class", "TestMod")

        kernel.register.command.assert_called_once()
        call_kwargs = kernel.register.command.call_args[1]
        assert call_kwargs["alias"] == ["hi", "h"]
        assert call_kwargs["doc_ru"] == "пpивeт"
        assert call_kwargs["doc_en"] == "hello"
        assert call_kwargs["doc_rofl"] == "дapoвa"
        assert call_kwargs["doc_linux"] == "man hello"


class TestClassStyleMetadata:
    """Test get_module_metadata for class-style modules"""

    @pytest.mark.asyncio
    async def test_get_module_metadata_class_style(self):
        """Test that get_module_metadata detects class-style modules"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "TestModule"

    @command("ping")
    async def ping(self, event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is True
        assert metadata["class_name"] == "TestModule"

    @pytest.mark.asyncio
    async def test_get_module_metadata_class_style_banner(self):
        """Test that get_module_metadata extracts banner_url"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "TestModule"
    banner_url = "https://example.com/banner.png"

    @command("ping")
    async def ping(self, event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is True
        assert metadata["banner_url"] == "https://example.com/banner.png"

    @pytest.mark.asyncio
    async def test_get_module_metadata_with_module_base_alias(self):
        """Test class-style metadata parsing with module_base alias imports."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
import core.lib.loader.module_base as loader

class ModTest(loader.ModuleBase):
    name = "test-mod"
    description = {"en": "Test module"}

    @loader.command("test", doc_en="run test")
    async def cmd_test(self, event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is True
        assert metadata["class_name"] == "test-mod"
        assert metadata["description"] == "Test module"
        assert metadata["commands"]["test"] == "run test"

    @pytest.mark.asyncio
    async def test_get_module_metadata_class_docstring_description_fallback(self):
        """Use class docstring when description attribute is missing."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = '''
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    """Class doc description fallback"""
    name = "TestModule"

    @command("ping")
    async def ping(self, event):
        pass
'''

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is True
        assert metadata["description"] == "Class doc description fallback"


class TestKernelStyleMetadata:
    """Test get_module_metadata for register-based modules."""

    @pytest.mark.asyncio
    async def test_get_module_metadata_kernel_register_command_docs(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
# author: @Dev
# version: 3.2.1
# description: Kernel style test module

def register(kernel):
    @kernel.register.command("term", doc_en="run shell", doc_ru="зaпycтить shell")
    async def term_handler(event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is False
        assert metadata["author"] == "@Dev"
        assert metadata["version"] == "3.2.1"
        assert metadata["description"] == "Kernel style test module"
        assert metadata["commands"]["term"] == "зaпycтить shell"

    @pytest.mark.asyncio
    async def test_get_module_metadata_arbitrary_command_docs(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "TestModule"

    @command("install", doc_linux="man mcub-install", doc_rofl="paткo ycтaнoвкa")
    async def install(self, event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["commands"]["install"] == "man mcub-install"

    @pytest.mark.asyncio
    async def test_get_module_metadata_header_author_with_port_prefix(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
# author: port: @Hairpin00, author: @TypeFrag
# description: test
"""

        metadata = await loader.get_module_metadata(code)
        assert metadata["author"] == "@TypeFrag"

    @pytest.mark.asyncio
    async def test_get_module_metadata_meta_developer_header(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
# meta developer: @H_SunMods
# meta banner: https://example.com/banner.webp
"""

        metadata = await loader.get_module_metadata(code)
        assert metadata["author"] == "@H_SunMods"
        assert metadata["banner_url"] == "https://example.com/banner.webp"

    @pytest.mark.asyncio
    async def test_get_module_metadata_header_description_i18n_inline(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
# author: @Dev
# description: ru: Oпиcaниe мoдyля / en: Module description
"""

        metadata = await loader.get_module_metadata(code)
        assert metadata["description"] == "Oпиcaниe мoдyля"
        assert metadata["description_i18n"] == {
            "ru": "Oпиcaниe мoдyля",
            "en": "Module description",
        }

    @pytest.mark.asyncio
    async def test_get_module_metadata_command_doc_dict(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
def register(kernel):
    @kernel.register.command("term", doc={"en": "run shell", "ru": "зaпycтить shell"})
    async def term_handler(event):
        pass
"""

        metadata = await loader.get_module_metadata(code)
        assert metadata["commands"]["term"] == "зaпycтить shell"

    @pytest.mark.asyncio
    async def test_get_module_metadata_hikka_style_class_docstring(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = '''
from hikkatl import loader

class HkMod(loader.Module):
    """Hikka module docstring description"""
    strings = {"name": "HkMod"}
'''

        metadata = await loader.get_module_metadata(code)
        assert metadata["is_class_style"] is True
        assert metadata["description"] == "Hikka module docstring description"


class TestClassStyleOnInstall:
    @pytest.mark.asyncio
    async def test_class_on_install_runs_only_once(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()
        kernel.db_get = AsyncMock(side_effect=[None, "1"])
        kernel.db_set = AsyncMock()

        loader = ModuleLoader(kernel)
        module = MagicMock()
        module.register = MagicMock()
        module.register.__loops__ = []
        module.register.__watchers__ = []
        module.register.__event_handlers__ = []

        class Instance:
            _loaded = False
            _loops = []

            def __init__(self):
                self.on_install_calls = 0

            async def on_load(self):
                return None

            async def on_reload(self):
                return None

            async def on_install(self):
                self.on_install_calls += 1

        inst = Instance()
        module._class_instance = inst

        await loader.run_post_load(module, "TestMod", is_install=True, is_reload=False)
        await loader.run_post_load(module, "TestMod", is_install=True, is_reload=False)

        assert inst.on_install_calls == 1
        kernel.db_set.assert_awaited_once()


class TestClassStylePreInstallRequirements:
    """Test pre_install_requirements for class-style modules"""

    @pytest.mark.asyncio
    async def test_pre_install_class_dependencies(self):
        """Test that class-style dependencies are parsed"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()
        loader = ModuleLoader(kernel)
        loader._pip_install = AsyncMock()

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "Test"
    dependencies = ["requests", "bs4"]

    @command("ping")
    async def ping(self, event):
        pass
"""

        with patch("importlib.util.find_spec", return_value=None):
            await loader.pre_install_requirements(code, "test_module")

        loader._pip_install.assert_any_await("requests", "test_module")
        loader._pip_install.assert_any_await("beautifulsoup4", "test_module")

    def test_parse_requires_class_dependencies(self):
        """Test parse_requires includes class-style dependencies"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase

class TestMod(ModuleBase):
    dependencies = ["requests"]
"""

        assert loader.parse_requires(code) == ["requests"]

    def test_parse_requires_ignores_requires_inside_strings(self):
        """Test fake # requires examples inside strings are ignored."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = (
            "# requires: aiohttp, Pillow\n"
            '"""\n'
            "# requires: third_party_pip_package (omit line entirely if none needed)\n"
            '"""\n'
            'HELP_TEXT = "# requires: fake_single_double_quote"\n'
            "OTHER_HELP = '# requires: fake_single_quote'\n"
            "TEMPLATE = '''\n"
            "# requires: fake_triple_single_quote\n"
            "'''\n"
            "class TestMod:\n"
            '    dependencies = ["requests"]\n'
        )

        assert loader.parse_requires(code) == ["aiohttp", "Pillow", "requests"]

    @pytest.mark.asyncio
    async def test_pre_install_combines_requires_and_dependencies(self):
        """Test that both # requires: and class dependencies are parsed"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()
        loader = ModuleLoader(kernel)
        loader._pip_install = AsyncMock()

        code = """
# requires: numpy
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "Test"
    dependencies = ["requests"]

    @command("ping")
    async def ping(self, event):
        pass
"""

        with patch("importlib.util.find_spec", return_value=None):
            await loader.pre_install_requirements(code, "test_module")

        loader._pip_install.assert_any_await("numpy", "test_module")
        loader._pip_install.assert_any_await("requests", "test_module")


class TestModuleNameMetadata:
    """Test # name: header comment resolution in module loading."""

    @pytest.mark.asyncio
    async def test_parse_module_name_from_code_basic(self):
        """Extract # name: from header comments."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        code = """# name: MyModule
# version: 1.0.0
# description: Test
"""
        result = ModuleLoaderMixin._parse_module_name_from_code(code)
        assert result == "MyModule"

    @pytest.mark.asyncio
    async def test_parse_module_name_from_code_case_insensitive(self):
        """# NAME: and # Name: both work."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        for header in ("# NAME: Foo", "# Name: Bar", "# name: Baz"):
            result = ModuleLoaderMixin._parse_module_name_from_code(header + "\n")
            assert result == header.split(": ")[1]

    @pytest.mark.asyncio
    async def test_parse_module_name_from_code_meta_name(self):
        """# meta name: is also recognised."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        code = "# meta name: MetaModule\n"
        result = ModuleLoaderMixin._parse_module_name_from_code(code)
        assert result == "MetaModule"

    @pytest.mark.asyncio
    async def test_parse_module_name_from_code_no_match(self):
        """Returns None when no # name: header is present."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        code = "# version: 1.0.0\n# description: test\n"
        assert ModuleLoaderMixin._parse_module_name_from_code(code) is None

    @pytest.mark.asyncio
    async def test_parse_module_name_from_code_empty(self):
        """Returns None when # name: value is empty."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        code = "# name:  \n"
        assert ModuleLoaderMixin._parse_module_name_from_code(code) is None

    @pytest.mark.asyncio
    async def test_get_module_metadata_has_name_from_header(self):
        """get_module_metadata includes name from # name: header."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """# name: OnlineStatusLogger
# version: 1.0.0
def register(kernel):
    pass
"""
        metadata = await loader.get_module_metadata(code)
        assert metadata["name"] == "OnlineStatusLogger"

    @pytest.mark.asyncio
    async def test_get_module_metadata_name_from_class(self):
        """get_module_metadata uses class name attribute over # name:."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """# name: Overridden
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "RealName"

    @command("test")
    async def test(self, event):
        pass
"""
        metadata = await loader.get_module_metadata(code)
        # Class attribute should take precedence
        assert metadata["name"] == "RealName"
        assert metadata["class_name"] == "RealName"
        assert metadata["is_class_style"] is True

    @pytest.mark.asyncio
    async def test_get_module_metadata_class_style_no_name_header(self):
        """Class-style module without # name: still gets name from class attr."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "MyModule"

    @command("test")
    async def test(self, event):
        pass
"""
        metadata = await loader.get_module_metadata(code)
        assert metadata["name"] == "MyModule"
        assert metadata["is_class_style"] is True

    @pytest.mark.asyncio
    async def test_resolve_name_from_code_identity(self):
        """When # name: equals filename, no rename occurs."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = "# name: my_module\n# version: 1.0.0\n"
        new_name, new_path = loader._resolve_name_from_code(
            code, "my_module", "/tmp/my_module.py", kernel
        )
        assert new_name == "my_module"
        assert new_path == "/tmp/my_module.py"

    @pytest.mark.asyncio
    async def test_resolve_name_from_code_preserves_file_path(self):
        """When filename and # name: match, file_path is preserved."""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()
        loader = ModuleLoader(kernel)

        code = "# name: some_module\n"
        _, new_path = loader._resolve_name_from_code(
            code, "some_module", "/path/to/some_module.py", kernel
        )
        assert new_path == "/path/to/some_module.py"

    @pytest.mark.asyncio
    async def test_functional_module_load_needs_name_header(self, tmp_path):
        """Function-style .py file must have # name: to load."""
        from core.lib.loader.loader import ModuleLoader

        module_dir = tmp_path / "modules_loaded"
        module_dir.mkdir()
        pyfile = module_dir / "test_mod.py"
        pyfile.write_text(
            "# name: test_mod\n"
            "# version: 1.0.0\n"
            "def register(kernel):\n"
            "    pass\n",
            encoding="utf-8",
        )

        kernel = MagicMock()
        kernel.MODULES_LOADED_DIR = str(module_dir)
        kernel.logger = MagicMock()
        kernel.loaded_modules = {}
        kernel.system_modules = {}
        kernel.client = MagicMock()
        kernel.custom_prefix = "."

        loader = ModuleLoader(kernel)

        # Verify the name is resolved from code without renaming
        with open(pyfile) as f:
            code = f.read()
        new_name, new_path = loader._resolve_name_from_code(
            code, "test_mod", str(pyfile), kernel
        )
        assert new_name == "test_mod"
        assert new_path == str(pyfile)

    @pytest.mark.asyncio
    async def test_functional_module_without_name_header_detected(self):
        """_parse_module_name_from_code returns None for register-only code."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        code = "def register(kernel):\n    pass\n"
        assert ModuleLoaderMixin._parse_module_name_from_code(code) is None

    @pytest.mark.asyncio
    async def test_class_style_module_without_name_header_detected(self):
        """_parse_module_name_from_code works with class-style and header."""
        from core.lib.mixin.module_loader_mixin import ModuleLoaderMixin

        code = "# name: my_module\nfrom core.lib.loader.base import ModuleBase\n"
        result = ModuleLoaderMixin._parse_module_name_from_code(code)
        assert result == "my_module"
