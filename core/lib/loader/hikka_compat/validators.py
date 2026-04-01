import random
import re
from typing import Any, Iterable, Optional
from urllib.parse import urlparse


class ValidationError(Exception):
    pass


class Validator:
    secret = False

    def __init__(self, doc: Any = None, internal_id: Optional[str] = None):
        self.doc = doc or {"en": ""}
        self.internal_id = internal_id or type(self).__name__

    def validate(self, value: Any) -> Any:
        return value


class Boolean(Validator):
    _TRUE_VALUES = frozenset(
        ("True", "true", "1", 1, True, "yes", "Yes", "on", "On", "y", "Y")
    )
    _FALSE_VALUES = frozenset(
        ("False", "false", "0", 0, False, "no", "No", "off", "Off", "n", "N")
    )
    _ALL_VALUES = _TRUE_VALUES | _FALSE_VALUES

    def __init__(self):
        super().__init__({"en": "boolean value"}, "Boolean")

    def validate(self, value: Any) -> bool:
        if value not in self._ALL_VALUES:
            raise ValidationError("Passed value must be a boolean")
        return value in self._TRUE_VALUES


class Integer(Validator):
    def __init__(self, *, digits=None, minimum=None, maximum=None):
        super().__init__({"en": "integer value"}, "Integer")
        self.digits = digits
        self.minimum = minimum
        self.maximum = maximum

    def validate(self, value: Any) -> int:
        try:
            value = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValidationError(f"Passed value ({value}) must be a number")

        if self.minimum is not None and value < self.minimum:
            raise ValidationError(f"Passed value ({value}) is lower than minimum one")
        if self.maximum is not None and value > self.maximum:
            raise ValidationError(f"Passed value ({value}) is greater than maximum one")
        if self.digits is not None and len(str(abs(value))) != self.digits:
            raise ValidationError(f"The length of passed value ({value}) is incorrect")

        return value


class Float(Validator):
    def __init__(self, *, minimum=None, maximum=None):
        super().__init__({"en": "float value"}, "Float")
        self.minimum = minimum
        self.maximum = maximum

    def validate(self, value: Any) -> float:
        try:
            value = float(str(value).strip())
        except (TypeError, ValueError):
            raise ValidationError(f"Passed value ({value}) must be a float")

        if self.minimum is not None and value < self.minimum:
            raise ValidationError(f"Passed value ({value}) is lower than minimum one")
        if self.maximum is not None and value > self.maximum:
            raise ValidationError(f"Passed value ({value}) is greater than maximum one")

        return value


class String(Validator):
    def __init__(self, *, min_len=None, max_len=None):
        super().__init__({"en": "string value"}, "String")
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> str:
        value = "" if value is None else str(value)
        if self.min_len is not None and len(value) < self.min_len:
            raise ValidationError(
                f"Passed value is shorter than minimum length {self.min_len}"
            )
        if self.max_len is not None and len(value) > self.max_len:
            raise ValidationError(
                f"Passed value is longer than maximum length {self.max_len}"
            )
        return value


class Choice(Validator):
    def __init__(self, possible_values: list, /):
        super().__init__({"en": "one of allowed values"}, "Choice")
        self.possible_values = list(possible_values)
        self.choices = self.possible_values

        def _choice_validator(value: Any) -> Any:
            if value not in self.possible_values:
                raise ValidationError(
                    f"Passed value ({value}) is not one of the following: "
                    f"{' / '.join(map(str, self.possible_values))}"
                )
            return value

        _choice_validator.keywords = {"possible_values": self.possible_values}
        self.validate = _choice_validator


class MultiChoice(Validator):
    def __init__(self, possible_values: list, /):
        super().__init__({"en": "multiple allowed values"}, "MultiChoice")
        self.possible_values = list(possible_values)
        self.choices = self.possible_values

        def _multichoice_validator(value: Any) -> list:
            if not isinstance(value, (list, tuple, set)):
                value = [value]

            result = list(value)
            for item in result:
                if item not in self.possible_values:
                    raise ValidationError(
                        f"One of passed values ({item}) is not one of the following: "
                        f"{' / '.join(map(str, self.possible_values))}"
                    )
            return result

        _multichoice_validator.keywords = {"possible_values": self.possible_values}
        self.validate = _multichoice_validator


