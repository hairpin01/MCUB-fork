# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Тecты для yтилит modules/man.py."""

import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

import pytest

from modules import man

_ASSERT = TestCase()


@pytest.mark.asyncio
async def test_man_repairs_python_literal_config_and_clamps_page_size():
    saved = {}

    async def db_get(module, key):
        assert (module, key) == ("module_configs", "man")
        return "{'man_modules_per_page': 999, 'man_banner_url': 'https://example.com/a.jpg'}"

    async def db_set(module, key, value):
        saved[(module, key)] = value

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.name = "man"
    module_instance.kernel = SimpleNamespace(db_get=db_get, db_set=db_set)
    module_instance.log = SimpleNamespace(debug=lambda *_, **__: None)

    await module_instance._repair_persisted_config()

    payload = json.loads(saved[("module_configs", "man")])
    assert payload["man_modules_per_page"] == 50
    assert payload["man_banner_url"] == "https://example.com/a.jpg"


@pytest.mark.asyncio
async def test_man_repairs_unparseable_config_payload():
    saved = {}

    async def db_get(module, key):
        assert (module, key) == ("module_configs", "man")
        return "{broken config"

    async def db_set(module, key, value):
        saved[(module, key)] = value

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.name = "man"
    module_instance.kernel = SimpleNamespace(db_get=db_get, db_set=db_set)
    module_instance.log = SimpleNamespace(debug=lambda *_, **__: None)

    await module_instance._repair_persisted_config()

    assert json.loads(saved[("module_configs", "man")]) == {}


class CallableStrings(dict):
    def __call__(self, key: str, **kwargs):
        value = self[key]
        if isinstance(value, dict):
            return CallableStrings(value)
        return value.format(**kwargs) if kwargs and isinstance(value, str) else value


@pytest.mark.asyncio
async def test_load_module_metadata_uses_cache(tmp_path, monkeypatch):
    """Пoвтopнaя зaгpyзкa мeтaдaнныx нe дoлжнa читaть фaйл пoвтopнo."""

    kernel = SimpleNamespace()
    kernel.MODULES_DIR = str(tmp_path)
    kernel.MODULES_LOADED_DIR = str(tmp_path)
    kernel.get_module_metadata = AsyncMock(return_value={"description": "ok"})

    module_file = tmp_path / "demo.py"
    module_file.write_text("# dummy", encoding="utf-8")

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.kernel = kernel
    module_instance.strings = {"no_description": "нeт", "unknown": "?"}

    man._METADATA_CACHE.clear()

    first = await module_instance._load_module_metadata("demo", "system")
    _ASSERT.assertEqual(first["description"], "ok")

    called = False

    async def _fail(_):
        nonlocal called
        called = True
        return {}

    kernel.get_module_metadata = _fail

    second = await module_instance._load_module_metadata("demo", "system")
    _ASSERT.assertEqual(second, first)
    _ASSERT.assertFalse(called)


def test_gather_all_modules_hides_modules():
    """gather_all_modules hides modules if show_hidden=False."""

    kernel = SimpleNamespace(
        system_modules={"sys": object()},
        loaded_modules={"user": object()},
    )

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.kernel = kernel

    hidden = ["user"]

    result = module_instance._gather_all_modules(show_hidden=False, hidden=hidden)
    _ASSERT.assertNotIn("user", result)
    _ASSERT.assertIn("sys", result)

    result_shown = module_instance._gather_all_modules(show_hidden=True, hidden=hidden)
    _ASSERT.assertIn("user", result_shown)
    _ASSERT.assertIn("sys", result_shown)


