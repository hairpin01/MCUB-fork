# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from types import SimpleNamespace
from unittest import TestCase

import pytest

from core.lib.kernel_pipeline import KernelPipelineMixin
from core.lib.loader.dispatcher import CommandDispatcher


class DummyDispatcher:
    async def process_command(self, event):
        await event.edit("captured output")
        return True


class NoneOutputDispatcher:
    async def process_command(self, event):
        await event.edit(None)
        return True


class StatefulDispatcher:
    def __init__(self):
        self.vars = {}
        self.calls = []

    async def process_command(self, event):
        self.calls.append(event.text)
        if event.text == "1export var text":
            self.vars["var"] = "text"
            await event.edit("exported")
            return True
        if event.text == "1import var":
            await event.edit(self.vars.get("var", "missing"))
            return True
        return False


class DummyKernel(KernelPipelineMixin):
    def __init__(self):
        self._pipe_vars = {"var": "saved text", "nested": {"value": "deep"}}
        self.dispatcher = DummyDispatcher()
        self.logger = SimpleNamespace(debug=lambda *args, **kwargs: None)


def test_pipe_interpolate_resolves_exported_vars():
    kernel = DummyKernel()

    assert kernel.pipe_interpolate(".echo @{var}") == ".echo saved text"
    assert kernel.pipe_interpolate(".echo @{nested.value}") == ".echo deep"


@pytest.mark.asyncio
async def test_async_pipe_interpolate_returns_captured_command_output():
    kernel = DummyKernel()
    event = SimpleNamespace(chat_id=1, sender_id=2)

    result = await kernel.async_pipe_interpolate(
        ".echo @(.import var)",
        event=event,
        active_prefix=".",
    )

    assert result == ".echo captured output"


@pytest.mark.asyncio
async def test_async_pipe_interpolate_handles_none_command_output():
    kernel = DummyKernel()
    kernel.dispatcher = NoneOutputDispatcher()
    event = SimpleNamespace(chat_id=1, sender_id=2)

    result = await kernel.async_pipe_interpolate(
        ".echo @(.empty)",
        event=event,
        active_prefix=".",
    )

    TestCase().assertEqual(result, ".echo ")


@pytest.mark.asyncio
async def test_async_pipe_interpolate_runs_commands_left_to_right():
    kernel = DummyKernel()
    dispatcher = StatefulDispatcher()
    kernel.dispatcher = dispatcher
    event = SimpleNamespace(chat_id=1, sender_id=2)

    result = await kernel.async_pipe_interpolate(
        "1echo @(1export var text) -> @(1import var)",
        event=event,
        active_prefix="1",
    )

    assert dispatcher.calls == ["1export var text", "1import var"]
    assert result == "1echo exported -> text"


class PipelineKernel(KernelPipelineMixin):
    def __init__(self):
        self.calls = []
        self.config = {"piped": True}
        self.logger = SimpleNamespace(
            debug=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        )
        self.client = SimpleNamespace(send_message=self.send_message)
        self._pipe_vars = {}

    async def send_message(self, chat_id, text, **kwargs):
        return SimpleNamespace(id=len(self.calls) + 1, sender_id=10)

    def _set_event_text(self, event, text):
        event.text = text
        if hasattr(event, "message"):
            event.message.text = text
            event.message.message = text

    async def process_command(self, event, depth=0):
        self.calls.append(event.text)
        if event.text.startswith(".fail"):
            event.pipe_exit_code = 1
            await event.edit("failed")
            return True
        event.pipe_exit_code = 0
        await event.edit(f"ok {event.text}")
        return True


def make_event(text):
    captured = []

    async def edit(new_text, *args, **kwargs):
        captured.append(new_text)

    return SimpleNamespace(
        text=text,
        chat_id=1,
        piped=False,
        pipe_input=None,
        pipe_output=None,
        pipe_exit_code=0,
        edit=edit,
        captured=captured,
    )


@pytest.mark.asyncio
async def test_pipeline_pipe_forward_reuses_base_command():
    from utils.arg_parser import PipelineParser

    kernel = PipelineKernel()
    event = make_event(".ping 1.1.1.1 |> 8.8.8.8")

    await kernel._execute_pipeline(event, PipelineParser(event.text), 0)

    assert kernel.calls == [".ping 1.1.1.1", ".ping 8.8.8.8"]


