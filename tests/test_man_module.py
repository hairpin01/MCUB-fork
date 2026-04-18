# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""Тесты для утилит modules/man.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules import man


@pytest.mark.asyncio
async def test_load_module_metadata_uses_cache(tmp_path, monkeypatch):
    """Повторная загрузка метаданных не должна читать файл повторно."""

    kernel = SimpleNamespace()
    kernel.MODULES_DIR = str(tmp_path)
    kernel.MODULES_LOADED_DIR = str(tmp_path)
    kernel.get_module_metadata = AsyncMock(return_value={"description": "ok"})

    module_file = tmp_path / "demo.py"
    module_file.write_text("# dummy", encoding="utf-8")

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.kernel = kernel
    module_instance.strings = {"no_description": "нет", "unknown": "?"}

    man._METADATA_CACHE.clear()

    first = await module_instance._load_module_metadata("demo", "system")
    assert first["description"] == "ok"

    called = False

    async def _fail(_):
        nonlocal called
        called = True
        return {}

    kernel.get_module_metadata = _fail

    second = await module_instance._load_module_metadata("demo", "system")
    assert second == first
    assert called is False


def test_gather_all_modules_hides_modules():
    """gather_all_modules скрывает модули, если show_hidden=False."""

    kernel = SimpleNamespace(
        system_modules={"sys": object()},
        loaded_modules={"user": object()},
    )

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.kernel = kernel

    hidden = ["user"]

    result = module_instance._gather_all_modules(show_hidden=False, hidden=hidden)
    assert "user" not in result and "sys" in result

    result_shown = module_instance._gather_all_modules(show_hidden=True, hidden=hidden)
    assert "user" in result_shown and "sys" in result_shown