def _make_man_instance(**kernel_overrides):
    kernel = SimpleNamespace(
        system_modules={},
        loaded_modules={},
        _hikka_compat_libraries=[],
        config={"language": "ru"},
        custom_prefix=".",
        _loader=SimpleNamespace(_module_type_cache={}),
        get_module_inline_commands=lambda name: [],
    )
    for key, value in kernel_overrides.items():
        setattr(kernel, key, value)

    module_instance = man.ManModule.__new__(man.ManModule)
    module_instance.kernel = kernel
    module_instance.strings = CallableStrings(
        {
            "no_description": "нeт",
            "unknown": "?",
            "no_commands": "нeт кoмaнд",
            "author": "Aвтop",
            "aliases": "Aлиacы",
            "placeholders_title": "Плeйcxoлдepы",
            "type_module": {
                "module_style_class": "Class",
                "module_style_kernel": "Kernel",
                "module_style_client_old": "Client (устаревший)",
                "module_type_native": "Данный модуль MCUB нативный, использует {style} стиль",
                "module_type_hikka": "Данный модуль использует Heroku/Hikka compat (возможны ошибки)",
                "module_type_hikka_library": "Данный модуль-библиотека использует Heroku/Hikka compat (возможны ошибки)",
                "module_config_info": "У этого модуля есть Module config, всего ключей {count}",
            },
        }
    )
    return module_instance


def test_module_type_text_for_native_styles():
    module_instance = _make_man_instance()

    class_module = SimpleNamespace(_class_instance=object())
    _ASSERT.assertIn(
        "Class стиль",
        module_instance._build_module_type_text("NativeClass", "user", class_module),
    )

    kernel_module = SimpleNamespace(register=lambda kernel: None, __name__="kernel_mod")
    _ASSERT.assertIn(
        "Kernel стиль",
        module_instance._build_module_type_text("kernel_mod", "user", kernel_module),
    )

    client_module = SimpleNamespace(register=lambda client: None, __name__="client_mod")
    _ASSERT.assertIn(
        "Client (устаревший) стиль",
        module_instance._build_module_type_text("client_mod", "user", client_module),
    )


def test_module_type_text_for_hikka_module_and_library():
    class VoiceLib:
        name = "VoiceLib"

    library = VoiceLib()
    module_instance = _make_man_instance(_hikka_compat_libraries=[library])

    hikka_module = SimpleNamespace(_hikka_compat=True)
    _ASSERT.assertEqual(
        module_instance._build_module_type_text("H", "user", hikka_module),
        "Данный модуль использует Heroku/Hikka compat (возможны ошибки)",
    )
    _ASSERT.assertEqual(
        module_instance._build_module_type_text("VoiceLib", "library", library),
        "Данный модуль-библиотека использует Heroku/Hikka compat (возможны ошибки)",
    )

    gathered = module_instance._gather_all_modules(show_hidden=False, hidden=[])
    _ASSERT.assertEqual(gathered["VoiceLib"], ("library", library))


def test_module_config_text_counts_keys():
    module_instance = _make_man_instance()

    module = SimpleNamespace(config={"a": 1, "b": 2, "__mcub_config__": True})
    _ASSERT.assertEqual(module_instance._module_config_key_count("demo", module), 2)
    _ASSERT.assertIn("2", module_instance._build_module_config_text("demo", module))

    config = SimpleNamespace(_values={"x": object(), "y": object(), "z": object()})
    module = SimpleNamespace(config=config)
    _ASSERT.assertEqual(module_instance._module_config_key_count("demo", module), 3)


@pytest.mark.asyncio
async def test_build_module_detail_includes_module_type_text(monkeypatch):
    loader = SimpleNamespace(
        _module_type_cache={},
        pick_localized_text=lambda i18n, lang, fallback: fallback,
        get_module_commands=lambda name, lang: ({}, {}, {}),
    )
    kernel_module = SimpleNamespace(register=lambda kernel: None, __name__="kernel_mod")
    module_instance = _make_man_instance(_loader=loader)

    async def _metadata(name, typ):
        return {
            "description": "desc",
            "description_i18n": {},
            "version": "1.0.0",
            "author": "me",
            "banner_url": None,
            "commands": {},
        }

    monkeypatch.setattr(module_instance, "_load_module_metadata", _metadata)

    text, banner = await module_instance._build_module_detail(
        ("kernel_mod", "user", kernel_module)
    )

    _ASSERT.assertIsNone(banner)
    _ASSERT.assertIn("Данный модуль MCUB нативный, использует Kernel стиль", text)
