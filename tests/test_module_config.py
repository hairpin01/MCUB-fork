# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for core/lib/loader/module_config - validators and config containers.
"""

import asyncio

import pytest

from core.lib.loader.module_config import (
    Answer,
    Boolean,
    Buttons,
    Callback,
    Choice,
    ConfigValue,
    DictType,
    Divider,
    Emoji,
    EntityLike,
    Float,
    Group,
    Integer,
    Link,
    List,
    ModuleConfig,
    MultiChoice,
    NoneType,
    Notice,
    Placeholders,
    RegExp,
    Row,
    Secret,
    Status,
    String,
    TelegramID,
    Union,
    Url,
    ValidationError,
    Validator,
)


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


#     String


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


#     Placeholders


class TestPlaceholders:
    def test_inherits_string(self):
        pv = Placeholders(default="")
        assert pv.validate("test") == "test"
        assert pv.validate(None) is None

    def test_default_scope(self):
        pv = Placeholders(default="")
        assert pv.placeholder_scope == "any"


#     Link / URL


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


#     RegExp


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


#     TelegramID


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

    def test_zero_rejected_by_default(self):
        tv = TelegramID(default=None)
        with pytest.raises(ValidationError, match="zero"):
            tv.validate(0)

    def test_allow_zero_accepts_zero(self):
        tv = TelegramID(default=0, allow_zero=True)
        assert tv.validate(0) == 0

    def test_default_zero_keeps_zero_sentinel_compatible(self):
        tv = TelegramID(default=0)
        assert tv.validate(0) == 0

    def test_hikka_compat_allow_zero_accepts_zero(self):
        from core.lib.loader.hikka_compat.validators import (
            TelegramID as HikkaTelegramID,
        )

        assert HikkaTelegramID(allow_zero=True).validate(0) == 0
        with pytest.raises(Exception, match="zero"):
            HikkaTelegramID().validate(0)


#     NoneType


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


#     Emoji


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


#     EntityLike


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


#     Choice


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


#     MultiChoice


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


#     Union


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


#     List


class TestList:
    def test_item_type_can_be_python_type(self):
        lv = List(item_type=str)
        assert lv.validate(["a", "b"]) == ["a", "b"]
        with pytest.raises(ValidationError, match="List items"):
            lv.validate(["a", 1])

    def test_item_type_can_be_validator(self):
        lv = List(item_type=TelegramID(allow_zero=True))
        assert lv.validate([0, "123"]) == [0, 123]


#     DictType


class TestDictType:
    def test_key_value_types_can_be_python_types(self):
        dv = DictType(key_type=str, value_type=int)
        assert dv.validate({"a": 1}) == {"a": 1}
        with pytest.raises(ValidationError, match="Dictionary values"):
            dv.validate({"a": "1"})

    def test_key_value_types_can_be_validators(self):
        dv = DictType(key_type=String(), value_type=Union(Integer(), Float(), String()))
        assert dv.validate({"a": "text", "b": 2, "c": 3.5}) == {
            "a": "text",
            "b": 2,
            "c": 3.5,
        }


#     Secret


class TestSecret:
    def test_validate_passthrough(self):
        sv = Secret(default="")
        assert sv.validate("token123") == "token123"
        assert sv.validate(None) is None

    def test_secret_flag(self):
        sv = Secret(default="")
        assert getattr(sv, "secret", False) is True


#     ConfigValue


class TestConfigValue:
    def test_default_used_when_not_set(self):
        cv = ConfigValue("key", 42, validator=Integer())
        assert cv.get_value() == 42

    def test_set_value_validates(self):
        cv = ConfigValue("key", 0, validator=Integer())
        cv.set_value(10)
        assert cv.get_value() == 10

    def test_set_value_invalid_raises(self):
        cv = ConfigValue("key", 0, validator=Integer())
        with pytest.raises(ValidationError):
            cv.set_value("not_a_number")

    def test_from_storage_none_integer_does_not_crash(self):
        """Regression: backup_chat_id=None on load must not crash."""
        cv = ConfigValue("backup_chat_id", None, validator=Integer())
        cv.from_storage(None)
        assert cv.get_value() is None

    def test_to_storage(self):
        cv = ConfigValue("key", 42, validator=Integer())
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

    def test_owner_aware_on_change_called(self):
        """on_change can receive bound module owner as (module, old, new)."""
        owner = object()
        calls = []
        cfg = ModuleConfig(
            ConfigValue(
                "key",
                0,
                on_change=lambda module, old, new: calls.append((module, old, new)),
            )
        ).bind_owner(owner)

        cfg["key"] = 7

        assert calls == [(owner, 0, 7)]

    @pytest.mark.asyncio
    async def test_async_on_change_called(self):
        """Async on_change callbacks are scheduled from ModuleConfig.__setitem__."""
        calls = []

        async def on_change(old, new):
            await asyncio.sleep(0)
            calls.append((old, new))

        cfg = ModuleConfig(ConfigValue("key", 0, on_change=on_change))
        cfg["key"] = 42

        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert calls == [(0, 42)]

    @pytest.mark.asyncio
    async def test_async_owner_aware_on_change_called(self):
        """Async owner-aware on_change callbacks are scheduled correctly."""
        owner = object()
        calls = []

        async def on_change(module, old, new):
            await asyncio.sleep(0)
            calls.append((module, old, new))

        cfg = ModuleConfig(ConfigValue("key", 0, on_change=on_change)).bind_owner(owner)
        cfg["key"] = 42

        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert calls == [(owner, 0, 42)]

    def test_from_dict_does_not_call_on_change(self):
        """Hydrating persisted config must not fire user-change hooks."""
        calls = []
        cfg = ModuleConfig(
            ConfigValue("key", 0, on_change=lambda old, new: calls.append((old, new)))
        )

        cfg.from_dict({"key": 99})

        assert cfg["key"] == 99
        assert calls == []

    def test_global_on_change_called_for_any_key(self):
        calls = []
        cfg = ModuleConfig(
            ConfigValue("first", 1),
            ConfigValue("second", 2),
            on_change=lambda key, old, new: calls.append((key, old, new)),
        )

        cfg["second"] = 20

        assert calls == [("second", 2, 20)]

    def test_owner_aware_global_on_change_called(self):
        owner = object()
        calls = []
        cfg = ModuleConfig(
            ConfigValue("key", 0),
            on_change=lambda module, key, old, new: calls.append(
                (module, key, old, new)
            ),
        ).bind_owner(owner)

        cfg["key"] = 5

        assert calls == [(owner, "key", 0, 5)]

    def test_from_dict_does_not_call_global_on_change(self):
        calls = []
        cfg = ModuleConfig(
            ConfigValue("key", 0),
            on_change=lambda key, old, new: calls.append((key, old, new)),
        )

        cfg.from_dict({"key": 10})

        assert cfg["key"] == 10
        assert calls == []

    def test_set_on_change_global_and_per_key(self):
        global_calls = []
        key_calls = []
        cfg = ModuleConfig(ConfigValue("key", 0), ConfigValue("other", 10))

        cfg.set_on_change(lambda key, old, new: global_calls.append((key, old, new)))
        cfg.set_on_change("key", lambda old, new: key_calls.append((old, new)))

        cfg["key"] = 1
        cfg["other"] = 11

        assert key_calls == [(0, 1)]
        assert global_calls == [("key", 0, 1), ("other", 10, 11)]

    def test_reset_to_defaults_all_selected_and_silent(self):
        calls = []
        cfg = ModuleConfig(
            ConfigValue(
                "first", 1, on_change=lambda old, new: calls.append((old, new))
            ),
            ConfigValue("second", "a"),
        )

        cfg["first"] = 5
        cfg["second"] = "b"
        cfg.reset_to_defaults("second")

        assert cfg["first"] == 5
        assert cfg["second"] == "a"

        cfg.reset_to_defaults(trigger_on_change=False)

        assert cfg["first"] == 1
        assert cfg["second"] == "a"
        assert calls == [(1, 5)]

    @pytest.mark.asyncio
    async def test_custom_handler_receives_owner_event_data(self):
        owner = object()
        event = object()
        data = {"standard_config": b"module_cfg_page_nav_x"}
        calls = []
        cfg = ModuleConfig(
            ConfigValue("key", 1),
            custom_handler=lambda module, event, data: calls.append(
                (module, event, data)
            )
            or ("text", [["button"]]),
        ).bind_owner(owner)

        result = await cfg.trigger_custom_handler(owner, event, data)

        assert result == ("text", [["button"]])
        assert calls == [(owner, event, data)]

    @pytest.mark.asyncio
    async def test_set_custom_handler(self):
        calls = []
        cfg = ModuleConfig(ConfigValue("key", 1))

        def handle_event(event):
            calls.append(event)
            return "ok"

        cfg.set_custom_handler(handle_event)
        result = await cfg.trigger_custom_handler(None, "event")

        assert result == "ok"
        assert calls == ["event"]

    def test_version_is_saved_and_migrate_can_rename_keys(self):
        def migrate(data, old_version):
            assert old_version == 1
            migrated = dict(data)
            migrated["new_key"] = migrated.pop("old_key")
            return migrated

        cfg = ModuleConfig(
            ConfigValue("new_key", "default", validator=String()),
            version=2,
            migrate=migrate,
        )

        cfg.from_dict(
            {
                "old_key": "persisted",
                "__mcub_config__": True,
                "__mcub_config_version__": 1,
            }
        )

        assert cfg["new_key"] == "persisted"
        assert cfg.to_dict() == {
            "new_key": "persisted",
            "__mcub_config__": True,
            "__mcub_config_version__": 2,
        }


#     ModuleConfig


class TestModuleConfig:
    def test_get_item(self):
        cfg = ModuleConfig(ConfigValue("port", 8080, validator=Integer()))
        assert cfg["port"] == 8080

    def test_config_value_owner_aware_description(self):
        class Owner:
            def strings(self, key):
                return {"desc_none": "None description"}[key]

        value = ConfigValue(
            "key",
            None,
            description=lambda module: module.strings("desc_none"),
            validator=NoneType(),
        )

        assert value.description == ""
        assert value.get_description(Owner()) == "None description"

    def test_set_item(self):
        cfg = ModuleConfig(ConfigValue("port", 8080, validator=Integer()))
        cfg["port"] = 9000
        assert cfg["port"] == 9000

    def test_buttons_are_ui_only_items(self):
        button = object()
        buttons_item = Buttons(
            "Actions",
            "Module actions",
            "Open actions",
            [[button]],
            key="actions",
        )
        cfg = ModuleConfig(
            ConfigValue("enabled", True, validator=Boolean()),
            buttons_item,
        )

        assert cfg.items() == [("enabled", True)]
        assert cfg.keys() == ["enabled"]
        assert cfg.to_dict() == {"enabled": True, "__mcub_config__": True}
        assert buttons_item.ui_only is True
        assert buttons_item.ui_type == "buttons"
        assert cfg.get_button("buttons_actions") is buttons_item
        assert cfg.button_keys() == ["buttons_actions"]
        assert cfg.ui_items() == [("enabled", True), ("buttons_actions", buttons_item)]

    def test_custom_ui_only_item_is_not_config_value(self):
        class CustomUiItem:
            ui_only = True
            ui_type = "custom"
            key = None

        item = CustomUiItem()
        cfg = ModuleConfig(ConfigValue("enabled", True, validator=Boolean()), item)

        assert cfg.items() == [("enabled", True)]
        assert cfg.keys() == ["enabled"]
        assert cfg.to_dict() == {"enabled": True, "__mcub_config__": True}
        assert cfg.ui_items() == [("enabled", True), ("custom_1", item)]
        assert item.key == "custom_1"

    def test_buttons_schema_entry(self):
        cfg = ModuleConfig(
            Buttons("Actions", "Module actions", "Open actions", [], key="actions")
        )

        assert cfg.schema == [
            {
                "key": "buttons_actions",
                "type": "buttons",
                "default": None,
                "description": "Module actions",
                "hidden": False,
                "button_text": "Open actions",
                "title": "Actions",
            }
        ]

    def test_buttons_only_config_keeps_ui_items_without_stored_keys(self):
        buttons_item = Buttons("Actions", "Module actions", "Open actions", [])
        cfg = ModuleConfig(buttons_item)

        assert cfg.to_dict() == {"__mcub_config__": True}
        assert cfg.items() == []
        assert cfg.ui_items() == [("buttons_0", buttons_item)]

    def test_row_is_layout_only_item(self):
        row = Row()
        cfg = ModuleConfig(
            ConfigValue("first", 1, validator=Integer()),
            row,
            ConfigValue("second", 2, validator=Integer()),
        )

        assert cfg.items() == [("first", 1), ("second", 2)]
        assert cfg.keys() == ["first", "second"]
        assert row.ui_only is True
        assert row.ui_type == "row"
        assert cfg.row_keys() == ["row_1"]
        assert cfg.to_dict() == {"first": 1, "second": 2, "__mcub_config__": True}
        assert cfg.ui_items() == [("first", 1), ("row_1", row), ("second", 2)]
        assert [entry["key"] for entry in cfg.schema] == ["first", "second"]

    def test_answer_is_ui_only_item(self):
        answer = Answer("About", "API key from Gemini AI", alert=False, key="about")
        cfg = ModuleConfig(
            ConfigValue("enabled", True, validator=Boolean()),
            answer,
        )

        assert cfg.items() == [("enabled", True)]
        assert cfg.keys() == ["enabled"]
        assert cfg.to_dict() == {"enabled": True, "__mcub_config__": True}
        assert answer.ui_only is True
        assert answer.ui_type == "answer"
        assert answer.button_text == "About"
        assert answer.text == "API key from Gemini AI"
        assert answer.alert is False
        assert cfg.get_ui_item("answer_about") is answer
        assert cfg.ui_items() == [("enabled", True), ("answer_about", answer)]
        assert [entry["key"] for entry in cfg.schema] == ["enabled"]

    def test_config_value_show_if_accepts_owner(self):
        class Owner:
            show_secret = True

        item = ConfigValue(
            "log_chat",
            "",
            validator=String(),
            show_if=lambda module: module.show_secret,
        )

        assert item.is_visible(Owner()) is True
        owner = Owner()
        owner.show_secret = False
        assert item.is_visible(owner) is False

    def test_group_show_if_accepts_owner(self):
        class Owner:
            enabled = False

        group = Group(
            "Advanced",
            [ConfigValue("debug", False, validator=Boolean())],
            show_if=lambda module: module.enabled,
        )

        assert group.is_visible(Owner()) is False

        owner = Owner()
        owner.enabled = True
        assert group.is_visible(owner) is True

    @pytest.mark.asyncio
    async def test_group_on_click_owner_event_callback(self):
        owner = object()
        event = object()
        calls = []
        group = Group(
            "Advanced",
            [],
            on_click=lambda module, event: calls.append((module, event)),
        )

        await group.trigger_on_click(owner, event)

        assert calls == [(owner, event)]

    def test_new_ui_items_are_ui_only_items(self):
        divider = Divider("    ", key="line")
        url = Url("Docs", "https://example.com", key="docs")
        callback = Callback("Refresh", key="refresh")
        status = Status("Runtime", "ready", key="runtime")
        notice = Notice("Only visible when rules match", key="rules")
        cfg = ModuleConfig(
            ConfigValue("enabled", True, validator=Boolean()),
            divider,
            url,
            callback,
            status,
            notice,
        )

        assert cfg.items() == [("enabled", True)]
        assert cfg.keys() == ["enabled"]
        assert cfg.to_dict() == {"enabled": True, "__mcub_config__": True}
        assert cfg.get_ui_item("divider_line") is divider
        assert cfg.get_ui_item("url_docs") is url
        assert cfg.get_ui_item("callback_refresh") is callback
        assert cfg.get_ui_item("status_runtime") is status
        assert cfg.get_ui_item("notice_rules") is notice
        assert cfg.ui_items() == [
            ("enabled", True),
            ("divider_line", divider),
            ("url_docs", url),
            ("callback_refresh", callback),
            ("status_runtime", status),
            ("notice_rules", notice),
        ]
        assert [entry["key"] for entry in cfg.schema] == ["enabled"]

    def test_new_ui_items_accept_owner_aware_values(self):
        class Owner:
            show_notice = True
            status_text = "runtime ok"

        owner = Owner()
        divider = Divider(lambda module: module.status_text)
        url = Url(
            lambda module: f"Docs: {module.status_text}",
            lambda module: "https://example.com/docs",
        )
        status = Status("Runtime", lambda module: module.status_text)
        notice = Notice(
            lambda module: module.status_text, lambda module: module.show_notice
        )

        assert divider.get_button_text(owner) == "runtime ok"
        assert url.get_button_text(owner) == "Docs: runtime ok"
        assert url.get_url(owner) == "https://example.com/docs"
        assert status.get_value(owner) == "runtime ok"
        assert notice.get_text(owner) == "runtime ok"
        assert notice.is_visible(owner) is True

        owner.show_notice = False
        assert notice.is_visible(owner) is False

    def test_owner_aware_ui_values_do_not_crash_without_owner(self):
        divider = Divider(lambda module: module.status_text)
        buttons = Buttons(
            lambda module: module.status_text,
            lambda module: module.status_text,
            lambda module: module.status_text,
            [],
        )
        notice = Notice(lambda module: module.status_text)
        status = Status(
            lambda module: module.status_text, lambda module: module.status_text
        )
        url = Url(lambda module: module.status_text, lambda module: module.docs_url)
        answer = Answer(
            lambda module: module.status_text, lambda module: module.status_text
        )
        group = Group(
            lambda module: module.status_text,
            [],
            lambda module: module.status_text,
            button_text=lambda module: module.status_text,
        )

        assert divider.button_text == "────────"
        assert buttons.title == ""
        assert buttons.description == ""
        assert buttons.button_text == "Buttons"
        assert notice.button_text == "Notice"
        assert notice.text == ""
        assert status.button_text == "Status"
        assert status.value == ""
        assert url.button_text == "Link"
        assert url.url == ""
        assert answer.button_text == "Info"
        assert answer.text == ""
        assert group.title == ""
        assert group.description == ""
        assert group.button_text == "Group"

    @pytest.mark.asyncio
    async def test_callback_ui_item_triggers_owner_event_callback(self):
        owner = object()
        event = object()
        calls = []
        item = Callback("Refresh", lambda module, event: calls.append((module, event)))

        await item.trigger_on_click(owner, event)

        assert calls == [(owner, event)]

    def test_group_registers_nested_config_and_ui_items(self):
        row = Row()
        answer = Answer("About", "api key from gemini ai")
        group = Group(
            "🗂 API",
            [
                ConfigValue("api_key", "", validator=Secret()),
                row,
                answer,
            ],
            description="Gemini API settings",
            key="api",
        )
        cfg = ModuleConfig(
            ConfigValue("enabled", True, validator=Boolean()),
            group,
            ConfigValue("mode", "chat", validator=String()),
        )

        assert cfg.keys() == ["enabled", "api_key", "mode"]
        assert cfg.items() == [("enabled", True), ("api_key", ""), ("mode", "chat")]
        assert cfg.to_dict() == {
            "enabled": True,
            "api_key": "",
            "mode": "chat",
            "__mcub_config__": True,
        }
        assert group.ui_only is True
        assert group.ui_type == "group"
        assert group.title == "🗂 API"
        assert group.description == "Gemini API settings"
        assert cfg.get_ui_item("group_api") is group
        assert cfg.ui_items() == [
            ("enabled", True),
            ("group_api", group),
            ("mode", "chat"),
        ]
        assert cfg.group_items("group_api") == [
            ("api_key", ""),
            ("row_1_1", row),
            ("answer_1_2", answer),
        ]
        assert [entry["key"] for entry in cfg.schema] == [
            "enabled",
            "api_key",
            "mode",
        ]

    def test_from_dict_to_dict_prunes_stale_keys(self):
        cfg = ModuleConfig(ConfigValue("active", True, validator=Boolean()))

        cfg.from_dict(
            {"active": False, "removed_key": "stale", "__mcub_config__": True}
        )

        assert cfg.to_dict() == {"active": False, "__mcub_config__": True}

    def test_buttons_accept_callable_content(self):
        cfg = ModuleConfig(
            Buttons(
                lambda: "Dynamic title",
                lambda: "Dynamic description",
                lambda: "Dynamic button",
                lambda: [["button"]],
            )
        )
        item = cfg.get_button("buttons_0")

        assert item is not None
        assert item.title == "Dynamic title"
        assert item.description == "Dynamic description"
        assert item.button_text == "Dynamic button"
        assert item.get_buttons() == [["button"]]

    def test_buttons_callable_can_accept_owner(self):
        owner = object()
        cfg = ModuleConfig(Buttons("Actions", buttons=lambda module: [[module]]))
        item = cfg.get_button("buttons_0")

        assert item is not None
        assert item.get_buttons(owner) == [[owner]]

    @pytest.mark.asyncio
    async def test_buttons_on_click_owner_event_callback(self):
        owner = object()
        event = object()
        calls = []
        item = Buttons(
            "Actions",
            on_click=lambda module, event: calls.append((module, event)),
        )

        await item.trigger_on_click(owner, event)

        assert calls == [(owner, event)]

    @pytest.mark.asyncio
    async def test_buttons_on_click_event_only_callback(self):
        event = object()
        calls = []

        def handle_event(event):
            calls.append(event)

        item = Buttons("Actions", on_click=handle_event)

        await item.trigger_on_click(None, event)

        assert calls == [event]

    @pytest.mark.asyncio
    async def test_buttons_on_click_async_callback(self):
        owner = object()
        event = object()
        calls = []

        async def on_click(module, event):
            await asyncio.sleep(0)
            calls.append((module, event))

        item = Buttons("Actions", on_click=on_click)

        await item.trigger_on_click(owner, event)

        assert calls == [(owner, event)]

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
            ConfigValue("host", "localhost", validator=String()),
            ConfigValue("port", 8080, validator=Integer()),
        )
        cfg.from_dict({"host": "0.0.0.0", "port": 9090})
        assert cfg["host"] == "0.0.0.0"
        assert cfg["port"] == 9090

    def test_from_dict_skips_missing_keys(self):
        cfg = ModuleConfig(
            ConfigValue("host", "default_host", validator=String()),
        )
        cfg.from_dict({})
        assert cfg["host"] == "default_host"

    def test_from_dict_none_integer_does_not_crash(self):
        """Regression: ModuleConfig loading with None for Integer field."""
        cfg = ModuleConfig(
            ConfigValue("chat_id", None, validator=Integer()),
            ConfigValue("interval", 12, validator=Integer()),
        )
        cfg.from_dict({"chat_id": None, "interval": 12})
        assert cfg["chat_id"] is None
        assert cfg["interval"] == 12

    def test_to_dict(self):
        cfg = ModuleConfig(
            ConfigValue("port", 8080, validator=Integer()),
        )
        cfg["port"] = 7070
        d = cfg.to_dict()
        assert d["port"] == 7070
        assert d["__mcub_config__"] is True

    def test_items(self):
        cfg = ModuleConfig(
            ConfigValue("a", 1, validator=Integer()),
            ConfigValue("b", 2, validator=Integer()),
        )
        items = dict(cfg.items())
        assert items == {"a": 1, "b": 2}

    def test_keys(self):
        cfg = ModuleConfig(
            ConfigValue("x", 0, validator=Integer()),
        )
        assert list(cfg.keys()) == ["x"]

    def test_values(self):
        cfg = ModuleConfig(
            ConfigValue("x", 42, validator=Integer()),
        )
        assert list(cfg.values()) == [42]

    def test_update(self):
        cfg = ModuleConfig(
            ConfigValue("a", 1, validator=Integer()),
        )
        cfg.update({"a": 99})
        assert cfg["a"] == 99

    def test_schema(self):
        cfg = ModuleConfig(
            ConfigValue("port", 8080, description="Port number", validator=Integer()),
        )
        schema = cfg.schema
        assert len(schema) == 1
        assert schema[0]["key"] == "port"
        assert schema[0]["type"] == "integer"
        assert schema[0]["default"] == 8080
        assert schema[0]["description"] == "Port number"
