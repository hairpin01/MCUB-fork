# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

# lib/module_config.py
"""
Module configuration system for MCUB.
Provides declarative configuration similar to Hikka.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, List


class Validator:
    """Base validator class."""

    def __init__(self, default: Any = None):
        self.default = default

    def validate(self, value: Any) -> Any:
        """Validate and possibly transform value."""
        return value

    def to_python(self, value: Any) -> Any:
        """Convert stored value to Python object."""
        return value

    def to_storage(self, value: Any) -> Any:
        """Convert Python object to storable form (e.g., for JSON)."""
        return value


class ValidationError(Exception):
    """Raised when a config value fails validation."""

    pass


class Boolean(Validator):
    def validate(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ("true", "1", "yes", "on"):
                return True
            if value.lower() in ("false", "0", "no", "off"):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValidationError(f"Expected boolean, got {type(value).__name__}")


class Integer(Validator):
    def __init__(
        self, default: Any = None, min: int | None = None, max: int | None = None
    ):
        super().__init__(default)
        self.min = min
        self.max = max

    def validate(self, value: Any) -> int:
        try:
            val = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Expected integer, got {type(value).__name__}")
        if self.min is not None and val < self.min:
            raise ValidationError(f"Value must be >= {self.min}")
        if self.max is not None and val > self.max:
            raise ValidationError(f"Value must be <= {self.max}")
        return val


class Float(Validator):
    def __init__(
        self,
        default: Any = None,
        min: float | None = None,
        max: float | None = None,
    ):
        super().__init__(default)
        self.min = min
        self.max = max

    def validate(self, value: Any) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Expected float, got {type(value).__name__}")
        if self.min is not None and val < self.min:
            raise ValidationError(f"Value must be >= {self.min}")
        if self.max is not None and val > self.max:
            raise ValidationError(f"Value must be <= {self.max}")
        return val


class String(Validator):
    def __init__(
        self,
        default: Any = None,
        min_len: int | None = None,
        max_len: int | None = None,
    ):
        super().__init__(default)
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> str:
        if value is None:
            return value
        if not isinstance(value, str):
            try:
                value = str(value)
            except (TypeError, ValueError):
                raise ValidationError(f"Expected string, got {type(value).__name__}")
        if self.min_len is not None and len(value) < self.min_len:
            raise ValidationError(f"String length must be >= {self.min_len}")
        if self.max_len is not None and len(value) > self.max_len:
            raise ValidationError(f"String length must be <= {self.max_len}")
        return value


class Placeholders(String):
    """String validator that marks config value as placeholder-aware."""

    def __init__(
        self,
        default: Any = None,
        min_len: int | None = None,
        max_len: int | None = None,
        *,
        placeholder_scope: str = "any",
    ):
        super().__init__(default=default, min_len=min_len, max_len=max_len)
        self.supports_placeholders = True
        self.placeholder_scope = placeholder_scope


class Choice(Validator):
    def __init__(self, choices: list[Any], default: Any = None):
        super().__init__(default)
        self.choices = choices

    def validate(self, value: Any) -> Any:
        if value not in self.choices:
            raise ValidationError(
                f"Value must be one of: {', '.join(map(str, self.choices))}"
            )
        return value


class MultiChoice(Validator):
    def __init__(self, choices: list[Any], default: list[Any] | None = None):
        super().__init__(default or [])
        self.choices = choices

    def validate(self, value: Any) -> list[Any]:
        if not isinstance(value, (list, tuple, set)):
            raise ValidationError("Expected a list of choices")
        for item in value:
            if item not in self.choices:
                raise ValidationError(f"Invalid choice: {item}")
        return list(value)


class Secret(Validator):
    """Validator for sensitive values (like tokens) – they will be hidden in UI."""

    def __init__(self, default: Any = None):
        super().__init__(default)
        self.secret = True

    def validate(self, value: Any) -> Any:
        # Accept anything, but treat as secret
        return value

    def to_python(self, value: Any) -> Any:
        # In UI we might show ****, but keep actual value in memory
        return value


class List(Validator):
    def __init__(
        self,
        default: Any = None,
        item_type: type | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
    ):
        super().__init__(default or [])
        self.item_type = item_type
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> list:
        if not isinstance(value, (list, tuple, set)):
            raise ValidationError("Expected a list")
        if self.min_len is not None and len(value) < self.min_len:
            raise ValidationError(f"List length must be >= {self.min_len}")
        if self.max_len is not None and len(value) > self.max_len:
            raise ValidationError(f"List length must be <= {self.max_len}")
        if self.item_type is not None:
            for item in value:
                if not isinstance(item, self.item_type):
                    raise ValidationError(
                        f"List items must be of type {self.item_type.__name__}"
                    )
        return list(value)


class DictType(Validator):
    """Validator for dictionary configuration values."""

    def __init__(
        self,
        default: Any = None,
        key_type: type | None = None,
        value_type: type | None = None,
    ):
        super().__init__(default or {})
        self.key_type = key_type
        self.value_type = value_type

    def validate(self, value: Any) -> dict:
        if not isinstance(value, dict):
            raise ValidationError("Expected a dictionary")
        if self.key_type is not None:
            for key in value:
                if not isinstance(key, self.key_type):
                    raise ValidationError(
                        f"Dictionary keys must be of type {self.key_type.__name__}"
                    )
        if self.value_type is not None:
            for val in value.values():
                if not isinstance(val, self.value_type):
                    raise ValidationError(
                        f"Dictionary values must be of type {self.value_type.__name__}"
                    )
        return dict(value)


class ConfigValue:
    """
    Represents a single configuration option for a module.
    """

    def __init__(
        self,
        key: str,
        default: Any,
        description: str | Callable | None = None,
        validator: Validator | None = None,
        hidden: bool = False,
        on_change: Callable | None = None,
    ):
        self.key = key
        self._default = default
        self._description = description
        self.validator = validator or Validator(default)
        self.hidden = hidden
        self.on_change = on_change
        self._value = None

    @property
    def default(self):
        # Allow default to be callable (like lambda for dynamic default)
        return self._default() if callable(self._default) else self._default

    @property
    def description(self):
        return (
            self._description()
            if callable(self._description)
            else self._description or ""
        )

    def set_value(self, value: Any):
        """Validate and set the value."""
        validated = self.validator.validate(value)
        self._value = validated

    def get_value(self) -> Any:
        """Get current value or default if not set."""
        if self._value is None:
            return self.default
        return self._value

    def to_storage(self) -> Any:
        """Convert value to storable format."""
        return self.validator.to_storage(self.get_value())

    def from_storage(self, stored: Any):
        """Load value from storage."""
        if stored is not None:
            self._value = self.validator.to_python(stored)
        else:
            self._value = None


class ModuleConfig:
    """
    Container for module configuration.
    Provides dictionary-like access to config values.
    """

    def __init__(self, *config_values: ConfigValue):
        self._values: dict[str, ConfigValue] = {}
        for cv in config_values:
            self._values[cv.key] = cv

    def __getitem__(self, key: str) -> Any:
        if key not in self._values:
            raise KeyError(f"Unknown config key: {key}")
        return self._values[key].get_value()

    def __setitem__(self, key: str, value: Any):
        if key not in self._values:
            raise KeyError(f"Unknown config key: {key}")
        cv = self._values[key]
        old = cv.get_value()
        cv.set_value(value)
        if cv.on_change:
            cv.on_change(old, value)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        return [(key, cv.get_value()) for key, cv in self._values.items()]

    def keys(self):
        return list(self._values.keys())

    def values(self):
        return [cv.get_value() for cv in self._values.values()]

    def update(self, mapping: dict[str, Any]):
        for key, value in mapping.items():
            self[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Return current config as plain dict (for saving)."""
        data = {key: cv.to_storage() for key, cv in self._values.items()}
        data["__mcub_config__"] = True
        return data

    def from_dict(self, data: dict[str, Any]):
        """Load config from dict (e.g., from database)."""
        for key, cv in self._values.items():
            if key in data and data[key] is not None:
                cv.from_storage(data[key])
            # If key not in data or value is None, keep the default

    @property
    def schema(self) -> List[dict]:
        """Return schema for UI generation."""
        return [
            {
                "key": cv.key,
                "type": cv.validator.__class__.__name__.lower(),
                "default": cv.default,
                "description": cv.description,
                "hidden": cv.hidden or getattr(cv.validator, "secret", False),
                "choices": getattr(cv.validator, "choices", None),
                "min": getattr(cv.validator, "min", None),
                "max": getattr(cv.validator, "max", None),
            }
            for cv in self._values.values()
        ]
