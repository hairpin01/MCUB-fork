# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Language packs management for MCUB."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "CUSTOM_LANGPACKS_DIR",
    "LANGPACKS",
    "clear_langpacks_cache",
    "get_all_module_strings",
    "get_available_locales",
    "get_kernel_strings",
    "get_langpacks",
    "get_module_strings",
]

_LANGPACKS_DIR = Path(__file__).parent
_ICONS_DIR = _LANGPACKS_DIR / "icons"
CUSTOM_LANGPACKS_DIR = _LANGPACKS_DIR / "custom"

LANGPACKS: dict[str, dict[str, Any]] = {}
_GLOBAL_MODULE = "__global__"
_GLOBAL_MARKER = "__global__"
_PREMIUM_EMOJI_MARKER = "__premium_emoji__"
_GROUP_VALUE = "__value__"
_PREMIUM_EMOJI_RE = re.compile(r"\[(\d+)\]\(([^()]*)\)")
_UNQUOTED_PREMIUM_EMOJI_RE = re.compile(
    r"^(?P<prefix>\s*(?:[\w.-]+|'[^']+'|\"[^\"]+\")\s*:\s*)"
    r"(?P<value>(?:\[\d+\]\([^()\r\n]*\))+)(?P<suffix>\s*(?:#.*)?)$"
)


def clear_langpacks_cache() -> None:
    """Clear the langpacks cache so the next get_langpacks() call reloads from disk."""
    LANGPACKS.clear()


def _is_global_marker(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return value == 1


def _iter_langpack_files() -> list[Path]:
    """Return bundled packs followed by user-installed custom packs."""
    files = sorted(_LANGPACKS_DIR.glob("*.yaml")) + sorted(_LANGPACKS_DIR.glob("*.yml"))
    if CUSTOM_LANGPACKS_DIR.is_dir():
        files.extend(sorted(CUSTOM_LANGPACKS_DIR.glob("*.yaml")))
        files.extend(sorted(CUSTOM_LANGPACKS_DIR.glob("*.yml")))
    return files


def get_available_locales() -> list[str]:
    """Return locale names from bundled and user-installed langpacks."""
    return sorted({file_path.stem for file_path in _iter_langpack_files()})


def _quote_unquoted_premium_emoji(text: str) -> str:
    """Make the compact ``[id](alt)`` notation valid YAML when unquoted."""
    lines = []
    for line in text.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        content = line[:-1] if newline else line
        match = _UNQUOTED_PREMIUM_EMOJI_RE.fullmatch(content)
        if match:
            content = (
                f"{match['prefix']}{json.dumps(match['value'], ensure_ascii=False)}"
                f"{match['suffix']}"
            )
        lines.append(content + newline)
    return "".join(lines)


def _load_yaml(file_path: Path, *, icon_syntax: bool = False) -> dict[str, Any]:
    try:
        import yaml

        text = file_path.read_text(encoding="utf-8")
        if icon_syntax:
            text = _quote_unquoted_premium_emoji(text)
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    except ImportError:
        return {}


def _render_premium_emoji(value: Any) -> Any:
    if isinstance(value, str):
        return _PREMIUM_EMOJI_RE.sub(
            lambda match: (
                f'<tg-emoji emoji-id="{match.group(1)}">'
                f"{html.escape(match.group(2))}</tg-emoji>"
            ),
            value,
        )
    if isinstance(value, dict):
        return {key: _render_premium_emoji(item) for key, item in value.items()}
    return value


def _merge_pack_data(locale_data: dict[str, Any], data: dict[str, Any]) -> None:
    """Merge one locale or icon-pack mapping into normalized locale data."""
    for module_name, strings in data.items():
        if isinstance(strings, dict):
            premium_emoji = _is_global_marker(strings.get(_PREMIUM_EMOJI_MARKER))
            normalized = {
                key: _render_premium_emoji(value) if premium_emoji else value
                for key, value in strings.items()
                if key != _PREMIUM_EMOJI_MARKER
            }

            if _is_global_marker(normalized.get(_GLOBAL_MARKER)):
                normalized.pop(_GLOBAL_MARKER, None)
                global_groups = locale_data.setdefault(_GLOBAL_MODULE, {})
                current = global_groups.setdefault(module_name, {})
                if isinstance(current, dict):
                    current.update(normalized)
                else:
                    global_groups[module_name] = normalized
                continue

            module_strings = locale_data.setdefault(module_name, {})
            if not isinstance(module_strings, dict):
                module_strings = {}
                locale_data[module_name] = module_strings
            for key, value in normalized.items():
                if isinstance(value, (str, dict)):
                    module_strings[key] = value
        elif isinstance(strings, str):
            # Top-level string metadata, e.g. "lang: ru".
            locale_data[module_name] = strings


def _load_icon_packs() -> list[dict[str, Any]]:
    if not _ICONS_DIR.is_dir():
        return []
    files = sorted(_ICONS_DIR.glob("*.yaml")) + sorted(_ICONS_DIR.glob("*.yml"))
    return [_load_yaml(file_path, icon_syntax=True) for file_path in files]


def get_langpacks(locale: str | None = None) -> dict[str, dict[str, Any]]:
    if LANGPACKS:
        if locale and locale in LANGPACKS:
            return {locale: LANGPACKS[locale]}
        return LANGPACKS

    icon_packs = _load_icon_packs()
    for yaml_file in _iter_langpack_files():
        locale_name = yaml_file.stem
        data = _load_yaml(yaml_file)

        locale_data = LANGPACKS.setdefault(locale_name, {})
        for icon_pack in icon_packs:
            _merge_pack_data(locale_data, icon_pack)
        _merge_pack_data(locale_data, data)

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
