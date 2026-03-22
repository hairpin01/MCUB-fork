import asyncio
import html
import types
from typing import Any, Callable, Optional


class _TranslatorStub:
    def __init__(self, lang: str = "en"):
        self._lang = lang
        self._data: dict = {}

    def getkey(self, key: str) -> Any:
        return self._data.get(key, False)

    def gettext(self, text: str) -> str:
        return self._data.get(text, text)

    def get(self, key: str, lang: str = "en") -> str:
        return self._data.get(key, key)

    def getdict(self, key: str, **kwargs) -> dict:
        base = self._data.get(key, key)
        return {"en": _fmt(base, kwargs)}

    @property
    def raw_data(self) -> dict:
        return {"en": self._data}


def _fmt(text: str, kwargs: dict) -> str:
    for k, v in kwargs.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text


_translator_stub = _TranslatorStub()


class _CallableStringsDict(dict):
    def __call__(self, key: str, _=None) -> str:
        return self.get(key, key)


class _StringsShim:
    def __init__(self, mod, translator=None):
        self._mod = mod
        self._translator = translator
        self._base = getattr(mod, "strings", {})
        self.external_strings: dict = {}

    def get(self, key: str, lang: Optional[str] = None) -> str:
        return self[key]

    def __getitem__(self, key: str) -> str:
        if key in self.external_strings:
            return self.external_strings[key]
        if self._translator is not None:
            try:
                lang = getattr(self._translator, "_lang", "en")
                lang_dict = getattr(self._mod, f"strings_{lang}", {})
                if key in lang_dict:
                    return lang_dict[key]
            except Exception:
                pass
        return self._base.get(key, f"Unknown strings: {key}")

    def __call__(self, key: str, _=None) -> str:
        return self.__getitem__(key)

    def __iter__(self):
        return iter(self._base)


class DbProxy:
    def __init__(self, kernel, module_name: str):
        self._kernel = kernel
        self._module_name = module_name
        self._mem: dict[str, Any] = {}

    def _mem_key(self, module: str, key: str) -> str:
        return f"{module}:{key}"

    def _schedule_write(self, module: str, key: str, value: Any) -> None:
        if not getattr(self._kernel, "db_manager", None):
            return

        async def _write():
            try:
                await self._kernel.db_set(module, key, value)
            except Exception as e:
                self._kernel.logger.warning(
                    f"[hikka_compat] DbProxy write failed ({module}.{key}): {e}"
                )

        try:
            asyncio.get_event_loop().create_task(_write())
        except RuntimeError:
            pass

    def set(self, module: str, key: str, value: Any) -> None:
        self._mem[self._mem_key(module, key)] = value
        self._schedule_write(module, key, value)

    def get(self, module: str, key: str, default: Any = None) -> Any:
        mk = self._mem_key(module, key)
        if mk in self._mem:
            return self._mem[mk]
        return default

    async def async_get(self, module: str, key: str, default: Any = None) -> Any:
        mk = self._mem_key(module, key)
        if mk in self._mem:
            return self._mem[mk]
        try:
            result = await self._kernel.db_get(module, key)
            if result is not None:
                self._mem[mk] = result
                return result
        except Exception as e:
            self._kernel.logger.warning(
                f"[hikka_compat] DbProxy async_get failed ({module}.{key}): {e}"
            )
        return default

    async def async_set(self, module: str, key: str, value: Any) -> None:
        self._mem[self._mem_key(module, key)] = value
        try:
            await self._kernel.db_set(module, key, value)
        except Exception as e:
            self._kernel.logger.warning(
                f"[hikka_compat] DbProxy async_set failed ({module}.{key}): {e}"
            )

    async def preload(self, module: str, *keys: str) -> None:
        for key in keys:
            await self.async_get(module, key)


