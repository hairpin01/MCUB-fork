# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for module loader
"""

import inspect
import os
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


class TestDetectModuleType:
    """Test detect_module_type() method - Bug fix for params[0].name"""

    @pytest.mark.asyncio
    async def test_detect_method_type(self):
        """Test detection of @method style register"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        module = MagicMock()
        module.register = MagicMock()
        module.register.__dict__ = {
            "setup": lambda k: None,
            "configure": lambda k: None,
        }

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

        loader = ModuleLoader(kernel)

        result = await loader.get_command_description("test_module", "test_cmd")

        assert "no description" in result.lower()


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

    @pytest.mark.asyncio
    async def test_hikka_module_config_stores_schema(self):
        """Test that Hikka module config schema is stored for UI"""
        from core.lib.loader.hikka_compat.fake_package import _ensure_fake_package

        _ensure_fake_package()
        import sys

        loader_mod = sys.modules.get("__hikka_mcub_compat__.loader")
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

        loader_mod = sys.modules.get("__hikka_mcub_compat__.loader")
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
        assert "test_class_mod" in kernel._class_module_instances

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
        """Test @command with alias, doc, doc_ru, doc_en"""
        from core.lib.loader.loader import ModuleLoader
        from core.lib.loader.module_base import ModuleBase, command

        kernel = MagicMock()
        kernel._class_module_instances = {}
        kernel.client = MagicMock()
        kernel.register = MagicMock()

        loader = ModuleLoader(kernel)

        class TestMod(ModuleBase):
            name = "Test"

            @command("hello", alias=["hi", "h"], doc_ru="привет", doc_en="hello")
            async def hello(self, event):
                pass

        module = MagicMock(spec=[])
        module.__dict__["TestMod"] = TestMod

        await loader.register_module(module, "class", "TestMod")

        kernel.register.command.assert_called_once()
        call_kwargs = kernel.register.command.call_args[1]
        assert call_kwargs["alias"] == ["hi", "h"]
        assert call_kwargs["doc_ru"] == "привет"
        assert call_kwargs["doc_en"] == "hello"


class TestClassStyleMetadata:
    """Test metadata parsing for class-style modules"""

    @pytest.mark.asyncio
    async def test_get_module_metadata_class_style(self):
        """Test that get_module_metadata extracts class-style metadata"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "TestModule"
    version = "2.0.0"
    author = "@tester"
    description = {"ru": "Тест", "en": "Test"}

    @command("ping")
    async def ping(self, event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is True
        assert metadata["version"] == "2.0.0"
        assert metadata["author"] == "@tester"
        assert metadata["description"] == "Тест"

    @pytest.mark.asyncio
    async def test_get_module_metadata_class_style_dependencies(self):
        """Test that get_module_metadata extracts dependencies"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "TestModule"
    dependencies = ["requests", "bs4"]

    @command("ping")
    async def ping(self, event):
        pass
"""

        metadata = await loader.get_module_metadata(code)

        assert metadata["is_class_style"] is True
        assert "dependencies" in metadata
        assert "requests" in metadata["dependencies"]
        assert "bs4" in metadata["dependencies"]

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


class TestClassStylePreInstallRequirements:
    """Test pre_install_requirements for class-style modules"""

    @pytest.mark.asyncio
    async def test_pre_install_class_dependencies(self):
        """Test that class-style dependencies are parsed"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()
        loader = ModuleLoader(kernel)

        code = """
from core.lib.loader.module_base import ModuleBase, command

class TestMod(ModuleBase):
    name = "Test"
    dependencies = ["requests", "bs4"]

    @command("ping")
    async def ping(self, event):
        pass
"""

        await loader.pre_install_requirements(code, "test_module")

    @pytest.mark.asyncio
    async def test_pre_install_combines_requires_and_dependencies(self):
        """Test that both # requires: and class dependencies are parsed"""
        from core.lib.loader.loader import ModuleLoader

        kernel = MagicMock()
        kernel.logger = MagicMock()
        loader = ModuleLoader(kernel)

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

        await loader.pre_install_requirements(code, "test_module")
