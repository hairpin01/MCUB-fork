# SPDX-License-Identifier: MIT
# Copyright (c) 2026 rich_beluga | @rich_beluga

"""
Tests for ``$args`` substitution in alias targets
(``CommandDispatcher._dispatch_single_command``).

Behavior under test:

- An alias whose target contains the literal ``$args`` placeholder gets that
  placeholder replaced with the text the caller actually typed after the
  alias name, instead of (as before) blindly appending that text to the end
  of the target.
- The substituted value is escaped so it is safe to embed inside a
  double-quoted Python string literal - the alias system's own stated use
  case is handing the result to ``.py`` - so a caller-supplied ``"`` or
  ``\\`` cannot break out of the quotes and splice in extra Python code.
- An alias target with no ``$args`` placeholder keeps the old behavior
  (plain append) unchanged, for backward compatibility with existing
  aliases.
"""

import ast
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.lib.loader.dispatcher import CommandDispatcher


def make_kernel(aliases: dict, command_handlers: dict | None = None):
    kernel = MagicMock()
    kernel.custom_prefix = "."
    kernel.logger_name = "test"
    kernel.aliases = dict(aliases)
    kernel.command_handlers = dict(command_handlers or {})
    kernel.command_owners = {name: "mod" for name in kernel.command_handlers}
    kernel.config = {"piped": True}
    kernel.should_deliver_module_event = MagicMock(return_value=True)
    kernel.handle_error = AsyncMock()
    kernel.get_prefix_for_sender = MagicMock(return_value=".")

    def _set_text(event, text):
        event.text = text
        event.raw_text = text

    kernel._set_event_text = _set_text
    return kernel


def make_event(text: str):
    return SimpleNamespace(
        text=text,
        raw_text=text,
        sender_id=1,
        chat_id=100,
        no_add_args_to_input=False,
    )


@pytest.fixture
def captured_handler():
    """An async command handler that records the fully-resolved event text."""
    calls: list[str] = []

    async def handler(event):
        calls.append(event.text)

    handler.calls = calls
    return handler


@pytest.mark.asyncio
class TestArgsSubstitution:
    async def test_basic_substitution_matches_the_spec_example(self, captured_handler):
        kernel = make_kernel(
            aliases={
                "test_alias": 'py await c.send_message(m.chat_id, "$args")',
            },
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".test_alias argument")

        handled = await dispatcher.process_command(event)

        assert handled is True
        assert captured_handler.calls == [
            '.py await c.send_message(m.chat_id, "argument")'
        ]

    async def test_no_placeholder_keeps_old_append_behavior(self, captured_handler):
        """An alias with no $args must behave exactly as it did before."""
        kernel = make_kernel(
            aliases={"ls": "t ls -la"},
            command_handlers={"t": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".ls /tmp")

        await dispatcher.process_command(event)

        assert captured_handler.calls == [".t ls -la /tmp"]

    async def test_no_args_supplied_substitutes_empty_string(self, captured_handler):
        kernel = make_kernel(
            aliases={"greet": 'py print("hello $args")'},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".greet")

        await dispatcher.process_command(event)

        assert captured_handler.calls == ['.py print("hello ")']

    async def test_multiple_occurrences_are_all_substituted(self, captured_handler):
        kernel = make_kernel(
            aliases={
                "echo2": 'py print("$args" + "$args")',
            },
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".echo2 hi")

        await dispatcher.process_command(event)

        assert captured_handler.calls == ['.py print("hi" + "hi")']

    async def test_lookalike_token_is_not_substituted(self, captured_handler):
        """`$argslist` is a different token and must not match `$args`."""
        kernel = make_kernel(
            aliases={"weird": "py print($argslist)"},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".weird x")

        await dispatcher.process_command(event)

        assert captured_handler.calls == [".py print($argslist) x"]

    async def test_chained_aliases_each_substitute_their_own_tail(
        self, captured_handler
    ):
        kernel = make_kernel(
            aliases={
                "a": 'b wrapped($args)',
                "b": 'py print("$args")',
            },
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".a value")

        await dispatcher.process_command(event)

        assert captured_handler.calls == ['.py print("wrapped(value)")']


@pytest.mark.asyncio
class TestArgsEscaping:
    async def test_double_quote_cannot_break_out_of_the_string_literal(
        self, captured_handler
    ):
        kernel = make_kernel(
            aliases={"test_alias": 'py await c.send_message(m.chat_id, "$args")'},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        payload = '"); import os; os.system("id'
        event = make_event(f".test_alias {payload}")

        await dispatcher.process_command(event)

        resolved = captured_handler.calls[0]
        code = resolved[len(".py ") :]
        # It must still parse as ONE call with ONE string-literal argument -
        # if the quote had broken out, this would parse as multiple
        # statements/expressions instead of a single Expr(Await(Call(...))).
        tree = ast.parse(code, mode="exec")
        assert len(tree.body) == 1
        call = tree.body[0].value.value  # Expr -> Await -> Call
        assert isinstance(call, ast.Call)
        literal = call.args[1]
        assert isinstance(literal, ast.Constant)
        assert literal.value == payload

    async def test_backslash_is_escaped(self, captured_handler):
        kernel = make_kernel(
            aliases={"test_alias": 'py print("$args")'},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(r".test_alias C:\Users\test")

        await dispatcher.process_command(event)

        resolved = captured_handler.calls[0]
        code = resolved[len(".py ") :]
        value = ast.literal_eval(code[len("print(") : -1])
        assert value == r"C:\Users\test"

    async def test_newline_is_escaped_not_literal(self, captured_handler):
        kernel = make_kernel(
            aliases={"test_alias": 'py print("$args")'},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".test_alias line1\nline2")

        await dispatcher.process_command(event)

        resolved = captured_handler.calls[0]
        assert "\n" not in resolved[len(".py print(") :]  # no raw newline in the source
        code = resolved[len(".py ") :]
        value = ast.literal_eval(code[len("print(") : -1])
        assert value == "line1\nline2"

    async def test_unicode_is_preserved_readably(self, captured_handler):
        kernel = make_kernel(
            aliases={"test_alias": 'py print("$args")'},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        event = make_event(".test_alias Привет, мир!")

        await dispatcher.process_command(event)

        resolved = captured_handler.calls[0]
        assert "Привет, мир!" in resolved  # not turned into \u escapes
        code = resolved[len(".py ") :]
        value = ast.literal_eval(code[len("print(") : -1])
        assert value == "Привет, мир!"

    async def test_combined_adversarial_payload_round_trips_safely(
        self, captured_handler
    ):
        kernel = make_kernel(
            aliases={"test_alias": 'py print("$args")'},
            command_handlers={"py": captured_handler},
        )
        dispatcher = CommandDispatcher(kernel)
        payload = 'a"b\\c\nd\t"); __import__("os").system("whoami'
        event = make_event(f".test_alias {payload}")

        await dispatcher.process_command(event)

        resolved = captured_handler.calls[0]
        code = resolved[len(".py ") :]
        tree = ast.parse(code, mode="exec")
        assert len(tree.body) == 1
        call = tree.body[0].value
        assert isinstance(call, ast.Call)
        literal = call.args[0]
        assert isinstance(literal, ast.Constant)
        assert literal.value == payload
