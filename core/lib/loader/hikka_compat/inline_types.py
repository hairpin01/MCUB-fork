import logging
import types
import typing

if typing.TYPE_CHECKING:
    from .runtime import _InlineProxy

logger = logging.getLogger(__name__)


class InlineMessage:
    """Stub for inline messages edited via inline bot"""

    def __init__(
        self,
        inline_message_id: str,
        unit_id: str,
        inline_proxy: "_InlineProxy",
    ):
        self.inline_message_id = inline_message_id
        self.unit_id = unit_id
        self._inline_proxy = inline_proxy

    async def edit(self, *args, **kwargs) -> "InlineMessage":
        return self

    async def delete(self) -> bool:
        return True

    async def unload(self) -> bool:
        return True


class BotMessage:
    """Stub for bot-sent messages"""

    def __init__(self, chat_id: int, message_id: int):
        self.chat_id = chat_id
        self.message_id = message_id

    async def edit(self, *args, **kwargs) -> "BotMessage":
        return self

    async def delete(self) -> bool:
        return True


class InlineCall:
    """Stub for inline callback queries"""

    def __init__(
        self,
        call_data: str,
        unit_id: str,
        inline_proxy: "_InlineProxy",
    ):
        self.data = call_data
        self.unit_id = unit_id
        self._inline_proxy = inline_proxy
        self._answered = False
        self.inline_message_id: typing.Optional[str] = None
        self.message: typing.Optional[BotMessage] = None

    async def answer(
        self,
        text: str = "",
        show_alert: bool = False,
        url: typing.Optional[str] = None,
    ) -> None:
        self._answered = True

    async def edit(
        self,
        text: typing.Optional[str] = None,
        *args,
        **kwargs,
    ) -> InlineMessage:
        return InlineMessage(
            self.inline_message_id or "",
            self.unit_id,
            self._inline_proxy,
        )

    @property
    def answer_callback(self) -> typing.Callable[..., typing.Awaitable[None]]:
        return self.answer


class BotInlineCall(InlineCall):
    """Stub for bot callback queries"""

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
    "InlineCall": InlineCall,
    "BotInlineCall": BotInlineCall,
    "InlineUnit": InlineUnit,
    "InlineQuery": InlineQuery,
    "InlineResults": InlineResults,
}.items():
    setattr(_inline_types_mod, _name, _val)
