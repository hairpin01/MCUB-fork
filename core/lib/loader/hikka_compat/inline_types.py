import logging
import types
import typing

if typing.TYPE_CHECKING:
    from .runtime import _InlineProxy

logger = logging.getLogger(__name__)


def _resolve_inline_manager(inline_proxy):
    if inline_proxy is None:
        return None

    candidates = [
        inline_proxy,
        getattr(inline_proxy, "_inline_manager", None),
    ]

    kernel = getattr(inline_proxy, "_kernel", None)
    if kernel is not None:
        candidates.append(getattr(kernel, "_inline", None))

    for candidate in candidates:
        if candidate is not None:
            return candidate

    return inline_proxy


class InlineMessage:
    """Inline message adapter for Heroku-compatible modules."""

    def __init__(
        self,
        inline_message_id: str,
        unit_id: str,
        inline_proxy: "_InlineProxy",
        chat_id: typing.Optional[int] = None,
        message_id: typing.Optional[int] = None,
    ):
        self.inline_message_id = inline_message_id
        self.unit_id = unit_id
        self._inline_proxy = inline_proxy
        self.chat_id = chat_id
        self.message_id = message_id
        self.inline_manager = _resolve_inline_manager(inline_proxy)
        self._units = getattr(self.inline_manager, "_units", {})
        self.form = {}
        if unit_id and unit_id in self._units:
            unit = dict(self._units[unit_id])
            unit.setdefault("uid", unit_id)
            unit.setdefault("id", unit_id)
            unit.setdefault("message", message_id)
            unit.setdefault("top_msg_id", message_id)
            self.form = unit

    async def edit(self, *args, **kwargs) -> "InlineMessage":
        kwargs.pop("unit_id", None)
        kwargs.pop("inline_message_id", None)
        kwargs.pop("chat_id", None)
        kwargs.pop("message_id", None)

        manager = self.inline_manager
        edit_unit = getattr(manager, "_edit_unit", None) if manager else None
        if callable(edit_unit):
            try:
                result = await edit_unit(
                    *args,
                    unit_id=self.unit_id,
                    inline_message_id=self.inline_message_id or None,
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    **kwargs,
                )
                if isinstance(result, InlineMessage):
                    return result
            except Exception as e:
                logger.debug("InlineMessage.edit fallback due to error: %s", e)

        return self

    async def delete(self) -> bool:
        manager = self.inline_manager
        delete_message = (
            getattr(manager, "_delete_unit_message", None) if manager else None
        )
        if callable(delete_message):
            try:
                return bool(
                    await delete_message(
                        self,
                        unit_id=self.unit_id,
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                    )
                )
            except Exception as e:
                logger.debug("InlineMessage.delete fallback due to error: %s", e)

        return False

    async def unload(self) -> bool:
        manager = self.inline_manager
        unload_unit = getattr(manager, "_unload_unit", None) if manager else None
        if callable(unload_unit):
            try:
                return bool(await unload_unit(unit_id=self.unit_id))
            except Exception as e:
                logger.debug("InlineMessage.unload fallback due to error: %s", e)

        return False


class BotMessage:
    """Adapter for bot-sent messages."""

    def __init__(
        self,
        chat_id: int,
        message_id: int,
        inline_proxy: typing.Optional["_InlineProxy"] = None,
        unit_id: str = "",
    ):
        self.chat_id = chat_id
        self.message_id = message_id
        self.unit_id = unit_id
        self._inline_proxy = inline_proxy
        self.inline_manager = _resolve_inline_manager(inline_proxy)
        self._units = getattr(self.inline_manager, "_units", {})
        self.form = {}
        if unit_id and unit_id in self._units:
            unit = dict(self._units[unit_id])
            unit.setdefault("uid", unit_id)
            unit.setdefault("id", unit_id)
            unit.setdefault("message", message_id)
            unit.setdefault("top_msg_id", message_id)
            self.form = unit

    async def edit(self, *args, **kwargs) -> "BotMessage":
        kwargs.pop("unit_id", None)
        kwargs.pop("chat_id", None)
        kwargs.pop("message_id", None)

        manager = self.inline_manager
        edit_unit = getattr(manager, "_edit_unit", None) if manager else None
        if callable(edit_unit):
            try:
                await edit_unit(
                    *args,
                    unit_id=self.unit_id or None,
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    **kwargs,
                )
            except Exception as e:
                logger.debug("BotMessage.edit fallback due to error: %s", e)

        return self

    async def delete(self) -> bool:
        manager = self.inline_manager
        delete_message = (
            getattr(manager, "_delete_unit_message", None) if manager else None
        )
        if callable(delete_message):
            try:
                return bool(
                    await delete_message(
                        self,
                        unit_id=self.unit_id or None,
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                    )
                )
            except Exception as e:
                logger.debug("BotMessage.delete fallback due to error: %s", e)

        return False

    async def unload(self) -> bool:
        manager = self.inline_manager
        unload_unit = getattr(manager, "_unload_unit", None) if manager else None
        if callable(unload_unit) and self.unit_id:
            try:
                return bool(await unload_unit(unit_id=self.unit_id))
            except Exception as e:
                logger.debug("BotMessage.unload fallback due to error: %s", e)

        return False


