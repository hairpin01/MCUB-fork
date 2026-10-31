# SPDX-License-Identifier: MIT

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_install_dependencies_batch_handles_versions_and_git_urls():
    from core.lib.loader.loader import ModuleLoader

    kernel = MagicMock()
    kernel.logger = MagicMock()
    loader = ModuleLoader(kernel)
    loader._pip_install = AsyncMock()

    reqs = [
        "pillow>=10.0.0",
        "git+https://github.com/MarshalX/yandex-music-api",
    ]

    with patch(
        "core.lib.mixin.dependency_manager_mixin.importlib.util.find_spec",
        return_value=None,
    ):
        await loader.install_dependencies_batch(reqs, module_name="YaMusic")

    calls = [c.args[0] for c in loader._pip_install.await_args_list]
    assert "pillow>=10.0.0" in calls
    assert "git+https://github.com/MarshalX/yandex-music-api" in calls


@pytest.mark.asyncio
async def test_install_dependencies_batch_skips_installed_imports():
    from core.lib.loader.loader import ModuleLoader

    kernel = MagicMock()
    kernel.logger = MagicMock()
    loader = ModuleLoader(kernel)
    loader._pip_install = AsyncMock()

    with patch(
        "core.lib.mixin.dependency_manager_mixin.importlib.util.find_spec",
        return_value=object(),
    ):
        await loader.install_dependencies_batch(
            ["aiohttp", "aiohttp"], module_name="mod"
        )

    loader._pip_install.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_failure_logs_original_traceback_and_calls_handle_error():
    from core.lib.loader.loader import ModuleLoader

    kernel = MagicMock()
    kernel.logger = MagicMock()
    kernel.handle_error = AsyncMock()
    loader = ModuleLoader(kernel)
    loader._pip_install = AsyncMock(side_effect=ImportError("pip install failed"))

    spec = MagicMock()
    spec.loader.exec_module.side_effect = ImportError(
        "cannot import name 'DEFAULT_TOOL_TIMEOUT' from 'OpenAgent.Settings'"
    )
    module = MagicMock()
    module.__name__ = "OpenAgent"

    with pytest.raises(ImportError, match="pip install failed"):
        await loader.exec_with_auto_deps(
            spec, module, "/tmp/OpenAgent.py", "OpenAgent", ""
        )

    logged = "\n".join(str(call.args[0]) for call in kernel.logger.error.call_args_list)
    assert "Traceback (most recent call last)" in logged
    assert "cannot import name 'DEFAULT_TOOL_TIMEOUT'" in logged

    reported = kernel.handle_error.await_args
    assert isinstance(reported.args[0], ImportError)
    assert "DEFAULT_TOOL_TIMEOUT" in str(reported.args[0])
