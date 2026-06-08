# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Integration tests: load real Heroku modules via hikka_compat."""

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

HEROKU_MODULES_DIR = Path(__file__).parent.parent / "modules_loaded"


def _setup_mock_kernel():
    """Create a mock kernel with minimal required attributes."""
    k = MagicMock()
    k.logger = MagicMock()
    k.tg_id = 12345
    k.db_manager = MagicMock()
    k._hikka_compat_inline_state = {}
    k._hikka_compat_inline_units = {}
    k._hikka_compat_inline_custom_map = {}
    k._loader = MagicMock()
    k._inline = None
    k.bot_client = None
    k.client = MagicMock()
    k.client.tg_id = 12345
    k.client.send_message = AsyncMock()
    k.config = {}
    k.get_prefix = MagicMock(return_value=".")
    k.get_prefixes = MagicMock(return_value=["."])
    k.inline_handlers = {}
    k.inline_handlers_owners = {}
    k.callback_handlers = {}
    k._hikka_compat_db_facade = None

    async def db_set(module, key, value):
        return True

    k.db_set = db_set

    from core.lib.loader.hikka_compat.runtime import DbProxy

    k._hikka_compat_db = DbProxy(k, "test")
    k._allclients = []
    k.allclients = [k.client]

    from core.lib.loader.hikka_compat.runtime import InlineProxy

    k._hikka_compat_inline = InlineProxy(k)

    return k


def _ensure_fake_package():
    """Initialize the hikka_compat fake package."""
    from core.lib.loader.hikka_compat import _ensure_fake_package

    return _ensure_fake_package()


