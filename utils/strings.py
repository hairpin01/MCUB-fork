# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

# author: @Hairpin00
# version: 1.1.0
# description: Localization helper for MCUB modules

from __future__ import annotations

__all__ = ["Strings", "get_available_locales"]

_FALLBACK = "en"

_LANGPACKS_CACHE: dict[str, dict[str, str]] | None = None


def get_available_locales() -> list[str]:
    """Returns list of available locales from langpacks files."""
    try:
        from core.langpacks import get_available_locales as _get_locales

        return _get_locales()
    except ImportError:
        return [_FALLBACK, "ru"]


def _get_locales_list() -> list[str]:
    """Returns list of locales to try, in order of preference."""
    locales = get_available_locales()
    fb = _FALLBACK
    # Ensure fallback is always last
    if fb in locales:
        locales.remove(fb)
    locales.append(fb)
    return locales


def _load_langpacks() -> dict[str, dict[str, str]]:
    global _LANGPACKS_CACHE
    if _LANGPACKS_CACHE is not None:
        return _LANGPACKS_CACHE

    try:
        from core.langpacks import get_langpacks

        _LANGPACKS_CACHE = get_langpacks()
        return _LANGPACKS_CACHE
    except ImportError:
        _LANGPACKS_CACHE = {}
        return _LANGPACKS_CACHE


class _MissingKey(str):
    """Returned for missing keys instead of raising, so modules don't crash."""

    def format_map(self, _mapping):
        return self

    def format(self, *a, **kw):
        return self


class Strings:
    def __init__(
        self,
        kernel_or_lang,
        data: dict[str, dict[str, str]],
        *,
        fallback: str = _FALLBACK,
        strict: bool = False,
    ) -> None:
        if not data:
            raise ValueError("Strings: data dict must not be empty")

        self._fallback = fallback
        self._strict = strict

        # Resolve language
        if isinstance(kernel_or_lang, str):
            self._locale = kernel_or_lang
        else:
            try:
                self._locale = (
                    kernel_or_lang.config.get("language", fallback) or fallback
                )
            except Exception:
                self._locale = fallback

        # Check for langpacks mode with "name" key
        module_name = data.get("name")
        self._module_name = module_name
        if module_name:
            self._data = self._load_from_langpacks(module_name, data)
        else:
            self._data = data

        # Resolve active locale dict with fallback chain
        active = self._data.get(self._locale) or self._data.get(fallback)
        if not active:
            for v in self._data.values():
                if v:
                    active = v
                    break
        if not active:
            raise ValueError(
                f"Strings: no valid locale data found. "
                f"Requested: {self._locale}, fallback: {fallback}, available: {list(self._data.keys())}"
            )
        self._active: dict[str, str] = active

    def _load_from_langpacks(
        self, module_name: str, data: dict[str, dict[str, str]]
    ) -> dict[str, dict[str, str]]:
        langpacks = _load_langpacks()
        fb = _FALLBACK
        result: dict[str, dict[str, str]] = {}

        locales_to_try = _get_locales_list()

        for locale in locales_to_try:
            pack = langpacks.get(locale, {})
            module_strings = pack.get(module_name, {})
            result[locale] = dict(module_strings)

        for locale in locales_to_try:
            inline = data.get(locale, {})
            if inline:
                result.setdefault(locale, {}).update(inline)

        if not result.get(fb):
            for locale, strings in langpacks.items():
                if strings:
                    result[locale] = strings.get(module_name, {})
                    break

        return {k: v for k, v in result.items() if v}

    @property
    def locale(self) -> str:
        return self._locale

    def _lookup(self, key: str) -> str:
        value = self._active.get(key)
        if value is not None:
            return value

        for _locale, locale_dict in self._data.items():
            if locale_dict and key in locale_dict:
                return locale_dict[key]

        if self._strict:
            raise KeyError(
                f"Strings: missing key {key!r} in locale {self._locale!r} (fallback: {self._fallback})"
            )

        return _MissingKey(f"[{key}]")

    def __getitem__(self, key: str) -> str:
        result = self._lookup(key)
        if isinstance(result, _MissingKey):
            raise KeyError(key)
        return result

    def __call__(self, key: str, **kwargs) -> str:
        return self._lookup(key).format(**kwargs) if kwargs else self._lookup(key)

    def get(self, key: str, default: str | None = None) -> str | None:
        value = self._active.get(key)
        if value is not None:
            return value
        fallback_dict = self._data.get(self._fallback, {})
        return fallback_dict.get(key, default)

    def fmt(self, key: str, **kwargs) -> str:
        return self(key, **kwargs)

    def has(self, key: str) -> bool:
        return key in self._active or key in self._data.get(self._fallback, {})

    def keys(self) -> set[str]:
        fallback_keys = set(self._data.get(self._fallback, {}).keys())
        return set(self._active.keys()) | fallback_keys

    @classmethod
    def validate(cls, data: dict[str, dict[str, str]]) -> list[str]:
        if not data:
            return ["data dict is empty"]

        if "name" in data:
            return []

        available = get_available_locales()
        locales = [k for k in data.keys() if k in available]
        if not locales:
            return [f"no valid locale keys found, expected one of: {available}"]

        reference_locale = locales[0]
        reference_keys = set(data[reference_locale].keys())
        problems: list[str] = []

        for locale in locales[1:]:
            locale_keys = set(data[locale].keys())
            missing = reference_keys - locale_keys
            extra = locale_keys - reference_keys
            if missing:
                problems.append(
                    f"[{locale}] missing keys (present in [{reference_locale}]): "
                    + ", ".join(sorted(missing))
                )
            if extra:
                problems.append(
                    f"[{locale}] extra keys (absent in [{reference_locale}]): "
                    + ", ".join(sorted(extra))
                )

        return problems

    def __repr__(self) -> str:
        return (
            f"Strings(locale={self._locale!r}, "
            f"locales={list(self._data.keys())}, "
            f"keys={len(self._active)})"
        )
