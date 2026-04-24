# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.1.0
# description: MCUB command argument parser
import re
import shlex
from dataclasses import dataclass
from typing import Any


class ArgumentParser:
    """Argument parser for MCUB commands"""

    def __init__(self, text: str, prefix: str = "."):
        """
        Initialize argument parser

        Args:
            text: Full message text (with command and arguments)
            prefix: Command prefix (default '.')
        """
        self.full_text = text.strip()
        self.prefix = prefix
        self.command = ""
        self.args = []
        self.kwargs = {}
        self.flags = set()
        self.raw_args = ""

        self._parse()

    def _parse(self):
        """Parse text into command and arguments"""
        if not self.full_text.startswith(self.prefix):
            raise ValueError(f"Text doesn't start with prefix '{self.prefix}'")

        text_without_prefix = self.full_text[len(self.prefix) :].strip()

        if not text_without_prefix:
            return

        parts = text_without_prefix.split(None, 1)
        self.command = parts[0]

        if len(parts) > 1:
            self.raw_args = parts[1]
            self._parse_arguments(parts[1])

    def _parse_arguments(self, args_string: str):
        """Parse argument string"""
        try:
            tokens = shlex.split(args_string)
        except ValueError:
            tokens = self._simple_split(args_string)

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.startswith("--"):
                flag_name = token[2:]
                if "=" in flag_name:
                    key, value = flag_name.split("=", 1)
                    self.kwargs[key] = self._parse_value(value)
                else:
                    if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                        self.kwargs[flag_name] = self._parse_value(tokens[i + 1])
                        i += 1
                    else:
                        self.flags.add(flag_name)
                        self.kwargs[flag_name] = True

            elif token.startswith("-"):
                if len(token) > 1:
                    flag_chars = token[1:]

                    if len(flag_chars) > 1:
                        for char in flag_chars:
                            self.flags.add(char)
                            self.kwargs[char] = True
                    else:
                        if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                            self.kwargs[flag_chars] = self._parse_value(tokens[i + 1])
                            i += 1
                        else:
                            self.flags.add(flag_chars)
                            self.kwargs[flag_chars] = True

            else:
                self.args.append(self._parse_value(token))

            i += 1

    def _simple_split(self, args_string: str) -> list[str]:
        """Simple string splitting into tokens"""
        tokens = []
        current = []
        in_quotes = False
        quote_char = None

        for char in args_string:
            if char in ('"', "'") and (not in_quotes or char == quote_char):
                if in_quotes:
                    in_quotes = False
                    if current:
                        tokens.append("".join(current))
                        current = []
                else:
                    in_quotes = True
                    quote_char = char
            elif char == " " and not in_quotes:
                if current:
                    tokens.append("".join(current))
                    current = []
            else:
                current.append(char)

        if current:
            tokens.append("".join(current))

        return tokens

    def _parse_value(self, value: str) -> Any:
        """Parse value, trying to determine its type"""
        if not value:
            return ""

        if value.isdigit():
            return int(value)

        try:
            return float(value)
        except ValueError:
            pass

        lower_value = value.lower()
        if lower_value in ("true", "yes", "on", "1"):
            return True
        elif lower_value in ("false", "no", "off", "0"):
            return False

        if "," in value:
            parts = [self._parse_value(part.strip()) for part in value.split(",")]
            return parts

        return value

    def get(self, index: int, default: Any = None) -> Any:
        """Get positional argument by index"""
        try:
            return self.args[index]
        except IndexError:
            return default

    def get_flag(self, flag: str) -> bool:
        """Check if flag exists"""
        return flag in self.flags or flag in self.kwargs

    def get_kwarg(self, key: str, default: Any = None) -> Any:
        """Get named argument value"""
        return self.kwargs.get(key, default)

    def has(self, key: str) -> bool:
        """Check if argument exists (positional or named)"""
        return key in self.kwargs

    def join_args(self, start: int = 0, end: int | None = None) -> str:
        """Join positional arguments into string"""
        args = self.args[start:end]
        return " ".join(str(arg) for arg in args)

    def __repr__(self) -> str:
        return (
            f"ArgumentParser(command='{self.command}', "
            f"args={self.args}, kwargs={self.kwargs}, flags={self.flags})"
        )

    def __len__(self) -> int:
        return len(self.args)

    def __contains__(self, item: str) -> bool:
        return item in self.flags or item in self.kwargs

    def get_all(self) -> list[Any]:
        """Get all positional arguments as a list."""
        return self.args.copy()

    def slice(self, start: int = 0, end: int | None = None) -> list[Any]:
        """Get a slice of positional arguments."""
        return self.args[start:end]

    def require(self, *names: str) -> tuple[bool, str]:
        """
        Validate that required arguments are present.

        Args:
            *names: Required argument names (positional indices or kwarg keys).

        Returns:
            (is_valid, missing_name)
        """
        for name in names:
            if isinstance(name, int):
                if name >= len(self.args):
                    return False, f"arg[{name}]"
            else:
                if name not in self.kwargs:
                    return False, name
        return True, ""

    def remaining(self, start: int = 0) -> str:
        """Get remaining raw args as string from position."""
        tokens = self.raw_args.split()
        if start >= len(tokens):
            return ""
        return " ".join(tokens[start:])


