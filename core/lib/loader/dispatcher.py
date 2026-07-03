# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @Hairpin00
# version: 1.0.0
# description: Central command dispatcher - message handler + command processing

from __future__ import annotations

import html
import logging
import traceback
from typing import TYPE_CHECKING, Any

from core.lib.types.event import Event

try:
    from telethon import events
    from telethon.errors import RPCError
except ImportError:
    events = None
    RPCError = Exception

try:
    from core.lib.loader.kernel_proxy import wrap_event_for_module
except ImportError:

    def wrap_event_for_module(e: Any, *a: Any, **kw: Any) -> Any:
        return e


if TYPE_CHECKING:
    from core.lib.types import Kernel


try:
    from utils.strings import Strings
except ImportError:
    Strings = None


class CommandDispatcher:
    """
    Central dispatcher for userbot commands.

    Owns the core message handler (``watcher_message_handler``) that the
    kernel registers on the Telethon client, and the command resolution
    logic (``process_command``) that matches incoming text against
    registered commands, aliases, and pipelines.

    Usage (inside kernel)::

        self.dispatcher = CommandDispatcher(self)
        self.dispatcher.register()
    """

    def __init__(self, kernel: Kernel) -> None:
        self.kernel = kernel
        self.logger = logging.getLogger(getattr(kernel, "logger_name", __name__))
        if Strings is None:
            self.strings = None
        else:
            self.strings = Strings(kernel, {"name": "kernel"})

    def register(self) -> None:
        """
        Bind the central message handler to the Telethon client.

        Registers ``watcher_message_handler`` for both ``NewMessage``
        and ``MessageEdited`` events so that edited messages are also
        re-dispatched.

        Idempotent - skips registration if the handler is already bound.
        """
        if events is None:
            self.logger.error(
                "[dispatcher] cannot register - telethon.events unavailable"
            )
            return

        client = getattr(self.kernel, "client", None)
        if client is None:
            self.logger.error("[dispatcher] cannot register - kernel.client is None")
            return

        builders = getattr(client, "_event_builders", []) or []

        has_new = any(
            cb == self.watcher_message_handler and type(ev).__name__ == "NewMessage"
            for ev, cb in builders
        )
        has_edit = any(
            cb == self.watcher_message_handler and type(ev).__name__ == "MessageEdited"
            for ev, cb in builders
        )

        if has_new and has_edit:
            self.logger.debug(
                "[dispatcher] already registered - skipping (has_new=%s has_edit=%s)",
                has_new,
                has_edit,
            )
            return

        if not has_new:
            client.add_event_handler(self.watcher_message_handler, events.NewMessage())
        if not has_edit:
            client.add_event_handler(
                self.watcher_message_handler, events.MessageEdited()
            )

        self.logger.debug(
            "[dispatcher] registered watcher_message handler for "
            "NewMessage + MessageEdited (added_new=%s added_edit=%s)",
            not has_new,
            not has_edit,
        )

    async def watcher_message_handler(self, event: Event) -> None:
        """
        Core message handler.

        Intercepts every new (or edited) message, filters out bot
        messages and non-owner events, and dispatches the rest to
        ``process_command``.

        Registered automatically via ``register()``.
        """
        msg = getattr(event, "message", event)

        # Skip messages sent via bots
        if not str(getattr(self.kernel, "CORE_NAME", True)).lower == "bot":
            if getattr(msg, "via_bot", None) is not None:
                return

        if not self.kernel.should_process_command_event(event):
            self.logger.debug(
                "[dispatcher] skip-nonoutgoing handler=watcher_message "
                "text=%r sender=%r chat=%r out=%r admin=%r",
                getattr(msg, "raw_text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
                getattr(msg, "out", False),
                self.kernel.is_admin(getattr(event, "sender_id", None)),
            )
            return

        if self.kernel._is_command_event_processed(event):
            self.logger.debug(
                "[dispatcher] skip-duplicate handler=watcher_message "
                "text=%r sender=%r chat=%r",
                getattr(msg, "raw_text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
            )
            return

        self.kernel._mark_command_event_processed(event)

        try:
            await self.process_command(event)
        except RPCError as e:
            await self._handle_rpc_error(event, e)
        except Exception as e:
            await self.kernel.handle_error(
                e, message="Message handler error", event=event
            )
            tb = traceback.format_exc()
            if len(tb) > 1000:
                tb = "…" + tb[-997:]
            try:
                safe_cmd = html.escape(getattr(event, "raw_text", "") or "")

                await event.edit(
                    (
                        f"<b>Error in <code>{safe_cmd}</code></b>\n" f"<pre>{tb}</pre>"
                        if self.strings is None
                        else self.strings(
                            "call_failed_traceback", cmd=safe_cmd, traceback=tb
                        )
                    ),
                    parse_mode="html",
                )
            except Exception:
                pass

    async def process_command(self, event: Event, depth: int = 0) -> bool:
        """
        Match and dispatch an outgoing message event to a command handler.

        Resolves aliases recursively (max depth 5).  Returns ``True``
        when a handler was found and called, ``False`` otherwise.

        This method is also the single entry-point for pipeline segments.
        """
        if depth > 5:
            self.logger.error(
                "[process_command] alias recursion limit reached: %r",
                getattr(event, "raw_text", None),
            )
            await self.kernel.logger.info(
                f"Alias recursion limit reached: {event.text}"
            )
            return False

        text = getattr(event, "raw_text", "") or ""
        active_prefix = self.kernel.get_prefix_for_sender(
            getattr(event, "sender_id", None)
        )

        self.logger.debug(
            "[process_command] depth=%d text=%r sender=%r chat=%r "
            "handlers=%d aliases=%d",
            depth,
            text,
            getattr(event, "sender_id", None),
            getattr(event, "chat_id", None),
            len(self.kernel.command_handlers),
            len(self.kernel.aliases),
        )

        if not text or not text.startswith(active_prefix):
            self.logger.debug(
                "[process_command] ignored text=%r reason=no_prefix " "prefix=%r",
                text,
                active_prefix,
            )
            return False

        # Try pipeline execution first
        try:
            from utils.arg_parser import PipelineParser

            pipeline = PipelineParser(text)
        except ImportError:
            pipeline = None

        piped_enabled = self.kernel.config.get("piped", True)
        if pipeline is not None and not pipeline.is_simple() and piped_enabled:
            # If any segment after the first doesn't start with the command
            # prefix, treat the whole text as a single command instead of
            # an MCUB pipeline.  This lets shell pipelines like::
            #
            #   .t ls | grep home
            #
            # pass the entire ``ls | grep home`` as arguments to ``.t``,
            # while ``.t ls | .wc -l`` still works as a proper MCUB
            # pipeline.
            if any(
                not seg.command.startswith(active_prefix)
                for seg in pipeline.segments[1:]
            ):
                self.logger.debug(
                    "[process_command] pipeline segments lack prefix, "
                    "treating as single command: text=%r",
                    text,
                )
            else:
                return await self._execute_pipeline(event, pipeline, depth)

        if "@{" in text:
            pipe_in = getattr(event, "pipe_input", None) or ""
            interpolated = self.kernel.pipe_interpolate(text, pipe_in)
            if interpolated != text:
                self.kernel._set_event_text(event, interpolated)
                text = interpolated
                self.logger.debug(
                    "[process_command] interpolated %r -> %r",
                    text,
                    interpolated,
                )
        if "@(" in text:
            pipe_in = getattr(event, "pipe_input", None) or ""
            interpolated = await self.kernel.async_pipe_interpolate(
                text, pipe_in, event, active_prefix
            )
            if interpolated != text:
                self.kernel._set_event_text(event, interpolated)
                text = interpolated

        return await self._dispatch_single_command(event, depth, active_prefix)

    async def _dispatch_single_command(
        self,
        event: Any,
        depth: int,
        active_prefix: str,
    ) -> bool:
        """
        Dispatch a single (non-pipeline) command to its handler.

        Resolves aliases, wraps the event for the owning module and
        calls the handler.
        """
        text = getattr(event, "raw_text", "") or ""

        # Guarantee pipeline attributes exist
        for attr_name, default in (
            ("piped", False),
            ("pipe_input", None),
            ("pipe_output", None),
            ("pipe_exit_code", 0),
            ("no_add_args_to_input", False),
        ):
            if not hasattr(event, attr_name):
                setattr(event, attr_name, default)

        cmd = (
            text[len(active_prefix) :].split()[0]
            if " " in text
            else text[len(active_prefix) :]
        )

        # Alias resolution
        if cmd in self.kernel.aliases:
            alias_target = self.kernel.aliases[cmd]
            self.logger.debug(
                "[process_command] alias-hit cmd=%r target=%r text=%r",
                cmd,
                alias_target,
                text,
            )
            alias_cmd = alias_target.split()[0] if " " in alias_target else alias_target
            if (
                alias_cmd not in self.kernel.command_handlers
                and alias_cmd not in self.kernel.aliases
            ):
                self.logger.warning(
                    "Alias '%s' points to non-existent target '%s', "
                    "executing '%s' directly",
                    cmd,
                    alias_target,
                    cmd,
                )
                if cmd in self.kernel.command_handlers:
                    _mod = self.kernel.command_owners.get(cmd, "unknown")
                    await self.kernel.command_handlers[cmd](
                        wrap_event_for_module(event, _mod, self.kernel)
                    )
                    return True
                event.pipe_exit_code = 5
                return False

            args = text[len(active_prefix) + len(cmd) :]
            new_text = active_prefix + alias_target + args
            self.kernel._set_event_text(event, new_text)
            return await self.process_command(event, depth + 1)

        # Direct command dispatch
        if cmd in self.kernel.command_handlers:
            handler = self.kernel.command_handlers[cmd]
            self.logger.debug(
                "[process_command] dispatch cmd=%r owner=%r handler=%r",
                cmd,
                self.kernel.command_owners.get(cmd),
                getattr(handler, "__name__", repr(handler)),
            )
            if not callable(handler):
                self.logger.warning(
                    "Command handler for '%s' is not callable, skipping",
                    cmd,
                )
                event.pipe_exit_code = 5
                return False

            _mod = self.kernel.command_owners.get(cmd, "unknown")
            await handler(wrap_event_for_module(event, _mod, self.kernel))
            return True

        self.logger.debug(
            "[process_command] miss cmd=%r known=%r",
            cmd,
            sorted(self.kernel.command_handlers.keys()),
        )
        event.pipe_exit_code = 5
        return False

    async def _execute_pipeline(
        self,
        event: Any,
        pipeline: Any,
        depth: int,
    ) -> bool:
        """
        Execute a multi-segment pipeline expression.

        Delegates to the kernel's pipeline implementation.
        """
        # Delegate to the kernel - the kernel owns pipeline state
        # (client, send_message, etc.) and _make_simple_event / _run_and_capture.
        if hasattr(self.kernel, "_execute_pipeline"):
            return await self.kernel._execute_pipeline(event, pipeline, depth)

        self.logger.warning("[dispatcher] kernel has no _execute_pipeline - skipping")
        return False

    async def _handle_rpc_error(self, event: Event, error: RPCError) -> None:
        """Display a user-friendly RPC error in the chat."""
        cmd_text = html.escape(getattr(event, "raw_text", "") or "")
        rpc_msg = html.escape(str(error))
        try:
            _tele = '<tg-emoji emoji-id="5429283852684124412">' "\U0001f52d</tg-emoji>"
            msg = (
                f"{_tele} {self.strings('call_failed', cmd=cmd_text, rpc_msg=rpc_msg)}"
                if self.strings is not None
                else f"\U0001f52d Call failed: <code>{cmd_text}</code> - {rpc_msg}"
            )
            await event.edit(msg, parse_mode="html")
        except Exception as edit_err:
            self.logger.error("Could not edit RPC error message: %s", edit_err)
