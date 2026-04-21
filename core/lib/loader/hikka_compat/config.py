# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from collections.abc import Callable
from typing import Any

from .validators import ValidationError


class ConfigValue:
    def __init__(
        self,
        option: str,
        default: Any = None,
        doc: Any = None,
        description: Any = None,
        validator: Any | None = None,
        on_change: Callable | None = None,
    ):
        self.option = option
        self.default = default
        self._doc_raw = doc if doc is not None else description
        self.validator = validator
        self.on_change = on_change
        self._value: Any = None

        if validator is not None and default is not None:
            self.default = validator.validate(default)

    def _apply_value(
        self, value: Any, *, soft: bool = False, mark: bool = True
    ) -> None:
        old = self.value

        try:
            if self.validator is not None and value is not None:
                value = self.validator.validate(value)
        except ValidationError:
            if not soft:
                raise
            value = self.default

        self._value = value

        if old != self.value:
            if mark:
                self._save_marker = True
            if self.on_change:
                self._run_on_change()

    @property
    def doc(self) -> Any:
        raw = self._doc_raw
        if callable(raw):
            try:
                return raw()
            except Exception:
                return "No description"
        return raw if raw is not None else "No description"

    @doc.setter
    def doc(self, value: Any) -> None:
        self._doc_raw = value

    @property
    def description(self) -> Any:
        return self.doc

    @description.setter
    def description(self, value: Any) -> None:
        self._doc_raw = value

    @property
    def value(self) -> Any:
        return self.default if self._value is None else self._value

    @value.setter
    def value(self, value: Any) -> None:
        self._apply_value(value)

    def _run_on_change(self) -> None:
        try:
            import asyncio

            if asyncio.iscoroutinefunction(self.on_change):
                asyncio.ensure_future(self.on_change())
            else:
                self.on_change()
        except Exception:
            pass

    def set_no_raise(self, value: Any, *, mark: bool = True) -> None:
        self._apply_value(value, soft=True, mark=mark)

    @property
    def is_secret(self) -> bool:
        return getattr(self.validator, "secret", False)


class ModuleConfig(dict):
    def __init__(self, *entries):
        if entries and all(isinstance(entry, ConfigValue) for entry in entries):
            self._config = {entry.option: entry for entry in entries}
        else:
            keys, defaults, docs = [], [], []
            for index, entry in enumerate(entries):
                if index % 3 == 0:
                    keys.append(entry)
                elif index % 3 == 1:
                    defaults.append(entry)
                else:
                    docs.append(entry)

            self._config = {
                key: ConfigValue(option=key, default=default, doc=doc)
                for key, default, doc in zip(keys, defaults, docs, strict=False)
            }

        super().__init__(
            {option: config.value for option, config in self._config.items()}
        )

    def __getitem__(self, key: str) -> Any:
        if key not in self._config:
            return None
        return self._config[key].value

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self._config:
            raise KeyError(key)
        self._config[key].value = value
        super().__setitem__(key, self._config[key].value)

    def __contains__(self, key: object) -> bool:
        return key in self._config

    def __iter__(self):
        return iter(self._config)

    def __len__(self) -> int:
        return len(self._config)

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._config:
            return default
        value = self._config[key].value
        return default if value is None else value

    def keys(self):
        return self._config.keys()

    def values(self):
        return [config.value for config in self._config.values()]

    def items(self):
        return [(key, config.value) for key, config in self._config.items()]

    def getdoc(self, key: str, message=None) -> Any:
        if key not in self._config:
            return ""
        result = self._config[key].doc
        if callable(result):
            try:
                result = result(message)
            except TypeError:
                result = result()
        return result or ""

    def getdef(self, key: str) -> Any:
        return self._config[key].default if key in self._config else None

    def set_no_raise(self, key: str, value: Any, *, mark: bool = True) -> None:
        if key not in self._config:
            return
        self._config[key].set_no_raise(value, mark=mark)
        super().__setitem__(key, self._config[key].value)

    def reload(self) -> None:
        for key, config in self._config.items():
            super().__setitem__(key, config.value)

    def change_validator(self, key: str, validator) -> None:
        if key in self._config:
            self._config[key].validator = validator

    def to_dict(self) -> dict:
        return {key: config.value for key, config in self._config.items()}

    def load_from_dict(self, data: dict) -> None:
        for key, value in data.items():
            if key not in self._config:
                continue
            self.set_no_raise(key, value, mark=False)

    @property
    def schema(self) -> list[dict]:
        return [
            {
                "key": config.option,
                "default": config.default,
                "description": config.doc,
                "secret": config.is_secret,
                "type": getattr(config.validator, "internal_id", "String").lower(),
            }
            for config in self._config.values()
        ]


LibraryConfig = ModuleConfig
