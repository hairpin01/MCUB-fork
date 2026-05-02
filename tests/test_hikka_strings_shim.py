# SPDX-License-Identifier: MIT

from types import SimpleNamespace

from core.lib.loader.hikka_compat.runtime import _StringsShim as RuntimeStringsShim
from core.lib.loader.hikka_compat.translat import _StringsShim as TranslatStringsShim


def _make_module():
    return SimpleNamespace(
        strings={
            "errors": {"en": "base-en", "ru": "base-ru"},
            "name": "Demo",
        },
        strings_ru={
            "errors": {"no_playing": "Ничего не играет"},
        },
    )


def test_runtime_strings_shim_call_returns_raw_dict():
    mod = _make_module()
    tr = SimpleNamespace(_lang="ru")
    shim = RuntimeStringsShim(mod, tr)

    val = shim("errors")

    assert isinstance(val, dict)
    assert val["no_playing"] == "Ничего не играет"


def test_runtime_strings_shim_getitem_localizes_dict():
    mod = _make_module()
    tr = SimpleNamespace(_lang="ru")
    shim = RuntimeStringsShim(mod, tr)

    assert shim["errors"] == "Ничего не играет"


def test_translat_strings_shim_call_returns_raw_dict():
    mod = _make_module()
    tr = SimpleNamespace(_lang="ru")
    shim = TranslatStringsShim(mod, tr)

    val = shim("errors")

    assert isinstance(val, dict)
    assert val["no_playing"] == "Ничего не играет"
