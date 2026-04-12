import typing


class FakeClient:
    """Wrapper for TelegramClient.

    For hikka modules: injects parse_mode='html' per-call without touching the
    underlying client object (so native mcub modules that share the same
    kernel.client are not affected).
    """

    def __init__(self, client, inline_proxy=None, is_hikka: bool = False):
        self._client = client
        self._inline_proxy = inline_proxy
        self._is_hikka = is_hikka
        # per-instance default; never written to the real Telethon client
        self._default_parse_mode: typing.Optional[str] = "html" if is_hikka else None

    async def send_message(
        self,
        entity: typing.Any,
        message: str = "",
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._default_parse_mode is not None and "parse_mode" not in kwargs:
            kwargs["parse_mode"] = self._default_parse_mode
        return await self._client.send_message(entity, message, *args, **kwargs)

    async def send_file(
        self,
        entity: typing.Any,
        file: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._default_parse_mode is not None and "parse_mode" not in kwargs:
            caption = kwargs.pop("caption", None) or kwargs.pop("message", None)
            if caption:
                return await self._client.send_file(
                    entity,
                    file,
                    *args,
                    caption=caption,
                    parse_mode=self._default_parse_mode,
                    **kwargs,
                )
            kwargs["parse_mode"] = self._default_parse_mode
        return await self._client.send_file(entity, file, *args, **kwargs)

    async def edit_message(
        self,
        entity: typing.Any,
        message: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._default_parse_mode is not None and "parse_mode" not in kwargs:
            kwargs["parse_mode"] = self._default_parse_mode
        return await self._client.edit_message(entity, message, *args, **kwargs)

    async def forward_messages(
        self,
        entity: typing.Any,
        messages: typing.Any,
        *args,
        **kwargs,
    ) -> typing.Any:
        return await self._client.forward_messages(entity, messages, *args, **kwargs)

    async def form(
        self,
        text: str,
        message: typing.Any = None,
        reply_markup: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._inline_proxy and hasattr(self._inline_proxy, "form"):
            return await self._inline_proxy.form(
                text, message, reply_markup, *args, **kwargs
            )
        return False

    async def list(
        self,
        text: str,
        message: typing.Any = None,
        reply_markup: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._inline_proxy and hasattr(self._inline_proxy, "list"):
            return await self._inline_proxy.list(
                text, message, reply_markup, *args, **kwargs
            )
        return False

    async def gallery(
        self,
        text: str,
        message: typing.Any = None,
        reply_markup: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._inline_proxy and hasattr(self._inline_proxy, "gallery"):
            return await self._inline_proxy.gallery(
                text, message, reply_markup, *args, **kwargs
            )
        return False

    async def query(
        self,
        bot: typing.Any,
        query: str,
        *args,
        **kwargs,
    ) -> typing.Any:
        if self._inline_proxy and hasattr(self._inline_proxy, "query"):
            return await self._inline_proxy.query(bot, query, *args, **kwargs)
        return False

    async def animate(
        self,
        message: typing.Any,
        frames: typing.List[str],
        interval: float = 1.0,
        *args,
        **kwargs,
    ) -> typing.Any:
        import asyncio

        for frame in frames:
            try:
                await self.edit_message(message, frame, *args, **kwargs)
            except Exception:
                pass
            await asyncio.sleep(interval)
        return message

    async def invoke(
        self,
        command: str,
        args: str = None,
        *args_,
        **kwargs,
    ) -> typing.Any:
        return False

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._client, name)
