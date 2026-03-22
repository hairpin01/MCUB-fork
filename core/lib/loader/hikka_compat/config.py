from typing import Any, Callable, Optional


class ConfigValue:
    def __init__(
        self,
        option: str,
        default: Any = None,
        doc: Any = None,
        description: Any = None,
        validator: Optional[Any] = None,
        on_change: Optional[Callable] = None,
    ):
        self.option = option
        self.default = default
        self._doc_raw = doc if doc is not None else description
        self.validator = validator
        self.on_change = on_change
        self._value: Any = None

    @property
    def doc(self) -> str:
        raw = self._doc_raw
        if callable(raw):
            try:
                return raw()
            except Exception:
                return "No description"
        return str(raw) if raw is not None else "No description"

    @doc.setter
    def doc(self, value: Any) -> None:
        self._doc_raw = value

    @property
    def description(self) -> str:
        return self.doc

    @description.setter
    def description(self, value: Any) -> None:
        self._doc_raw = value

    @property
    def value(self) -> Any:
        return self._value if self._value is not None else self.default

    @value.setter
    def value(self, v: Any) -> None:
        if self.validator and v is not None:
            try:
                v = self.validator.validate(v)
            except Exception:
                v = self.default
        old = self._value
        self._value = v
        if self.on_change and old != v:
            try:
                import asyncio as _asyncio
                if _asyncio.iscoroutinefunction(self.on_change):
                    _asyncio.ensure_future(self.on_change())
                else:
                    self.on_change()
            except Exception:
                pass

    def set_no_raise(self, value: Any) -> None:
        if self.validator and value is not None:
            try:
                value = self.validator.validate(value)
            except Exception:
                value = self.default
        self._value = value

    @property
    def is_secret(self) -> bool:
        return getattr(self.validator, "secret", False)


class ModuleConfig(dict):
    def __init__(self, *entries):
        if entries and all(isinstance(e, ConfigValue) for e in entries):
            self._config: dict[str, ConfigValue] = {cv.option: cv for cv in entries}
        else:
            keys, defaults, docs = [], [], []
            for i, entry in enumerate(entries):
                if i % 3 == 0:
                    keys.append(entry)
                elif i % 3 == 1:
                    defaults.append(entry)
                else:
                    docs.append(entry)
            self._config = {
                key: ConfigValue(option=key, default=default, doc=doc)
                for key, default, doc in zip(keys, defaults, docs)
            }

        super().__init__(
            {option: cv.value for option, cv in self._config.items()}
        )

    def __getitem__(self, key: str) -> Any:
        try:
            return self._config[key].value
        except KeyError:
            return None

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._config:
            self._config[key].value = value
        super().__setitem__(key, value)

    def __contains__(self, key: object) -> bool:
        return key in self._config

    def __iter__(self):
        return iter(self._config)

    def __len__(self) -> int:
        return len(self._config)

    def __repr__(self) -> str:
        return f"ModuleConfig({dict(self._config)!r})"

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._config:
            v = self._config[key].value
            return v if v is not None else default
        return default

    def keys(self):
        return self._config.keys()

    def values(self):
        return [cv.value for cv in self._config.values()]

    def items(self):
        return [(k, cv.value) for k, cv in self._config.items()]

    def getdoc(self, key: str, message=None) -> str:
        if key not in self._config:
            return ""
        ret = self._config[key].doc
        if callable(ret):
            try:
                ret = ret(message)
            except Exception:
                ret = ret()
        return ret or ""

    def getdef(self, key: str) -> Any:
        return self._config[key].default if key in self._config else None

    def set_no_raise(self, key: str, value: Any) -> None:
        if key in self._config:
            self._config[key].set_no_raise(value)
            super().__setitem__(key, self._config[key].value)

    def reload(self) -> None:
        for key, cv in self._config.items():
            super().__setitem__(key, cv.value)

    def change_validator(self, key: str, validator) -> None:
        if key in self._config:
            self._config[key].validator = validator

    def to_dict(self) -> dict:
        return {k: cv.value for k, cv in self._config.items()}

    def load_from_dict(self, data: dict) -> None:
        for k, v in data.items():
            self[k] = v

    @property
    def schema(self) -> list[dict]:
        return [
            {
                "key": cv.option,
                "default": cv.default,
                "description": cv.doc,
                "secret": cv.is_secret,
                "type": type(cv.validator).__name__.lstrip("_").lower()
                if cv.validator else "string",
            }
            for cv in self._config.values()
        ]


LibraryConfig = ModuleConfig
