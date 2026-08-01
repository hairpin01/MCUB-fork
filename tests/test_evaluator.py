import pytest

from modules.evaluator import (
    _NO_RETURN,
    _compile_eval_function,
    _format_eval_value,
)


async def _run_eval(code: str):
    scope = {"_NO_RETURN": _NO_RETURN}
    exec(_compile_eval_function(code), scope)
    return await scope["__exec"]()


@pytest.mark.asyncio
async def test_eval_auto_returns_last_expression():
    assert await _run_eval("x = 40\nx + 2") == 42


@pytest.mark.asyncio
async def test_eval_no_expression_returns_sentinel():
    assert await _run_eval("x = 1") is _NO_RETURN


@pytest.mark.asyncio
async def test_eval_explicit_return_none_is_preserved():
    assert await _run_eval("return None") is None


def test_format_eval_value_pretty_prints_structures():
    result = _format_eval_value({"a": [1, 2, {"nested": True}], "b": (3, 4)})

    assert result.startswith("{")
    assert "'nested': True" in result
    assert "\n" in result


def test_format_eval_value_keeps_strings_plain():
    assert _format_eval_value("hello") == "hello"
