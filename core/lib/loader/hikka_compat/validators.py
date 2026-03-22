from typing import Any, Optional


class _Validator:
    def validate(self, value: Any) -> Any:
        return value


class _Hidden(_Validator):
    secret = True


class _Float(_Validator):
    def __init__(self, minimum=None, maximum=None):
        self.minimum = minimum
        self.maximum = maximum

    def validate(self, value: Any) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Expected a number, got {type(value).__name__!r}")
        if self.minimum is not None and v < self.minimum:
            raise ValueError(f"Value must be >= {self.minimum}")
        if self.maximum is not None and v > self.maximum:
            raise ValueError(f"Value must be <= {self.maximum}")
        return v


class _Integer(_Validator):
    def __init__(self, minimum=None, maximum=None):
        self.minimum = minimum
        self.maximum = maximum

    def validate(self, value: Any) -> int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Expected an integer, got {type(value).__name__!r}")
        if self.minimum is not None and v < self.minimum:
            raise ValueError(f"Value must be >= {self.minimum}")
        if self.maximum is not None and v > self.maximum:
            raise ValueError(f"Value must be <= {self.maximum}")
        return v


class _String(_Validator):
    def __init__(self, min_len=None, max_len=None):
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> str:
        v = str(value)
        if self.min_len is not None and len(v) < self.min_len:
            raise ValueError(f"String too short (min {self.min_len})")
        if self.max_len is not None and len(v) > self.max_len:
            raise ValueError(f"String too long (max {self.max_len})")
        return v


class _Boolean(_Validator):
    def validate(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).lower() in ("true", "1", "yes", "on")


class _Series(_Validator):
    def __init__(self, separator: str = ",", min_len: Optional[int] = None,
                 max_len: Optional[int] = None):
        self.separator = separator
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> list:
        if isinstance(value, (list, tuple)):
            result = [str(v).strip() for v in value if str(v).strip()]
        elif isinstance(value, str):
            result = [v.strip() for v in value.split(self.separator) if v.strip()]
        else:
            raise ValueError(f"Expected a list or comma-separated string, got {type(value).__name__!r}")
        if self.min_len is not None and len(result) < self.min_len:
            raise ValueError(f"List must have at least {self.min_len} items")
        if self.max_len is not None and len(result) > self.max_len:
            raise ValueError(f"List must have at most {self.max_len} items")
        return result


class _RegExp(_Validator):
    def __init__(self, pattern: str, flags: int = 0):
        import re
        self._pattern = re.compile(pattern, flags)

    def validate(self, value: Any) -> str:
        import re
        v = str(value)
        if not self._pattern.match(v):
            raise ValueError(f"Value {v!r} does not match pattern {self._pattern.pattern!r}")
        return v


class _TelegramID(_Validator):
    def validate(self, value: Any) -> int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Expected a Telegram ID (integer), got {type(value).__name__!r}")
        return v


class _EntityLike(_Validator):
    def validate(self, value: Any) -> Any:
        if isinstance(value, int):
            return value
        v = str(value).strip()
        if not v:
            raise ValueError("Entity cannot be empty")
        return v


class _Choice(_Validator):
    def __init__(self, choices: list, name: str = None):
        self.choices = choices
        self.name = name

    def validate(self, value: Any) -> Any:
        v = str(value)
        if v not in self.choices:
            raise ValueError(f"Value must be one of: {', '.join(map(str, self.choices))}")
        return v


class _MultiChoice(_Validator):
    def __init__(self, choices: list, name: str = None):
        self.choices = choices
        self.name = name

    def validate(self, value: Any) -> list:
        if isinstance(value, (list, tuple)):
            values = [str(v) for v in value]
        elif isinstance(value, str):
            values = [v.strip() for v in value.split(",") if v.strip()]
        else:
            raise ValueError(f"Expected a list or comma-separated string, got {type(value).__name__!r}")

        invalid = [v for v in values if v not in self.choices]
        if invalid:
            raise ValueError(f"Invalid choices: {', '.join(invalid)}. Must be from: {', '.join(map(str, self.choices))}")
        return values


class _Link(_Validator):
    def validate(self, value: Any) -> str:
        import re
        v = str(value).strip()
        pattern = re.compile(
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if not pattern.match(v):
            raise ValueError(f"Invalid URL: {v}")
        return v


class _Emoji(_Validator):
    def validate(self, value: Any) -> str:
        import re
        v = str(value).strip()
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        if not emoji_pattern.match(v):
            raise ValueError(f"Value {v!r} does not look like an emoji")
        return v


class validators:
    Hidden = _Hidden
    Float = _Float
    Integer = _Integer
    String = _String
    Boolean = _Boolean
    Series = _Series
    RegExp = _RegExp
    TelegramID = _TelegramID
    EntityLike = _EntityLike
    Choice = _Choice
    MultiChoice = _MultiChoice
    Link = _Link
    Emoji = _Emoji
