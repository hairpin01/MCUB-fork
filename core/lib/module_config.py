# lib/module_config.py
"""
Module configuration system for MCUB.
Provides declarative configuration similar to Hikka.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Union


class ValidationError(Exception):
    """Raised when a config value fails validation."""
    pass


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


class Boolean(Validator):
    def validate(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ('true', '1', 'yes', 'on'):
                return True
            if value.lower() in ('false', '0', 'no', 'off'):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValidationError(f"Expected boolean, got {type(value).__name__}")


class Integer(Validator):
    def __init__(self, default: Any = None, min: Optional[int] = None, max: Optional[int] = None):
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
    def __init__(self, default: Any = None, min: Optional[float] = None, max: Optional[float] = None):
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
    def __init__(self, default: Any = None, min_len: Optional[int] = None, max_len: Optional[int] = None):
        super().__init__(default)
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> str:
        if not isinstance(value, str):
            try:
                value = str(value)
            except:
                raise ValidationError(f"Expected string, got {type(value).__name__}")
        if self.min_len is not None and len(value) < self.min_len:
            raise ValidationError(f"String length must be >= {self.min_len}")
        if self.max_len is not None and len(value) > self.max_len:
            raise ValidationError(f"String length must be <= {self.max_len}")
        return value


class Choice(Validator):
    def __init__(self, choices: List[Any], default: Any = None):
        super().__init__(default)
        self.choices = choices

    def validate(self, value: Any) -> Any:
        if value not in self.choices:
            raise ValidationError(f"Value must be one of: {', '.join(map(str, self.choices))}")
        return value


class MultiChoice(Validator):
    def __init__(self, choices: List[Any], default: Optional[List[Any]] = None):
        super().__init__(default or [])
        self.choices = choices

    def validate(self, value: Any) -> List[Any]:
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


class ConfigValue:
    """
    Represents a single configuration option for a module.
    """
    def __init__(
        self,
        key: str,
        default: Any,
        description: Optional[Union[str, Callable]] = None,
        validator: Optional[Validator] = None,
        hidden: bool = False,
        on_change: Optional[Callable] = None,
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
        return self._description() if callable(self._description) else self._description or ""

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
        self._values: Dict[str, ConfigValue] = {}
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

    def update(self, mapping: Dict[str, Any]):
        for key, value in mapping.items():
            self[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Return current config as plain dict (for saving)."""
        return {key: cv.to_storage() for key, cv in self._values.items()}

    def from_dict(self, data: Dict[str, Any]):
        """Load config from dict (e.g., from database)."""
        for key, cv in self._values.items():
            if key in data:
                cv.from_storage(data[key])
            else:
                cv.from_storage(None)  # reset to default

    @property
    def schema(self) -> List[Dict]:
        """Return schema for UI generation."""
        return [
            {
                "key": cv.key,
                "type": cv.validator.__class__.__name__.lower(),
                "default": cv.default,
                "description": cv.description,
                "hidden": cv.hidden or getattr(cv.validator, 'secret', False),
                "choices": getattr(cv.validator, 'choices', None),
                "min": getattr(cv.validator, 'min', None),
                "max": getattr(cv.validator, 'max', None),
            }
            for cv in self._values.values()
        ]
