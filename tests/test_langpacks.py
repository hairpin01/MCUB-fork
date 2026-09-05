# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Tests for bundled localization language packs."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LANGPACKS_DIR = PROJECT_ROOT / "core" / "langpacks"
ICONS_DIR = LANGPACKS_DIR / "icons"
LANGPACK_FILES = sorted(LANGPACKS_DIR.glob("*.yaml")) + sorted(
    LANGPACKS_DIR.glob("*.yml")
)
ICON_PACK_FILES = sorted(ICONS_DIR.glob("*.yaml")) + sorted(ICONS_DIR.glob("*.yml"))


def test_langpacks_directory_contains_yaml_files():
    """Ensure the localization directory is covered by this test module."""
    assert LANGPACK_FILES, f"No localization YAML files found in {LANGPACKS_DIR}"


@pytest.mark.parametrize("path", LANGPACK_FILES, ids=lambda path: path.name)
def test_langpack_yaml_file_is_valid_mapping(path):
    """Every localization file must be valid YAML mapping data."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        relative_path = path.relative_to(PROJECT_ROOT)
        pytest.fail(f"{relative_path} is invalid YAML: {exc}")

    assert isinstance(data, dict), f"{path.name} must contain a YAML mapping"
    assert data, f"{path.name} must not be empty"


def test_langpacks_loader_can_load_all_yaml_files():
    """The langpack manager should load every bundled locale file."""
    from core.langpacks import clear_langpacks_cache, get_langpacks

    clear_langpacks_cache()
    try:
        packs = get_langpacks()
        expected_locales = {path.stem for path in LANGPACK_FILES}

        assert expected_locales <= set(packs), (
            "Loaded langpacks are missing locales: "
            f"{sorted(expected_locales - set(packs))}"
        )
    finally:
        clear_langpacks_cache()


def test_custom_langpacks_are_discovered_and_loaded(tmp_path, monkeypatch):
    """User-installed packs in ``langpacks/custom`` are regular locales."""
    from core import langpacks

    langpacks_dir = tmp_path / "langpacks"
    custom_dir = langpacks_dir / "custom"
    custom_dir.mkdir(parents=True)
    (langpacks_dir / "en.yaml").write_text(
        "lang: en\nprobe:\n  hello: Hello\n", encoding="utf-8"
    )
    (custom_dir / "es.yaml").write_text(
        "lang: en\nprobe:\n  hello: Hola\n", encoding="utf-8"
    )

    monkeypatch.setattr(langpacks, "_LANGPACKS_DIR", langpacks_dir)
    monkeypatch.setattr(langpacks, "_ICONS_DIR", langpacks_dir / "icons")
    monkeypatch.setattr(langpacks, "CUSTOM_LANGPACKS_DIR", custom_dir)
    langpacks.clear_langpacks_cache()
    try:
        assert langpacks.get_available_locales() == ["en", "es"]
        assert langpacks.get_langpacks()["es"]["probe"]["hello"] == "Hola"
    finally:
        langpacks.clear_langpacks_cache()


def test_icons_directory_contains_yaml_files():
    assert ICON_PACK_FILES, f"No icon pack YAML files found in {ICONS_DIR}"


@pytest.mark.parametrize("path", ICON_PACK_FILES, ids=lambda path: path.name)
def test_icon_pack_file_is_valid_mapping(path):
    from core import langpacks

    try:
        data = langpacks._load_yaml(path, icon_syntax=True)
    except yaml.YAMLError as exc:
        relative_path = path.relative_to(PROJECT_ROOT)
        pytest.fail(f"{relative_path} is not a valid icon pack: {exc}")

    assert isinstance(data, dict), f"{path.name} must contain a YAML mapping"
    assert data, f"{path.name} must not be empty"


def test_compact_premium_emoji_syntax_is_rendered(tmp_path):
    from core import langpacks

    path = tmp_path / "md5.yaml"
    path.write_text(
        """\
