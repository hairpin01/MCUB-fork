# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

__all__ = ["get_langpacks", "LANGPACKS"]

_LANGPACKS_DIR = Path(__file__).parent

LANGPACKS: dict[str, dict[str, str]] = {}


def _load_yaml(file_path: Path) -> dict[str, Any]:
    try:
        import yaml

        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}


def get_langpacks(locale: str | None = None) -> dict[str, dict[str, str]]:
    global LANGPACKS

    if LANGPACKS:
        if locale and locale in LANGPACKS:
            return {locale: LANGPACKS[locale]}
        return LANGPACKS

    for yaml_file in _LANGPACKS_DIR.glob("*.yaml"):
        locale_name = yaml_file.stem
        data = _load_yaml(yaml_file)

        if locale_name not in LANGPACKS:
            LANGPACKS[locale_name] = {}

        for module_name, strings in data.items():
            if isinstance(strings, dict):
                for key, value in strings.items():
                    if isinstance(value, str):
                        LANGPACKS[locale_name].setdefault(module_name, {})[key] = value

    if locale and locale in LANGPACKS:
        return {locale: LANGPACKS[locale]}
    return LANGPACKS


def get_module_strings(module_name: str, locale: str = "ru") -> dict[str, str]:
    packs = get_langpacks()
    locale_data = packs.get(locale, {})
    return locale_data.get(module_name, {})
