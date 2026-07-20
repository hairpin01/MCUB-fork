# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
#
# lib/module_config.py
"""
Module configuration system for MCUB.
Provides declarative configuration similar to Hikka.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import unicodedata
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urlparse

_UNSET = object()
_LOGGER = logging.getLogger(__name__)


def _resolve_ui_value(value: Any, owner: Any | None = None) -> Any:
    """Resolve a static value or a zero/owner-argument UI callback."""
    if not callable(value):
        return value

    if owner is not None:
        try:
            signature = inspect.signature(value)
            accepts_owner = any(
                parameter.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.VAR_POSITIONAL,
                )
                for parameter in signature.parameters.values()
            )
            if accepts_owner:
                return value(owner)
        except (TypeError, ValueError):
            pass

    return value()


def _ui_visible(show_if: Any, owner: Any | None = None) -> bool:
    return bool(_resolve_ui_value(show_if, owner))


class ValidationError(Exception):
    """Raised when a config value fails validation."""

    pass


class Validator:
    """Base validator class."""

    internal_id = "Validator"

    def __init__(self, default: Any = None):
        self.default = default

    def validate(self, value: Any) -> Any:
        """Validate and possibly transform value."""
        return value

    def to_python(self, value: Any) -> Any:
        """Convert stored value to Python object."""
        return self.validate(value)

    def to_storage(self, value: Any) -> Any:
        """Convert Python object to storable form (e.g., for JSON)."""
        return value

    @property
    def type_name(self) -> str:
        return getattr(self, "internal_id", self.__class__.__name__)


class Boolean(Validator):
    internal_id = "Boolean"

    def validate(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValidationError(f"Expected boolean, got {type(value).__name__}")


class Integer(Validator):
    internal_id = "Integer"

    def __init__(
        self, default: Any = None, min: int | None = None, max: int | None = None
    ):
        super().__init__(default)
        self.min = min
        self.max = max

    def validate(self, value: Any) -> int | None:
        if value is None:
            return value
        if isinstance(value, bool):
            raise ValidationError("Expected integer, got bool")
        if isinstance(value, float) and not value.is_integer():
            raise ValidationError("Expected integer, got non-integral float")
        try:
            val = int(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Expected integer, got {type(value).__name__}"
            ) from None
        if self.min is not None and val < self.min:
            raise ValidationError(f"Value must be >= {self.min}")
        if self.max is not None and val > self.max:
            raise ValidationError(f"Value must be <= {self.max}")
        return val


class Float(Validator):
    internal_id = "Float"

    def __init__(
        self,
        default: Any = None,
        min: float | None = None,
        max: float | None = None,
    ):
        super().__init__(default)
        self.min = min
        self.max = max

    def validate(self, value: Any) -> float | None:
        if value is None:
            return value
        if isinstance(value, bool):
            raise ValidationError("Expected float, got bool")
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Expected float, got {type(value).__name__}"
            ) from None
        if self.min is not None and val < self.min:
            raise ValidationError(f"Value must be >= {self.min}")
        if self.max is not None and val > self.max:
            raise ValidationError(f"Value must be <= {self.max}")
        return val


class String(Validator):
    internal_id = "String"

    def __init__(
        self,
        default: Any = "",
        min_len: int | None = None,
        max_len: int | None = None,
        supports_placeholders: bool = False,
        placeholder_scope: str | None = None,
    ):
        super().__init__(default)
        self.min_len = min_len
        self.max_len = max_len
        self.supports_placeholders = supports_placeholders
        self.placeholder_scope = placeholder_scope

    def validate(self, value: Any) -> str | None:
        if value is None:
            return value
        val = str(value)
        if self.min_len is not None and len(val) < self.min_len:
            raise ValidationError(f"String length must be >= {self.min_len}")
        if self.max_len is not None and len(val) > self.max_len:
            raise ValidationError(f"String length must be <= {self.max_len}")
        return val


class Placeholders(String):
    """String validator that marks config value as placeholder-aware."""

    internal_id = "Placeholders"

    def __init__(
        self,
        default: Any = "",
        min_len: int | None = None,
        max_len: int | None = None,
        *,
        placeholder_scope: str = "any",
    ):
        super().__init__(
            default=default,
            min_len=min_len,
            max_len=max_len,
            supports_placeholders=True,
            placeholder_scope=placeholder_scope,
        )


class Link(String):
    """Valid URL validator."""

    internal_id = "Link"

    def __init__(
        self,
        default: Any = "",
        schemes: Iterable[str] | None = ("http", "https"),
        require_netloc: bool = True,
        **kwargs,
    ):
        super().__init__(default=default, **kwargs)
        self.schemes = (
            tuple(s.lower() for s in schemes) if schemes is not None else None
        )
        self.require_netloc = require_netloc

    def validate(self, value: Any) -> str:
        val = super().validate(value)
        if val is None:
            raise ValidationError("Expected URL, got None")
        val = val.strip()
        parsed = urlparse(val)
        if not parsed.scheme:
            raise ValidationError("Expected URL with scheme")
        if self.schemes is not None and parsed.scheme.lower() not in self.schemes:
            allowed = ", ".join(self.schemes)
            raise ValidationError(f"URL scheme must be one of: {allowed}")
        if self.require_netloc and not parsed.netloc:
            raise ValidationError("Expected URL with host")
        return val


class RegExp(String):
    """String that matches the given regular expression."""

    internal_id = "RegExp"

    def __init__(
        self,
        pattern: str | re.Pattern,
        default: Any = "",
        flags: int = 0,
        fullmatch: bool = True,
        **kwargs,
    ):
        super().__init__(default=default, **kwargs)
        self.pattern = (
            pattern.pattern if isinstance(pattern, re.Pattern) else str(pattern)
        )
        self.flags = flags if not isinstance(pattern, re.Pattern) else pattern.flags
        self.fullmatch = fullmatch
        self.regex = (
            pattern
            if isinstance(pattern, re.Pattern)
            else re.compile(self.pattern, flags)
        )

    def validate(self, value: Any) -> str:
        val = super().validate(value)
        if val is None:
            raise ValidationError("Expected string, got None")
        matched = (
            self.regex.fullmatch(val) if self.fullmatch else self.regex.search(val)
        )
        if not matched:
            raise ValidationError(
                f"String must match regular expression: {self.pattern}"
            )
        return val


class TelegramID(Integer):
    """Telegram ID validator (user, chat, channel, supergroup, etc.)."""

    internal_id = "TelegramID"

    def __init__(
        self,
        default: Any = 0,
        min: int | None = -(10**15),
        max: int | None = 10**15,
    ):
        super().__init__(default=default, min=min, max=max)

    def validate(self, value: Any) -> int:
        return super().validate(value)


_EMOJI_MODIFIERS = {
    0xFE0E,
    0xFE0F,
    *range(0x1F3FB, 0x1F400),
}


def _is_emoji_codepoint(char: str) -> bool:
    code = ord(char)
    return (
        0x1F000 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x2300 <= code <= 0x23FF
        or code in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D}
    )


class NoneType(Validator):
    """Validator that accepts only None."""

    internal_id = "NoneType"

    def __init__(self, default: Any = None):
        super().__init__(default)

    def validate(self, value: Any) -> None:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
            return None
        raise ValidationError("Expected None")


class Emoji(String):
    """Valid emoji or emoji sequence validator."""

    internal_id = "Emoji"

    def __init__(
        self,
        default: Any = "",
        min_count: int | None = 1,
        max_count: int | None = None,
        **kwargs,
    ):
        super().__init__(default=default, **kwargs)
        self.min_count = min_count
        self.max_count = max_count

    def validate(self, value: Any) -> str:
        val = super().validate(value)
        if val is None:
            raise ValidationError("Expected emoji, got None")
        val = val.strip()
        if not val:
            raise ValidationError("Expected emoji, got empty string")

        emoji_count = 0
        for char in val:
            if char.isspace():
                continue
            if _is_emoji_codepoint(char):
                if ord(char) not in _EMOJI_MODIFIERS:
                    emoji_count += 1
                continue
            category = unicodedata.category(char)
            if category in {"Mn", "Me", "Cf"}:
                continue
            raise ValidationError("Expected emoji characters only")

        if self.min_count is not None and emoji_count < self.min_count:
            raise ValidationError(f"Expected at least {self.min_count} emoji")
        if self.max_count is not None and emoji_count > self.max_count:
            raise ValidationError(f"Expected no more than {self.max_count} emoji")
        return val


class EntityLike(Validator):
    """Valid Telegram entity reference: link, URL, @username or Telegram ID."""

    internal_id = "EntityLike"

    _username_re = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
    _invite_re = re.compile(
        r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[A-Za-z0-9_+-]+/?$",
        re.I,
    )

    def __init__(self, default: Any = ""):
        super().__init__(default)
        self._telegram_id = TelegramID(default=None)
        self._url = Link(
            default="", schemes=("http", "https", "tg"), require_netloc=False
        )

    def validate(self, value: Any) -> int | str:
        if isinstance(value, bool):
            raise ValidationError("Expected entity-like value, got bool")
        if isinstance(value, int):
            return self._telegram_id.validate(value)
        if value is None:
            raise ValidationError("Expected entity-like value, got None")

        val = str(value).strip()
        if not val:
            raise ValidationError("Expected entity-like value, got empty string")

        try:
            return self._telegram_id.validate(val)
        except ValidationError:
            pass

        if self._username_re.fullmatch(val):
            return val
        if self._invite_re.fullmatch(val):
            return val
        try:
            return self._url.validate(val)
        except ValidationError:
            pass
        raise ValidationError("Expected Telegram ID, @username, t.me link or URL")


class Choice(Validator):
    internal_id = "Choice"

    def __init__(self, choices: list[Any], default: Any = None):
        super().__init__(default if default is not None else choices[0])
        self.choices = choices

    def validate(self, value: Any) -> Any:
        if value not in self.choices:
            raise ValidationError(
                f"Value must be one of: {', '.join(map(str, self.choices))}"
            )
        return value


class MultiChoice(Validator):
    internal_id = "MultiChoice"

    def __init__(self, choices: list[Any], default: list[Any] | None = None):
        super().__init__(default or [])
        self.choices = choices

    def validate(self, value: Any) -> list[Any]:
        if not isinstance(value, (list, tuple, set)):
            raise ValidationError("Expected a list of choices")
        invalid = [v for v in value if v not in self.choices]
        if invalid:
            raise ValidationError(f"Invalid choices: {invalid}")
        return value


class Union(Validator):
    """Combine multiple validators; first successful validator wins."""

    internal_id = "Union"

    def __init__(self, *validators: Validator, default: Any = _UNSET):
        if not validators:
            raise ValueError("Union requires at least one validator")
        self.validators = validators
        if default is _UNSET:
            default = validators[0].default
        super().__init__(default)

    def validate(self, value: Any) -> Any:
        errors = []
        for validator in self.validators:
            try:
                return validator.validate(value)
            except ValidationError as e:
                errors.append(str(e))
        names = ", ".join(
            getattr(v, "type_name", v.__class__.__name__) for v in self.validators
        )
        raise ValidationError(
            f"Value must match one of: {names}. Errors: {'; '.join(errors)}"
        )

    def to_python(self, value: Any) -> Any:
        return self.validate(value)

    def to_storage(self, value: Any) -> Any:
        validated = self.validate(value)
        for validator in self.validators:
            try:
                validator.validate(validated)
            except ValidationError:
                continue
            return validator.to_storage(validated)
        return validated


class Secret(Validator):
    """Validator for sensitive values (like tokens) - they will be hidden in UI."""

    internal_id = "Secret"

    def __init__(self, default: Any = None):
        super().__init__(default)
        self.secret = True

    def validate(self, value: Any) -> Any:
        # Accept anything, but treat as secret
        return value

    def to_python(self, value: Any) -> Any:
        # In UI we might show ****, but keep actual value in memory
        return value


class Hidden(Validator):
    """Hide another validator from UI."""

    internal_id = "Hidden"

    def __init__(self, validator: Validator | None = None, default: Any = None):
        self.validator = validator or String(default if default is not None else "")
        super().__init__(self.validator.default if default is None else default)
        self.secret = True

    def validate(self, value: Any) -> Any:
        return self.validator.validate(value)

    def to_python(self, value: Any) -> Any:
        return self.validator.to_python(value)

    def to_storage(self, value: Any) -> Any:
        return self.validator.to_storage(value)


class List(Validator):
    internal_id = "List"

    def __init__(self, default: list | None = None, item_type: type | None = None):
        super().__init__(default or [])
        self.item_type = item_type

    def validate(self, value: Any) -> list:
        if not isinstance(value, list):
            raise ValidationError("Expected list")
        if self.item_type is not None:
            for item in value:
                if not isinstance(item, self.item_type):
                    raise ValidationError(
                        f"List items must be of type {self.item_type.__name__}"
                    )
        return value


class DictType(Validator):
    internal_id = "DictType"

    def __init__(
        self,
        default: dict | None = None,
        key_type: type | None = None,
        value_type: type | None = None,
    ):
        super().__init__(default or {})
        self.key_type = key_type
        self.value_type = value_type

    def validate(self, value: Any) -> dict:
        if not isinstance(value, dict):
            raise ValidationError("Expected dictionary")
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
        description: str | Callable | Validator | None = None,
        validator: Validator | None = None,
        hidden: bool = False,
        on_change: Callable | None = None,
        show_if: bool | Callable = True,
    ):
        # Backward compatibility: ConfigValue("key", default, Validator())
        if isinstance(description, Validator) and validator is None:
            validator = description
            description = None

        self.key = key
        self._default = default
        self._description = description
        self.validator = validator or Validator(default)
        self.hidden = hidden
        self.on_change = on_change
        self._show_if = show_if
        self._value = _UNSET

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

    def is_visible(self, owner: Any | None = None) -> bool:
        """Return whether this value should be visible in config UI."""
        return _ui_visible(self._show_if, owner)

    def set_value(self, value: Any):
        """Validate and set the value."""
        validated = self.validator.validate(value)
        self._value = validated

    def get_value(self) -> Any:
        """Get current value or default if not set."""
        if self._value is _UNSET:
            return self.default
        return self._value

    def to_storage(self) -> Any:
        """Convert value to storable format."""
        return self.validator.to_storage(self.get_value())

    def from_storage(self, stored: Any):
        """Load value from storage."""
        self._value = self.validator.to_python(stored)


class Buttons:
    """UI-only ModuleConfig item that opens a custom buttons menu."""

    ui_only = True
    ui_type = "buttons"

    def __init__(
        self,
        title: str | Callable,
        description: str | Callable = "",
        button_text: str | Callable | None = None,
        buttons: list | Callable | None = None,
        *,
        on_click: Callable | None = None,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._title = title
        self._description = description
        self._button_text = button_text if button_text is not None else title
        self._buttons = buttons if buttons is not None else []
        self.on_click = on_click

    @staticmethod
    def _resolve(value: Any, owner: Any | None = None) -> Any:
        if not callable(value):
            return value

        if owner is not None:
            try:
                signature = inspect.signature(value)
                accepts_owner = any(
                    parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.VAR_POSITIONAL,
                    )
                    for parameter in signature.parameters.values()
                )
                if accepts_owner:
                    return value(owner)
            except (TypeError, ValueError):
                pass

        return value()

    @property
    def title(self) -> str:
        return str(self._resolve(self._title) or "")

    @property
    def description(self) -> str:
        return str(self._resolve(self._description) or "")

    @property
    def button_text(self) -> str:
        return str(
            self._resolve(self._button_text) or self.title or self.key or "Buttons"
        )

    def get_buttons(self, owner: Any | None = None) -> list:
        buttons = self._resolve(self._buttons, owner)
        return buttons if isinstance(buttons, list) else []

    @staticmethod
    def _call_click_callback(
        callback: Callable, owner: Any | None, event: Any | None
    ) -> Any:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return callback(owner, event)

        parameters = list(signature.parameters.values())
        if any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in parameters
        ):
            return callback(owner, event)

        positional = [
            parameter
            for parameter in parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if len(positional) >= 2:
            return callback(owner, event)
        if len(positional) >= 1:
            return callback(event)
        return callback()

    async def trigger_on_click(self, owner: Any | None, event: Any | None) -> None:
        if self.on_click is None:
            return

        result = self._call_click_callback(self.on_click, owner, event)
        if inspect.isawaitable(result):
            await result


class Row:
    """UI-only ModuleConfig layout marker that starts a new button row."""

    ui_only = True
    ui_type = "row"

    def __init__(self, *, key: str | None = None):
        self.key = str(key).strip() if key is not None else None


class Divider:
    """UI-only ModuleConfig visual divider button."""

    ui_only = True
    ui_type = "divider"

    def __init__(
        self,
        text: str | Callable = "────────",
        show_if: bool | Callable = True,
        *,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._text = text
        self._show_if = show_if

    def get_button_text(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._text, owner) or "────────")

    @property
    def button_text(self) -> str:
        return self.get_button_text()

    def is_visible(self, owner: Any | None = None) -> bool:
        return _ui_visible(self._show_if, owner)


class Url:
    """UI-only ModuleConfig URL button."""

    ui_only = True
    ui_type = "url"

    def __init__(
        self,
        button_text: str | Callable,
        url: str | Callable,
        show_if: bool | Callable = True,
        *,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._button_text = button_text
        self._url = url
        self._show_if = show_if

    def get_button_text(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._button_text, owner) or self.key or "Link")

    @property
    def button_text(self) -> str:
        return self.get_button_text()

    def get_url(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._url, owner) or "")

    @property
    def url(self) -> str:
        return self.get_url()

    def is_visible(self, owner: Any | None = None) -> bool:
        return _ui_visible(self._show_if, owner)


class Callback:
    """UI-only ModuleConfig single callback button."""

    ui_only = True
    ui_type = "callback"

    def __init__(
        self,
        button_text: str | Callable,
        on_click: Callable | None = None,
        show_if: bool | Callable = True,
        *,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._button_text = button_text
        self.on_click = on_click
        self._show_if = show_if

    def get_button_text(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._button_text, owner) or self.key or "Action")

    @property
    def button_text(self) -> str:
        return self.get_button_text()

    def is_visible(self, owner: Any | None = None) -> bool:
        return _ui_visible(self._show_if, owner)

    async def trigger_on_click(self, owner: Any | None, event: Any | None) -> None:
        if self.on_click is None:
            return
        result = Buttons._call_click_callback(self.on_click, owner, event)
        if inspect.isawaitable(result):
            await result


class Status:
    """UI-only ModuleConfig read-only status view."""

    ui_only = True
    ui_type = "status"

    def __init__(
        self,
        title: str | Callable,
        value: Any = "",
        show_if: bool | Callable = True,
        *,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._title = title
        self._value = value
        self._show_if = show_if

    def get_button_text(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._title, owner) or self.key or "Status")

    @property
    def button_text(self) -> str:
        return self.get_button_text()

    def get_value(self, owner: Any | None = None) -> Any:
        return _resolve_ui_value(self._value, owner)

    @property
    def value(self) -> Any:
        return self.get_value()

    def is_visible(self, owner: Any | None = None) -> bool:
        return _ui_visible(self._show_if, owner)


class Notice:
    """UI-only ModuleConfig conditional notice popup button."""

    ui_only = True
    ui_type = "notice"

    def __init__(
        self,
        text: str | Callable,
        show_if: bool | Callable = True,
        *,
        alert: bool = True,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._text = text
        self._show_if = show_if
        self.alert = alert

    def get_text(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._text, owner) or "")

    @property
    def text(self) -> str:
        return self.get_text()

    def get_button_text(self, owner: Any | None = None) -> str:
        return self.get_text(owner) or self.key or "Notice"

    @property
    def button_text(self) -> str:
        return self.get_button_text()

    def is_visible(self, owner: Any | None = None) -> bool:
        return _ui_visible(self._show_if, owner)


class Answer:
    """UI-only ModuleConfig item that answers with a popup text."""

    ui_only = True
    ui_type = "answer"

    def __init__(
        self,
        button_text: str | Callable,
        text: str | Callable = "",
        *,
        alert: bool = True,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._button_text = button_text
        self._text = text
        self.alert = alert

    @staticmethod
    def _resolve(value: Any) -> Any:
        return value() if callable(value) else value

    @property
    def button_text(self) -> str:
        return str(self._resolve(self._button_text) or self.key or "Info")

    @property
    def text(self) -> str:
        return str(self._resolve(self._text) or "")


class Group:
    """UI-only ModuleConfig submenu with nested config/UI items."""

    ui_only = True
    ui_type = "group"

    def __init__(
        self,
        title: str | Callable,
        items: list | tuple,
        description: str | Callable = "",
        *,
        button_text: str | Callable | None = None,
        on_click: Callable | None = None,
        show_if: bool | Callable = True,
        key: str | None = None,
    ):
        self.key = str(key).strip() if key is not None else None
        self._title = title
        self._description = description
        self._button_text = button_text if button_text is not None else title
        self.on_click = on_click
        self._show_if = show_if
        self.items = list(items or [])

    @staticmethod
    def _resolve(value: Any) -> Any:
        return value() if callable(value) else value

    @property
    def title(self) -> str:
        return str(self._resolve(self._title) or "")

    @property
    def description(self) -> str:
        return str(self._resolve(self._description) or "")

    @property
    def button_text(self) -> str:
        return str(
            self._resolve(self._button_text) or self.title or self.key or "Group"
        )

    def get_title(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._title, owner) or "")

    def get_description(self, owner: Any | None = None) -> str:
        return str(_resolve_ui_value(self._description, owner) or "")

    def get_button_text(self, owner: Any | None = None) -> str:
        return str(
            _resolve_ui_value(self._button_text, owner)
            or self.get_title(owner)
            or self.key
            or "Group"
        )

    def is_visible(self, owner: Any | None = None) -> bool:
        return _ui_visible(self._show_if, owner)

    async def trigger_on_click(self, owner: Any | None, event: Any | None) -> None:
        if self.on_click is None:
            return
        result = Buttons._call_click_callback(self.on_click, owner, event)
        if inspect.isawaitable(result):
            await result


class ModuleConfig:
    """
    Container for module configuration.
    Provides dictionary-like access to config values.
    """

    def __init__(
        self,
        *config_values: ConfigValue
        | Buttons
        | Row
        | Divider
        | Url
        | Callback
        | Status
        | Notice
        | Answer
        | Group,
        on_change: Callable | None = None,
        version: int | str | None = None,
        migrate: Callable | None = None,
    ):
        self._values: dict[str, ConfigValue] = {}
        self._ui_items: dict[str, Any] = {}
        self._group_items: dict[str, list[str]] = {}
        self._items_order: list[str] = []
        self._owner: Any | None = None
        self.on_change = on_change
        self.version = version
        self.migrate = migrate
        for index, item in enumerate(config_values):
            self._register_item(item, index, self._items_order)

    def _register_item(self, item: Any, index: Any, order: list[str]) -> None:
        if self._is_ui_only_item(item):
            key = self._prepare_ui_key(item, index)
            try:
                item.key = key
            except Exception:
                pass
            self._ui_items[key] = item
            order.append(key)
            if getattr(item, "ui_type", None) == "group":
                group_order: list[str] = []
                self._group_items[key] = group_order
                for child_index, child in enumerate(getattr(item, "items", []) or []):
                    self._register_item(child, f"{index}_{child_index}", group_order)
            return

        if not isinstance(item, ConfigValue):
            raise TypeError("ModuleConfig accepts only ConfigValue or ui_only items")

        self._values[item.key] = item
        order.append(item.key)

    @staticmethod
    def _is_ui_only_item(item: Any) -> bool:
        return bool(getattr(item, "ui_only", False))

    def _prepare_ui_key(self, item: Any, index: Any) -> str:
        ui_type = str(getattr(item, "ui_type", "ui") or "ui")
        raw_key = getattr(item, "key", None) or f"{ui_type}_{index}"
        key = re.sub(r"\W+", "_", str(raw_key).strip().lower()).strip("_")
        key = key or str(index)
        prefix = f"{ui_type}_"
        if not key.startswith(prefix):
            key = f"{prefix}{key}"
        base = key
        suffix = 2
        while key in self._values or key in self._ui_items:
            key = f"{base}_{suffix}"
            suffix += 1
        return key

    def bind_owner(self, owner: Any) -> "ModuleConfig":
        """Bind a live module instance for owner-aware callbacks."""
        self._owner = owner
        return self

    @staticmethod
    async def _await_on_change_result(result: Any) -> None:
        await result

    @staticmethod
    def _consume_on_change_task(task: asyncio.Task) -> None:
        try:
            task.result()
        except Exception:
            _LOGGER.exception("ModuleConfig on_change callback failed")

    @staticmethod
    def _on_change_accepts_owner(callback: Callable) -> bool:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return False

        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        ):
            return True
        return len(positional) >= 3

    @classmethod
    def _run_on_change(
        cls, callback: Callable, old: Any, new: Any, owner: Any | None = None
    ) -> None:
        if owner is not None and cls._on_change_accepts_owner(callback):
            result = callback(owner, old, new)
        else:
            result = callback(old, new)
        if not inspect.isawaitable(result):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(cls._await_on_change_result(result))
            return

        task = loop.create_task(cls._await_on_change_result(result))
        task.add_done_callback(cls._consume_on_change_task)

    @staticmethod
    def _global_on_change_accepts_owner(callback: Callable) -> bool:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return False

        if any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        ):
            return True

        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        return len(positional) >= 4

    @classmethod
    def _run_global_on_change(
        cls,
        callback: Callable,
        key: str,
        old: Any,
        new: Any,
        owner: Any | None = None,
    ) -> None:
        if owner is not None and cls._global_on_change_accepts_owner(callback):
            result = callback(owner, key, old, new)
        else:
            result = callback(key, old, new)
        if not inspect.isawaitable(result):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(cls._await_on_change_result(result))
            return

        task = loop.create_task(cls._await_on_change_result(result))
        task.add_done_callback(cls._consume_on_change_task)

    @staticmethod
    def _migrate_accepts_version(callback: Callable) -> bool:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return False
        if any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        ):
            return True
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        return len(positional) >= 2

    def _apply_migration(self, data: dict[str, Any]) -> dict[str, Any]:
        if not callable(self.migrate):
            return data
        old_version = data.get("__mcub_config_version__")
        migrated = (
            self.migrate(data, old_version)
            if self._migrate_accepts_version(self.migrate)
            else self.migrate(data)
        )
        return dict(migrated) if migrated is not None else data

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
            self._run_on_change(cv.on_change, old, cv.get_value(), self._owner)
        if self.on_change:
            self._run_global_on_change(
                self.on_change, key, old, cv.get_value(), self._owner
            )

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        return [(key, cv.get_value()) for key, cv in self._values.items()]

    def ui_items(self):
        return self._items_from_order(self._items_order)

    def group_items(self, key: str):
        return self._items_from_order(self._group_items.get(key, []))

    def _schema_order(self) -> list[str]:
        order: list[str] = []
        seen: set[str] = set()
        for key in self._items_order:
            if key not in seen:
                order.append(key)
                seen.add(key)
            for child_key in self._group_items.get(key, []):
                if child_key not in seen:
                    order.append(child_key)
                    seen.add(child_key)
        for key in self._values:
            if key not in seen:
                order.append(key)
                seen.add(key)
        return order

    def _items_from_order(self, order: list[str]):
        items = []
        seen = set()
        for key in order:
            if key in seen:
                continue
            seen.add(key)
            if key in self._values:
                items.append((key, self._values[key].get_value()))
            elif key in self._ui_items:
                items.append((key, self._ui_items[key]))
        return items

    def get_button(self, key: str) -> Buttons | None:
        item = self._ui_items.get(key)
        return item if getattr(item, "ui_type", None) == "buttons" else None

    def button_keys(self) -> list[str]:
        return [
            key
            for key, item in self._ui_items.items()
            if getattr(item, "ui_type", None) == "buttons"
        ]

    def row_keys(self) -> list[str]:
        return [
            key
            for key, item in self._ui_items.items()
            if getattr(item, "ui_type", None) == "row"
        ]

    def get_ui_item(self, key: str, ui_type: str | None = None) -> Any | None:
        item = self._ui_items.get(key)
        if item is None:
            return None
        if ui_type is not None and getattr(item, "ui_type", None) != ui_type:
            return None
        return item

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
        if self.version is not None:
            data["__mcub_config_version__"] = self.version
        return data

    def from_dict(self, data: dict[str, Any]):
        """Load config from dict (e.g., from database)."""
        data = self._apply_migration(dict(data or {}))
        for key, cv in self._values.items():
            if key in data:
                cv.from_storage(data[key])
            # If key not in data, keep the default

    @property
    def schema(self) -> list[dict]:
        """Return schema for UI generation."""
        schema = []
        for key in self._schema_order():
            if key in self._values:
                cv = self._values[key]
                schema.append(
                    {
                        "key": cv.key,
                        "type": getattr(
                            cv.validator,
                            "internal_id",
                            cv.validator.__class__.__name__,
                        ).lower(),
                        "default": cv.default,
                        "description": cv.description,
                        "hidden": cv.hidden or getattr(cv.validator, "secret", False),
                        "choices": getattr(cv.validator, "choices", None),
                        "min": getattr(cv.validator, "min", None),
                        "max": getattr(cv.validator, "max", None),
                        "min_len": getattr(cv.validator, "min_len", None),
                        "max_len": getattr(cv.validator, "max_len", None),
                        "pattern": getattr(cv.validator, "pattern", None),
                        "validators": [
                            getattr(v, "internal_id", v.__class__.__name__)
                            for v in getattr(cv.validator, "validators", [])
                        ],
                    }
                )
            elif key in self._ui_items:
                item = self._ui_items[key]
                if getattr(item, "ui_type", None) != "buttons":
                    continue
                schema.append(
                    {
                        "key": key,
                        "type": "buttons",
                        "default": None,
                        "description": item.description,
                        "hidden": False,
                        "button_text": item.button_text,
                        "title": item.title,
                    }
                )
        return schema