class InlineCall:
    """Inline callback adapter compatible with Heroku callback handlers."""

    def __init__(
        self,
        call_data: str,
        unit_id: str,
        inline_proxy: "_InlineProxy",
        *,
        original_call=None,
        inline_message_id: typing.Optional[str] = None,
        chat_id: typing.Optional[int] = None,
        message_id: typing.Optional[int] = None,
        from_user_id: typing.Optional[int] = None,
    ):
        self.data = call_data
        self.unit_id = unit_id
        self._inline_proxy = inline_proxy
        self.inline_manager = _resolve_inline_manager(inline_proxy)
        self.original_call = original_call
        self._answered = False
        self.inline_message_id = inline_message_id
        self.message = (
            BotMessage(chat_id, message_id, inline_proxy=inline_proxy, unit_id=unit_id)
            if chat_id is not None and message_id is not None
            else None
        )
        self.from_user = (
            types.SimpleNamespace(id=from_user_id) if from_user_id else None
        )

    async def answer(
        self,
        text: str = "",
        show_alert: bool = False,
        url: typing.Optional[str] = None,
    ) -> None:
        if self.original_call is not None and hasattr(self.original_call, "answer"):
            try:
                await self.original_call.answer(
                    text=text,
                    show_alert=show_alert,
                    url=url,
                )
                self._answered = True
                return
            except Exception as e:
                logger.debug("InlineCall.answer fallback due to error: %s", e)

        self._answered = True

    async def edit(
        self,
        text: typing.Optional[str] = None,
        *args,
        **kwargs,
    ) -> InlineMessage:
        msg = InlineMessage(
            inline_message_id=self.inline_message_id or "",
            unit_id=self.unit_id,
            inline_proxy=self._inline_proxy,
            chat_id=getattr(self.message, "chat_id", None),
            message_id=getattr(self.message, "message_id", None),
        )
        if text is not None:
            kwargs["text"] = text
        await msg.edit(*args, **kwargs)
        return msg

    async def delete(self) -> bool:
        if self.message:
            return await self.message.delete()
        return False

    async def unload(self) -> bool:
        msg = InlineMessage(
            inline_message_id=self.inline_message_id or "",
            unit_id=self.unit_id,
            inline_proxy=self._inline_proxy,
            chat_id=getattr(self.message, "chat_id", None),
            message_id=getattr(self.message, "message_id", None),
        )
        return await msg.unload()

    @property
    def answer_callback(self) -> typing.Callable[..., typing.Awaitable[None]]:
        return self.answer


class BotInlineCall(InlineCall):
    """Stub for bot callback queries"""

    pass


class BotInlineMessage(BotMessage):
    """Alias used by Heroku inline modules."""

    pass


class InlineUnit:
    """Base class for inline units"""

    pass


class InlineQuery:
    """Stub for inline queries"""

    def __init__(
        self,
        query_id: str,
        query: str,
        offset: str,
        user_id: int,
        inline_proxy: "_InlineProxy",
    ):
        self.query_id = query_id
        self.query = query
        self.offset = offset
        self.from_user = types.SimpleNamespace(id=user_id, username="")
        self._inline_proxy = inline_proxy
        self.args: str = ""
        self.inline_query = types.SimpleNamespace(
            query_id=query_id, query=query, offset=offset, from_user=self.from_user
        )

        if query:
            parts = query.split(maxsplit=1)
            if len(parts) > 1:
                self.args = parts[1]

    @property
    def id(self) -> str:
        return self.query_id

    async def answer(
        self,
        results: typing.List[dict],
        cache_time: int = 300,
    ) -> None:
        pass

    async def e400(self) -> None:
        await self.answer(
            [
                {
                    "title": "Bad request",
                    "description": "Invalid arguments",
                    "message": "Invalid request",
                }
            ],
            cache_time=0,
        )

    async def e403(self) -> None:
        await self.answer(
            [
                {
                    "title": "Forbidden",
                    "description": "No permissions",
                    "message": "You have no permissions",
                }
            ],
            cache_time=0,
        )

    async def e404(self) -> None:
        await self.answer(
            [
                {
                    "title": "Not found",
                    "description": "No results",
                    "message": "No results found",
                }
            ],
            cache_time=0,
        )

    async def e426(self) -> None:
        await self.answer(
            [
                {
                    "title": "Update required",
                    "description": "Update your userbot",
                    "message": "Update required",
                }
            ],
            cache_time=0,
        )

    async def e500(self) -> None:
        await self.answer(
            [
                {
                    "title": "Error",
                    "description": "Internal error",
                    "message": "Internal error occurred",
                }
            ],
            cache_time=0,
        )


class InlineResults:
    """Stub for inline query results"""

    pass


_inline_types_mod = types.ModuleType("__hikka_mcub_compat_inline_types__")
for _name, _val in {
    "InlineMessage": InlineMessage,
    "BotMessage": BotMessage,
    "BotInlineMessage": BotInlineMessage,
    "InlineCall": InlineCall,
    "BotInlineCall": BotInlineCall,
    "InlineUnit": InlineUnit,
    "InlineQuery": InlineQuery,
    "InlineResults": InlineResults,
}.items():
    setattr(_inline_types_mod, _name, _val)
