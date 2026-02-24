from typing import TYPE_CHECKING

from telethon import Button, events

if TYPE_CHECKING:
    from kernel import Kernel


class InlineManager:
    """Handles inline queries, callback handlers, and inline form creation."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

    def register_inline_handler(self, pattern: str, handler) -> None:
        """Register an inline query handler for the given pattern.

        Args:
            pattern: Inline query pattern string.
            handler: Async callable to handle matching queries.
        """
        k = self.k
        k.inline_handlers[pattern] = handler
        if k.current_loading_module:
            k.inline_handlers_owners[pattern] = k.current_loading_module

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        """Remove all inline handlers registered by *module_name*.

        Args:
            module_name: Module whose handlers should be removed.
        """
        k = self.k
        to_remove = [p for p, owner in k.inline_handlers_owners.items() if owner == module_name]
        for pattern in to_remove:
            k.inline_handlers.pop(pattern, None)
            k.inline_handlers_owners.pop(pattern, None)
            k.logger.debug(f"Removed inline handler: {pattern}")

    def register_callback_handler(self, pattern, handler) -> None:
        """Register a Telethon CallbackQuery handler for *pattern*.

        Attaches the handler to the client immediately if already connected.

        Args:
            pattern: Bytes or str pattern for callback data.
            handler: Async callable.
        """
        k = self.k
        try:
            if isinstance(pattern, str):
                pattern = pattern.encode()
            k.callback_handlers[pattern] = handler

            if k.client:
                @k.client.on(events.CallbackQuery(data=pattern))
                async def _wrapper(event):
                    try:
                        await handler(event)
                    except Exception as e:
                        await k.handle_error(e, source="callback_handler", event=event)

        except Exception as e:
            k.logger.error(f"Callback registration error: {e}")

    def _build_buttons(self, raw_buttons: list) -> list:
        """Convert a mixed-format button list into a list of dicts.

        Supports dicts and (text, type, data, hint?) tuples/lists.

        Returns:
            Normalized list of button dicts.
        """
        out = []
        for btn in raw_buttons:
            if isinstance(btn, dict):
                out.append(btn)
            elif isinstance(btn, (list, tuple)) and len(btn) >= 2:
                d = {"text": str(btn[0]), "type": str(btn[1]).lower()}
                if len(btn) >= 3:
                    t = d["type"]
                    if t == "callback":
                        d["data"] = str(btn[2])
                    elif t == "url":
                        d["url"] = str(btn[2])
                    elif t == "switch":
                        d["query"] = str(btn[2])
                        if len(btn) >= 4:
                            d["hint"] = str(btn[3])
                out.append(d)
        return out

    def _format_telethon_buttons(self, buttons: list) -> list:
        """Convert normalized button dicts into Telethon Button rows.

        Returns:
            List of button rows (each row is a list).
        """
        rows = []
        for btn in buttons:
            t = btn.get("type", "callback").lower()
            text = btn.get("text", "Button")
            if t == "callback":
                rows.append([Button.inline(text, btn.get("data", "").encode())])
            elif t == "url":
                rows.append([Button.url(text, btn.get("url", btn.get("data", "")))])
            elif t == "switch":
                rows.append([Button.switch_inline(text, btn.get("query", ""), btn.get("hint", ""))])
        return rows

    async def inline_query_and_click(
        self,
        chat_id: int,
        query: str,
        bot_username: str | None = None,
        result_index: int = 0,
        buttons: list | None = None,
        silent: bool = False,
        reply_to: int | None = None,
        **kwargs,
    ):
        """Perform an inline query and automatically click the specified result.

        Args:
            chat_id: Target chat ID.
            query: Inline query text.
            bot_username: Bot to query (defaults to config ``inline_bot_username``).
            result_index: Which result to click (0-based).
            buttons: Optional list of buttons to attach.
            silent: Send the resulting message silently.
            reply_to: Reply-to message ID.

        Returns:
            (success: bool, message | None)
        """
        k = self.k
        try:
            if not bot_username:
                bot_username = k.config.get("inline_bot_username")
                if not bot_username:
                    raise ValueError("No inline bot configured")

            results = await k.client.inline_query(bot_username, query)
            if not results:
                return False, None

            if result_index >= len(results):
                result_index = 0

            click_kwargs = {}
            if buttons:
                rows = self._format_telethon_buttons(self._build_buttons(buttons))
                if rows:
                    click_kwargs["buttons"] = rows
            if silent:
                click_kwargs["silent"] = silent
            if reply_to:
                click_kwargs["reply_to"] = reply_to
            click_kwargs.update(kwargs)

            message = await results[result_index].click(chat_id, **click_kwargs)
            k.logger.info(f"Inline query OK: {query[:50]}...")
            return True, message

        except Exception as e:
            k.logger.error(f"Inline query error: {e}")
            await k.handle_error(e, source="inline_query_and_click")
            return False, None

    async def send_inline(
        self, chat_id: int, query: str, buttons: list | None = None
    ) -> bool:
        """Send an inline result using the configured inline bot.

        Returns:
            True on success.
        """
        k = self.k
        bot_username = k.config.get("inline_bot_username")
        if not bot_username:
            return False
        try:
            results = await k.client.inline_query(bot_username, query)
            if results:
                kw = {"buttons": buttons} if buttons else {}
                await results[0].click(chat_id, **kw)
                return True
        except Exception:
            pass
        return False

    async def send_inline_from_config(
        self, chat_id: int, query: str, buttons: list | None = None
    ):
        """Simplified inline send using the bot configured in config.json.

        Returns:
            Result of inline_query_and_click.
        """
        return await self.inline_query_and_click(
            chat_id=chat_id,
            query=query,
            bot_username=self.k.config.get("inline_bot_username"),
            buttons=buttons,
        )

    async def inline_form(
        self,
        chat_id: int,
        title: str,
        fields=None,
        buttons=None,
        auto_send: bool = True,
        ttl: int = 200,
        **kwargs,
    ):
        """Create and optionally send an inline form.

        Args:
            chat_id: Target chat.
            title: Form title / first line.
            fields: Dict or list of field values appended below the title.
            buttons: Buttons in any supported format.
            auto_send: If True, send immediately and return (success, message).
                       If False, return the form_id string.
            ttl: Cache TTL for the form (seconds).

        Returns:
            (success, message) when auto_send=True, else form_id str.
        """
        k = self.k
        try:
            from core_inline.handlers import InlineHandlers

            lines = [title]
            if isinstance(fields, dict):
                lines += [f"{k}: {v}" for k, v in fields.items()]
            elif isinstance(fields, list):
                lines += [f"Field {i}: {v}" for i, v in enumerate(fields, 1)]

            handlers = InlineHandlers(k, k.bot_client)
            form_id = handlers.create_inline_form("\n".join(lines), buttons, ttl)

            if auto_send:
                return await self.inline_query_and_click(chat_id=chat_id, query=form_id, **kwargs)
            return form_id

        except Exception as e:
            k.logger.error(f"inline_form error: {e}")
            await k.handle_error(e, source="inline_form")
            return (False, None) if auto_send else None