class Series(Validator):
    def __init__(
        self,
        separator: str = ",",
        *,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
        validator: Optional[Validator] = None,
    ):
        super().__init__({"en": "series value"}, "Series")
        self.separator = separator
        self.min_len = min_len
        self.max_len = max_len
        self.validator = validator

    def validate(self, value: Any) -> list:
        if isinstance(value, str):
            result = [item.strip() for item in value.split(self.separator)]
            result = [item for item in result if item]
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
            result = list(value)
        else:
            raise ValidationError("Passed value must be list-like")

        if self.min_len is not None and len(result) < self.min_len:
            raise ValidationError("Passed value contains less items than required")
        if self.max_len is not None and len(result) > self.max_len:
            raise ValidationError("Passed value contains more items than allowed")

        if self.validator:
            validated = []
            for item in result:
                validated.append(self.validator.validate(item))
            result = validated

        return result


class RegExp(Validator):
    def __init__(self, pattern: str, flags: int = 0, description: Any = None):
        super().__init__(description or {"en": "regexp value"}, "RegExp")
        self.pattern = pattern
        self._compiled = re.compile(pattern, flags)

    def validate(self, value: Any) -> str:
        value = "" if value is None else str(value)
        if not self._compiled.match(value):
            raise ValidationError(
                f"Passed value ({value}) must follow pattern {self.pattern}"
            )
        return value


class Link(Validator):
    def __init__(self):
        super().__init__({"en": "url value"}, "Link")

    def validate(self, value: Any) -> str:
        value = "" if value is None else str(value).strip()
        try:
            parsed = urlparse(value)
        except Exception:
            parsed = None

        if not parsed or not parsed.scheme or not parsed.netloc:
            raise ValidationError(f"Passed value ({value}) is not a valid URL")
        return value


class Hidden(Validator):
    secret = True

    def __init__(self, validator: Optional[Validator] = None):
        super().__init__({"en": "hidden value"}, "Hidden")
        self.validator = validator

    def validate(self, value: Any) -> Any:
        if self.validator:
            return self.validator.validate(value)
        return value


class TelegramID(Integer):
    def __init__(self):
        super().__init__()
        self.internal_id = "TelegramID"


class EntityLike(String):
    def __init__(self):
        super().__init__(min_len=1)
        self.internal_id = "EntityLike"


class NoneType(Validator):
    def __init__(self):
        super().__init__({"en": "null value"}, "NoneType")

    def validate(self, value: Any) -> None:
        if value not in (None, "", "None", "none", "null"):
            raise ValidationError(f"Passed value ({value}) is not None")
        return None


class Union(Validator):
    def __init__(self, *validators: Validator):
        super().__init__({"en": "union value"}, "Union")
        self.validators = validators

    def validate(self, value: Any) -> Any:
        for validator in self.validators:
            try:
                return validator.validate(value)
            except ValidationError:
                continue
        raise ValidationError(f"Passed value ({value}) is not valid")


class Emoji(String):
    def __init__(self, *, length: Optional[int] = None):
        super().__init__(min_len=1)
        self.length = length
        self.internal_id = "Emoji"

    def validate(self, value: Any) -> str:
        value = super().validate(value)
        if self.length is not None and len(value) != self.length:
            raise ValidationError(
                f"Passed value ({value}) is not {self.length} emojis long"
            )
        return value


class RandomLinkList(list):
    def random(self) -> Optional[str]:
        return random.choice(self) if self else None


class RandomLink(Series):
    def __init__(self):
        super().__init__(validator=Link(), min_len=1)
        self.internal_id = "RandomLink"

    def validate(self, value: Any) -> RandomLinkList:
        return RandomLinkList(super().validate(value))


class validators:
    ValidationError = ValidationError
    Validator = Validator
    Boolean = Boolean
    Integer = Integer
    Float = Float
    String = String
    Choice = Choice
    MultiChoice = MultiChoice
    Series = Series
    RegExp = RegExp
    Link = Link
    Hidden = Hidden
    TelegramID = TelegramID
    EntityLike = EntityLike
    NoneType = NoneType
    Union = Union
    Emoji = Emoji
    RandomLink = RandomLink