class InlineProxy:
    def __init__(self, kernel):
        self._kernel = kernel

    async def form(self, text: str, *, reply_markup=None, message=None, **kwargs):
        if message is None:
            return None

        if self._kernel._inline and hasattr(self._kernel._inline, "form"):
            try:
                return await self._kernel._inline.form(
                    message.chat_id,
                    text,
                    buttons=reply_markup,
                    auto_send=True,
                )
            except Exception as e:
                self._kernel.logger.debug(
                    f"[hikka_compat] InlineProxy.form() via _inline failed: {e}"
                )

        return await self._plain_send(message, text)

    async def list(self, text: str, *, strings: list[str] = None, message=None, **kwargs):
        body = text
        if strings:
            body = text + "\n" + "\n".join(f"• {s}" for s in strings)
        return await self._plain_send(message, body) if message else None

    async def gallery(self, *args, message=None, **kwargs):
        if message:
            return await self._plain_send(
                message, "⚠️ Gallery requires full Heroku/Hikka inline support."
            )

    @staticmethod
    async def _plain_send(message, text: str):
        try:
            return await message.edit(text, parse_mode="html")
        except Exception:
            try:
                return await message.respond(text, parse_mode="html")
            except Exception:
                return None


def _get_members(mod, ending: str, attribute: Optional[str] = None,
                 strict: bool = False) -> dict:
    result = {}
    for method_name in dir(type(mod)):
        if isinstance(getattr(type(mod), method_name, None), property):
            continue
        method = getattr(mod, method_name, None)
        if not callable(method):
            continue
        matches_ending = (method_name == ending) if strict else method_name.endswith(ending)
        matches_attr = bool(attribute and getattr(method, attribute, False))
        if not matches_ending and not matches_attr:
            continue
        key = (
            method_name.rsplit(ending, maxsplit=1)[0] if matches_ending else method_name
        ).lower()
        if not key:
            key = method_name.lower()
        result[key] = method
    return result


class _AllModulesStub:
    def __init__(self, kernel):
        self._kernel = kernel
        self.db = getattr(kernel, "db_manager", None)
        self.client = kernel.client
        self.inline = None
        self.allclients = [kernel.client]
        self.libraries: list = []

    def lookup(self, name: str):
        loaded: dict = getattr(self._kernel, "loaded_modules", {})
        for inst in loaded.values():
            raw = type(inst).__dict__.get("strings", {})
            if raw.get("name") == name:
                return inst
        return None

    def get_prefix(self) -> str:
        return getattr(self._kernel, "custom_prefix", ".")

    def get_prefixes(self) -> list:
        return [self.get_prefix()]

    @property
    def commands(self) -> dict:
        result = {}
        for inst in getattr(self._kernel, "loaded_modules", {}).values():
            result.update(_get_members(inst, "cmd", "is_command"))
        return result


