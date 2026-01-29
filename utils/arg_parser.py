# author: @Hairpin00
# version: 1.0.0
# description: MCUB command argument parser

import re
import shlex
from typing import List, Dict, Any, Tuple, Optional, Union

class ArgumentParser:
    """Argument parser for MCUB commands"""

    def __init__(self, text: str, prefix: str = '.'):
        """
        Initialize argument parser

        Args:
            text: Full message text (with command and arguments)
            prefix: Command prefix (default '.')
        """
        self.full_text = text.strip()
        self.prefix = prefix
        self.command = ''
        self.args = []
        self.kwargs = {}
        self.flags = set()
        self.raw_args = ''

        self._parse()

    def _parse(self):
        """Parse text into command and arguments"""
        if not self.full_text.startswith(self.prefix):
            raise ValueError(f"Text doesn't start with prefix '{self.prefix}'")

        text_without_prefix = self.full_text[len(self.prefix):].strip()

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
        except:
            tokens = self._simple_split(args_string)

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.startswith('--'):
                flag_name = token[2:]
                if '=' in flag_name:
                    key, value = flag_name.split('=', 1)
                    self.kwargs[key] = self._parse_value(value)
                else:
                    if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                        self.kwargs[flag_name] = self._parse_value(tokens[i + 1])
                        i += 1
                    else:
                        self.flags.add(flag_name)
                        self.kwargs[flag_name] = True

            elif token.startswith('-'):
                if len(token) > 1:
                    flag_chars = token[1:]

                    if len(flag_chars) > 1:
                        for char in flag_chars:
                            self.flags.add(char)
                            self.kwargs[char] = True
                    else:
                        if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                            self.kwargs[flag_chars] = self._parse_value(tokens[i + 1])
                            i += 1
                        else:
                            self.flags.add(flag_chars)
                            self.kwargs[flag_chars] = True

            else:
                self.args.append(self._parse_value(token))

            i += 1

    def _simple_split(self, args_string: str) -> List[str]:
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
                        tokens.append(''.join(current))
                        current = []
                else:
                    in_quotes = True
                    quote_char = char
            elif char == ' ' and not in_quotes:
                if current:
                    tokens.append(''.join(current))
                    current = []
            else:
                current.append(char)

        if current:
            tokens.append(''.join(current))

        return tokens

    def _parse_value(self, value: str) -> Any:
        """Parse value, trying to determine its type"""
        if not value:
            return ''

        if value.isdigit():
            return int(value)

        try:
            return float(value)
        except ValueError:
            pass

        lower_value = value.lower()
        if lower_value in ('true', 'yes', 'on', '1'):
            return True
        elif lower_value in ('false', 'no', 'off', '0'):
            return False

        if ',' in value:
            parts = [self._parse_value(part.strip()) for part in value.split(',')]
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

    def join_args(self, start: int = 0, end: Optional[int] = None) -> str:
        """Join positional arguments into string"""
        args = self.args[start:end]
        return ' '.join(str(arg) for arg in args)

    def __repr__(self) -> str:
        return (f"ArgumentParser(command='{self.command}', "
                f"args={self.args}, kwargs={self.kwargs}, flags={self.flags})")

    def __len__(self) -> int:
        return len(self.args)

    def __contains__(self, item: str) -> bool:
        return item in self.flags or item in self.kwargs

def parse_arguments(text: str, prefix: str = '.') -> ArgumentParser:
    """Create argument parser from message text"""
    return ArgumentParser(text, prefix)

def extract_command(text: str, prefix: str = '.') -> Tuple[str, str]:
    """Extract command and arguments from text"""
    if not text.startswith(prefix):
        return '', text

    text_without_prefix = text[len(prefix):].strip()
    if not text_without_prefix:
        return '', ''

    parts = text_without_prefix.split(None, 1)
    command = parts[0]
    args = parts[1] if len(parts) > 1 else ''

    return command, args

def split_args(args_string: str) -> List[str]:
    """Split argument string into tokens considering quotes"""
    try:
        return shlex.split(args_string)
    except:
        parser = ArgumentParser(f".cmd {args_string}", '.')
        return parser.args

def parse_kwargs(args_string: str) -> Dict[str, Any]:
    """Parse argument string into key-value dictionary"""
    parser = ArgumentParser(f".cmd {args_string}", '.')
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
    def validate_count(parser: ArgumentParser, min_count: int = 0, max_count: Optional[int] = None) -> bool:
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

        for i, (arg, expected_type) in enumerate(zip(parser.args, types)):
            if not isinstance(arg, expected_type):
                try:
                    expected_type(arg)
                except (ValueError, TypeError):
                    return False

        return True

    @staticmethod
    def validate_kwarg_type(parser: ArgumentParser, key: str, expected_type: type) -> bool:
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

def example_usage():
    """Example usage of argument parser"""

    parser1 = parse_arguments(".ping")
    print(f"Command: {parser1.command}")
    print(f"Args: {parser1.args}")

    parser2 = parse_arguments(".echo Hello World!")
    print(f"Command: {parser2.command}")
    print(f"Args: {parser2.args}")
    print(f"Arg 0: {parser2.get(0)}")
    print(f"Arg 1: {parser2.get(1)}")

    parser3 = parse_arguments(".send --to=12345 --message='Hello' --silent")
    print(f"Command: {parser3.command}")
    print(f"Flags: {parser3.flags}")
    print(f"Kwargs: {parser3.kwargs}")
    print(f"Has silent: {parser3.get_flag('silent')}")
    print(f"Get to: {parser3.get_kwarg('to')}")

    parser4 = parse_arguments(".search python --limit=10 --verbose")
    print(f"Command: {parser4.command}")
    print(f"Args: {parser4.args}")
    print(f"Kwargs: {parser4.kwargs}")

    parser5 = parse_arguments(".backup -v -f --output=/backup")
    print(f"Command: {parser5.command}")
    print(f"Flags: {parser5.flags}")
    print(f"Kwargs: {parser5.kwargs}")

    validator = ArgumentValidator()
    parser6 = parse_arguments(".user add --name=John --age=25")

    if validator.validate_required(parser6, 'name', 'age'):
        print("All required arguments present")

    if validator.validate_kwarg_type(parser6, 'age', int):
        print("Age is a number")

if __name__ == "__main__":
    example_usage()
