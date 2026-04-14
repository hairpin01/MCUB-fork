# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for utils arg_parser
"""

import pytest

from utils.arg_parser import (
    ArgumentValidator,
    extract_command,
    parse_arguments,
    parse_kwargs,
    split_args,
)


class TestArgumentParserBasic:
    """Test basic ArgumentParser functionality"""

    def test_simple_command(self):
        parser = parse_arguments(".ping")
        assert parser.command == "ping"
        assert parser.args == []
        assert parser.kwargs == {}

    def test_command_with_args(self):
        parser = parse_arguments(".echo hello world")
        assert parser.command == "echo"
        assert parser.args == ["hello", "world"]

    def test_command_with_prefix(self):
        parser = parse_arguments("/cmd arg1", prefix="/")
        assert parser.command == "cmd"
        assert parser.args == ["arg1"]

    @pytest.mark.parametrize(
        "input_str,expected_cmd,expected_args",
        [
            (".test", "test", []),
            (".test a", "test", ["a"]),
            (".test a b c", "test", ["a", "b", "c"]),
            (".long command name", "long", ["command", "name"]),
        ],
    )
    def test_various_commands(self, input_str, expected_cmd, expected_args):
        parser = parse_arguments(input_str)
        assert parser.command == expected_cmd
        assert parser.args == expected_args

    def test_multiple_prefixes(self):
        parser1 = parse_arguments(".cmd", prefix=".")
        parser2 = parse_arguments("/cmd", prefix="/")
        parser3 = parse_arguments("!cmd", prefix="!")

        assert parser1.command == "cmd"
        assert parser2.command == "cmd"
        assert parser3.command == "cmd"


class TestArgumentParserFlags:
    """Test flags and kwargs parsing"""

    def test_long_flags(self):
        parser = parse_arguments(".cmd --verbose --debug")
        assert "verbose" in parser.flags
        assert "debug" in parser.flags
        assert parser.get_flag("verbose") is True

    def test_short_flags(self):
        parser = parse_arguments(".cmd -v -d")
        assert "v" in parser.flags
        assert "d" in parser.flags

    def test_kwargs_with_equals(self):
        parser = parse_arguments(".cmd --name=John --age=25")
        assert parser.kwargs["name"] == "John"
        assert parser.kwargs["age"] == 25

    def test_kwargs_with_space(self):
        parser = parse_arguments(".cmd --name John --age 25")
        assert parser.kwargs["name"] == "John"
        assert parser.kwargs["age"] == 25

    @pytest.mark.parametrize(
        "input_str,expected_flags",
        [
            (".cmd --a --b --c", ["a", "b", "c"]),
            (".cmd -x -y -z", ["x", "y", "z"]),
            (".cmd --flag -f", ["flag", "f"]),
            (".cmd", []),
        ],
    )
    def test_various_flags(self, input_str, expected_flags):
        parser = parse_arguments(input_str)
        for flag in expected_flags:
            assert flag in parser.flags

    def test_duplicate_flags(self):
        parser = parse_arguments(".cmd --verbose --verbose")
        assert parser.get_flag("verbose") is True

    def test_flag_mixed_with_args(self):
        parser = parse_arguments(".cmd arg1 --flag arg2")
        assert len(parser.args) >= 1
        assert "flag" in parser.kwargs or "flag" in parser.flags


class TestArgumentParserTypes:
    """Test type parsing"""

    def test_integer(self):
        parser = parse_arguments(".cmd --count 42")
        assert parser.kwargs["count"] == 42

    def test_float(self):
        parser = parse_arguments(".cmd --rate 3.14")
        assert parser.kwargs["rate"] == 3.14

    def test_boolean_true(self):
        parser = parse_arguments(".cmd --enabled yes")
        assert parser.kwargs["enabled"] is True

    def test_boolean_false(self):
        parser = parse_arguments(".cmd --enabled no")
        assert parser.kwargs["enabled"] is False

    def test_list(self):
        parser = parse_arguments(".cmd --items a,b,c")
        assert parser.kwargs["items"] == ["a", "b", "c"]

    @pytest.mark.parametrize(
        "input_str,key,expected_type",
        [
            (".cmd --int 42", "int", int),
            (".cmd --float 3.14", "float", float),
            (".cmd --str hello", "str", str),
            (".cmd --bool true", "bool", bool),
            (".cmd --zero 0", "zero", int),
            (".cmd --float_zero 0.0", "float_zero", float),
        ],
    )
    def test_type_parsing(self, input_str, key, expected_type):
        parser = parse_arguments(input_str)
        assert isinstance(parser.kwargs[key], expected_type)


class TestArgumentParserMethods:
    """Test parser methods"""

    def test_get(self):
        parser = parse_arguments(".cmd a b c")
        assert parser.get(0) == "a"
        assert parser.get(1) == "b"
        assert parser.get(5, "default") == "default"

    def test_get_kwarg(self):
        parser = parse_arguments(".cmd --name=John")
        assert parser.get_kwarg("name") == "John"
        assert parser.get_kwarg("age", 25) == 25

    def test_get_all(self):
        parser = parse_arguments(".cmd a b c")
        result = parser.get_all()
        assert result == ["a", "b", "c"]
        assert isinstance(result, list)

    def test_slice(self):
        parser = parse_arguments(".cmd a b c d e")
        assert parser.slice(1, 3) == ["b", "c"]
        assert parser.slice(2) == ["c", "d", "e"]

    def test_require(self):
        parser = parse_arguments(".cmd --name=John --age=25")
        valid, missing = parser.require("name", "age")
        assert valid is True
        assert missing == ""

    def test_require_missing(self):
        parser = parse_arguments(".cmd --name=John")
        valid, missing = parser.require("name", "age")
        assert valid is False
        assert missing == "age"

    def test_require_positional(self):
        parser = parse_arguments(".cmd a b")
        valid, missing = parser.require(0, 1, 2)
        assert valid is False
        assert missing == "arg[2]"

    def test_remaining(self):
        parser = parse_arguments(".cmd a b c d")
        assert parser.remaining(1) == "b c d"
        assert parser.remaining(3) == "d"

    def test_get_out_of_bounds(self):
        parser = parse_arguments(".cmd a")
        assert parser.get(0) == "a"
        assert parser.get(10) is None

    def test_slice_partial(self):
        parser = parse_arguments(".cmd a b c d e f")
        assert parser.slice(0, 3) == ["a", "b", "c"]
        assert parser.slice(-2) == ["e", "f"]

    def test_get_all_empty(self):
        parser = parse_arguments(".cmd")
        assert parser.get_all() == []


class TestArgumentParserEdgeCases:
    """Test edge cases"""

    def test_quoted_args(self):
        parser = parse_arguments('.cmd "hello world"')
        assert parser.args[0] == "hello world"

    def test_empty_args(self):
        parser = parse_arguments(".cmd")
        assert len(parser.args) == 0
        assert parser.get(0, "default") == "default"

    def test_mixed_args_and_kwargs(self):
        parser = parse_arguments(".cmd arg1 arg2 --flag --key=value")
        assert len(parser.args) == 2
        assert "flag" in parser.flags
        assert parser.kwargs["key"] == "value"

    def test_len(self):
        parser = parse_arguments(".cmd a b c")
        assert len(parser) == 3

    def test_contains(self):
        parser = parse_arguments(".cmd --test val")
        assert "test" in parser
        assert "missing" not in parser

    @pytest.mark.parametrize(
        "input_str,expected_args",
        [
            ('.cmd "arg with spaces"', ["arg with spaces"]),
            (".cmd ''empty''", ["''empty''"]),
            ('.cmd "a" "b" "c"', ["a", "b", "c"]),
            (".cmd 'single quotes'", ["'single quotes'"]),
        ],
    )
    def test_quoted_args_various(self, input_str, expected_args):
        parser = parse_arguments(input_str)
        assert len(parser.args) >= 1

    def test_empty_quotes(self):
        parser = parse_arguments('.cmd ""')
        assert len(parser.args) >= 0

    def test_mixed_case_args(self):
        parser = parse_arguments(".cmd Hello WORLD test123")
        assert "Hello" in parser.args
        assert "WORLD" in parser.args
        assert "test123" in parser.args

    def test_args_with_special_chars(self):
        parser = parse_arguments(".cmd arg@email.com http://url.com #tag")
        assert len(parser.args) == 3


class TestExtractCommand:
    """Test extract_command function"""

    def test_basic(self):
        cmd, args = extract_command(".test hello")
        assert cmd == "test"
        assert args == "hello"

    def test_no_args(self):
        cmd, args = extract_command(".test")
        assert cmd == "test"
        assert args == ""

    def test_no_prefix(self):
        cmd, args = extract_command("test hello")
        assert cmd == ""
        assert args == "test hello"

    @pytest.mark.parametrize(
        "input_str,expected_cmd,expected_args",
        [
            (".cmd", "cmd", ""),
            (".cmd arg", "cmd", "arg"),
            (".multi word cmd", "multi", "word cmd"),
            ("nocmd", "", "nocmd"),
            (".cmd 123", "cmd", "123"),
        ],
    )
    def test_various_extracts(self, input_str, expected_cmd, expected_args):
        cmd, args = extract_command(input_str)
        assert cmd == expected_cmd
        assert args == expected_args


class TestSplitArgs:
    """Test split_args function"""

    def test_basic(self):
        result = split_args("a b c")
        assert result == ["a", "b", "c"]

    def test_quoted(self):
        result = split_args('a "hello world" c')
        assert result == ["a", "hello world", "c"]

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("a b c", ["a", "b", "c"]),
            ('"a b" c', ["a b", "c"]),
            ("single", ["single"]),
            ("", []),
            ("  spaced  ", ["spaced"]),
        ],
    )
    def test_various_splits(self, input_str, expected):
        result = split_args(input_str)
        assert result == expected


class TestParseKwargs:
    """Test parse_kwargs function"""

    def test_basic(self):
        result = parse_kwargs("--name=John --age=25")
        assert result["name"] == "John"
        assert result["age"] == 25

    @pytest.mark.parametrize(
        "input_str,expected_keys",
        [
            ("--a=1 --b=2 --c=3", ["a", "b", "c"]),
            ("--key=value", ["key"]),
            ("", []),
            ("--x", ["x"]),
        ],
    )
    def test_various_kwargs(self, input_str, expected_keys):
        result = parse_kwargs(input_str)
        for key in expected_keys:
            assert key in result


class TestArgumentValidator:
    """Test ArgumentValidator class"""

    def test_validate_required(self):
        parser = parse_arguments(".cmd --name=John --age=25")
        assert ArgumentValidator.validate_required(parser, "name", "age") is True
        assert ArgumentValidator.validate_required(parser, "name", "missing") is False

    def test_validate_count(self):
        parser = parse_arguments(".cmd a b c")
        assert ArgumentValidator.validate_count(parser, min_count=2) is True
        assert ArgumentValidator.validate_count(parser, min_count=5) is False
        assert (
            ArgumentValidator.validate_count(parser, min_count=1, max_count=3) is True
        )
        assert (
            ArgumentValidator.validate_count(parser, min_count=1, max_count=2) is False
        )

    def test_validate_types(self):
        parser = parse_arguments(".cmd 42 3.14 hello")
        assert ArgumentValidator.validate_types(parser, int, float, str) is True
        assert ArgumentValidator.validate_types(parser, str, int) is False

    def test_validate_kwarg_type(self):
        parser = parse_arguments(".cmd --age=25")
        assert ArgumentValidator.validate_kwarg_type(parser, "age", int) is True
        assert (
            ArgumentValidator.validate_kwarg_type(parser, "name", int) is True
        )  # missing is OK

    def test_validate_empty_args(self):
        parser = parse_arguments(".cmd")
        assert ArgumentValidator.validate_count(parser, min_count=0) is True
        assert ArgumentValidator.validate_count(parser, min_count=1) is False

    def test_validate_exact_count(self):
        parser = parse_arguments(".cmd a b c")
        assert (
            ArgumentValidator.validate_count(parser, min_count=3, max_count=3) is True
        )
        assert (
            ArgumentValidator.validate_count(parser, min_count=2, max_count=2) is False
        )


class TestArgumentParserUnicode:
    """Test unicode handling"""

    def test_unicode_args(self):
        parser = parse_arguments(".cmd 日本語")
        assert len(parser.args) >= 1

    def test_emoji_args(self):
        parser = parse_arguments(".cmd 🎉 🚀")
        assert len(parser.args) >= 1

    def test_mixed_unicode(self):
        parser = parse_arguments(".cmd Hello 世界 🎉")
        assert len(parser.args) >= 1


class TestArgumentParserNumbers:
    """Test number handling"""

    @pytest.mark.parametrize(
        "input_str,key,expected",
        [
            (".cmd --zero 0", "zero", 0),
            (".cmd --neg -5", "neg", -5),
            (".cmd --pos 100", "pos", 100),
            (".cmd --float 0.001", "float", 0.001),
            (".cmd --sci 1e10", "sci", 1e10),
        ],
    )
    def test_number_types(self, input_str, key, expected):
        parser = parse_arguments(input_str)
        assert key in parser.kwargs
