# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for real modules in the modules/ directory
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class TestLoaderModule:
    """Tests for modules/loader.py"""

    def test_import_loader_module(self):
        """Test that loader module can be imported"""
        import modules.loader as loader_module

        assert loader_module is not None

    def test_loader_has_custom_emoji(self):
        """Test loader module has CUSTOM_EMOJI"""
        import modules.loader as loader_module

        assert hasattr(loader_module, "CUSTOM_EMOJI")
        assert isinstance(loader_module.CUSTOM_EMOJI, dict)
        assert "success" in loader_module.CUSTOM_EMOJI
        assert "error" in loader_module.CUSTOM_EMOJI

    def test_loader_custom_emoji_format(self):
        """Test CUSTOM_EMOJI values have correct format"""
        import modules.loader as loader_module

        for key, value in loader_module.CUSTOM_EMOJI.items():
            assert value.startswith("<tg-emoji"), f"{key} should start with <tg-emoji>"

    def test_loader_has_register(self):
        """Test loader module has register function"""
        import modules.loader as loader_module

        assert hasattr(loader_module, "register")
        assert callable(loader_module.register)

    def test_loader_has_random_emojis(self):
        """Test loader module has RANDOM_EMOJIS"""
        import modules.loader as loader_module

        assert hasattr(loader_module, "RANDOM_EMOJIS")
        assert isinstance(loader_module.RANDOM_EMOJIS, list)
        assert len(loader_module.RANDOM_EMOJIS) > 0

    def test_loader_has_safe_edit(self):
        """Test loader module has safe_edit function"""
        import modules.loader as loader_module

        assert hasattr(loader_module, "safe_edit")
        assert callable(loader_module.safe_edit)

    def test_loader_has_module_config(self):
        """Test loader module has ModuleConfig"""
        import modules.loader as loader_module

        assert hasattr(loader_module, "ModuleConfig")
        assert hasattr(loader_module, "ConfigValue")
        assert hasattr(loader_module, "Boolean")


class TestCommandModule:
    """Tests for modules/command.py"""

    def test_import_command_module(self):
        """Test that command module can be imported"""
        import modules.command as command_module

        assert command_module is not None

    def test_command_has_register(self):
        """Test command module has register function"""
        import modules.command as command_module

        assert hasattr(command_module, "register")
        assert callable(command_module.register)


class TestConfigModule:
    """Tests for modules/config.py"""

    def test_import_config_module(self):
        """Test that config module can be imported"""
        import modules.config as config_module

        assert config_module is not None

    def test_config_has_custom_emoji(self):
        """Test config module has CUSTOM_EMOJI"""
        import modules.config as config_module

        assert hasattr(config_module, "CUSTOM_EMOJI")
        assert isinstance(config_module.CUSTOM_EMOJI, dict)

    def test_config_has_register(self):
        """Test config module has register function"""
        import modules.config as config_module

        assert hasattr(config_module, "register")
        assert callable(config_module.register)

    def test_config_has_type_emojis(self):
        """Test config module has TYPE_EMOJIS"""
        import modules.config as config_module

        assert hasattr(config_module, "TYPE_EMOJIS")
        assert isinstance(config_module.TYPE_EMOJIS, dict)


class TestEvalModule:
    """Tests for modules/eval.py"""

    def test_import_eval_module(self):
        """Test that eval module can be imported"""
        import modules.eval as eval_module

        assert eval_module is not None

    def test_eval_has_custom_emoji(self):
        """Test eval module has CUSTOM_EMOJI"""
        import modules.eval as eval_module

        assert hasattr(eval_module, "CUSTOM_EMOJI")
        assert isinstance(eval_module.CUSTOM_EMOJI, dict)


class TestTrustedModule:
    """Tests for modules/trusted.py"""

    def test_import_trusted_module(self):
        """Test that trusted module can be imported"""
        import modules.trusted as trusted_module

        assert trusted_module is not None

    def test_trusted_has_register(self):
        """Test trusted module has register function"""
        import modules.trusted as trusted_module

        assert hasattr(trusted_module, "register")
        assert callable(trusted_module.register)

    def test_trusted_has_inline_manager(self):
        """Test trusted module has InlineManager"""
        import modules.trusted as trusted_module

        assert hasattr(trusted_module, "InlineManager")


class TestTrModule:
    """Tests for modules/tr.py"""

    def test_import_tr_module(self):
        """Test that tr module can be imported"""
        import modules.tr as tr_module

        assert tr_module is not None

    def test_tr_has_module_config(self):
        """Test tr module has ModuleConfig"""
        import modules.tr as tr_module

        assert hasattr(tr_module, "ModuleConfig")
        assert hasattr(tr_module, "ConfigValue")


