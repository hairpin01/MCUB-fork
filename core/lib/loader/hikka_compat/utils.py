import asyncio
import contextlib
import functools
import html
import inspect
import os
import platform
import random
import re
import string
import subprocess
import time
import types
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

_PLACEHOLDERS: dict[str, dict] = {}
_INIT_TS = time.perf_counter()


def _looks_like_html(text: str) -> bool:
    return bool(re.search(r"</?[A-Za-z][^>]*>", text or ""))


def _split_html_text(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break

        chunk = remaining[:limit]
        cut = max(chunk.rfind("\n"), chunk.rfind(" "))
        if cut < limit // 4:
            cut = limit
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    return parts or [text]


class _Utils:
    @staticmethod
    async def answer(message, text: str = "", **kwargs):
        if "response" in kwargs and not text:
            text = kwargs.pop("response")
        reply_markup = kwargs.pop("reply_markup", None)
        parse_mode = kwargs.pop("parse_mode", "html")
        file = kwargs.pop("file", None)

        if file is not None:
            return await _Utils.answer_file(message, file, text, **kwargs)

        edit_kwargs = dict(kwargs)
        if reply_markup is not None:
            edit_kwargs.setdefault("reply_markup", reply_markup)
            edit_kwargs.setdefault("buttons", reply_markup)

        if hasattr(message, "edit") and callable(message.edit):
            try:
                return await message.edit(text, parse_mode=parse_mode, **edit_kwargs)
            except TypeError:
                edit_kwargs.pop("reply_markup", None)
                edit_kwargs.pop("reply_to", None)
                return await message.edit(text, parse_mode=parse_mode, **edit_kwargs)
            except Exception:
                pass

        send_kwargs = dict(kwargs)
        if reply_markup is not None:
            send_kwargs["buttons"] = reply_markup

        sender = getattr(message, "respond", None) or getattr(message, "reply", None)
        if callable(sender):
            chunks_ = _split_html_text(str(text or ""))
            result = None
            for part in chunks_:
                try:
                    result = await sender(part, parse_mode=parse_mode, **send_kwargs)
                except TypeError:
                    result = await sender(part, **send_kwargs)
            return result

        return None

    @staticmethod
    async def answer_file(message, file: Any, caption: Optional[str] = None, **kwargs):
        parse_mode = kwargs.pop("parse_mode", "html")
        if hasattr(message, "client") and hasattr(message, "chat_id"):
            return await message.client.send_file(
                message.chat_id,
                file,
                caption=caption,
                reply_to=getattr(message, "id", None),
                parse_mode=parse_mode,
                **kwargs,
            )
        kwargs["parse_mode"] = parse_mode
        return await _Utils.answer(message, caption or "", **kwargs)

    @staticmethod
    def get_args(message) -> list[str]:
        raw = _Utils.get_args_raw(message)
        return [item for item in raw.split() if item]

    @staticmethod
    def get_args_raw(message) -> str:
        text = getattr(message, "raw_text", None) or getattr(message, "text", "") or ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    @staticmethod
    def get_args_split_by(message, separator: str) -> list[str]:
        return [
            part.strip()
            for part in _Utils.get_args_raw(message).split(separator)
            if part.strip()
        ]

    @staticmethod
    def get_args_html(message) -> str:
        return html.escape(_Utils.get_args_raw(message))

    @staticmethod
    def get_chat_id(message) -> int:
        return getattr(message, "chat_id", 0)

    @staticmethod
    def escape_html(text: Any) -> str:
        return html.escape("" if text is None else str(text))

    @staticmethod
    def escape_non_html(text: Any) -> str:
        return html.escape(re.sub(r"<[^>]+>", "", "" if text is None else str(text)))

    @staticmethod
    def remove_html(text: Any) -> str:
        return re.sub(r"<[^>]+>", "", "" if text is None else str(text))

    @staticmethod
    def get_entity_url(entity, openmessage: bool = False) -> str:
        if entity is None:
            return ""
        username = getattr(entity, "username", None)
        if username:
            return f"tg://resolve?domain={username}"
        uid = getattr(entity, "id", entity) if not isinstance(entity, int) else entity
        if uid:
            return (
                f"tg://openmessage?id={uid}" if openmessage else f"tg://user?id={uid}"
            )
        return ""

    @staticmethod
    def get_lang_flag(countrycode: str) -> str:
        if not countrycode:
            return ""
        code = [
            c for c in countrycode.lower() if c in string.ascii_letters + string.digits
        ]
        if len(code) == 2:
            return "".join([chr(ord(c.upper()) + (ord("🇦") - ord("A"))) for c in code])
        return countrycode

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

        raw = args or _Utils.get_args_raw(message)
        if raw and hasattr(message, "client"):
            try:
                return await message.client.get_entity(raw)
            except Exception:
                return None
        return None

    @staticmethod
    def run_sync(func, *args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(
            None, functools.partial(func, *args, **kwargs)
        )

    @staticmethod
    def rand(size: int, /) -> str:
        return "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(size)
        )

    @staticmethod
    def chunks(_list: Iterable, n: int, /) -> list[list[Any]]:
        _list = list(_list)
        return [_list[index : index + n] for index in range(0, len(_list), n)]

    @staticmethod
    def array_sum(array: list[list[Any]], /) -> list[Any]:
        result = []
        for item in array:
            result.extend(item)
        return result

    @staticmethod
    def check_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        return bool(parsed.scheme and parsed.netloc)

    @staticmethod
    def smart_split(
        text: str,
        entities=None,
        length: int = 4096,
        split_on: tuple[str, ...] = ("\n", " "),
        min_length: int = 1,
    ):
        del entities, min_length
        if not text:
            yield ""
            return

        remaining = text
        while remaining:
            if len(remaining) <= length:
                yield remaining
                break
            chunk = remaining[:length]
            cut = max(chunk.rfind(split_on[0]), chunk.rfind(split_on[-1]))
            if cut <= 0:
                cut = length
            yield remaining[:cut]
            remaining = remaining[cut:].lstrip()

    @staticmethod
    def get_kwargs() -> dict:
        frame = inspect.currentframe()
        if frame is None or frame.f_back is None:
            return {}
        return {
            key: value for key, value in frame.f_back.f_locals.items() if key != "self"
        }

    @staticmethod
    def register_placeholder(
        placeholder: str,
        callback,
        description: Optional[str] = None,
    ):
        module_name = getattr(
            getattr(callback, "__self__", None), "__class__", type("X", (), {})
        ).__name__
        _PLACEHOLDERS[placeholder] = {
            "module_name": module_name,
            "callback": callback,
            "description": description,
        }
        return True

    @staticmethod
    async def get_placeholders(data, custom_message):
        if custom_message is None:
            return data
        for placeholder, placeholder_data in _PLACEHOLDERS.items():
            if f"{{{placeholder}}}" not in custom_message:
                continue
            callback = placeholder_data["callback"]
            try:
                value = await callback(data)
            except TypeError:
                value = await callback()
            data[placeholder] = str(value)
        return data

    @staticmethod
    def unregister_placeholders(module_name: str) -> int:
        to_remove = [
            name
            for name, data in _PLACEHOLDERS.items()
            if data.get("module_name") == module_name
        ]
        for name in to_remove:
            _PLACEHOLDERS.pop(name, None)
        return len(to_remove)

    @staticmethod
    def config_placeholders():
        if not _PLACEHOLDERS:
            return None
        return "\n".join(
            f"{{{name}}} - {data.get('description') or 'No docs'}"
            for name, data in _PLACEHOLDERS.items()
        )

    @staticmethod
    def help_placeholders(module_name, self):
        prefix = "• "
        try:
            prefix = self.db.get("Help", "__config__", None).get("command_emoji")
        except Exception:
            pass
        return [
            f"{prefix} {{{name}}} - {data.get('description') or 'No docs'}"
            for name, data in _PLACEHOLDERS.items()
            if data.get("module_name") == module_name
        ]

    @staticmethod
    def get_base_dir() -> str:
        return str(Path.cwd())

    @staticmethod
    def formatted_uptime() -> str:
        total_seconds = round(time.perf_counter() - _INIT_TS)
        days, remainder = divmod(total_seconds, 86400)
        uptime = str(timedelta(seconds=remainder))
        return f"{days} day(s), {uptime}" if days else uptime

    @staticmethod
    def get_ram_usage() -> float:
        try:
            import psutil

            proc = psutil.Process(os.getpid())
            mem = proc.memory_info().rss / 2.0**20
            for child in proc.children(recursive=True):
                mem += child.memory_info().rss / 2.0**20
            return round(mem, 1)
        except Exception:
            return 0.0

    @staticmethod
    def get_cpu_usage() -> str:
        try:
            import psutil

            return f"{psutil.cpu_percent(interval=0.1):.2f}"
        except Exception:
            return "0.00"

    @staticmethod
    def get_platform_name() -> str:
        return _Utils.get_named_platform()

    @staticmethod
    def get_named_platform() -> str:
        system = platform.system()
        if "LAVHOST" in os.environ:
            return f"lavHost {os.environ['LAVHOST']}"
        if system == "Windows":
            return "Windows"
        if system == "Darwin":
            return "MacOS"
        if "DOCKER" in os.environ:
            return "Docker"
        return system or "VDS"

    @staticmethod
    def get_platform_emoji() -> str:
        return "🪐"

    @staticmethod
    def get_named_platform_emoji() -> str:
        mapping = {
            "Windows": "💻 ",
            "MacOS": "🍏 ",
            "Docker": "🐳 ",
        }
        return mapping.get(_Utils.get_named_platform(), "💎 ")

    @staticmethod
    def get_git_hash() -> str | bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=3,
                cwd=Path.cwd(),
            )
            return result.stdout.strip() if result.returncode == 0 else False
        except Exception:
            return False

    @staticmethod
    def get_commit_url() -> str:
        hash_ = _Utils.get_git_hash()
        if not hash_:
            return "Unknown"
        return f"#{str(hash_)[:7]}"

    @staticmethod
    def get_git_status() -> str:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=Path.cwd(),
            )
            if result.returncode != 0:
                return "Not a Git repo"
            lines = result.stdout.strip().splitlines()
            if not lines:
                return "Clean"
            count = len(lines)
            word = "file" if count == 1 else "files"
            return f"{count} {word} modified"
        except Exception:
            return "Unknown"

    @staticmethod
    def is_up_to_date() -> bool:
        try:
            status = subprocess.run(
                ["git", "status", "-sb"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=Path.cwd(),
            )
            output = status.stdout.lower()
            return "ahead" not in output and "behind" not in output
        except Exception:
            return True

    @staticmethod
    def ascii_face() -> str:
        return random.choice(["(•_•)", "ಠ_ಠ", "(◕‿◕✿)", "ʕ•ᴥ•ʔ"])

    @staticmethod
    def get_topic(message) -> Optional[int]:
        reply_to = getattr(message, "reply_to", None)
        if reply_to:
            return getattr(reply_to, "reply_to_top_id", None) or getattr(
                reply_to, "reply_to_msg_id", None
            )
        return None

    @staticmethod
    async def wait_for_content_channel(db, timeout: int = 0):
        del timeout
        if hasattr(db, "get"):
            return db.get("heroku.forums", "channel_id", None)
        return None

    @staticmethod
    async def get_topic_id(db, topic_name: str):
        if hasattr(db, "get"):
            topics = db.get("heroku.forums", "topics", {}) or {}
            return topics.get(topic_name)
        return None

    @staticmethod
    async def invite_inline_bot(client, peer):
        del client, peer
        return True

    @staticmethod
    async def asset_channel(
        client,
        title: str,
        description: str,
        *,
        channel: bool = False,
        silent: bool = False,
        archive: bool = False,
        invite_bot: bool = False,
        avatar: Optional[str] = None,
        ttl: Optional[int] = None,
        forum: bool = False,
        hide_general: bool = False,
        _folder: Optional[str] = None,
    ) -> tuple[Any, bool]:
        del silent, avatar, _folder

        if client is None:
            return None, False

        cache = getattr(client, "_channels_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            with contextlib.suppress(Exception):
                setattr(client, "_channels_cache", cache)

        cached = cache.get(title)
        if cached and cached.get("exp", 0) > time.time():
            return cached.get("peer"), False

        with contextlib.suppress(Exception):
            async for dialog in client.iter_dialogs():
                dialog_title = getattr(dialog, "title", None) or getattr(
                    getattr(dialog, "entity", None), "title", None
                )
                if dialog_title != title:
                    continue

                peer = getattr(dialog, "entity", None) or dialog
                cache[title] = {"peer": peer, "exp": time.time() + 300}
                if invite_bot:
                    with contextlib.suppress(Exception):
                        await _Utils.invite_inline_bot(client, peer)
                return peer, False

        peer = None
        with contextlib.suppress(Exception):
            from telethon.tl.functions.channels import CreateChannelRequest

            result = await client(
                CreateChannelRequest(
                    title=title,
                    about=description,
                    megagroup=not channel,
                    forum=forum,
                )
            )
            for attr in ("chats", "chat", "channel", "peer"):
                value = getattr(result, attr, None)
                if isinstance(value, list) and value:
                    peer = value[0]
                    break
                if value is not None:
                    peer = value
                    break

        if peer is None:
            return None, False

        if invite_bot:
            with contextlib.suppress(Exception):
                await _Utils.invite_inline_bot(client, peer)

        if archive and hasattr(client, "edit_folder"):
            with contextlib.suppress(Exception):
                await client.edit_folder(peer, 1)

        if ttl:
            with contextlib.suppress(Exception):
                from telethon.tl.functions.messages import SetHistoryTTLRequest

                await client(SetHistoryTTLRequest(peer=peer, period=ttl))

        if hide_general and forum:
            with contextlib.suppress(Exception):
                from telethon.tl.functions.messages import EditForumTopicRequest

                await client(EditForumTopicRequest(peer=peer, topic_id=1, hidden=True))

        cache[title] = {"peer": peer, "exp": time.time() + 300}
        return peer, True

    @staticmethod
    async def asset_forum_topic(
        client,
        db,
        peer,
        title: str,
        description: Optional[str] = None,
        icon_emoji_id: Optional[int] = None,
        invite_bot: bool = False,
    ):
        del invite_bot

        if client is None:
            return None

        entity = peer
        if hasattr(client, "get_entity"):
            with contextlib.suppress(Exception):
                entity = await client.get_entity(peer)

        entity_id = getattr(entity, "id", peer)
        forums_cache = {}
        if hasattr(db, "pointer"):
            with contextlib.suppress(Exception):
                forums_cache = db.pointer("heroku.forums", "forums_cache", {})
        elif hasattr(db, "get"):
            forums_cache = db.get("heroku.forums", "forums_cache", {}) or {}

        entity_key = str(entity_id)
        cached_topic_id = forums_cache.get(entity_key, {}).get(title)
        if cached_topic_id:
            return types.SimpleNamespace(id=cached_topic_id, title=title, peer=entity)

        with contextlib.suppress(Exception):
            from telethon.tl.functions.messages import GetForumTopicsRequest

            result = await client(
                GetForumTopicsRequest(
                    peer=entity,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )
            for topic in getattr(result, "topics", []) or []:
                if getattr(topic, "title", None) != title:
                    continue
                forums_cache.setdefault(entity_key, {})[title] = getattr(
                    topic, "id", None
                )
                return topic

        topic_id = None
        with contextlib.suppress(Exception):
            from telethon.tl.functions.messages import CreateForumTopicRequest

            result = await client(
                CreateForumTopicRequest(
                    peer=entity,
                    title=title,
                    icon_emoji_id=icon_emoji_id,
                )
            )
            topic_id = (
                getattr(result, "id", None)
                or getattr(getattr(result, "topic", None), "id", None)
                or getattr(getattr(result, "updates", [None])[0], "id", None)
            )

        if topic_id is None:
            return None

        forums_cache.setdefault(entity_key, {})[title] = topic_id
        if hasattr(db, "set"):
            with contextlib.suppress(Exception):
                db.set("heroku.forums", "forums_cache", forums_cache)

        if description and hasattr(client, "send_message"):
            with contextlib.suppress(Exception):
                await client.send_message(
                    entity=entity,
                    message=description,
                    reply_to=topic_id,
                )

        with contextlib.suppress(Exception):
            from telethon.tl.functions.messages import GetForumTopicsByIDRequest

            result = await client(
                GetForumTopicsByIDRequest(peer=entity, topics=[topic_id])
            )
            topics = getattr(result, "topics", None) or []
            if topics:
                return topics[0]

        return types.SimpleNamespace(id=topic_id, title=title, peer=entity)


answer = _Utils.answer
answer_file = _Utils.answer_file
get_args = _Utils.get_args
get_args_raw = _Utils.get_args_raw
get_args_split_by = _Utils.get_args_split_by
get_args_html = _Utils.get_args_html
get_chat_id = _Utils.get_chat_id
escape_html = _Utils.escape_html
escape_non_html = _Utils.escape_non_html
remove_html = _Utils.remove_html
get_link = _Utils.get_link
mention = _Utils.mention
get_user = _Utils.get_user
get_target = _Utils.get_target
run_sync = _Utils.run_sync
rand = _Utils.rand
chunks = _Utils.chunks
array_sum = _Utils.array_sum
check_url = _Utils.check_url
smart_split = _Utils.smart_split
get_kwargs = _Utils.get_kwargs
register_placeholder = _Utils.register_placeholder
get_placeholders = _Utils.get_placeholders
unregister_placeholders = _Utils.unregister_placeholders
config_placeholders = _Utils.config_placeholders
help_placeholders = _Utils.help_placeholders
get_base_dir = _Utils.get_base_dir
formatted_uptime = _Utils.formatted_uptime
get_ram_usage = _Utils.get_ram_usage
get_cpu_usage = _Utils.get_cpu_usage
get_platform_name = _Utils.get_platform_name
get_named_platform = _Utils.get_named_platform
get_platform_emoji = _Utils.get_platform_emoji
get_named_platform_emoji = _Utils.get_named_platform_emoji
get_git_hash = _Utils.get_git_hash
get_commit_url = _Utils.get_commit_url
get_git_status = _Utils.get_git_status
ascii_face = _Utils.ascii_face
get_topic = _Utils.get_topic
wait_for_content_channel = _Utils.wait_for_content_channel
get_topic_id = _Utils.get_topic_id
invite_inline_bot = _Utils.invite_inline_bot
get_entity_url = _Utils.get_entity_url
get_lang_flag = _Utils.get_lang_flag
is_up_to_date = _Utils.is_up_to_date
asset_channel = _Utils.asset_channel
asset_forum_topic = _Utils.asset_forum_topic


class _UtilsModule:
    answer = staticmethod(_Utils.answer)
    answer_file = staticmethod(_Utils.answer_file)
    get_args = staticmethod(_Utils.get_args)
    get_args_raw = staticmethod(_Utils.get_args_raw)
    get_args_split_by = staticmethod(_Utils.get_args_split_by)
    get_args_html = staticmethod(_Utils.get_args_html)
    get_chat_id = staticmethod(_Utils.get_chat_id)
    escape_html = staticmethod(_Utils.escape_html)
    escape_non_html = staticmethod(_Utils.escape_non_html)
    remove_html = staticmethod(_Utils.remove_html)
    get_link = staticmethod(_Utils.get_link)
    mention = staticmethod(_Utils.mention)
    get_user = staticmethod(_Utils.get_user)
    get_target = staticmethod(_Utils.get_target)
    run_sync = staticmethod(_Utils.run_sync)
    rand = staticmethod(_Utils.rand)
    chunks = staticmethod(_Utils.chunks)
    array_sum = staticmethod(_Utils.array_sum)
    check_url = staticmethod(_Utils.check_url)
    smart_split = staticmethod(_Utils.smart_split)
    get_kwargs = staticmethod(_Utils.get_kwargs)
    register_placeholder = staticmethod(_Utils.register_placeholder)
    get_placeholders = staticmethod(_Utils.get_placeholders)
    unregister_placeholders = staticmethod(_Utils.unregister_placeholders)
    config_placeholders = staticmethod(_Utils.config_placeholders)
    help_placeholders = staticmethod(_Utils.help_placeholders)
    get_base_dir = staticmethod(_Utils.get_base_dir)
    formatted_uptime = staticmethod(_Utils.formatted_uptime)
    get_ram_usage = staticmethod(_Utils.get_ram_usage)
    get_cpu_usage = staticmethod(_Utils.get_cpu_usage)
    get_platform_name = staticmethod(_Utils.get_platform_name)
    get_named_platform = staticmethod(_Utils.get_named_platform)
    get_platform_emoji = staticmethod(_Utils.get_platform_emoji)
    get_named_platform_emoji = staticmethod(_Utils.get_named_platform_emoji)
    get_git_hash = staticmethod(_Utils.get_git_hash)
    get_commit_url = staticmethod(_Utils.get_commit_url)
    get_git_status = staticmethod(_Utils.get_git_status)
    is_up_to_date = staticmethod(_Utils.is_up_to_date)
    ascii_face = staticmethod(_Utils.ascii_face)
    get_topic = staticmethod(_Utils.get_topic)
    wait_for_content_channel = staticmethod(_Utils.wait_for_content_channel)
    get_topic_id = staticmethod(_Utils.get_topic_id)
    invite_inline_bot = staticmethod(_Utils.invite_inline_bot)
    get_entity_url = staticmethod(_Utils.get_entity_url)
    get_lang_flag = staticmethod(_Utils.get_lang_flag)
    asset_channel = staticmethod(_Utils.asset_channel)
    asset_forum_topic = staticmethod(_Utils.asset_forum_topic)


utils = _UtilsModule()