def parse_arguments(text: str, prefix: str = ".") -> ArgumentParser:
    """Create argument parser from message text"""
    return ArgumentParser(text, prefix)


def extract_command(text: str, prefix: str = ".") -> tuple[str, str]:
    """Extract command and arguments from text"""
    if not text.startswith(prefix):
        return "", text

    text_without_prefix = text[len(prefix) :].strip()
    if not text_without_prefix:
        return "", ""

    parts = text_without_prefix.split(None, 1)
    command = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    return command, args


def split_args(args_string: str) -> list[str]:
    """Split argument string into tokens considering quotes"""
    try:
        return shlex.split(args_string)
    except ValueError:
        parser = ArgumentParser(f".cmd {args_string}", ".")
        return parser.args


def parse_kwargs(args_string: str) -> dict[str, Any]:
    """Parse argument string into key-value dictionary"""
    parser = ArgumentParser(f".cmd {args_string}", ".")
    return parser.kwargs


class ArgumentValidator:
    """Argument validator"""

    @staticmethod
    def validate_required(parser: ArgumentParser, *args: str) -> bool:
        """Check if required arguments exist"""
        for arg in args:
            if arg not in parser.kwargs and not parser.args:
                return False
        return True

    @staticmethod
    def validate_count(
        parser: ArgumentParser, min_count: int = 0, max_count: int | None = None
    ) -> bool:
        """Check positional argument count"""
        count = len(parser.args)
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False
        return True

    @staticmethod
    def validate_types(parser: ArgumentParser, *types: type) -> bool:
        """Check positional argument types"""
        if len(types) < len(parser.args):
            return False

        for _i, (arg, expected_type) in enumerate(
            zip(parser.args, types, strict=False)
        ):
            if not isinstance(arg, expected_type):
                try:
                    expected_type(arg)
                except (ValueError, TypeError):
                    return False

        return True

    @staticmethod
    def validate_kwarg_type(
        parser: ArgumentParser, key: str, expected_type: type
    ) -> bool:
        """Check named argument type"""
        if key not in parser.kwargs:
            return True

        value = parser.kwargs[key]
        if isinstance(value, expected_type):
            return True

        try:
            expected_type(value)
            return True
        except (ValueError, TypeError):
            return False


@dataclass
class PipelineSegment:
    """One command stage inside a pipeline expression."""

    command: str
    """Raw command text (stripped, prefix included)."""

    operator: str | None
    """Operator that PRECEDES this segment.
    None  = first segment (no preceding operator)
    '|'   = pipe from previous output
    '&&'  = new-message sequential (run after previous finishes)
    '&'   = same-message sequential (no pipe)
    '||'  = conditional: run only if previous command returned an error
    """

    def __repr__(self) -> str:
        return f"PipelineSegment(op={self.operator!r}, cmd={self.command!r})"


