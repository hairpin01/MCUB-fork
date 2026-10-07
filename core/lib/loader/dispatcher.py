# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @Hairpin00
# version: 1.0.0
# description: Central command dispatcher - message handler + command processing

from __future__ import annotations

import html
import json
import logging
import re
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

    # Matches the literal ``$args`` placeholder inside an alias target, e.g.
    # ``py await c.send_message(m.chat_id, "$args")``. The trailing ``\b``
    # stops it from also matching a longer, unrelated token that merely
    # starts with "args" (``$argslist``).
    _ALIAS_ARGS_PATTERN = re.compile(r"\$args\b")

    def __init__(self, kernel: Kernel) -> None:
        self.kernel = kernel
        self.logger = logging.getLogger(getattr(kernel, "logger_name", __name__))
        if Strings is None:
            self.strings = None
        else:
            self.strings = Strings(kernel, {"name": "kernel"})

    @staticmethod
    def _escape_alias_args(value: str) -> str:
        """
        Escape ``value`` so it is safe to substitute into an alias target in
        place of the ``$args`` placeholder.

        Aliases commonly embed ``$args`` inside a quoted Python string
        literal for ``.py``, e.g. ``py await c.send_message(m.chat_id,
        "$args")``. Without escaping, a user-supplied ``"`` or ``\\`` in the
        argument text would close that string literal early and let
        arbitrary Python code run through ``.py``.

        ``json.dumps`` already implements exactly the escaping a double-quoted
        Python string literal needs (``\\``, ``"``, and control characters
        such as newlines); stripping its surrounding quotes leaves just the
        escaped inner content. ``ensure_ascii=False`` keeps non-ASCII text
        (e.g. Cyrillic) readable instead of turning it into ``\\uXXXX``
        escapes.
        """
        return json.dumps(value, ensure_ascii=False)[1:-1]

    @staticmethod
    def _event_text(event: Any) -> str:
        """Return command text from real, proxy, or lightweight events."""
        for source in (event, getattr(event, "message", None)):
            if source is None:
                continue
            for attr in ("raw_text", "text", "message"):
                value = getattr(source, attr, None)
                if isinstance(value, str) and value:
                    return value
        return ""

    def _should_deliver(
        self,
        event: Any,
        module: str | None,
        action: str,
    ) -> bool:
        checker = getattr(self.kernel, "should_deliver_module_event", None)
        if not callable(checker):
            return True
        return bool(checker(event, module=module, action=action))

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

        # Guest-mode queries arrive on the bot account (``kernel.bot_client``).
        self.register_guest()

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

    def register_guest(self, client: Any = None) -> bool:
        """
        Bind ``guest_message_handler`` to *client* (default: ``kernel.bot_client``).

        Guest bots are queried by ``@username`` and receive
        ``updateBotGuestChatQuery``, so the handler has to live on the bot
        client.  Idempotent; returns ``True`` only when a handler was added.
        Safe to call before the bot client exists (does nothing then) and
        with a Telethon build without ``events.GuestMessage``.
        """
        guest_event = getattr(events, "GuestMessage", None) if events else None
        if guest_event is None:
            self.logger.debug(
                "[dispatcher] events.GuestMessage unavailable - guest mode off"
            )
            return False

        if client is None:
            client = getattr(self.kernel, "bot_client", None)
        if client is None:
            self.logger.debug("[dispatcher] no bot client yet - guest handler skipped")
            return False

        builders = getattr(client, "_event_builders", []) or []
        if any(cb == self.guest_message_handler for _ev, cb in builders):
            return False

        client.add_event_handler(self.guest_message_handler, guest_event())
        self.logger.debug("[dispatcher] registered guest_message handler")
        return True

    async def _guest_bot_username(self, event: Any) -> str | None:
        """Username (without ``@``) of the bot that received the guest query."""
        cached = getattr(self, "_guest_username", None)
        if cached:
            return cached

        username = None
        config = getattr(self.kernel, "config", None)
        if hasattr(config, "get"):
            try:
                username = config.get("inline_bot_username")
            except Exception:
                username = None

        if not username:
            client = getattr(event, "_client", None) or getattr(
                self.kernel, "bot_client", None
            )
            try:
                me = await client.get_me() if client is not None else None
                username = getattr(me, "username", None)
            except Exception:
                username = None

        if isinstance(username, str) and username:
            self._guest_username = username.lstrip("@")
            return self._guest_username
        return None

    @staticmethod
    def _strip_guest_mention(text: str, username: str | None) -> str:
        """Remove the bot ``@username`` from the guest query text."""
        if username:
            text = re.sub(rf"(?<!\w)@{re.escape(username)}(?!\w)", "", text, flags=re.I)
        else:
            # Username unknown: the query always starts with the mention.
            text = re.sub(r"^\s*@\w+", "", text, count=1)
        return text.strip()

    def _guest_owner_alive(self, owner: str | None) -> bool:
        loaded = getattr(self.kernel, "loaded_modules", None) or {}
        system = getattr(self.kernel, "system_modules", None) or {}
        return owner in loaded or owner in system

    def _guest_sender_allowed(self, event: Any) -> bool:
        """Guest queries are answered for the kernel admin only.

        Anyone can invoke a guest bot in any chat, so without this check the
        guest commands would be a public entry point.  Kernels without
        ``is_admin`` (or without a known sender) are allowed through.
        """
        checker = getattr(self.kernel, "is_admin", None)
        if not callable(checker):
            return True

        sender_id = getattr(event, "sender_id", None)
        if sender_id is None:
            sender_id = getattr(getattr(event, "query", None), "sender_id", None)
        if sender_id is None:
            return True

        try:
            return bool(checker(sender_id))
        except Exception as e:
            self.logger.error(
                "[guest] is_admin check failed sender=%r error=%s", sender_id, e
            )
            return False

    async def guest_message_handler(self, event: Any) -> None:
        """
        Guest-mode dispatcher.

        Catches a guest query, removes the bot ``@username`` from the
        arguments, takes the first argument as the command name and, when it
        is registered in ``kernel.guest_handler``, runs its handler.

        Only queries from the kernel admin are dispatched - anyone can invoke
        a guest bot, so everybody else is skipped.

        Messages *posted* by a guest bot (what a userbot sees) are not
        queries and are ignored here.
        """
        if not getattr(event, "is_query", False):
            return

        if not self._guest_sender_allowed(event):
            self.logger.debug(
                "[guest] skip-nonadmin sender=%r", getattr(event, "sender_id", None)
            )
            return

        handlers = getattr(self.kernel, "guest_handler", None)
        if not isinstance(handlers, dict) or not handlers:
            return

        raw = self._event_text(event)
        username = await self._guest_bot_username(event)
        text = self._strip_guest_mention(raw, username)
        if not text:
            return

        parts = text.split(None, 1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        prefix = getattr(self.kernel, "custom_prefix", "") or ""
        if prefix and cmd.startswith(prefix) and len(cmd) > len(prefix):
            cmd = cmd[len(prefix) :]

        handler = handlers.get(cmd)
        if handler is None:
            cmd = cmd.lower()
            handler = handlers.get(cmd)
        if handler is None:
            self.logger.debug(
                "[guest] miss cmd=%r known=%r", cmd, sorted(handlers.keys())
            )
            return

        owners = getattr(self.kernel, "guest_handler_owners", {}) or {}
        owner = owners.get(cmd, "unknown")

        # Module was unloaded / failed to load: drop the stale entry.
        if not self._guest_owner_alive(owner):
            self.logger.debug("[guest] stale cmd=%r owner=%r - removed", cmd, owner)
            handlers.pop(cmd, None)
            owners.pop(cmd, None)
            return

        if not callable(handler):
            self.logger.warning("Guest handler for '%s' is not callable, skipping", cmd)
            return

        if not self._should_deliver(event, owner, "command"):
            self.logger.debug("[guest] blocked-security cmd=%r owner=%r", cmd, owner)
            return

        # Handler sees the query without the mention: "<cmd> <args>".
        self.kernel._set_event_text(event, f"{cmd} {args}".strip())
        for attr_name, value in (
            ("guest_command", cmd),
            ("guest_args", args),
            ("guest_argv", args.split()),
        ):
            try:
                setattr(event, attr_name, value)
            except Exception:
                pass

        self.logger.debug("[guest] dispatch cmd=%r owner=%r args=%r", cmd, owner, args)
        try:
            await handler(wrap_event_for_module(event, owner, self.kernel))
        except RPCError as e:
            self.logger.error("[guest] RPC error in %r: %s", cmd, e)
        except Exception as e:
            await self.kernel.handle_error(
                e, message=f"Guest handler error: {cmd}", event=event
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

        if not self._should_deliver(event, None, "command_discovery"):
            self.logger.debug(
                "[dispatcher] skip-security handler=watcher_message "
                "text=%r sender=%r chat=%r",
                getattr(msg, "raw_text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
            )
            return

        text = self._event_text(event)
        active_prefix = self.kernel.get_prefix_for_sender(
            getattr(event, "sender_id", None)
        )
        is_command_text = bool(text and text.startswith(active_prefix))

        if is_command_text and self.kernel._is_command_event_processed(event):
            self.logger.debug(
                "[dispatcher] skip-duplicate handler=watcher_message "
                "text=%r sender=%r chat=%r",
                getattr(msg, "raw_text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
            )
            return

        if is_command_text:
            self.kernel._mark_command_event_processed(event)

        try:
            handled = await self.process_command(event)
            if is_command_text and not handled:
                self.kernel._unmark_command_event_processed(event)
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
                        f"🪫 <b>Error in <code>{safe_cmd}</code></b>\n"
                        f"<pre>{tb}</pre>"
                        if self.strings is None
                        else f"{self.strings('material_emoji')('load_1')} {self.strings(
                            "call_failed_traceback", cmd=safe_cmd, traceback=tb
                        )}"
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

        text = self._event_text(event)
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
        text = self._event_text(event)

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
                    if not self._should_deliver(event, _mod, "command"):
                        self.logger.debug(
                            "[process_command] blocked-security cmd=%r owner=%r",
                            cmd,
                            _mod,
                        )
                        return True
                    await self.kernel.command_handlers[cmd](
                        wrap_event_for_module(event, _mod, self.kernel)
                    )
                    return True
                event.pipe_exit_code = 5
                return False

            args = text[len(active_prefix) + len(cmd) :]
            if self._ALIAS_ARGS_PATTERN.search(alias_target):
                # args without the single separating space the raw tail
                # keeps for the plain-append case below, e.g. "$args" in
                # ".test_alias argument" should become "argument", not
                # " argument".
                args_value = args[1:] if args.startswith(" ") else args
                escaped = self._escape_alias_args(args_value)
                resolved_target = self._ALIAS_ARGS_PATTERN.sub(
                    lambda _m: escaped, alias_target
                )
                new_text = active_prefix + resolved_target
            else:
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
            if not self._should_deliver(event, _mod, "command"):
                self.logger.debug(
                    "[process_command] blocked-security cmd=%r owner=%r",
                    cmd,
                    _mod,
                )
                return True
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
            _tele = '<tg-emoji emoji-id="5348118479847333898">🗑</tg-emoji>'
            msg = (
                f"{_tele} {self.strings('call_failed', cmd=cmd_text, rpc_msg=rpc_msg)}"
                if self.strings is not None
                else f"\U0001f52d Call failed: <code>{cmd_text}</code> - {rpc_msg}"
            )
            await event.edit(msg, parse_mode="html")
        except Exception as edit_err:
            self.logger.error("Could not edit RPC error message: %s", edit_err)
