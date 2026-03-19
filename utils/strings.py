# author: @Hairpin00
# version: 1.0.0
# description: Localization helper for MCUB modules

from __future__ import annotations

__all__ = ["Strings"]

_FALLBACK = "ru"


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

        self._data = data
        self._fallback = fallback
        self._strict = strict

        # Resolve language
        if isinstance(kernel_or_lang, str):
            self._locale = kernel_or_lang
        else:
            # kernel object
            try:
                self._locale = kernel_or_lang.config.get("language", fallback) or fallback
            except Exception:
                self._locale = fallback

        # Resolve active locale dict with fallback chain
        self._active: dict[str, str] = (
            data.get(self._locale)
            or data.get(fallback)
            or next(iter(data.values()))
        )

    @property
    def locale(self) -> str:
        return self._locale

    def _lookup(self, key: str) -> str:
        value = self._active.get(key)
        if value is not None:
            return value

        # Try fallback locale
        fallback_dict = self._data.get(self._fallback, {})
        value = fallback_dict.get(key)
        if value is not None:
            return value

        if self._strict:
            raise KeyError(f"Strings: missing key {key!r} in locale {self._locale!r}")

        return _MissingKey(f"[{key}]")

    def __getitem__(self, key: str) -> str:
        return self._lookup(key)

    def __call__(self, key: str, **kwargs) -> str:
        return self._lookup(key).format_map(kwargs)

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

        locales = list(data.keys())
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
