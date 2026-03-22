import asyncio
import functools
import html
import re
from typing import Optional


class _Utils:
    @staticmethod
    async def answer(message, text: str, **kwargs) -> None:
        parse_mode = kwargs.pop("parse_mode", "html")
        try:
            await message.edit(text, parse_mode=parse_mode, **kwargs)
        except Exception:
            try:
                await message.respond(text, parse_mode=parse_mode, **kwargs)
            except Exception:
                pass

    @staticmethod
    def get_args(message) -> str:
        text = getattr(message, "text", "") or ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    @staticmethod
    def get_args_raw(message) -> str:
        return _Utils.get_args(message)

    @staticmethod
    def get_args_split_by(message, separator: str) -> list[str]:
        raw = _Utils.get_args(message)
        return [p.strip() for p in raw.split(separator) if p.strip()]

    @staticmethod
    def get_args_html(message) -> str:
        return html.escape(_Utils.get_args(message))

    @staticmethod
    def get_chat_id(message) -> int:
        return getattr(message, "chat_id", 0)

    @staticmethod
    def escape_html(text: str) -> str:
        return html.escape(str(text))

    @staticmethod
    def remove_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", str(text))

    @staticmethod
    def get_link(user) -> str:
        if hasattr(user, "username") and user.username:
            return f"https://t.me/{user.username}"
        uid = getattr(user, "id", user) if not isinstance(user, int) else user
        return f"tg://user?id={uid}"

    @staticmethod
    def mention(user, name: Optional[str] = None) -> str:
        uid = getattr(user, "id", None)
        display = name or getattr(user, "first_name", None) or str(uid or "?")
        if uid:
            return f'<a href="tg://user?id={uid}">{html.escape(display)}</a>'
        return html.escape(display)

    @staticmethod
    async def get_user(message):
        try:
            return await message.get_sender()
        except Exception:
            return None

    @staticmethod
    async def get_target(message, args: Optional[str] = None):
        try:
            reply = await message.get_reply_message()
            if reply:
                return await reply.get_sender()
        except Exception:
            pass

        raw = args or _Utils.get_args(message)
        if raw:
            try:
                client = message.client
                return await client.get_entity(raw)
            except Exception:
                pass
        return None

    @staticmethod
    def run_sync(func, *args, **kwargs):
        """Run a non-async function in a new thread and return an awaitable."""
        return asyncio.get_event_loop().run_in_executor(
            None,
            functools.partial(func, *args, **kwargs),
        )


answer = _Utils.answer
get_args = _Utils.get_args
get_args_raw = _Utils.get_args_raw
get_args_split_by = _Utils.get_args_split_by
get_args_html = _Utils.get_args_html
get_chat_id = _Utils.get_chat_id
escape_html = _Utils.escape_html
remove_html = _Utils.remove_html
get_link = _Utils.get_link
mention = _Utils.mention
get_user = _Utils.get_user
get_target = _Utils.get_target
run_sync = _Utils.run_sync


class _UtilsModule:
    answer = staticmethod(_Utils.answer)
    get_args = staticmethod(_Utils.get_args)
    get_args_raw = staticmethod(_Utils.get_args_raw)
    get_args_split_by = staticmethod(_Utils.get_args_split_by)
    get_args_html = staticmethod(_Utils.get_args_html)
    get_chat_id = staticmethod(_Utils.get_chat_id)
    escape_html = staticmethod(_Utils.escape_html)
    remove_html = staticmethod(_Utils.remove_html)
    get_link = staticmethod(_Utils.get_link)
    mention = staticmethod(_Utils.mention)
    get_user = staticmethod(_Utils.get_user)
    get_target = staticmethod(_Utils.get_target)
    run_sync = staticmethod(_Utils.run_sync)


utils = _UtilsModule()
