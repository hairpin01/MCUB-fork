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
