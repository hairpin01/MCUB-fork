import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jinja2
import pytest
from aiohttp import web

from core.lib.base.config import ConfigManager
from core.web.app import create_app
from core.web.plugin_manager import PluginManager


def _make_kernel(config_file: Path | str = "config.json") -> MagicMock:
    kernel = MagicMock()
    kernel.CONFIG_FILE = str(config_file)
    kernel.config = {}
    kernel.logger = MagicMock()
    return kernel


def test_config_manager_load_or_create_logs_debug(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "api_id": 12345,
                "api_hash": "hash",
                "phone": "+10000000000",
                "command_prefix": "!",
                "aliases": {"t": "test"},
                "power_save_mode": True,
                "language": "ru",
            }
        ),
        encoding="utf-8",
    )
    kernel = _make_kernel(config_path)

    manager = ConfigManager(kernel)

    assert manager.load_or_create() is True

    debug_messages = [call.args[0] for call in kernel.logger.debug.call_args_list]
    assert "Config loaded file=%s keys=%s" in debug_messages
    assert "Config contains required fields: %s" in debug_messages
    assert (
        "Config applied prefix=%r aliases=%d power_save=%s language=%r"
        in debug_messages
    )


@pytest.mark.asyncio
async def test_config_manager_set_and_delete_key_logs_debug():
    kernel = _make_kernel()
    kernel.db_get = AsyncMock(return_value=json.dumps({"old": 1}))
    kernel.db_set = AsyncMock()

    manager = ConfigManager(kernel)

    assert await manager.set_key("demo", "new", 2) is True
    assert await manager.delete_key("demo", "missing") is False

    debug_messages = [call.args[0] for call in kernel.logger.debug.call_args_list]
    assert "Config key set module=%r key=%r" in debug_messages
    assert "Config key delete skipped module=%r key=%r reason=missing" in debug_messages


def test_plugin_manager_load_plugins_logs_debug(caplog):
    app = web.Application()
    app["aiohttp_jinja2_environment"] = MagicMock(
        loader=jinja2.FileSystemLoader(["core/web/templates"])
    )
    manager = PluginManager(app, MagicMock())

    plugin_module = MagicMock()
    plugin_module.setup = MagicMock()

    caplog.set_level("DEBUG", logger="web.plugin_manager")

    with (
        patch(
            "core.web.plugin_manager.pkgutil.iter_modules",
            return_value=[(object(), "demo", True)],
        ),
        patch(
            "core.web.plugin_manager.importlib.import_module",
            return_value=plugin_module,
        ),
        patch.object(manager.plugins_dir.__class__, "exists", return_value=True),
    ):
        manager.load_plugins()

    log_text = caplog.text
    assert "Scanning plugins directory:" in log_text
    assert "Discovered plugin candidate name='demo'" in log_text
    assert "Importing plugin module: core.web.plugins.demo" in log_text
    assert "Calling setup() for plugin: demo" in log_text


def test_create_app_logs_debug():
    kernel = _make_kernel()

    with (
        patch("core.web.app.logger") as mock_logger,
        patch("core.web.app.PluginManager") as mock_plugin_manager_cls,
        patch("core.web.app.AuthMiddleware") as mock_auth_cls,
        patch("core.web.app.setup_routes"),
        patch("core.web.app.aiohttp_jinja2.setup"),
    ):
        plugin_manager = mock_plugin_manager_cls.return_value
        plugin_manager.plugins = ["demo"]
        auth_middleware = mock_auth_cls.return_value
        auth_middleware.auth_enabled = True

        app = create_app(kernel)

    assert isinstance(app, web.Application)
    debug_messages = [call.args[0] for call in mock_logger.debug.call_args_list]
    assert "Creating web app kernel_present=%s setup_event_present=%s" in debug_messages
    assert "Loading web plugins for configured kernel" in debug_messages
    assert "Web app ready plugins=%s auth_enabled=%s" in debug_messages
