# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""Тесты для утилит modules/man.py."""

from types import SimpleNamespace

import pytest

from modules import man


@pytest.mark.asyncio
async def test_load_module_metadata_uses_cache(tmp_path, monkeypatch):
    """Повторная загрузка метаданных не должна читать файл повторно."""

    kernel = SimpleNamespace()
    kernel.MODULES_DIR = str(tmp_path)
    kernel.MODULES_LOADED_DIR = str(tmp_path)

    # Файл модуля
    module_file = tmp_path / "demo.py"
    module_file.write_text("# dummy", encoding="utf-8")

    async def _metadata(_):
        return {"description": "ok"}

    kernel.get_module_metadata = _metadata

    strings = {"no_description": "нет", "unknown": "?"}

    # Очистить кеш между тестами
    man._METADATA_CACHE.clear()

    first = await man.load_module_metadata("demo", "system", kernel, strings)
    assert first["description"] == "ok"

    # Сдвиг mtime не происходит, поэтому вызов должен взять из кеша
    # подменяем метод, чтобы убедиться, что он не зовётся
    called = False

    async def _fail(_):
        nonlocal called
        called = True
        return {}

    kernel.get_module_metadata = _fail

    second = await man.load_module_metadata("demo", "system", kernel, strings)
    assert second == first
    assert called is False


def test_gather_all_modules_hides_modules():
    """gather_all_modules скрывает модули, если show_hidden=False."""

    kernel = SimpleNamespace(
        system_modules={"sys": object()},
        loaded_modules={"user": object()},
    )

    hidden = ["user"]

    result = man.gather_all_modules(kernel, show_hidden=False, hidden=hidden)
    assert "user" not in result and "sys" in result

    result_shown = man.gather_all_modules(kernel, show_hidden=True, hidden=hidden)
    assert "user" in result_shown and "sys" in result_shown
