# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Tests for bundled localization language packs."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LANGPACKS_DIR = PROJECT_ROOT / "core" / "langpacks"
LANGPACK_FILES = sorted(LANGPACKS_DIR.glob("*.yaml")) + sorted(
    LANGPACKS_DIR.glob("*.yml")
)


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
