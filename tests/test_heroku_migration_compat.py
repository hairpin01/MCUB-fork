# SPDX-License-Identifier: MIT

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
_ASSERT = TestCase()


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_loader_exposes_documented_heroku_aliases():
    source = _source("modules/loader.py")

    _ASSERT.assertIn('alias=["im", "loadmod", "lm"]', source)
    _ASSERT.assertIn('alias="dlmod"', source)
    _ASSERT.assertIn('alias=["unloadmod", "ulm"]', source)


def test_settings_exposes_heroku_alias_import_export_names():
    source = _source("modules/settings.py")

    _ASSERT.assertIn('alias=["ila", "loadaliases", "la"]', source)
    _ASSERT.assertIn('alias=["aliasload", "al"]', source)


def test_config_exposes_heroku_wrappers():
    source = _source("modules/config.py")

    _ASSERT.assertIn('@kernel.register.command(\n        "config"', source)
    _ASSERT.assertIn('@kernel.register.command(\n        "fconfig"', source)
    _ASSERT.assertIn('f"module {rest}"', source)
    _ASSERT.assertIn('f"module {module_name} set {key} {value}"', source)


def test_tester_supports_heroku_ping_placeholders():
    source = _source("modules/tester.py")

    for key in (
        '"ping"',
        '"me"',
        '"version"',
        '"build"',
        '"platform"',
        '"user"',
        '"os"',
        '"kernel"',
        '"cpu"',
        '"upd"',
    ):
        _ASSERT.assertIn(key, source)
    _ASSERT.assertIn("Heroku/hikka placeholders supported.", source)


def test_mcub_info_supports_heroku_info_placeholders():
    source = _source("modules/MCUB_info.py")

    for key in (
        '"ping"',
        '"uptime"',
        '"me"',
        '"version"',
        '"build"',
        '"platform"',
        '"user"',
        '"os"',
        '"kernel"',
        '"cpu"',
        '"upd"',
    ):
        _ASSERT.assertIn(key, source)
    _ASSERT.assertIn("Heroku/hikka placeholders supported.", source)
