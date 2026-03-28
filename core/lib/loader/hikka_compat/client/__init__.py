import typing


class FakeClient:
    """Wrapper for TelegramClient to add default parse_mode='html' for hikka modules."""

    def __init__(self, client, inline_proxy=None):
        self._client = client
        self._inline_proxy = inline_proxy
        self._patched = getattr(client, "_hikka_compat_patched", False)
        if not self._patched:
            self._patch()

    def _patch(self):
        client = self._client
        client.parse_mode = "html"
        client._hikka_compat_patched = True
        self._patched = True

    async def send_message(
        self,
        entity: typing.Any,
        message: str = "",
        *args,
        **kwargs,
    ) -> typing.Any:
        if "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "html"
        return await self._client.send_message(entity, message, *args, **kwargs)

    async def send_file(
        self,
        entity: typing.Any,
        file: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "html"
        return await self._client.send_file(entity, file, *args, **kwargs)

    async def edit_message(
        self,
        entity: typing.Any,
        message: typing.Any = None,
        *args,
        **kwargs,
    ) -> typing.Any:
        if "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "html"
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
