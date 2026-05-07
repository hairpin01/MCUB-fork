# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""Language packs management for MCUB."""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "LANGPACKS",
    "get_all_module_strings",
    "get_available_locales",
    "get_kernel_strings",
    "get_langpacks",
    "get_module_strings",
]

_LANGPACKS_DIR = Path(__file__).parent

LANGPACKS: dict[str, dict[str, Any]] = {}
_GLOBAL_MODULE = "__global__"
_GLOBAL_MARKER = "__global__"
_GROUP_VALUE = "__value__"


def _is_global_marker(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return value == 1


def get_available_locales() -> list[str]:
    """Returns list of available locales from langpacks files."""
    return [f.stem for f in _LANGPACKS_DIR.glob("*.yaml")]


def _load_yaml(file_path: Path) -> dict[str, Any]:
    try:
        import yaml

        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}


def get_langpacks(locale: str | None = None) -> dict[str, dict[str, Any]]:
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
                if _is_global_marker(strings.get(_GLOBAL_MARKER)):
                    LANGPACKS[locale_name].setdefault(_GLOBAL_MODULE, {})[
                        module_name
                    ] = {
                        key: value
                        for key, value in strings.items()
                        if key != _GLOBAL_MARKER
                    }
                    continue

                for key, value in strings.items():
                    if isinstance(value, (str, dict)):
                        LANGPACKS[locale_name].setdefault(module_name, {})[key] = value
            elif isinstance(strings, str):
                # Top-level string metadata, e.g. "lang: ru" — base language for fallback.
                # Stored directly on the locale dict so get_module_strings and
                # get_module_commands can resolve the correct fallback chain.
                LANGPACKS[locale_name][module_name] = strings  # type: ignore[assignment]

    if locale and locale in LANGPACKS:
        return {locale: LANGPACKS[locale]}
    return LANGPACKS


def _merge_globals(locale_data: dict[str, Any], module_strings: Any) -> dict[str, Any]:
    global_strings = locale_data.get(_GLOBAL_MODULE, {})
    if not isinstance(global_strings, dict):
        global_strings = {}

    if isinstance(module_strings, dict):
        result = dict(global_strings)
        for key, value in module_strings.items():
            global_value = result.get(key)
            if isinstance(global_value, dict):
                if isinstance(value, dict):
                    result[key] = {**global_value, **value}
                elif isinstance(value, str):
                    result[key] = {**global_value, _GROUP_VALUE: value}
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    if global_strings:
        return dict(global_strings)
    return {}


def get_kernel_strings(locale: str = "ru") -> dict[str, Any]:
    """Get kernel strings for the specified locale."""
    packs = get_langpacks()
    locale_data = packs.get(locale, {})
    return _merge_globals(locale_data, locale_data.get("kernel", {}))


def get_module_strings(module_name: str, locale: str = "ru") -> dict[str, Any]:
    """Get strings for a module, with fallback to base language if needed."""
    packs = get_langpacks()

    # Try requested locale first
    locale_data = packs.get(locale, {})
    result = locale_data.get(module_name, None)

    if result is not None:
        return _merge_globals(locale_data, result)

    # Check for base language fallback
    base_lang = packs.get(locale, {}).get("lang") or packs.get("ru", {}).get("lang")
    if base_lang:
        base_data = packs.get(base_lang, {})
        result = base_data.get(module_name, None)
        if result is not None:
            return _merge_globals(base_data, result)

    # Try fallback chain: ru -> en
    for fb in ("ru", "en"):
        if fb != locale:
            fb_data = packs.get(fb, {})
            result = fb_data.get(module_name, None)
            if result is not None:
                return _merge_globals(fb_data, result)

    return _merge_globals(locale_data, {})


def get_all_module_strings(module_name: str) -> dict[str, dict[str, Any]]:
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
            result[loc] = _merge_globals(loc_data, strings)
        else:
            base = loc_data.get("lang") or "en"
            base_data = packs.get(base, {})
            result[loc] = _merge_globals(base_data, base_data.get(module_name, {}))

    return {k: v for k, v in result.items() if v}