class TestMcubInfoModule:
    """Tests for modules/MCUB_info.py"""

    def test_import_mcub_info_module(self):
        """Test that MCUB_info module can be imported"""
        import modules.MCUB_info as mcub_info_module

        assert mcub_info_module is not None

    def test_mcub_info_has_custom_emoji(self):
        """Test MCUB_info module has CUSTOM_EMOJI"""
        import modules.MCUB_info as mcub_info_module

        assert hasattr(mcub_info_module, "CUSTOM_EMOJI")
        assert isinstance(mcub_info_module.CUSTOM_EMOJI, dict)


class TestUpdatesModule:
    """Tests for modules/updates.py"""

    def test_import_updates_module(self):
        """Test that updates module can be imported"""
        import modules.updates as updates_module

        assert updates_module is not None

    def test_updates_has_register(self):
        """Test updates module has register function"""
        import modules.updates as updates_module

        assert hasattr(updates_module, "register")
        assert callable(updates_module.register)


class TestSettingsModule:
    """Tests for modules/settings.py"""

    def test_import_settings_module(self):
        """Test that settings module can be imported"""
        import modules.settings as settings_module

        assert settings_module is not None

    def test_settings_has_register(self):
        """Test settings module has register function"""
        import modules.settings as settings_module

        assert hasattr(settings_module, "register")
        assert callable(settings_module.register)

    def test_settings_has_module_config(self):
        """Test settings module has ModuleConfig"""
        import modules.settings as settings_module

        assert hasattr(settings_module, "ModuleConfig")


class TestManModule:
    """Tests for modules/man.py"""

    def test_import_man_module(self):
        """Test that man module can be imported"""
        import modules.man as man_module

        assert man_module is not None

    def test_man_has_custom_emoji(self):
        """Test man module has CUSTOM_EMOJI"""
        import modules.man as man_module

        assert hasattr(man_module, "CUSTOM_EMOJI")
        assert isinstance(man_module.CUSTOM_EMOJI, dict)

    def test_man_has_man_module_class(self):
        """Test man module has ManModule class"""
        import modules.man as man_module

        assert hasattr(man_module, "ManModule")


class TestApiProtectionModule:
    """Tests for modules/api_protection.py"""

    def test_import_api_protection_module(self):
        """Test that api_protection module can be imported"""
        import modules.api_protection as api_protection_module

        assert api_protection_module is not None

    def test_api_protection_has_register(self):
        """Test api_protection module has register function"""
        import modules.api_protection as api_protection_module

        assert hasattr(api_protection_module, "register")
        assert callable(api_protection_module.register)

    def test_api_protection_has_module_config(self):
        """Test api_protection module has ModuleConfig"""
        import modules.api_protection as api_protection_module

        assert hasattr(api_protection_module, "ModuleConfig")


class TestTesterModule:
    """Tests for modules/tester.py"""

    def test_import_tester_module(self):
        """Test that tester module can be imported"""
        import modules.tester as tester_module

        assert tester_module is not None

    def test_tester_has_custom_emoji(self):
        """Test tester module has CUSTOM_EMOJI"""
        import modules.tester as tester_module

        assert hasattr(tester_module, "CUSTOM_EMOJI")
        assert isinstance(tester_module.CUSTOM_EMOJI, dict)


class TestAllModulesHaveRegister:
    """Test that all modules have register function"""

    MODULES = [
        "loader",
        "command",
        "config",
        "trusted",
        "updates",
        "settings",
        "api_protection",
    ]

    @pytest.mark.parametrize("module_name", MODULES)
    def test_module_has_register(self, module_name):
        """Test that module has register function"""
        mod = __import__(f"modules.{module_name}", fromlist=[""])
        assert hasattr(mod, "register"), f"{module_name} should have register function"
        assert callable(mod.register), f"{module_name}.register should be callable"


class TestLoaderIntegration:
    """Integration tests for loader module"""

    @pytest.mark.asyncio
    async def test_safe_edit_success(self):
        """Test safe_edit returns msg on success"""
        import modules.loader as loader_module

        mock_msg = AsyncMock()
        mock_msg.edit = AsyncMock(return_value=mock_msg)

        result = await loader_module.safe_edit(mock_msg, "test")
        mock_msg.edit.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_safe_edit_returns_msg_on_not_modified(self):
        """Test safe_edit returns msg when content not modified"""
        import modules.loader as loader_module

        mock_msg = AsyncMock()
        mock_msg.edit = AsyncMock(
            side_effect=Exception("Content of the message was not modified")
        )

        result = await loader_module.safe_edit(mock_msg, "test")
        assert result == mock_msg


class TestConfigIntegration:
    """Integration tests for config module"""

    def test_type_emojis_mapping(self):
        """Test TYPE_EMOJIS has correct mappings"""
        import modules.config as config_module

        assert config_module.TYPE_EMOJIS["str"] == "📝"
        assert config_module.TYPE_EMOJIS["int"] == "🔢"
        assert config_module.TYPE_EMOJIS["bool"] == "☑️"

    def test_custom_emoji_keys(self):
        """Test CUSTOM_EMOJI has expected keys"""
        import modules.config as config_module

        assert "📁" in config_module.CUSTOM_EMOJI
        assert "📝" in config_module.CUSTOM_EMOJI
