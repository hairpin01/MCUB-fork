# SPDX-License-Identifier: MIT

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_loader_exposes_documented_heroku_aliases():
    source = _source("modules/loader.py")

    assert 'alias=["im", "loadmod", "lm"]' in source
    assert 'alias="dlmod"' in source
    assert 'alias=["unloadmod", "ulm"]' in source


def test_settings_exposes_heroku_alias_import_export_names():
    source = _source("modules/settings.py")

    assert 'alias=["ila", "loadaliases", "la"]' in source
    assert 'alias=["aliasload", "al"]' in source


def test_config_exposes_heroku_wrappers():
    source = _source("modules/config.py")

    assert '@kernel.register.command(\n        "config"' in source
    assert '@kernel.register.command(\n        "fconfig"' in source
    assert 'f"module {rest}"' in source
    assert 'f"module {module_name} set {key} {value}"' in source


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
        assert key in source
    assert "Heroku/hikka placeholders supported." in source


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
        assert key in source
    assert "Heroku/hikka placeholders supported." in source