@pytest.mark.asyncio
async def test_pipeline_or_runs_after_failed_command():
    from utils.arg_parser import PipelineParser

    kernel = PipelineKernel()
    event = make_event(".fail || .echo fallback")

    await kernel._execute_pipeline(event, PipelineParser(event.text), 0)

    assert kernel.calls == [".fail", ".echo fallback"]


@pytest.mark.asyncio
async def test_pipeline_or_skips_after_successful_command():
    from utils.arg_parser import PipelineParser

    kernel = PipelineKernel()
    event = make_event(".echo ok || .echo fallback")

    await kernel._execute_pipeline(event, PipelineParser(event.text), 0)

    assert kernel.calls == [".echo ok"]


class DispatcherPipelineKernel(KernelPipelineMixin):
    def __init__(self):
        self._pipe_vars = {}
        self.config = {"piped": True}
        self.custom_prefix = "."
        self.aliases = {}
        self.calls = []
        self.command_owners = {
            "export": "utils-piped",
            "import": "utils-piped",
            "echo": "utils-piped",
        }
        self.command_handlers = {
            "export": self.cmd_export,
            "import": self.cmd_import,
            "echo": self.cmd_echo,
        }
        self.logger = SimpleNamespace(
            debug=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        )
        self.client = SimpleNamespace(send_message=self.send_message)
        self.dispatcher = CommandDispatcher(self)

    def get_prefix_for_sender(self, sender_id):
        return "."

    def _set_event_text(self, event, text):
        event.text = text
        if hasattr(event, "message"):
            event.message.text = text
            event.message.message = text

    async def process_command(self, event, depth=0):
        return await self.dispatcher.process_command(event, depth)

    async def send_message(self, chat_id, text, **kwargs):
        return SimpleNamespace(id=len(self.calls) + 1, sender_id=10)

    async def cmd_export(self, event):
        self.calls.append(("export", event.text))
        _cmd, name, value = event.text.split(maxsplit=2)
        self._pipe_vars[name] = value
        await event.edit("exported")

    async def cmd_import(self, event):
        self.calls.append(("import", event.text))
        _cmd, name = event.text.split(maxsplit=1)
        await event.edit(self._pipe_vars.get(name, "missing"))

    async def cmd_echo(self, event):
        self.calls.append(("echo", event.text))
        await event.edit(event.text.split(maxsplit=1)[1])


@pytest.mark.asyncio
async def test_dispatcher_defers_command_interpolation_inside_pipeline_segments():
    kernel = DispatcherPipelineKernel()
    event = make_event(".export var text && .echo @(.import var)")

    await kernel.process_command(event)

    assert kernel.calls == [
        ("export", ".export var text"),
        ("import", ".import var"),
        ("echo", ".echo text"),
    ]


@pytest.mark.asyncio
async def test_pipeline_merge_when_segment_lacks_prefix():
    """When a pipeline segment after the first lacks a command prefix,
    the whole text is dispatched as a single command instead of a pipeline."""

    kernel = DispatcherPipelineKernel()

    # Add a 't' (terminal) command for testing
    async def cmd_t(self, event):
        self.calls.append(("t", event.text))
        await event.edit("ok")

    kernel.cmd_t = cmd_t.__get__(kernel, DispatcherPipelineKernel)
    kernel.command_handlers["t"] = kernel.cmd_t
    kernel.command_owners["t"] = "terminal"

    # .t ls | .wc -l - all segments have prefix → MCUB pipeline
    kernel.calls.clear()
    event1 = make_event(".t ls | .wc -l")
    await kernel.process_command(event1)
    assert (
        "t",
        ".t ls",
    ) in kernel.calls, f"expected .t call with '.t ls' in {kernel.calls}"

    # .t ls | grep home - second segment lacks prefix → single command
    kernel.calls.clear()
    event2 = make_event(".t ls | grep home")
    await kernel.process_command(event2)
    assert (
        "t",
        ".t ls | grep home",
    ) in kernel.calls, f"expected .t to receive full text in {kernel.calls}"
