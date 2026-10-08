# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @Hairpin00
# version: 1.1.0
# description: Localization helper for MCUB modules

from __future__ import annotations

import weakref
from typing import Any

__all__ = ["Strings", "get_available_locales", "reload_packs"]

_FALLBACK = "en"
_GROUP_VALUE = "__value__"
_ESCAPED_NEWLINE = "\\n"


def _unescape(value: Any) -> Any:
    """Replace literal '\\n' escapes with real newlines in string values."""
    if isinstance(value, str):
        return value.replace(_ESCAPED_NEWLINE, "\n")
    return value

_LANGPACKS_CACHE: dict[str, dict[str, Any]] | None = None


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


def _load_langpacks() -> dict[str, dict[str, Any]]:
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


def reload_packs() -> None:
    global _LANGPACKS_CACHE
    _LANGPACKS_CACHE = None
    try:
        from core.langpacks import clear_langpacks_cache

        clear_langpacks_cache()
    except ImportError:
        pass
    current = {}
    for inst in list(Strings._instances):
        old_locale = inst._locale
        module_name = getattr(inst, "_module_name", None)
        if module_name is not None:
            current[module_name] = inst
    for module_name, inst in current.items():
        data = {"name": module_name}
        try:
            new_data = inst._load_from_langpacks(module_name, data)
            inst._data = new_data
            inst.set_locale(old_locale)
        except Exception:
            pass


class _MissingKey(str):
    """Returned for missing keys instead of raising, so modules don't crash."""

    def format_map(self, _mapping):
        return self

    def format(self, *a, **kw):
        return self


class StringsGroup:
    """Callable nested string group, e.g. self.strings("error")("key")."""

    def __init__(
        self, name: str, data: dict[str, Any], *, strict: bool = False
    ) -> None:
        self._name = name
        self._data = data
        self._strict = strict

    def _lookup(self, key: str) -> Any:
        value = self._data.get(key)
        if value is not None:
            if isinstance(value, dict):
                return StringsGroup(f"{self._name}.{key}", value, strict=self._strict)
            return value

        if self._strict:
            raise KeyError(f"StringsGroup: missing key {self._name}.{key}")

        return _MissingKey(f"[{self._name}.{key}]")

    def __getitem__(self, key: str) -> Any:
        result = self._lookup(key)
        if isinstance(result, _MissingKey):
            raise KeyError(key)
        return result

    def __call__(self, key: str, **kwargs) -> Any:
        result = _unescape(self._lookup(key))
        if kwargs and isinstance(result, str):
            escaped = {
                k: str(v).replace("{", "{{").replace("}", "}}")
                for k, v in kwargs.items()
            }
            return result.format(**escaped)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        return _unescape(self._data.get(key, default))

    def keys(self) -> set[str]:
        return set(self._data.keys())


class StringsGroupValue(str):
    """String value that is also callable as a nested global group."""

    def __new__(
        cls,
        value: str,
        name: str,
        data: dict[str, Any],
        *,
        strict: bool = False,
    ):
        obj = str.__new__(cls, value)
        obj._group = StringsGroup(name, data, strict=strict)
        return obj

    def __getitem__(self, key: str) -> Any:
        return self._group[key]

    def __call__(self, key: str, **kwargs) -> Any:
        return self._group(key, **kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        return self._group.get(key, default)

    def keys(self) -> set[str]:
        return self._group.keys()


def _wrap_group_value(name: str, value: dict[str, Any], *, strict: bool) -> Any:
    string_value = value.get(_GROUP_VALUE)
    group_data = {key: item for key, item in value.items() if key != _GROUP_VALUE}
    if isinstance(string_value, str):
        return StringsGroupValue(string_value, name, group_data, strict=strict)
    return StringsGroup(name, group_data or value, strict=strict)


class Strings:
    _instances: weakref.WeakSet[Strings] = weakref.WeakSet()

    def __init__(
        self,
        kernel_or_lang,
        data: dict[str, Any],
        *,
        fallback: str = _FALLBACK,
        strict: bool = False,
    ) -> None:
        if not data:
            raise ValueError("Strings: data dict must not be empty")

        self._fallback = fallback
        self._strict = strict
        Strings._instances.add(self)

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
        self._active: dict[str, Any] = active

    def _load_from_langpacks(
        self, module_name: str, data: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        langpacks = _load_langpacks()
        fb = _FALLBACK
        result: dict[str, dict[str, Any]] = {}

        locales_to_try = _get_locales_list()

        for locale in locales_to_try:
            try:
                from core.langpacks import get_module_strings

                module_strings = get_module_strings(module_name, locale)
            except ImportError:
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

    def _lookup(self, key: str) -> Any:
        value = self._active.get(key)
        if value is not None:
            if isinstance(value, dict):
                return _wrap_group_value(key, value, strict=self._strict)
            return value

        for _locale, locale_dict in self._data.items():
            if locale_dict and key in locale_dict:
                value = locale_dict[key]
                if isinstance(value, dict):
                    return _wrap_group_value(key, value, strict=self._strict)
                return value

        if self._strict:
            raise KeyError(
                f"Strings: missing key {key!r} in locale {self._locale!r} (fallback: {self._fallback})"
            )

        return _MissingKey(f"[{key}]")

    def __getitem__(self, key: str) -> Any:
        result = self._lookup(key)
        if isinstance(result, _MissingKey):
            raise KeyError(key)
        return result

    def __call__(self, key: str, **kwargs) -> Any:
        result = _unescape(self._lookup(key))
        if kwargs and isinstance(result, str):
            return result.format(**kwargs)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        value = self._active.get(key)
        if value is not None:
            if isinstance(value, dict):
                return _wrap_group_value(key, value, strict=self._strict)
            return _unescape(value)
        fallback_dict = self._data.get(self._fallback, {})
        value = fallback_dict.get(key, default)
        if isinstance(value, dict):
            return _wrap_group_value(key, value, strict=self._strict)
        return _unescape(value)

    def fmt(self, key: str, **kwargs) -> Any:
        return self(key, **kwargs)

    def has(self, key: str) -> bool:
        return key in self._active or key in self._data.get(self._fallback, {})

    def keys(self) -> set[str]:
        fallback_keys = set(self._data.get(self._fallback, {}).keys())
        return set(self._active.keys()) | fallback_keys

    @classmethod
    def validate(cls, data: dict[str, Any]) -> list[str]:
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

    def set_locale(self, locale: str) -> None:
        """Switch this Strings instance to a different locale at runtime."""
        self._locale = locale
        new_active = self._data.get(locale) or self._data.get(self._fallback)
        if new_active:
            self._active = new_active

    @classmethod
    def refresh_all(cls, locale: str) -> None:
        """Switch all registered Strings instances to a new locale."""
        for inst in list(cls._instances):
            inst.set_locale(locale)

    def __repr__(self) -> str:
        return (
            f"Strings(locale={self._locale!r}, "
            f"locales={list(self._data.keys())}, "
            f"keys={len(self._active)})"
        )
