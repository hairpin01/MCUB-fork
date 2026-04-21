# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

__all__ = [
    "get_langpacks",
    "LANGPACKS",
    "get_available_locales",
    "get_module_strings",
    "get_all_module_strings",
]

_LANGPACKS_DIR = Path(__file__).parent

LANGPACKS: dict[str, dict[str, str]] = {}


def get_available_locales() -> list[str]:
    """Returns list of available locales from langpacks files."""
    return [f.stem for f in _LANGPACKS_DIR.glob("*.yaml")]


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
    """Get strings for a module, with fallback to base language if needed."""
    packs = get_langpacks()

    # Try requested locale first
    locale_data = packs.get(locale, {})
    result = locale_data.get(module_name, None)

    if result is not None:
        return result

    # Check for base language fallback
    base_lang = packs.get(locale, {}).get("lang") or packs.get("ru", {}).get("lang")
    if base_lang:
        base_data = packs.get(base_lang, {})
        result = base_data.get(module_name, None)
        if result is not None:
            return result

    # Try fallback chain: ru -> en
    for fb in ("ru", "en"):
        if fb != locale:
            fb_data = packs.get(fb, {})
            result = fb_data.get(module_name, None)
            if result is not None:
                return result

    return {}


def get_all_module_strings(module_name: str) -> dict[str, dict[str, str]]:
    """Returns all locale strings for a module with fallback fill."""
    packs = get_langpacks()
    available = get_available_locales()
    result = {}

    for loc in available:
        # Try direct locale
        loc_data = packs.get(loc, {})
        strings = loc_data.get(module_name, {})

        # Fill missing keys from base language
        if strings:
            result[loc] = dict(strings)
        else:
            base = loc_data.get("lang") or "en"
            base_data = packs.get(base, {})
            result[loc] = dict(base_data.get(module_name, {}))

    return {k: v for k, v in result.items() if v}