pack_md5:
  __premium_emoji__: true
  __global__: true
  icon_1: [1234567890](🙂)
  text_qwe: [111](😀)[222](😎)[333](🤖) # compact sequence
  unsafe_alt: '[444](</tg-emoji><b>owned</b>)'
""",
        encoding="utf-8",
    )

    data = langpacks._load_yaml(path, icon_syntax=True)
    locale_data = {}
    langpacks._merge_pack_data(locale_data, data)
    pack = locale_data["__global__"]["pack_md5"]

    assert pack["icon_1"] == '<tg-emoji emoji-id="1234567890">🙂</tg-emoji>'
    assert pack["text_qwe"] == (
        '<tg-emoji emoji-id="111">😀</tg-emoji>'
        '<tg-emoji emoji-id="222">😎</tg-emoji>'
        '<tg-emoji emoji-id="333">🤖</tg-emoji>'
    )
    assert pack["unsafe_alt"] == (
        '<tg-emoji emoji-id="444">&lt;/tg-emoji&gt;&lt;b&gt;owned&lt;/b&gt;</tg-emoji>'
    )
    assert "__premium_emoji__" not in pack
    assert "__global__" not in pack


@pytest.mark.parametrize("locale", [path.stem for path in LANGPACK_FILES])
def test_icon_packs_are_available_in_every_locale(locale):
    from core.langpacks import clear_langpacks_cache
    from utils.strings import Strings, reload_packs

    reload_packs()
    try:
        strings = Strings(
            SimpleNamespace(config={"language": locale}), {"name": "icons_probe"}
        )

        assert strings("material_emoji")("load_1") == (
            '<tg-emoji emoji-id="5345778951031658558">😭</tg-emoji>'
        )
        assert "__premium_emoji__" not in strings("material_emoji").keys()
        assert "__global__" not in strings("material_emoji").keys()
    finally:
        clear_langpacks_cache()


def test_documented_builtin_strings_are_available_from_strings_helper():
    """Documented global groups should be callable by string keys."""
    from core.langpacks import clear_langpacks_cache
    from utils.strings import Strings, reload_packs

    reload_packs()
    try:
        strings = Strings(
            SimpleNamespace(config={"language": "en"}), {"name": "docs_probe"}
        )

        expected_keys = {
            "material_emoji": {
                "load_1",
                "load_2",
                "load_3",
                "wave_pr_1",
                "wave_pr_2",
                "wave_pr_3",
                "process_bar_pr_1",
                "process_bar_pr_2",
                "process_bar_pr_3",
                "load_process_bar_pr_1",
                "load_process_bar_pr_2",
                "load_process_bar_pr_3",
                "load_process_bar_mini",
                "pulsating_circle",
                "load_4",
                "tumbler",
                "load_5",
                "map",
                "delete",
                "music",
            },
            "type_module": {
                "module_style_class",
                "module_style_kernel",
                "module_style_client_old",
                "module_type_native",
                "module_type_hikka",
                "module_type_hikka_library",
                "module_config_info",
            },
            "null": {"null"},
            "error": {
                "full_error",
                "error",
                "timeout",
                "unknown",
                "api_error",
                "permission_denied",
            },
            "buttons": {
                "close",
                "yes",
                "no",
                "back",
                "next",
                "update",
                "page",
                "back_menu",
            },
        }

        for group, keys in expected_keys.items():
            assert keys <= strings(group).keys()

        assert strings("null")("null") == "null"
        assert strings("buttons")("yes") == "💠 Yes"
        assert strings("buttons")("no") == "🚫 No"
        assert "Class" in strings("type_module")("module_type_native", style="Class")
        assert "7" in strings("type_module")("module_config_info", count=7)

        full_error = strings("error")(
            "full_error",
            error=".cmd",
            full_error="traceback text",
        )
        assert ".cmd" in full_error
        assert "traceback text" in full_error
        assert strings("buttons")("page").format(3) == "Page: 3"
    finally:
        clear_langpacks_cache()