class PipelineParser:
    """Parse a full MCUB command expression into pipeline segments.

    Operators are matched left-to-right with longest-match priority:
      ' && ' before ' & ', ' || ' before ' | '
    Escape sequences (\\) and quoted strings are handled so that operators
    inside quotes or preceded by \\ are treated as literal text.

    Escape rules
    ------------
    A backslash before an operator core strips the backslash and prevents
    the operator from being detected.  Supported escape targets (longest
    match wins):

        \\&&   →  literal ``&&``
        \\||   →  literal ``||``
        \\|    →  literal ``|``
        \\&    →  literal ``&``
        \\x    →  literal ``x``   (general single-char escape)

    Examples::

        # Escape && so the whole expression is one command:
        .ping google.com \\&& bash -c 'ls'
        # → single segment: .ping google.com && bash -c 'ls'

        # Normal pipeline:
        .man | .grep foo | .wc -l
        # → three segments joined by '|'

        pp = PipelineParser(".man | .grep foo")
        for seg in pp.segments:
            print(seg)
    """

    # Checked in order; longest operators must come before their prefixes.
    _OPERATORS: list[tuple[str, str]] = [
        (" | ", "|"),
        ("& ", "&"),
        (" && ", "&&"),
        (" || ", "||"),
    ]

    # Operator cores sorted longest-first for escape resolution.
    _ESCAPE_CORES: tuple[str, ...] = ("&&", "||", "|", "&")

    _OP_PATTERN = re.compile(r"^((\|\||&&)\s*)")

    @staticmethod
    def _detect_operator(text: str, i: int) -> tuple[str | None, str | None]:
        """Detect operator at position i in text.

        Returns (matched_string, operator_key) or (None, None).
        """
        remaining = text[i:]
        for op_str, op_key in PipelineParser._OPERATORS:
            if remaining.startswith(op_str):
                return op_str, op_key
        match = PipelineParser._OP_PATTERN.match(remaining)
        if match:
            op = match.group(2)
            op_map = {"|": "|", "&": "&", "&&": "&&", "||": "||"}
            return match.group(1), op_map.get(op)
        return None, None

    def __init__(self, text: str) -> None:
        self.text = text
        self.segments: list[PipelineSegment] = self._parse()

    def _parse(self) -> list[PipelineSegment]:
        segments: list[PipelineSegment] = []
        buf: list[str] = []
        pending_op: str | None = None
        i = 0
        length = len(self.text)
        in_quotes = False
        quote_char: str | None = None

        while i < length:
            ch = self.text[i]

            if ch == "\\" and not in_quotes:
                i += 1
                if i < length:
                    remaining_after = self.text[i:]
                    escaped = False
                    # Try to match a full operator core (longest first).
                    for core in self._ESCAPE_CORES:
                        if remaining_after.startswith(core):
                            buf.append(core)
                            i += len(core)
                            escaped = True
                            break
                    if not escaped:
                        # General single-char escape: strip the backslash.
                        buf.append(self.text[i])
                        i += 1
                continue

            if ch in ('"', "'"):
                if in_quotes and ch == quote_char:
                    in_quotes = False
                    quote_char = None
                elif not in_quotes:
                    in_quotes = True
                    quote_char = ch
                buf.append(ch)
                i += 1
                continue

            if in_quotes:
                buf.append(ch)
                i += 1
                continue

            matched_str, matched_key = self._detect_operator(self.text, i)

            if matched_str and matched_key:
                seg = "".join(buf).strip()
                if seg:
                    segments.append(PipelineSegment(command=seg, operator=pending_op))
                pending_op = matched_key
                buf = []
                i += len(matched_str)
                continue

            buf.append(ch)
            i += 1

        # trailing segment
        seg = "".join(buf).strip()
        if seg:
            segments.append(PipelineSegment(command=seg, operator=pending_op))

        return segments

    def is_simple(self) -> bool:
        """True when there are no pipeline operators (single command)."""
        return len(self.segments) <= 1

    def __repr__(self) -> str:
        return f"PipelineParser(segments={self.segments!r})"


def parse_pipeline(text: str) -> PipelineParser:
    """Parse *text* into a :class:`PipelineParser`.  Convenience wrapper."""
    return PipelineParser(text)
