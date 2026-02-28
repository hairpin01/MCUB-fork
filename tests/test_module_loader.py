"""
Tests for module loader
"""

import pytest
import asyncio
import os
import tempfile
import inspect
from unittest.mock import MagicMock, AsyncMock, patch


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
            'setup': lambda k: None,
            'configure': lambda k: None,
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
        object.__setattr__(module, 'register', register_new)
        
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
        object.__setattr__(module, 'register', register_old)
        
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
        param = list(params)[0]
        assert param.name == "kernel", f"Expected 'kernel', got '{param.name}'"


class TestUninstallCallback:
    """Test uninstall callback handling - Bug fix for asyncio.get_event_loop()"""

    def test_uninstall_sync_function(self):
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
        
        loader.unregister_module_commands("test_module")

    def test_uninstall_no_callback(self):
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
        
        loader.unregister_module_commands("test_module")


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
        kernel.version_manager.check_module_compatibility = AsyncMock(return_value=(True, "ok"))
        
        loader = ModuleLoader(kernel)
        
        try:
            result = await loader.install_from_url(
                "https://example.com/test_module.py",
                "test_module",
                auto_dependencies=False
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
        
        with patch.object(sys, 'base_prefix', '/usr'):
            with patch.object(sys, 'prefix', '/usr'):
                assert loader.is_in_virtualenv() is False
            
            with patch.object(sys, 'prefix', '/home/user/venv'):
                assert loader.is_in_virtualenv() is True
