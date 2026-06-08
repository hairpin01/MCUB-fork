# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for core/lib/loader/module_config - validators and config containers.
"""

import pytest

from core.lib.loader.module_config import (
    Boolean,
    Choice,
    ConfigValue,
    Emoji,
    EntityLike,
    Float,
    Integer,
    Link,
    ModuleConfig,
    MultiChoice,
    NoneType,
    Placeholders,
    RegExp,
    Secret,
    String,
    TelegramID,
    Union,
    ValidationError,
    Validator,
)

# ─── Validator base ────────────────────────────────────────────────────


class TestValidator:
    def test_base_validate_passthrough(self):
        v = Validator(default=42)
        assert v.validate("anything") == "anything"

    def test_base_to_python_calls_validate(self):
        v = Validator(default=0)
        assert v.to_python("x") == "x"

    def test_base_to_storage(self):
        v = Validator(default=None)
        assert v.to_storage("x") == "x"

    def test_type_name(self):
        assert Validator(default=0).type_name == "Validator"


# ─── Boolean ───────────────────────────────────────────────────────────


class TestBoolean:
    @pytest.mark.parametrize("val", [True, False])
    def test_bool_passthrough(self, val):
        assert Boolean().validate(val) is val

    @pytest.mark.parametrize("val", ["true", "True", "1", "yes", "on"])
    def test_true_strings(self, val):
        assert Boolean().validate(val) is True

    @pytest.mark.parametrize("val", ["false", "False", "0", "no", "off"])
    def test_false_strings(self, val):
        assert Boolean().validate(val) is False

    @pytest.mark.parametrize("val", [1, 0, 1.0, 0.0])
    def test_numeric(self, val):
        assert Boolean().validate(val) is bool(val)

    @pytest.mark.parametrize("val", [None, "maybe", [], {}])
    def test_invalid_raises(self, val):
        with pytest.raises(ValidationError, match="Expected boolean"):
            Boolean().validate(val)


# ─── Integer ───────────────────────────────────────────────────────────


class TestInteger:
    def test_none_returns_none(self):
        """Integer must accept None - covers userbot-backup on_load crash."""
        iv = Integer(default=None)
        assert iv.validate(None) is None

    def test_valid_int(self):
        assert Integer().validate(42) == 42

    def test_string_parsed(self):
        assert Integer().validate("123") == 123
        assert Integer().validate("-5") == -5

    def test_float_rounded(self):
        assert Integer().validate(3.0) == 3

    def test_non_integral_float_raises(self):
        with pytest.raises(ValidationError, match="non-integral float"):
            Integer().validate(3.14)

    def test_bool_raises(self):
        with pytest.raises(ValidationError, match="Expected integer, got bool"):
            Integer().validate(True)

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError, match="Expected integer, got"):
            Integer().validate("not_a_number")

    def test_min_constraint(self):
        iv = Integer(default=0, min=5)
        with pytest.raises(ValidationError, match=">= 5"):
            iv.validate(3)
        assert iv.validate(10) == 10

    def test_max_constraint(self):
        iv = Integer(default=0, max=100)
        with pytest.raises(ValidationError, match="<= 100"):
            iv.validate(200)
        assert iv.validate(50) == 50

    def test_to_python_none(self):
        """to_python must also pass None through."""
        iv = Integer(default=None)
        assert iv.to_python(None) is None

    def test_to_storage_none(self):
        iv = Integer(default=None)
        assert iv.to_storage(None) is None

    def test_none_with_min_max_does_not_crash(self):
        """None bypasses min/max checks."""
        iv = Integer(default=None, min=1, max=10)
        assert iv.validate(None) is None


# ─── Float ─────────────────────────────────────────────────────────────


class TestFloat:
    def test_none_returns_none(self):
        fv = Float(default=None)
        assert fv.validate(None) is None

    def test_valid_float(self):
        assert Float().validate(3.14) == 3.14
        assert Float().validate(-2.5) == -2.5

    def test_string_parsed(self):
        assert Float().validate("2.5") == 2.5
        assert Float().validate("inf") == float("inf")

    def test_int_converted(self):
        assert Float().validate(5) == 5.0

    def test_bool_raises(self):
        with pytest.raises(ValidationError, match="Expected float, got bool"):
            Float().validate(False)

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError, match="Expected float, got"):
            Float().validate("not_a_float")

    def test_min_max(self):
        fv = Float(default=0, min=0.0, max=1.0)
        with pytest.raises(ValidationError, match=r">= 0\.0"):
            fv.validate(-1.0)
        with pytest.raises(ValidationError, match=r"<= 1\.0"):
            fv.validate(2.0)
        assert fv.validate(0.5) == 0.5


# ─── String ────────────────────────────────────────────────────────────


class TestString:
    def test_none_returns_none(self):
        sv = String(default=None)
        assert sv.validate(None) is None

    def test_valid_string(self):
        assert String().validate("hello") == "hello"

    def test_non_string_coerced(self):
        assert String().validate(42) == "42"

    def test_min_len(self):
        sv = String(default="", min_len=3)
        with pytest.raises(ValidationError, match=">= 3"):
            sv.validate("ab")
        assert sv.validate("abcd") == "abcd"

    def test_max_len(self):
        sv = String(default="", max_len=5)
        with pytest.raises(ValidationError, match="<= 5"):
            sv.validate("toolong")
        assert sv.validate("abc") == "abc"


# ─── Placeholders ──────────────────────────────────────────────────────


class TestPlaceholders:
    def test_inherits_string(self):
        pv = Placeholders(default="")
        assert pv.validate("test") == "test"
        assert pv.validate(None) is None

    def test_default_scope(self):
        pv = Placeholders(default="")
        assert pv.placeholder_scope == "any"


# ─── Link / URL ────────────────────────────────────────────────────────


class TestLink:
    def test_valid_url(self):
        lv = Link(default="")
        assert lv.validate("https://example.com") == "https://example.com"
        assert lv.validate("http://t.me/joinchat/abc") == "http://t.me/joinchat/abc"

    def test_no_scheme_raises(self):
        lv = Link(default="")
        with pytest.raises(ValidationError, match="scheme"):
            lv.validate("example.com")

    def test_none_raises(self):
        lv = Link(default="")
        with pytest.raises(ValidationError, match="None"):
            lv.validate(None)

    def test_custom_schemes(self):
        lv = Link(default="", schemes=("tg",))
        assert lv.validate("tg://user?id=1") == "tg://user?id=1"
        with pytest.raises(ValidationError, match="scheme"):
            lv.validate("https://example.com")


# ─── RegExp ────────────────────────────────────────────────────────────


class TestRegExp:
    def test_match(self):
        rv = RegExp(pattern=r"^\d+$", default="")
        assert rv.validate("123") == "123"

    def test_no_match_raises(self):
        rv = RegExp(pattern=r"^\d+$", default="")
        with pytest.raises(ValidationError, match="regular expression"):
            rv.validate("abc")

    def test_none_raises(self):
        rv = RegExp(pattern=r".*", default="")
        with pytest.raises(ValidationError, match="None"):
            rv.validate(None)

    def test_search_mode(self):
        rv = RegExp(pattern=r"\d+", default="", fullmatch=False)
        assert rv.validate("abc123") == "abc123"


# ─── TelegramID ────────────────────────────────────────────────────────


class TestTelegramID:
    def test_valid(self):
        tv = TelegramID(default=0)
        assert tv.validate(12345) == 12345
        assert tv.validate(-123) == -123

    def test_none_returns_none(self):
        """TelegramID inherits Integer, so None must be accepted."""
        tv = TelegramID(default=None)
        assert tv.validate(None) is None

    def test_out_of_range(self):
        tv = TelegramID(default=0)
        with pytest.raises(ValidationError):
            tv.validate(10**16)

    def test_bool_raises(self):
        tv = TelegramID(default=0)
        with pytest.raises(ValidationError):
            tv.validate(True)


# ─── NoneType ──────────────────────────────────────────────────────────


class TestNoneType:
    def test_none_accepted(self):
        assert NoneType().validate(None) is None

    def test_none_strings(self):
        assert NoneType().validate("") is None
        assert NoneType().validate("none") is None
        assert NoneType().validate("null") is None
        assert NoneType().validate("None") is None

    def test_other_raises(self):
        with pytest.raises(ValidationError, match="Expected None"):
            NoneType().validate(0)

    def test_other_raises_2(self):
        with pytest.raises(ValidationError, match="Expected None"):
            NoneType().validate("something")


# ─── Emoji ─────────────────────────────────────────────────────────────


class TestEmoji:
    def test_valid_emoji(self):
        ev = Emoji(default="")
        assert ev.validate("\U0001f44d") == "\U0001f44d"

    def test_none_raises(self):
        ev = Emoji(default="")
        with pytest.raises(ValidationError, match="None"):
            ev.validate(None)

    def test_empty_raises(self):
        ev = Emoji(default="")
        with pytest.raises(ValidationError, match="empty"):
            ev.validate("")

    def test_non_emoji_raises(self):
        ev = Emoji(default="")
        with pytest.raises(ValidationError, match="emoji"):
            ev.validate("abc")


# ─── EntityLike ────────────────────────────────────────────────────────


class TestEntityLike:
    def test_int_valid(self):
        ev = EntityLike(default="")
        assert ev.validate(12345) == 12345

    def test_username(self):
        ev = EntityLike(default="")
        assert ev.validate("@username") == "@username"
        assert ev.validate("username") == "username"

    def test_invite_link(self):
        ev = EntityLike(default="")
        result = ev.validate("https://t.me/+abc123")
        assert result is not None

    def test_none_raises(self):
        ev = EntityLike(default="")
        with pytest.raises(ValidationError):
            ev.validate(None)

    def test_bool_raises(self):
        ev = EntityLike(default="")
        with pytest.raises(ValidationError):
            ev.validate(True)


# ─── Choice ────────────────────────────────────────────────────────────


class TestChoice:
    def test_valid(self):
        cv = Choice(choices=["a", "b", "c"], default="a")
        assert cv.validate("a") == "a"
        assert cv.validate("c") == "c"

    def test_invalid_raises(self):
        cv = Choice(choices=["a", "b", "c"], default="a")
        with pytest.raises(ValidationError, match="one of"):
            cv.validate("d")

    def test_default_is_first(self):
        cv = Choice(choices=["x", "y"])
        assert cv.default == "x"

    def test_none_not_allowed_by_default(self):
        cv = Choice(choices=["a", "b"], default="a")
        with pytest.raises(ValidationError):
            cv.validate(None)


# ─── MultiChoice ───────────────────────────────────────────────────────


class TestMultiChoice:
    def test_valid(self):
        mcv = MultiChoice(choices=["a", "b", "c"], default=["a"])
        assert mcv.validate(["a", "b"]) == ["a", "b"]

    def test_not_a_list_raises(self):
        mcv = MultiChoice(choices=["a", "b"], default=[])
        with pytest.raises(ValidationError, match="list"):
            mcv.validate("a")

    def test_invalid_choices_raises(self):
        mcv = MultiChoice(choices=["a", "b"], default=[])
        with pytest.raises(ValidationError, match="Invalid"):
            mcv.validate(["a", "c"])


# ─── Union ─────────────────────────────────────────────────────────────


class TestUnion:
    def test_first_validator_wins(self):
        uv = Union(Integer(default=0), String(default=""))
        assert uv.validate(42) == 42
        assert uv.validate("hello") == "hello"

    def test_all_fail_raises(self):
        uv = Union(Integer(default=0))
        with pytest.raises(ValidationError, match="one of"):
            uv.validate("not_a_number")

    def test_requires_at_least_one(self):
        with pytest.raises(ValueError, match="at least one"):
            Union()

    def test_to_python(self):
        uv = Union(Integer(default=0), String(default=""))
        assert uv.to_python(42) == 42

    def test_to_storage(self):
        uv = Union(Integer(default=0), String(default=""))
        assert uv.to_storage(42) == 42


# ─── Secret ────────────────────────────────────────────────────────────


class TestSecret:
    def test_validate_passthrough(self):
        sv = Secret(default="")
        assert sv.validate("token123") == "token123"
        assert sv.validate(None) is None

    def test_secret_flag(self):
        sv = Secret(default="")
        assert getattr(sv, "secret", False) is True


# ─── ConfigValue ───────────────────────────────────────────────────────


class TestConfigValue:
    def test_default_used_when_not_set(self):
        cv = ConfigValue("key", 42, validator=Integer(default=42))
        assert cv.get_value() == 42

    def test_set_value_validates(self):
        cv = ConfigValue("key", 0, validator=Integer(default=0))
        cv.set_value(10)
        assert cv.get_value() == 10

    def test_set_value_invalid_raises(self):
        cv = ConfigValue("key", 0, validator=Integer(default=0))
        with pytest.raises(ValidationError):
            cv.set_value("not_a_number")

    def test_from_storage_none_integer_does_not_crash(self):
        """Regression: backup_chat_id=None on load must not crash."""
        cv = ConfigValue("backup_chat_id", None, validator=Integer(default=None))
        cv.from_storage(None)
        assert cv.get_value() is None

    def test_to_storage(self):
        cv = ConfigValue("key", 42, validator=Integer(default=42))
        cv.set_value(99)
        assert cv.to_storage() == 99

    def test_callable_default(self):
        cv = ConfigValue("key", lambda: 42)
        assert cv.default == 42

    def test_backward_compat_validator_as_description(self):
        """ConfigValue('key', 0, Integer()) should assign validator."""
        cv = ConfigValue("key", 0, Integer())
        assert isinstance(cv.validator, Integer)

    def test_on_change_called(self):
        """on_change is triggered via ModuleConfig.__setitem__ with old+new args."""
        calls = []
        cv = ConfigValue("key", 0, on_change=lambda old, new: calls.append((old, new)))
        cfg = ModuleConfig(cv)
        cfg["key"] = 99
        assert len(calls) == 1
        assert calls[0] == (0, 99)


# ─── ModuleConfig ──────────────────────────────────────────────────────


class TestModuleConfig:
    def test_get_item(self):
        cfg = ModuleConfig(ConfigValue("port", 8080, validator=Integer(default=8080)))
        assert cfg["port"] == 8080

    def test_set_item(self):
        cfg = ModuleConfig(ConfigValue("port", 8080, validator=Integer(default=8080)))
        cfg["port"] = 9000
        assert cfg["port"] == 9000

    def test_set_item_unknown_key_raises(self):
        cfg = ModuleConfig()
        with pytest.raises(KeyError, match="Unknown"):
            cfg["missing"] = 1

    def test_get_item_unknown_key_raises(self):
        cfg = ModuleConfig()
        with pytest.raises(KeyError, match="Unknown"):
            _ = cfg["missing"]

    def test_from_dict(self):
        cfg = ModuleConfig(
            ConfigValue("host", "localhost", validator=String(default="localhost")),
            ConfigValue("port", 8080, validator=Integer(default=8080)),
        )
        cfg.from_dict({"host": "0.0.0.0", "port": 9090})
        assert cfg["host"] == "0.0.0.0"
        assert cfg["port"] == 9090

    def test_from_dict_skips_missing_keys(self):
        cfg = ModuleConfig(
            ConfigValue(
                "host", "default_host", validator=String(default="default_host")
            ),
        )
        cfg.from_dict({})
        assert cfg["host"] == "default_host"

    def test_from_dict_none_integer_does_not_crash(self):
        """Regression: ModuleConfig loading with None for Integer field."""
        cfg = ModuleConfig(
            ConfigValue("chat_id", None, validator=Integer(default=None)),
            ConfigValue("interval", 12, validator=Integer(default=12)),
        )
        cfg.from_dict({"chat_id": None, "interval": 12})
        assert cfg["chat_id"] is None
        assert cfg["interval"] == 12

    def test_to_dict(self):
        cfg = ModuleConfig(
            ConfigValue("port", 8080, validator=Integer(default=8080)),
        )
        cfg["port"] = 7070
        d = cfg.to_dict()
        assert d["port"] == 7070
        assert d["__mcub_config__"] is True

    def test_items(self):
        cfg = ModuleConfig(
            ConfigValue("a", 1, validator=Integer(default=1)),
            ConfigValue("b", 2, validator=Integer(default=2)),
        )
        items = dict(cfg.items())
        assert items == {"a": 1, "b": 2}

    def test_keys(self):
        cfg = ModuleConfig(
            ConfigValue("x", 0, validator=Integer(default=0)),
        )
        assert list(cfg.keys()) == ["x"]

    def test_values(self):
        cfg = ModuleConfig(
            ConfigValue("x", 42, validator=Integer(default=42)),
        )
        assert list(cfg.values()) == [42]

    def test_update(self):
        cfg = ModuleConfig(
            ConfigValue("a", 1, validator=Integer(default=1)),
        )
        cfg.update({"a": 99})
        assert cfg["a"] == 99

    def test_schema(self):
        cfg = ModuleConfig(
            ConfigValue(
                "port", 8080, description="Port number", validator=Integer(default=8080)
            ),
        )
        schema = cfg.schema
        assert len(schema) == 1
        assert schema[0]["key"] == "port"
        assert schema[0]["type"] == "integer"
        assert schema[0]["default"] == 8080
        assert schema[0]["description"] == "Port number"
