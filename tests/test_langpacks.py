# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Tests for bundled localization language packs."""

from pathlib import Path

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
