# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import types
from typing import Any


def _fmt(text: str, kwargs: dict) -> str:
    for k, v in kwargs.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text


class _TranslatorStub:
    def __init__(self, lang: str = "en"):
        self._lang = lang
        self._data: dict = {}

    def getkey(self, key: str) -> Any:
        return self._data.get(key, False)

    def gettext(self, text: str) -> str:
        return self._data.get(text, text)

    def get(self, key: str, lang: str = "en") -> str:
        return self._data.get(key, key)

    def getdict(self, key: str, **kwargs) -> dict:
        base = self._data.get(key, key)
        return {"en": _fmt(base, kwargs)}

    @property
    def raw_data(self) -> dict:
        return {"en": self._data}


class _CallableStringsDict(dict):
    def __call__(self, key: str, _=None) -> str:
        return self.get(key, key)


class _StringsShim:
    def __init__(self, mod, translator=None):
        self._mod = mod
        self._translator = translator
        self._base = getattr(mod, "strings", {})
        self.external_strings: dict = {}

    def get(self, key: str, lang: str | None = None) -> str:
        return self[key]

    def __getitem__(self, key: str) -> str:
        if key in self.external_strings:
            return self.external_strings[key]
        if self._translator is not None:
            try:
                lang = getattr(self._translator, "_lang", "en")
                lang_dict = getattr(self._mod, f"strings_{lang}", {})
                if key in lang_dict:
                    return lang_dict[key]
            except Exception:
                pass
        return self._base.get(key, f"Unknown strings: {key}")

    def __call__(self, key: str, _=None) -> str:
        return self.__getitem__(key)

    def __iter__(self):
        return iter(self._base)


_translator_stub = _TranslatorStub()


class _TranslationsModule(types.ModuleType):
    pass


_translations_mod = _TranslationsModule("__hikka_mcub_compat_translations__")
_translations_mod.Strings = _StringsShim
_translations_mod.translator = _translator_stub
_translations_mod.fmt = _fmt
_translations_mod.SUPPORTED_LANGUAGES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "ua": "🇺🇦 Український",
    "de": "🇩🇪 Deutsch",
    "jp": "🇯🇵 日本語",
}
_translations_mod.MEME_LANGUAGES = {
    "leet": "🏴‍☠️ 1337",
    "uwu": "🏴‍☠️ UwU",
    "tiktok": "🏴‍☠️ TikTokKid",
    "neofit": "🏴‍☠️ Neofit",
}
