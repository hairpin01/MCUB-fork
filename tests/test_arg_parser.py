"""
Tests for utils arg_parser
"""

import pytest
from utils.arg_parser import (
    ArgumentParser,
    parse_arguments,
    extract_command,
    split_args,
    parse_kwargs,
    ArgumentValidator,
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


class TestSplitArgs:
    """Test split_args function"""

    def test_basic(self):
        result = split_args("a b c")
        assert result == ["a", "b", "c"]

    def test_quoted(self):
        result = split_args('a "hello world" c')
        assert result == ["a", "hello world", "c"]


class TestParseKwargs:
    """Test parse_kwargs function"""

    def test_basic(self):
        result = parse_kwargs("--name=John --age=25")
        assert result["name"] == "John"
        assert result["age"] == 25


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
        assert ArgumentValidator.validate_count(parser, min_count=1, max_count=3) is True
        assert ArgumentValidator.validate_count(parser, min_count=1, max_count=2) is False

    def test_validate_types(self):
        parser = parse_arguments(".cmd 42 3.14 hello")
        assert ArgumentValidator.validate_types(parser, int, float, str) is True
        assert ArgumentValidator.validate_types(parser, str, int) is False

    def test_validate_kwarg_type(self):
        parser = parse_arguments(".cmd --age=25")
        assert ArgumentValidator.validate_kwarg_type(parser, "age", int) is True
        assert ArgumentValidator.validate_kwarg_type(parser, "name", int) is True  # missing is OK