class Module:
    strings: dict = {"name": "UnknownHikkaModule"}
    strings_ru: dict = {}
    strings_en: dict = {}

    def __init__(self):
        pass

    def _mcub_bind(self, kernel) -> None:
        self._kernel = kernel
        self.client = kernel.client
        self._client = kernel.client
        _raw_strings = type(self).__dict__.get("strings", {"name": type(self).__name__})
        self.db = DbProxy(kernel, _raw_strings.get("name", type(self).__name__))
        self._db = self.db
        self.inline = InlineProxy(kernel)
        self.tg_id = getattr(kernel, "ADMIN_ID", None)
        self._tg_id = self.tg_id
        self.allmodules = _AllModulesStub(kernel)
        self.strings = _StringsShim(self, _translator_stub)
        self.translator = _translator_stub

    def get(self, key: str, default=None):
        return self._db.get(type(self).__name__, key, default)

    def set(self, key: str, value) -> None:
        self._db.set(type(self).__name__, key, value)

    def pointer(self, key: str, default=None):
        return self._db.get(type(self).__name__, key, default)

    @property
    def commands(self) -> dict:
        return _get_members(self, "cmd", "is_command")

    @property
    def heroku_commands(self) -> dict:
        return self.commands

    @property
    def inline_handlers(self) -> dict:
        return _get_members(self, "_inline_handler", "is_inline_handler")

    @property
    def heroku_inline_handlers(self) -> dict:
        return self.inline_handlers

    @property
    def callback_handlers(self) -> dict:
        return _get_members(self, "_callback_handler", "is_callback_handler")

    @property
    def heroku_callback_handlers(self) -> dict:
        return self.callback_handlers

    @property
    def watchers(self) -> dict:
        return _get_members(self, "watcher", "is_watcher", strict=True)

    @property
    def heroku_watchers(self) -> dict:
        return self.watchers

    @commands.setter
    def commands(self, _): pass
    @heroku_commands.setter
    def heroku_commands(self, _): pass
    @inline_handlers.setter
    def inline_handlers(self, _): pass
    @heroku_inline_handlers.setter
    def heroku_inline_handlers(self, _): pass
    @callback_handlers.setter
    def callback_handlers(self, _): pass
    @heroku_callback_handlers.setter
    def heroku_callback_handlers(self, _): pass
    @watchers.setter
    def watchers(self, _): pass
    @heroku_watchers.setter
    def heroku_watchers(self, _): pass

    def get_prefix(self) -> str:
        return getattr(self._kernel, "custom_prefix", ".")

    def get_prefixes(self) -> list:
        return [self.get_prefix()]

    def lookup(self, module_name: str) -> Optional["Module"]:
        loaded: dict = getattr(self._kernel, "loaded_modules", {})
        for inst in loaded.values():
            raw = type(inst).__dict__.get("strings", {})
            if raw.get("name") == module_name:
                return inst
        return None

    def get_string(self, key: str) -> str:
        return self.strings.get(key) or key

    async def animate(self, message, frames: list, interval: float, *, inline: bool = False):
        import asyncio as _asyncio
        if interval < 0.1:
            interval = 0.1
        for frame in frames:
            try:
                if inline and hasattr(message, "edit"):
                    await message.edit(frame)
                else:
                    message = await _Utils.answer(message, frame)
            except Exception:
                pass
            await _asyncio.sleep(interval)
        return message

    async def invoke(self, command: str, args: Optional[str] = None,
                     peer=None, message=None, edit: bool = False):
        all_cmds = self.allmodules.commands if hasattr(self, "allmodules") else {}
        if command not in all_cmds:
            raise ValueError(f"Command {command!r} not found")
        cmd_text = f"{self.get_prefix()}{command} {args or ''}".strip()
        if peer:
            message = await self._client.send_message(peer, cmd_text)
        elif message:
            message = await (message.edit if edit else message.respond)(cmd_text)
        await all_cmds[command](message)
        return message

    def config_complete(self): pass
    async def on_load(self) -> None: pass
    async def on_unload(self) -> None: pass
    async def on_dlmod(self) -> None: pass

    async def client_ready(self, client=None, db=None) -> None:
        pass


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
        import re
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


utils = _Utils()


class Library:
    def internal_init(self):
        self.name = self.__class__.__name__
        self.db = self.allmodules.db
        self._db = self.allmodules.db
        self.client = self.allmodules.client
        self._client = self.allmodules.client
        self.tg_id = self._client.tg_id
        self._tg_id = self._client.tg_id
        self.lookup = self.allmodules.lookup
        self.get_prefix = self.allmodules.get_prefix
        self.get_prefixes = self.allmodules.get_prefixes
        self.inline = self.allmodules.inline
        self.allclients = self.allmodules.allclients

    def _lib_get(self, key: str, default=None):
        return self._db.get(self.__class__.__name__, key, default)

    def _lib_set(self, key: str, value) -> None:
        self._db.set(self.__class__.__name__, key, value)

    def _lib_pointer(self, key: str, default=None):
        return self._db.get(self.__class__.__name__, key, default)