class TestHerokuModuleLoading:
    """Test loading real Heroku modules via hikka_compat."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.kernel = _setup_mock_kernel()
        self.pkg_name = _ensure_fake_package()
        yield
        # Cleanup loaded modules
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith(self.pkg_name) or mod_name.startswith("heroku"):
                del sys.modules[mod_name]

    def _load_module(self, module_path: str, module_name: str):
        """Load a Heroku module via hikka_compat's load_hikka_module."""
        from core.lib.loader.hikka_compat import is_hikka_module, load_hikka_module

        path = Path(module_path)
        source = path.read_text(encoding="utf-8")

        # Check it's detected as hikka
        assert is_hikka_module(source), f"{module_name} not detected as hikka module"

        # Load it
        import asyncio

        ok, msg, data = asyncio.run(
            load_hikka_module(self.kernel, str(path), module_name)
        )
        assert ok, f"Failed to load {module_name}: {msg}"
        return data

    def test_detect_heroku_info(self):
        """Verify heroku_info.py is detected as hikka module."""
        path = HEROKU_MODULES_DIR / "heroku_info.py"
        if not path.exists():
            pytest.skip("heroku_info.py not found in modules_loaded")
        source = path.read_text(encoding="utf-8")
        from core.lib.loader.hikka_compat import is_hikka_module

        assert is_hikka_module(source)

    def test_detect_heroku_config(self):
        """Verify heroku_config.py is detected as hikka module."""
        path = HEROKU_MODULES_DIR / "heroku_config.py"
        if not path.exists():
            pytest.skip("heroku_config.py not found in modules_loaded")
        source = path.read_text(encoding="utf-8")
        from core.lib.loader.hikka_compat import is_hikka_module

        assert is_hikka_module(source)

    def test_detect_terminal(self):
        """Verify terminal.py is detected as hikka module."""
        path = HEROKU_MODULES_DIR / "terminal.py"
        if not path.exists():
            pytest.skip("terminal.py not found in modules_loaded")
        source = path.read_text(encoding="utf-8")
        from core.lib.loader.hikka_compat import is_hikka_module

        assert is_hikka_module(source)

    def test_detect_help(self):
        """Verify help.py is detected as hikka module."""
        path = HEROKU_MODULES_DIR / "help.py"
        if not path.exists():
            pytest.skip("help.py not found in modules_loaded")
        source = path.read_text(encoding="utf-8")
        from core.lib.loader.hikka_compat import is_hikka_module

        assert is_hikka_module(source)

    def test_load_heroku_info(self):
        """Load heroku_info module and verify its class."""
        path = HEROKU_MODULES_DIR / "heroku_info.py"
        if not path.exists():
            pytest.skip("heroku_info.py not found")

        self._load_module(str(path), "heroku_info")
        mod_name = f"{self.pkg_name}.heroku_info"
        assert mod_name in sys.modules, f"{mod_name} not in sys.modules"

        mod = sys.modules[mod_name]
        # Find the module class (tds-decorated)
        classes = [
            v
            for v in mod.__dict__.values()
            if isinstance(v, type) and hasattr(v, "__hikka_module__")
        ]
        assert classes, "No hikka module class found"
        cls = classes[0]
        assert hasattr(cls, "strings")
        assert "name" in cls.strings

    def test_load_terminal(self):
        """Load terminal module and verify commands."""
        path = HEROKU_MODULES_DIR / "terminal.py"
        if not path.exists():
            pytest.skip("terminal.py not found")

        self._load_module(str(path), "terminal")
        mod_name = f"{self.pkg_name}.terminal"
        assert mod_name in sys.modules

        mod = sys.modules[mod_name]
        # Commands are methods on classes inside the module
        commands = []
        for val in mod.__dict__.values():
            if isinstance(val, type):
                for m_name in dir(val):
                    m = getattr(val, m_name, None)
                    if callable(m) and getattr(m, "is_command", False):
                        commands.append(m_name)
        assert commands, "No commands found in terminal module"

    def test_import_via_heroku_fake_package(self):
        """Test that 'from heroku import loader' works via compat."""
        import heroku  # Should be provided by compat layer

        assert hasattr(heroku, "loader")
        assert hasattr(heroku, "utils")
        assert hasattr(heroku, "security")

    def test_import_via_herokutl(self):
        """Test that herokutl imports work."""
        import herokutl

        assert hasattr(herokutl, "events")
        assert hasattr(herokutl, "errors")
        assert hasattr(herokutl, "utils")
        assert hasattr(herokutl, "types")

    def test_herokutl_types(self):
        """Test herokutl.tl.types.Message is available."""
        import herokutl

        if hasattr(herokutl, "tl") and hasattr(herokutl.tl, "types"):
            msg_cls = herokutl.tl.types.Message
            assert msg_cls is not None

    def test_herokutl_errors(self):
        """Test herokutl.errors are available."""
        import herokutl

        assert hasattr(herokutl.errors, "FloodWaitError")
        assert hasattr(herokutl.errors, "PhoneCodeInvalidError")

    def test_security_decorators_in_module_scope(self):
        """Test that @owner etc work when imported from heroku."""
        from heroku import security

        async def dummy():
            pass

        decorated = security.owner(dummy)
        assert decorated.security & 1

    def test_config_value_creation(self):
        """Test loader.ConfigValue works."""
        from heroku import loader

        cv = loader.ConfigValue(
            "test_option",
            "default_val",
            "Test description",
            validator=loader.validators.String(),
        )
        assert cv.option == "test_option"
        assert cv.value == "default_val"

    def test_module_config_creation(self):
        """Test loader.ModuleConfig works."""
        from heroku import loader

        mc = loader.ModuleConfig(
            loader.ConfigValue("opt1", 42, "Answer"),
        )
        assert "opt1" in mc

    def test_module_strings_shim(self):
        """Test that module strings work via _StringsShim."""
        mod = types.SimpleNamespace()
        mod.strings = {"name": "TestMod", "hello": "World"}

        from core.lib.loader.hikka_compat.translat import _StringsShim

        shim = _StringsShim(mod)
        assert shim["name"] == "TestMod"
        assert shim["hello"] == "World"

    def test_utils_functions_available(self):
        """Check key utils functions exist."""
        from heroku import utils

        assert callable(utils.answer)
        assert callable(utils.rand)
        assert callable(utils.escape_html)
        assert callable(utils.get_args_raw)
        assert callable(utils.get_args)
        assert callable(utils.get_chat_id)

    def test_rand_returns_correct_length(self):
        from heroku import utils

        assert len(utils.rand(6)) == 6
        assert len(utils.rand(12)) == 12

    def test_escape_html_works(self):
        from heroku import utils

        assert utils.escape_html("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"

    def test_inline_types_available(self):
        """Test inline types are importable from heroku."""
        from heroku.types import (
            InlineCall,
            InlineMessage,
            InlineQuery,
            InlineResults,
            InlineUnit,
        )

        assert InlineCall is not None
        assert InlineMessage is not None
        assert InlineQuery is not None
        assert InlineUnit is not None
        assert InlineResults is not None

    def test_pointers_available(self):
        """Test PointerList/PointerDict from heroku.types."""
        from heroku.types import PointerDict, PointerList

        assert PointerList is not None
        assert PointerDict is not None

    def test_safe_proxies_available(self):
        """Test Safe proxies from heroku.types."""
        from heroku.types import (
            SafeAllModulesProxy,
            SafeClientProxy,
            SafeDatabaseProxy,
            SafeInlineProxy,
        )

        assert SafeAllModulesProxy is not None
        assert SafeClientProxy is not None
        assert SafeDatabaseProxy is not None
        assert SafeInlineProxy is not None
