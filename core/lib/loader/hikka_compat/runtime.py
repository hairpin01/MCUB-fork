# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import asyncio
import ast
import contextlib
import html
import importlib.machinery
import importlib.util
import inspect
import json
import logging
import os
import re
import sqlite3
import sys
import time
import types
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import aiohttp

from .types import get_callback_handlers, get_inline_handlers, get_watchers

logger = logging.getLogger(__name__)


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


def _serialize_pointer_item(item: Any) -> Any:
    if hasattr(item, "_asdict"):
        return item._asdict()
    return item


class _PointerList(list):
    def __init__(self, setter: Callable[[list], None], initial=None):
        self._setter = setter
        super().__init__(initial or [])

    @property
    def data(self) -> list:
        return list(self)

    @data.setter
    def data(self, value: list):
        list.clear(self)
        list.extend(self, value)
        self._save()

    def _save(self) -> None:
        self._setter([_serialize_pointer_item(item) for item in self])

    def append(self, value: Any):
        super().append(value)
        self._save()

    def extend(self, value):
        super().extend(value)
        self._save()

    def insert(self, index: int, value: Any):
        super().insert(index, value)
        self._save()

    def remove(self, value: Any):
        super().remove(value)
        self._save()

    def pop(self, index: int = -1):
        value = super().pop(index)
        self._save()
        return value

    def clear(self):
        super().clear()
        self._save()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._save()

    def __delitem__(self, index):
        super().__delitem__(index)
        self._save()

    def __iadd__(self, other):
        result = super().__iadd__(other)
        self._save()
        return result

    def tolist(self) -> list:
        return list(self)


class _PointerDict(dict):
    def __init__(self, setter: Callable[[dict], None], initial=None):
        self._setter = setter
        super().__init__(initial or {})

    @property
    def data(self) -> dict:
        return dict(self)

    @data.setter
    def data(self, value: dict):
        dict.clear(self)
        dict.update(self, value)
        self._save()

    def _save(self) -> None:
        self._setter(
            {key: _serialize_pointer_item(value) for key, value in dict(self).items()}
        )

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._save()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._save()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._save()

    def setdefault(self, key, default=None):
        value = super().setdefault(key, default)
        self._save()
        return value

    def pop(self, key, default=None):
        value = super().pop(key, default)
        self._save()
        return value

    def popitem(self):
        value = super().popitem()
        self._save()
        return value

    def clear(self):
        super().clear()
        self._save()

    def todict(self) -> dict:
        return dict(self)


class _NamedTupleMiddlewareList:
    def __init__(self, pointer: _PointerList, item_type):
        self._pointer = pointer
        self._item_type = item_type

    def _serialize(self, item: Any) -> Any:
        return _serialize_pointer_item(item)

    def _deserialize(self, item: Any) -> Any:
        if isinstance(item, self._item_type):
            return item
        if isinstance(item, dict):
            return self._item_type(**item)
        return item

    @property
    def data(self) -> list:
        return [self._deserialize(item) for item in self._pointer.data]

    @data.setter
    def data(self, value: list):
        self._pointer.data = [self._serialize(item) for item in value]

    def append(self, item: Any):
        self._pointer.append(self._serialize(item))

    def extend(self, items):
        self._pointer.extend([self._serialize(item) for item in items])

    def remove(self, item: Any):
        self._pointer.remove(self._serialize(item))

    def pop(self, index: int = -1):
        return self._deserialize(self._pointer.pop(index))

    def clear(self):
        self._pointer.clear()

    def tolist(self) -> list:
        return [self._deserialize(item) for item in self._pointer]

    def __iter__(self):
        return (self._deserialize(item) for item in self._pointer)

    def __len__(self) -> int:
        return len(self._pointer)

    def __contains__(self, item: Any) -> bool:
        return self._serialize(item) in self._pointer

    def __getitem__(self, index):
        return self._deserialize(self._pointer[index])

    def __setitem__(self, index, value):
        self._pointer[index] = self._serialize(value)


class _NamedTupleMiddlewareDict:
    def __init__(self, pointer: _PointerDict, item_type):
        self._pointer = pointer
        self._item_type = item_type

    def _serialize(self, item: Any) -> Any:
        return _serialize_pointer_item(item)

    def _deserialize(self, item: Any) -> Any:
        if isinstance(item, self._item_type):
            return item
        if isinstance(item, dict):
            return self._item_type(**item)
        return item

    @property
    def data(self) -> dict:
        return {
            key: self._deserialize(value) for key, value in self._pointer.data.items()
        }

    @data.setter
    def data(self, value: dict):
        self._pointer.data = {key: self._serialize(item) for key, item in value.items()}

    def todict(self) -> dict:
        return {key: self._deserialize(value) for key, value in self._pointer.items()}

    def get(self, key, default=None):
        if key not in self._pointer:
            return default
        return self._deserialize(self._pointer[key])

    def setdefault(self, key, default=None):
        if key in self._pointer:
            return self._deserialize(self._pointer[key])
        self._pointer[key] = self._serialize(default)
        return default

    def pop(self, key, default=None):
        if key not in self._pointer:
            return default
        return self._deserialize(self._pointer.pop(key))

    def clear(self):
        self._pointer.clear()

    def items(self):
        return ((key, self._deserialize(value)) for key, value in self._pointer.items())

    def keys(self):
        return self._pointer.keys()

    def values(self):
        return (self._deserialize(value) for value in self._pointer.values())

    def __iter__(self):
        return iter(self._pointer)

    def __len__(self) -> int:
        return len(self._pointer)

    def __contains__(self, item: Any) -> bool:
        return item in self._pointer

    def __getitem__(self, key):
        return self._deserialize(self._pointer[key])

    def __setitem__(self, key, value):
        self._pointer[key] = self._serialize(value)

    def __delitem__(self, key):
        del self._pointer[key]


class _KernelDbFacade:
    def __init__(self, kernel):
        self._kernel = kernel
        self._mem: dict[str, Any] = {}

    def _mem_key(self, owner: str, key: str) -> str:
        return f"{owner}:{key}"

    def get(self, owner: str, key: str, default=None):
        mk = self._mem_key(owner, key)
        if mk in self._mem:
            return self._mem[mk]
        proxy = DbProxy(self._kernel, owner)
        result = proxy._read_persistent(owner, key, default)
        if result is not default:
            self._mem[mk] = result
        return result

    def set(self, owner: str, key: str, value) -> bool:
        self._mem[self._mem_key(owner, key)] = value
        if hasattr(self._kernel, "db_set"):
            try:
                asyncio.get_event_loop().create_task(
                    self._kernel.db_set(owner, key, value)
                )
            except Exception:
                pass
        return True

    def pointer(self, owner: str, key: str, default=None, item_type=None):
        value = self.get(owner, key, default)
        if isinstance(value, list):
            pointer = _PointerList(lambda saved: self.set(owner, key, saved), value)
            return (
                _NamedTupleMiddlewareList(pointer, item_type) if item_type else pointer
            )
        if isinstance(value, dict):
            pointer = _PointerDict(lambda saved: self.set(owner, key, saved), value)
            return (
                _NamedTupleMiddlewareDict(pointer, item_type) if item_type else pointer
            )
        self.set(owner, key, value)
        return value

    def save(self) -> bool:
        return True

    def keys(self):
        values = set(DbProxy(self._kernel, "__kernel__")._read_all_modules())
        values.update(key.split(":", maxsplit=1)[0] for key in self._mem)
        return list(values)


class _CompatTranslatorFacade:
    async def load_module_translations(self, pack_url: str):
        del pack_url
        return {}


class _CompatSecurityManager:
    def __init__(self, client):
        self._client = client
        self.any_admin = False
        self.default = 1
        self.owner = (
            [getattr(client, "tg_id", 0)] if getattr(client, "tg_id", None) else []
        )
        self.sudo = []
        self.support = []
        self.tsec_chat = []
        self.tsec_user = []
        self.all_users = list(self.owner)
        self._sgroups = {}

    def apply_sgroups(self, sgroups: dict):
        self._sgroups = dict(sgroups or {})

    async def check(self, **kwargs) -> bool:
        del kwargs
        return True

    def get_flags(self, obj) -> int:
        return getattr(obj, "security", 0)

    def add_rule(
        self, target_type: str, target, rule: str, duration: Optional[int] = None
    ):
        store = self.tsec_user if target_type == "user" else self.tsec_chat
        store.append(
            {
                "target_type": target_type,
                "target": getattr(target, "id", target),
                "rule": rule,
                "expires": time.time() + duration if duration else 0,
            }
        )
        return True

    def remove_rule(self, target_type: str, target, rule: Optional[str] = None):
        store = self.tsec_user if target_type == "user" else self.tsec_chat
        target_id = getattr(target, "id", target)
        for item in list(store):
            if item.get("target") != target_id:
                continue
            if rule is not None and item.get("rule") != rule:
                continue
            store.remove(item)
        return True

    def remove_rules(self, target_type: str, target):
        return self.remove_rule(target_type, target)


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

    def _coerce_value(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return value
        with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
            return json.loads(stripped)
        with contextlib.suppress(SyntaxError, TypeError, ValueError):
            return ast.literal_eval(stripped)
        return value

    def _coerce_to_default_shape(self, value: Any, default: Any) -> Any:
        if default is None:
            return value
        if isinstance(default, list):
            if isinstance(value, list):
                return value
            if isinstance(value, (tuple, set)):
                return list(value)
            if value in (None, "", {}):
                return list(default)
            return [value]
        if isinstance(default, dict):
            if isinstance(value, dict):
                return value
            return dict(default)
        return value

    def _read_persistent(self, module: str, key: str, default: Any = None) -> Any:
        db_manager = getattr(self._kernel, "db_manager", None)
        if db_manager is None or not hasattr(db_manager, "_resolve_db_file"):
            return default

        try:
            conn = sqlite3.connect(db_manager._resolve_db_file())
            try:
                row = conn.execute(
                    "SELECT value FROM module_data WHERE module = ? AND key = ?",
                    (module, key),
                ).fetchone()
            finally:
                conn.close()
        except Exception as e:
            self._kernel.logger.warning(
                f"[hikka_compat] DbProxy read failed ({module}.{key}): {e}"
            )
            return default

        return self._coerce_value(row[0]) if row else default

    def _read_all_modules(self) -> list[str]:
        db_manager = getattr(self._kernel, "db_manager", None)
        if db_manager is None or not hasattr(db_manager, "_resolve_db_file"):
            return []

        try:
            conn = sqlite3.connect(db_manager._resolve_db_file())
            try:
                rows = conn.execute(
                    "SELECT DISTINCT module FROM module_data ORDER BY module"
                ).fetchall()
            finally:
                conn.close()
        except Exception:
            return []

        return [row[0] for row in rows if row and row[0]]

    def _resolve_get_args(self, args, default=None):
        if len(args) == 1:
            return self._module_name, args[0], default
        if len(args) >= 2:
            return args[0], args[1], args[2] if len(args) >= 3 else default
        raise TypeError("get() missing required arguments")

    def _resolve_set_args(self, args):
        if len(args) == 2:
            return self._module_name, args[0], args[1]
        if len(args) >= 3:
            return args[0], args[1], args[2]
        raise TypeError("set() missing required arguments")

    def set(self, *args) -> None:
        module, key, value = self._resolve_set_args(args)
        self._mem[self._mem_key(module, key)] = value
        self._schedule_write(module, key, value)

    def get(self, *args, default: Any = None) -> Any:
        module, key, default = self._resolve_get_args(args, default)
        mk = self._mem_key(module, key)
        if mk in self._mem:
            return self._coerce_to_default_shape(self._mem[mk], default)
        result = self._read_persistent(module, key, default)
        if result is not default:
            self._mem[mk] = result
        return self._coerce_to_default_shape(result, default)

    def keys(self):
        values = set(self._read_all_modules())
        values.update(key.split(":", maxsplit=1)[0] for key in self._mem)
        return list(values)

    def clear(self, module: Optional[str] = None) -> bool:
        if module is None:
            prefix = f"{self._module_name}:"
            for key in list(self._mem):
                if key.startswith(prefix):
                    self._mem.pop(key, None)
            return True

        if ":" in str(module):
            self._mem.pop(module, None)
            return True

        prefix = f"{module}:"
        for key in list(self._mem):
            if key.startswith(prefix):
                self._mem.pop(key, None)
        return True

    def update(self, *args, **kwargs) -> bool:
        if len(args) == 2 and isinstance(args[1], dict):
            module, values = args
            for key, value in (values or {}).items():
                self.set(module, key, value)
            return True

        if len(args) == 1 and isinstance(args[0], dict):
            for module, values in args[0].items():
                if isinstance(values, dict):
                    self.update(module, values)
                else:
                    self.set(module, "__value__", values)
            return True

        for module, values in kwargs.items():
            if isinstance(values, dict):
                self.update(module, values)
            else:
                self.set(module, "__value__", values)
        return True

    def save(self) -> bool:
        return True

    def process_db_autofix(self, db_data=None) -> Any:
        return db_data if db_data is not None else True

    def __contains__(self, key: str) -> bool:
        return self._mem_key(self._module_name, key) in self._mem

    def __getitem__(self, key: str) -> Any:
        return self.get(self._module_name, key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(self._module_name, key, value)

    def __delitem__(self, key: str) -> None:
        self._mem.pop(self._mem_key(self._module_name, key), None)

    async def async_get(self, module: str, key: str, default: Any = None) -> Any:
        mk = self._mem_key(module, key)
        if mk in self._mem:
            return self._mem[mk]
        try:
            result = await self._kernel.db_get(module, key)
            if result is not None:
                result = self._coerce_value(result)
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

    def pointer(self, *args, item_type=None, default=None):
        module, key, default = self._resolve_get_args(args, default)
        value = self.get(module, key, default)
        if isinstance(value, list):
            pointer = _PointerList(lambda saved: self.set(module, key, saved), value)
            return (
                _NamedTupleMiddlewareList(pointer, item_type) if item_type else pointer
            )
        if isinstance(value, dict):
            pointer = _PointerDict(lambda saved: self.set(module, key, saved), value)
            return (
                _NamedTupleMiddlewareDict(pointer, item_type) if item_type else pointer
            )
        self.set(module, key, value)
        return value


async def _maybe_await(result):
    if asyncio.iscoroutine(result):
        return await result
    return result


def _rand_token(length: int = 30) -> str:
    return uuid.uuid4().hex[: max(8, int(length))]


def _normalize_source_url(url: str) -> str:
    if not isinstance(url, str):
        return url
    return re.sub(
        r"(https://raw\.githubusercontent\.com/[^/]+/[^/]+)/refs/heads/([^/]+)/",
        r"\1/\2/",
        url,
    )


def _iter_kernel_module_items(kernel):
    seen: set[int] = set()
    for mapping_name in ("loaded_modules", "system_modules"):
        mapping = getattr(kernel, mapping_name, {}) or {}
        for key, inst in mapping.items():
            marker = id(inst)
            if marker in seen:
                continue
            seen.add(marker)
            yield key, inst


def _module_matches_name(key: str, inst, lowered: str) -> bool:
    if str(key).lower() == lowered:
        return True

    raw_strings = getattr(inst, "strings", {})
    if callable(raw_strings):
        raw_name = str(raw_strings("name", None) or "").lower()
    elif isinstance(raw_strings, dict):
        raw_name = str(raw_strings.get("name", "")).lower()
    else:
        raw_name = ""
    if raw_name == lowered:
        return True

    class_name = getattr(getattr(inst, "__class__", None), "__name__", "")
    return str(class_name).lower() == lowered


def _instance_owner_names(instance, module_name: Optional[str] = None) -> list[str]:
    names = []
    raw_strings = getattr(type(instance), "__dict__", {}).get("strings", {})
    display_name = raw_strings.get("name") if isinstance(raw_strings, dict) else None
    for candidate in (
        getattr(instance, "_db_owner", None),
        getattr(getattr(instance, "__class__", None), "__name__", None),
        module_name,
        display_name,
    ):
        if candidate is None:
            continue
        candidate = str(candidate).strip()
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _find_kernel_module(kernel, name: str):
    lowered = str(name).lower()
    for key, inst in _iter_kernel_module_items(kernel):
        if _module_matches_name(key, inst, lowered):
            return key, inst
    return None, None


class _CompatRemoteStorage:
    def __init__(self, kernel):
        self._kernel = kernel

    async def fetch(self, url: str, auth: Optional[str] = None) -> str:
        url = _normalize_source_url(str(url))
        session = getattr(self._kernel, "session", None)
        own_session = session is None or getattr(session, "closed", False)
        if own_session:
            session = aiohttp.ClientSession()

        kwargs = {}
        if auth and ":" in auth:
            user, password = auth.split(":", 1)
            kwargs["auth"] = aiohttp.BasicAuth(user, password)

        try:
            async with session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.text()
        finally:
            if own_session:
                await session.close()

    async def preload(self, *_args, **_kwargs):
        return None


class _CompatLoaderProxy:
    def __init__(self, kernel, module=None):
        self._kernel = kernel
        self._module = module
        self._storage = getattr(module, "_storage", None) or _CompatRemoteStorage(
            kernel
        )
        existing_config = getattr(module, "config", None)
        if isinstance(existing_config, dict):
            self.config = existing_config
        else:
            self.config = {
                "basic_auth": getattr(kernel, "config", {}).get("basic_auth", "")
            }
        self.fully_loaded = True
        self.allmodules = getattr(kernel, "_hikka_compat_allmodules_proxy", None)
        if self.allmodules is None:
            self.allmodules = _AllModulesStub(kernel)
            setattr(kernel, "_hikka_compat_allmodules_proxy", self.allmodules)

    def __getattr__(self, name: str):
        if self._module is not None and hasattr(self._module, name):
            return getattr(self._module, name)
        raise AttributeError(name)

    async def load_module(
        self,
        path: str,
        module_name: str,
        *args,
        origin: str = "",
        save_fs: bool = True,
        is_system: bool = False,
        **kwargs,
    ):
        loader = getattr(self._kernel, "loader", None)
        if loader is not None and hasattr(loader, "load_module_from_file"):
            return await loader.load_module_from_file(path, module_name, is_system)
        return (False, "Loader not available")

    async def install_packages(self, packages) -> bool:
        logger.warning(
            "[hikka_compat] install_packages() is not supported on this platform: %s",
            packages,
        )
        return False

    def update_modules_in_db(self):
        return False


class _BotProxy:
    def __init__(self, inline_proxy: "InlineProxy"):
        self._inline_proxy = inline_proxy

    @property
    def _client(self):
        k = self._inline_proxy._kernel
        bot_client = getattr(k, "bot_client", None)
        if bot_client:
            return bot_client
        return getattr(k, "client", None)

    @property
    def id(self) -> Optional[int]:
        return self._inline_proxy.bot_id

    @property
    def username(self) -> Optional[str]:
        return self._inline_proxy.bot_username

    async def __call__(self, value):
        return await _maybe_await(value)

    def __getattr__(self, name: str):
        client = self._client
        if client is None:
            raise AttributeError(name)
        return getattr(client, name)

    async def get_me(self):
        kernel = self._inline_proxy._kernel
        bot_client = getattr(kernel, "bot_client", None)
        if bot_client and hasattr(bot_client, "get_me"):
            with contextlib.suppress(Exception):
                return await bot_client.get_me()

        username = self.username
        bot_id = self.id
        if username or bot_id:
            return types.SimpleNamespace(
                id=bot_id,
                username=username,
                first_name=username or "inline_bot",
                bot=True,
            )

        return types.SimpleNamespace(
            id=bot_id,
            username=username,
            first_name="inline_bot",
            bot=True,
        )

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup=None,
        disable_web_page_preview: bool = False,
        **kwargs,
    ):
        client = self._client
        if client is None or not hasattr(client, "send_message"):
            return False

        send_kwargs = {}
        buttons = self._inline_proxy._to_telethon_buttons(reply_markup)
        if buttons:
            send_kwargs["buttons"] = buttons

        # Telethon uses "link_preview"; keep "disable_web_page_preview" API for compat.
        send_kwargs["link_preview"] = not bool(disable_web_page_preview)
        send_kwargs.update(kwargs)
        return await client.send_message(chat_id, text, **send_kwargs)

    async def send_photo(self, chat_id: int, photo, caption: str = "", **kwargs):
        return await self.send_message(chat_id, caption, file=photo, **kwargs)

    async def send_document(self, chat_id: int, document, caption: str = "", **kwargs):
        return await self.send_message(chat_id, caption, file=document, **kwargs)

    def _resolve_message_target(
        self,
        *,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
    ) -> tuple[Optional[int], Optional[int]]:
        if chat_id is not None and message_id is not None:
            return chat_id, message_id

        if inline_message_id:
            _, unit = self._inline_proxy._find_unit(
                inline_message_id=str(inline_message_id)
            )
            if unit:
                return unit.get("chat"), unit.get("message_id")

        return chat_id, message_id

    async def edit_message_text(
        self,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        text: str = "",
        reply_markup=None,
        inline_message_id: Optional[str] = None,
        **kwargs,
    ):
        client = self._client
        if client is None or not hasattr(client, "edit_message"):
            return False

        chat_id, message_id = self._resolve_message_target(
            chat_id=chat_id,
            message_id=message_id,
            inline_message_id=inline_message_id,
        )
        if chat_id is None or message_id is None:
            return False
        edit_kwargs = {"parse_mode": "html"}
        buttons = self._inline_proxy._to_telethon_buttons(reply_markup)
        if buttons:
            edit_kwargs["buttons"] = buttons
        edit_kwargs.update(kwargs)
        return await client.edit_message(chat_id, message_id, text, **edit_kwargs)

    async def edit_message_reply_markup(
        self,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        reply_markup=None,
        inline_message_id: Optional[str] = None,
        **kwargs,
    ):
        client = self._client
        if client is None or not hasattr(client, "edit_message"):
            return False
        chat_id, message_id = self._resolve_message_target(
            chat_id=chat_id,
            message_id=message_id,
            inline_message_id=inline_message_id,
        )
        if chat_id is None or message_id is None:
            return False
        edit_kwargs = {}
        buttons = self._inline_proxy._to_telethon_buttons(reply_markup)
        if buttons:
            edit_kwargs["buttons"] = buttons
        edit_kwargs.update(kwargs)
        return await client.edit_message(chat_id, message_id, **edit_kwargs)


class InlineProxy:
    def __init__(self, kernel):
        self._kernel = kernel
        state = getattr(kernel, "_hikka_compat_inline_state", None)
        if not isinstance(state, dict):
            state = {}
            setattr(kernel, "_hikka_compat_inline_state", state)

        state.setdefault("units", {})
        state.setdefault("custom_map", {})
        self._units: dict = state["units"]
        self._custom_map: dict = state["custom_map"]

        # Expose global storages for bridge code in other runtime layers.
        setattr(kernel, "_hikka_compat_inline_units", self._units)
        setattr(kernel, "_hikka_compat_inline_custom_map", self._custom_map)

        self._module = None
        self._module_name = "hikka_compat"
        self._bot_wrapper = _BotProxy(self)
        self.init_complete = bool(getattr(kernel, "bot_client", None))

        self._register_callback_handler()

    def _register_callback_handler(self):
        pass

    def _bind_module(self, module) -> None:
        self._module = module
        raw = type(module).__dict__.get("strings", {})
        self._module_name = raw.get("name", type(module).__name__)

    @property
    def bot(self):
        return self._bot_wrapper

    @property
    def _bot(self):
        return self.bot

    @property
    def bot_id(self) -> Optional[int]:
        inline = getattr(self._kernel, "_inline", None)
        if inline is not None:
            bid = getattr(inline, "bot_id", None)
            if bid:
                return bid
        return None

    @property
    def bot_username(self) -> Optional[str]:
        inline = getattr(self._kernel, "_inline", None)
        if inline is not None:
            uname = getattr(inline, "bot_username", None)
            if uname:
                return uname
        cfg = getattr(self._kernel, "config", {}) or {}
        return cfg.get("inline_bot_username")

    async def check_bot(self, username: str) -> bool:
        current = (self.bot_username or "").strip("@").lower()
        return bool(current and current == str(username).strip("@").lower())

    def _derive_chat_id(self, message) -> Optional[int]:
        if message is None:
            return None
        if hasattr(message, "chat_id"):
            return getattr(message, "chat_id", None)
        if isinstance(message, int):
            return message
        return None

    def _unit_id(self, kind: str = "unit") -> str:
        return f"{kind}_{_rand_token(12)}"

    def _normalize_markup(self, markup):
        if not markup:
            return []

        if isinstance(markup, dict):
            if "inline_keyboard" in markup:
                markup = markup.get("inline_keyboard") or []
            elif "buttons" in markup:
                markup = markup.get("buttons") or []
            elif "text" in markup:
                return [[dict(markup)]]
            else:
                return []

        if not isinstance(markup, list):
            return []

        if not markup:
            return []

        # If all elements are dicts, it's a single row (list of buttons)
        if all(isinstance(btn, dict) for btn in markup):
            return [[dict(btn) for btn in markup]]

        rows = []
        for row in markup:
            if isinstance(row, dict):
                rows.append([dict(row)])
                continue
            if not isinstance(row, (list, tuple)):
                continue
            parsed_row = [dict(btn) for btn in row if isinstance(btn, dict)]
            if parsed_row:
                rows.append(parsed_row)
        return rows

    def _prepare_markup(
        self,
        markup,
        *,
        unit_id: Optional[str] = None,
        force_me: bool = False,
        always_allow=None,
        disable_security: bool = False,
    ):
        rows = self._normalize_markup(markup)
        if always_allow is None:
            always_allow = []

        prepared_rows = []
        for row in rows:
            prepared_row = []
            for button in row:
                btn = dict(button)

                # Handle non-callback buttons (URL, switch, phone, location, game)
                if "url" in btn and "callback" not in btn:
                    prepared_row.append(btn)
                    continue
                if ("switch" in btn or "input" in btn) and "callback" not in btn:
                    prepared_row.append(btn)
                    continue
                if "phone" in btn and "callback" not in btn:
                    prepared_row.append(btn)
                    continue
                if "location" in btn and "callback" not in btn:
                    prepared_row.append(btn)
                    continue
                if "game" in btn and "callback" not in btn:
                    prepared_row.append(btn)
                    continue

                if "callback" not in btn:
                    action = str(btn.get("action", "")).lower()
                    if action == "close":
                        btn["callback"] = self._close_unit_handler
                    elif action == "unload":
                        btn["callback"] = self._unload_unit_handler
                    elif action == "answer" and btn.get("message"):

                        async def _answer(
                            call,
                            _text=btn.get("message", ""),
                            _show=bool(
                                btn.get("alert") or btn.get("show_alert", False)
                            ),
                        ):
                            return await self._answer_unit_handler(
                                call, text=_text, show_alert=_show
                            )

                        btn["callback"] = _answer

                # Handle URL and other non-callback buttons - just add them without callback processing
                if "url" in btn and "callback" not in btn:
                    prepared_row.append(btn)
                    continue

                cb = btn.get("callback")
                if callable(cb):
                    cb_data = str(btn.get("_callback_data") or _rand_token(30))
                    btn["_callback_data"] = cb_data
                    btn["callback_data"] = cb_data

                    raw_args = btn.get("args", ())
                    if raw_args is None:
                        raw_args = ()
                    if not isinstance(raw_args, (list, tuple)):
                        raw_args = (raw_args,)
                    raw_kwargs = btn.get("kwargs", {})
                    if not isinstance(raw_kwargs, dict):
                        raw_kwargs = {}

                    self._custom_map[cb_data] = {
                        "handler": cb,
                        "args": tuple(raw_args),
                        "kwargs": dict(raw_kwargs),
                        "always_allow": btn.get("always_allow", always_allow),
                        "force_me": bool(btn.get("force_me", force_me)),
                        "disable_security": bool(
                            btn.get("disable_security", disable_security)
                        ),
                        "unit_id": unit_id,
                    }

                    cb_map = getattr(self._kernel, "inline_callback_map", None)
                    if cb_map is None:
                        cb_map = {}
                        setattr(self._kernel, "inline_callback_map", cb_map)

                    ttl = getattr(self, "_current_form_ttl", 3600)
                    import time as _time

                    cb_map[cb_data] = {
                        "handler": cb,
                        "args": tuple(raw_args),
                        "kwargs": dict(raw_kwargs),
                        "expires_at": _time.time() + ttl,
                    }
                elif isinstance(cb, str):
                    btn["callback_data"] = cb

                if "data" in btn and "callback_data" not in btn:
                    btn["callback_data"] = str(btn["data"])

                if "input" in btn and "switch_inline_query_current_chat" not in btn:
                    query_id = str(btn.get("_switch_query") or _rand_token(10))
                    btn["switch_inline_query_current_chat"] = f"{query_id} "

                if "copy" in btn and "copy_text" not in btn:
                    btn["copy_text"] = {"text": str(btn.get("copy", ""))}

                prepared_row.append(btn)

            if prepared_row:
                prepared_rows.append(prepared_row)
        return prepared_rows

    def _to_telethon_buttons(self, markup):
        if not markup:
            return None
        try:
            from telethon import Button
            from telethon.tl import types as tl_types
            from telethon.tl.custom.button import Button as TelethonButton
            from telethon.tl.tlobject import TLObject
        except Exception:
            return None

        rows = self._normalize_markup(markup)
        if not rows:
            return None

        result = []
        for row in rows:
            out_row = []
            for button in row:
                if isinstance(button, (TLObject, TelethonButton)):
                    out_row.append(button)
                    continue
                if not isinstance(button, dict):
                    continue

                text = str(button.get("text", "Button"))
                if "url" in button:
                    out_row.append(Button.url(text, str(button["url"])))
                elif "copy" in button or "copy_text" in button:
                    copy_value = button.get("copy")
                    if copy_value is None:
                        copy_value = button.get("copy_text")
                    if isinstance(copy_value, dict):
                        copy_value = copy_value.get("text", "")
                    style = button.get("style")
                    style_obj = None
                    if style == "primary":
                        style_obj = tl_types.KeyboardButtonStyle(bg_primary=True)
                    elif style == "success":
                        style_obj = tl_types.KeyboardButtonStyle(bg_success=True)
                    elif style == "danger":
                        style_obj = tl_types.KeyboardButtonStyle(bg_danger=True)
                    out_row.append(
                        tl_types.KeyboardButtonCopy(
                            text=text,
                            copy_text=str(copy_value or ""),
                            style=style_obj,
                        )
                    )
                elif "web_app" in button:
                    web_url = button.get("web_app")
                    if isinstance(web_url, dict):
                        web_url = web_url.get("url")
                    if web_url:
                        out_row.append(
                            tl_types.KeyboardButtonWebView(
                                text=text,
                                url=str(web_url),
                            )
                        )
                elif "switch_inline_query_current_chat" in button:
                    query = str(
                        button.get("switch_inline_query_current_chat", "")
                    ).strip()
                    out_row.append(Button.switch_inline(text, query, same_peer=True))
                elif "switch_inline_query" in button:
                    query = str(button.get("switch_inline_query", "")).strip()
                    out_row.append(Button.switch_inline(text, query, same_peer=False))
                elif "phone" in button:
                    out_row.append(Button.request_phone(text))
                elif "location" in button:
                    out_row.append(Button.request_location(text))
                elif "game" in button:
                    out_row.append(Button.game(text))
                else:
                    data = button.get("callback_data", button.get("data", ""))
                    if isinstance(data, bytes):
                        cb_data = data
                    else:
                        cb_data = str(data).encode("utf-8", errors="replace")
                    out_row.append(Button.inline(text, cb_data))
            if out_row:
                result.append(out_row)
        return result or None

    def _register_unit(self, unit_id: str, payload: dict) -> None:
        self._units[unit_id] = payload

    def _find_unit(
        self, *, unit_id=None, chat_id=None, message_id=None, inline_message_id=None
    ):
        if unit_id and unit_id in self._units:
            return unit_id, self._units[unit_id]

        for uid, unit in self._units.items():
            if inline_message_id and unit.get("inline_message_id") == inline_message_id:
                return uid, unit
            if (
                chat_id is not None
                and message_id is not None
                and unit.get("chat") == chat_id
                and unit.get("message_id") == message_id
            ):
                return uid, unit
        return None, None

    def _bind_unit_message(self, unit_id: str, sent_msg) -> None:
        unit = self._units.get(unit_id)
        if not unit:
            return
        if not sent_msg:
            return

        message_id = getattr(sent_msg, "id", None)
        if message_id is not None:
            unit["message_id"] = message_id
            unit["inline_message_id"] = str(message_id)

        chat_id = getattr(sent_msg, "chat_id", None)
        if chat_id is not None:
            unit["chat"] = chat_id

    async def _send_fallback(
        self,
        message,
        text: str,
        *,
        reply_markup=None,
        media=None,
        silent: bool = False,
    ):
        buttons = self._to_telethon_buttons(reply_markup)
        kwargs = {"parse_mode": "html"}
        if buttons:
            kwargs["buttons"] = buttons
        if media:
            kwargs["file"] = media
        if silent:
            kwargs["silent"] = True

        if hasattr(message, "edit"):
            try:
                return await message.edit(text, **kwargs)
            except Exception:
                pass

        if hasattr(message, "respond"):
            try:
                return await message.respond(text, **kwargs)
            except Exception:
                pass

        if isinstance(message, int) and getattr(self._kernel, "client", None):
            try:
                return await self._kernel.client.send_message(message, text, **kwargs)
            except Exception:
                pass
        return None

    async def dispatch_callback(
        self, call_data: str, call=None, unit_id: Optional[str] = None
    ) -> bool:
        payload = self._custom_map.get(str(call_data))
        if not payload:
            return False

        if unit_id and payload.get("unit_id") is None:
            payload["unit_id"] = unit_id

        handler = payload.get("handler")
        if not callable(handler):
            return False

        args = payload.get("args", ())
        kwargs = payload.get("kwargs", {})
        if not isinstance(args, (list, tuple)):
            args = (args,)
        if not isinstance(kwargs, dict):
            kwargs = {}

        await _maybe_await(handler(call, *args, **kwargs))
        return True

    async def form(
        self,
        text: str,
        message=None,
        reply_markup=None,
        *,
        force_me: bool = False,
        always_allow: list = None,
        manual_security: bool = False,
        disable_security: bool = False,
        ttl: int = None,
        on_unload: callable = None,
        photo: str = None,
        gif: str = None,
        file: str = None,
        mime_type: str = None,
        video: str = None,
        location: tuple = None,
        audio: dict = None,
        silent: bool = False,
        **kwargs,
    ):
        """Send inline form to chat (Hikka/Heroku compatible).

        Args:
            text: Content of inline form. HTML markdown supported.
            message: Message object or chat_id to send to.
            reply_markup: List of buttons to insert in markup.
            force_me: Either this form buttons must be pressed only by owner scope.
            always_allow: Users, that are allowed to press buttons in addition to previous rules.
            ttl: Time, when the form is going to be unloaded.
            photo: Attach a photo to the form. URL must be supplied.
            gif: Attach a gif to the form. URL must be supplied.
            file: Attach a file to the form. URL must be supplied.
            video: Attach a video to the form. URL must be supplied.
            location: Attach a map point (latitude, longitude).
            audio: Attach an audio. Dict or URL must be supplied.
            silent: Whether the form must be sent silently.

        Returns:
            InlineMessage on success, False otherwise.
        """
        from .inline_types import InlineMessage as _InlineMessage
        from .inline_utils import sanitise_text as _sanitise_text

        if message is None:
            return False

        if always_allow is None:
            always_allow = []

        text = _sanitise_text(text) if text else ""
        chat_id = self._derive_chat_id(message)
        if chat_id is None:
            return False

        self._current_form_ttl = ttl or 3600

        unit_type = str(kwargs.pop("_unit_type", "form"))
        unit_id = str(kwargs.pop("unit_id", self._unit_id(unit_type)))
        markup = self._prepare_markup(
            reply_markup,
            unit_id=unit_id,
            force_me=force_me,
            always_allow=always_allow,
            disable_security=disable_security,
        )

        media = photo or gif or video or file
        media_type = "photo"
        if gif:
            media_type = "gif"
        elif video:
            media_type = "document"
        elif file:
            media_type = "document"

        self._register_unit(
            unit_id,
            {
                "id": unit_id,
                "type": unit_type,
                "text": text,
                "buttons": markup,
                "chat": chat_id,
                "message_id": None,
                "inline_message_id": None,
                "ttl": ttl,
                "force_me": force_me,
                "always_allow": always_allow,
                "disable_security": disable_security,
                "manual_security": manual_security,
                "on_unload": on_unload,
                "media": media,
                "media_type": media_type,
                "audio": audio,
                "location": location,
            },
        )

        inline_form = (
            getattr(self._kernel._inline, "inline_form", None)
            if self._kernel._inline
            else None
        )
        if inline_form:
            try:
                result = await inline_form(
                    chat_id=chat_id,
                    title=text,
                    fields=None,
                    buttons=markup,
                    auto_send=True,
                    ttl=ttl or 200,
                    media=media,
                    media_type=media_type,
                )

                if isinstance(result, tuple) and len(result) == 2:
                    success, sent_msg = result
                    if success and sent_msg:
                        self._bind_unit_message(unit_id, sent_msg)
                        inline_msg_id = getattr(sent_msg, "inline_message_id", None)
                        if inline_msg_id:
                            if hasattr(inline_msg_id, "dc_id"):
                                inline_msg_id = f"{inline_msg_id.dc_id}:{inline_msg_id.id}:{inline_msg_id.access_hash}"
                            else:
                                inline_msg_id = str(inline_msg_id)
                        else:
                            inline_msg_id = ""
                        return _InlineMessage(
                            inline_message_id=inline_msg_id,
                            unit_id=unit_id,
                            inline_proxy=self,
                            chat_id=chat_id,
                            message_id=getattr(sent_msg, "id", None),
                        )
                return False
            except Exception as e:
                self._kernel.logger.debug(
                    f"[hikka_compat] InlineProxy.form() via inline_form failed: {e}"
                )

        sent = await self._send_fallback(
            message,
            text,
            reply_markup=markup,
            media=media,
            silent=silent,
        )
        if not sent:
            self._units.pop(unit_id, None)
            return False
        self._bind_unit_message(unit_id, sent)
        inline_msg_id = getattr(sent, "inline_message_id", None)
        if inline_msg_id:
            if hasattr(inline_msg_id, "dc_id"):
                inline_msg_id = f"{inline_msg_id.dc_id}:{inline_msg_id.id}:{inline_msg_id.access_hash}"
            else:
                inline_msg_id = str(inline_msg_id)
        else:
            inline_msg_id = ""
        return _InlineMessage(
            inline_message_id=inline_msg_id,
            unit_id=unit_id,
            inline_proxy=self,
            chat_id=chat_id,
            message_id=getattr(sent, "id", None),
        )

    async def list(
        self,
        *args,
        **kwargs,
    ):
        """Send inline list to chat.

        Args:
            text: List header text.
            message: Message object or chat_id.
            strings: List of strings to display.
            reply_markup: Inline buttons.
            ttl: Time to live.

        Returns:
            InlineMessage on success, False otherwise.
        """
        message = kwargs.pop("message", None)
        strings = kwargs.pop("strings", None)
        reply_markup = kwargs.pop("reply_markup", None)
        ttl = kwargs.pop("ttl", None)
        text = kwargs.pop("text", None)

        if args:
            first = args[0]
            if hasattr(first, "chat_id") or isinstance(first, int):
                message = first
                if len(args) > 1:
                    strings = args[1]
                if len(args) > 2:
                    text = args[2]
            else:
                text = first
                if len(args) > 1:
                    message = args[1]
                if len(args) > 2:
                    strings = args[2]

        if message is None:
            return False

        body = text or ""
        if strings:
            lines = [str(item) for item in strings]
            body = (
                body + ("\n" if body else "") + "\n".join(f"• {line}" for line in lines)
            )
        return await self.form(
            text=body,
            message=message,
            reply_markup=reply_markup,
            ttl=ttl,
            _unit_type="list",
            **kwargs,
        )

    async def gallery(
        self,
        message,
        text: str,
        rows: list = None,
        force_me: bool = False,
        always_allow: list = None,
        disable_security: bool = False,
        ttl: int = None,
        silent: bool = False,
        **kwargs,
    ):
        """Send inline gallery to chat.

        Args:
            message: Message object or chat_id to send to.
            text: Gallery header text.
            rows: List of items (dicts with photo/gif/video and text).
            force_me: Either this gallery must be controlled only by owner.
            always_allow: Additional users allowed to interact.
            disable_security: Disable all security checks.
            ttl: Time to live for the gallery.
            silent: Send silently.

        Returns:
            List of InlineMessages on success, False otherwise.
        """
        from .inline_types import InlineMessage as _InlineMessage

        if message is None:
            return False

        next_handler = kwargs.get("next_handler")
        caption = kwargs.get("caption")
        custom_buttons = kwargs.get("custom_buttons")
        preload = kwargs.get("preload", False)

        if always_allow is None:
            always_allow = []

        chat_id = self._derive_chat_id(message)
        if chat_id is None:
            return False

        unit_id = self._unit_id("gallery")
        self._register_unit(
            unit_id,
            {
                "id": unit_id,
                "type": "gallery",
                "text": text,
                "rows": rows or [],
                "chat": chat_id,
                "message_id": None,
                "inline_message_id": None,
                "ttl": ttl,
                "force_me": force_me,
                "always_allow": always_allow,
                "disable_security": disable_security,
                "caption": caption,
                "custom_buttons": custom_buttons or [],
                "next_handler": next_handler,
                "preload": preload,
                "current_index": 0,
            },
        )

        inline_gallery = (
            getattr(self._kernel._inline, "gallery", None)
            if self._kernel._inline
            else None
        )
        if inline_gallery and rows:
            try:
                results = await inline_gallery(
                    chat_id=chat_id,
                    title=text,
                    rows=rows[:10],
                    force_me=force_me,
                    always_allow=always_allow,
                    disable_security=disable_security,
                    ttl=ttl or 200,
                    silent=silent,
                )

                if isinstance(results, tuple) and len(results) == 2:
                    success, sent_msg = results
                    if success and sent_msg:
                        self._bind_unit_message(unit_id, sent_msg)
                        return _InlineMessage(
                            inline_message_id=str(getattr(sent_msg, "id", "") or ""),
                            unit_id=unit_id,
                            inline_proxy=self,
                        )

                messages = []
                if isinstance(results, list):
                    for i, result in enumerate(results):
                        if not (isinstance(result, tuple) and len(result) == 2):
                            continue
                        success, sent_msg = result
                        if not (success and sent_msg):
                            continue
                        msg_unit = f"{unit_id}_{i}"
                        self._register_unit(msg_unit, dict(self._units[unit_id]))
                        self._bind_unit_message(msg_unit, sent_msg)
                        messages.append(
                            _InlineMessage(
                                inline_message_id=str(
                                    getattr(sent_msg, "id", "") or ""
                                ),
                                unit_id=msg_unit,
                                inline_proxy=self,
                            )
                        )
                if messages:
                    return messages
            except Exception as e:
                self._kernel.logger.debug(
                    f"[hikka_compat] InlineProxy.gallery() via inline gallery failed: {e}"
                )

        first_row = (rows or [{}])[0] if rows else {}
        item_text = str(first_row.get("text") or first_row.get("title") or text)
        item_markup = custom_buttons or first_row.get("buttons", [])
        media = first_row.get("photo") or first_row.get("gif") or first_row.get("video")
        sent = await self._send_fallback(
            message,
            item_text,
            reply_markup=item_markup,
            media=media,
            silent=silent,
        )
        if not sent:
            self._units.pop(unit_id, None)
            return False

        self._bind_unit_message(unit_id, sent)
        return _InlineMessage(
            inline_message_id=str(getattr(sent, "id", "") or ""),
            unit_id=unit_id,
            inline_proxy=self,
        )

    def build_pagination(
        self,
        callback: Callable[[int], Any],
        total_pages: int,
        *,
        unit_id: Optional[str] = None,
        current_page: Optional[int] = None,
    ):
        if not callable(callback) or total_pages <= 1:
            return []

        if current_page is None:
            current_page = 1
            if unit_id:
                unit = self._units.get(unit_id, {})
                idx = unit.get("current_index")
                if isinstance(idx, int):
                    current_page = idx + 1

        current_page = max(1, min(total_pages, current_page))
        buttons = []
        for number in range(1, total_pages + 1):
            text = f"· {number} ·" if number == current_page else str(number)
            buttons.append(
                {
                    "text": text,
                    "args": (number - 1,),
                    "callback": callback,
                }
            )
        return [buttons]

    def sanitise_text(self, text: Optional[str]) -> str:
        from .inline_utils import sanitise_text as _sanitise_text

        return _sanitise_text(text or "")

    async def check_inline_security(
        self,
        *,
        func: Callable,
        user: Optional[int] = None,
    ) -> bool:
        dispatcher = getattr(getattr(self._kernel, "client", None), "dispatcher", None)
        security = getattr(dispatcher, "security", None)
        if security and hasattr(security, "check"):
            try:
                return bool(
                    await security.check(
                        message=None,
                        func=func,
                        user_id=user,
                        inline_cmd=getattr(func, "__name__", None),
                    )
                )
            except Exception:
                pass
        return bool(func)

    async def query(
        self,
        query: str,
        user_id: int,
        offset: str = "",
        cache_time: int = 300,
    ):
        if self._kernel._inline and hasattr(self._kernel._inline, "query"):
            try:
                return await self._kernel._inline.query(
                    query,
                    user_id,
                    offset=offset,
                    cache_time=cache_time,
                )
            except Exception as e:
                self._kernel.logger.debug(
                    f"[hikka_compat] InlineProxy.query() failed: {e}"
                )
        return []

    def generate_markup(self, reply_markup):
        prepared = self._prepare_markup(reply_markup)
        if not prepared:
            return None
        try:
            from aiogram.types import (
                CopyTextButton,
                InlineKeyboardButton,
                InlineKeyboardMarkup,
                WebAppInfo,
            )

            rows = []
            for row in prepared:
                aiogram_row = []
                for button in row:
                    if not isinstance(button, dict):
                        continue
                    payload = {"text": str(button.get("text", ""))}
                    if style := button.get("style"):
                        payload["style"] = style
                    if emoji_id := button.get("emoji_id"):
                        payload["icon_custom_emoji_id"] = str(emoji_id)
                    if "url" in button:
                        payload["url"] = str(button["url"])
                    elif "callback_data" in button:
                        payload["callback_data"] = str(button["callback_data"])
                    elif "data" in button:
                        payload["callback_data"] = str(button["data"])
                    elif "input" in button:
                        payload["switch_inline_query_current_chat"] = str(
                            button.get("switch_inline_query_current_chat")
                            or f"{button.get('_switch_query', '')} "
                        )
                    elif "switch_inline_query_current_chat" in button:
                        payload["switch_inline_query_current_chat"] = str(
                            button.get("switch_inline_query_current_chat", "")
                        )
                    elif "switch_inline_query" in button:
                        payload["switch_inline_query"] = str(
                            button.get("switch_inline_query", "")
                        )
                    elif "web_app" in button:
                        web_app = button.get("web_app")
                        if isinstance(web_app, str):
                            payload["web_app"] = WebAppInfo(url=web_app)
                        elif isinstance(web_app, dict):
                            payload["web_app"] = WebAppInfo(**web_app)
                    elif "copy" in button or "copy_text" in button:
                        copy_value = button.get("copy")
                        if copy_value is None:
                            copy_value = button.get("copy_text")
                        if isinstance(copy_value, dict):
                            payload["copy_text"] = CopyTextButton(**copy_value)
                        else:
                            payload["copy_text"] = CopyTextButton(
                                text=str(copy_value or "")
                            )
                    else:
                        continue
                    aiogram_row.append(InlineKeyboardButton(**payload))
                if aiogram_row:
                    rows.append(aiogram_row)
            if rows:
                return InlineKeyboardMarkup(inline_keyboard=rows)
        except Exception:
            pass
        return {"inline_keyboard": prepared}

    async def _edit_unit(
        self,
        text: Optional[str] = None,
        *,
        unit_id: Optional[str] = None,
        inline_message_id: Optional[str] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        reply_markup=None,
        photo: Optional[str] = None,
        gif: Optional[str] = None,
        file: Optional[str] = None,
        video: Optional[str] = None,
        audio: Optional[dict] = None,
        **kwargs,
    ):
        from .inline_types import InlineMessage as _InlineMessage

        found_id, unit = self._find_unit(
            unit_id=unit_id,
            chat_id=chat_id,
            message_id=message_id,
            inline_message_id=inline_message_id,
        )
        if not unit:
            return False

        unit_id = found_id
        if text is not None:
            unit["text"] = text
        if reply_markup is not None:
            unit["buttons"] = self._prepare_markup(
                reply_markup,
                unit_id=unit_id,
                force_me=bool(unit.get("force_me", False)),
                always_allow=unit.get("always_allow", []),
                disable_security=bool(unit.get("disable_security", False)),
            )

        media = photo or gif or video or file
        if not media and isinstance(audio, dict):
            media = audio.get("url")

        target_chat = chat_id if chat_id is not None else unit.get("chat")
        target_msg = message_id if message_id is not None else unit.get("message_id")
        if target_chat is None or target_msg is None:
            return _InlineMessage(
                inline_message_id=str(unit.get("inline_message_id", "") or ""),
                unit_id=unit_id,
                inline_proxy=self,
            )

        client = getattr(self._kernel, "client", None)
        if client is None or not hasattr(client, "edit_message"):
            return False

        edit_kwargs = {"parse_mode": "html"}
        buttons = self._to_telethon_buttons(unit.get("buttons"))
        if buttons:
            edit_kwargs["buttons"] = buttons
        if media:
            edit_kwargs["file"] = media
        edit_kwargs.update(kwargs)

        try:
            result = await client.edit_message(
                target_chat,
                target_msg,
                unit.get("text", ""),
                **edit_kwargs,
            )
            if result:
                self._bind_unit_message(unit_id, result)
        except Exception as e:
            self._kernel.logger.debug(f"[hikka_compat] _edit_unit failed: {e}")
            return False

        return _InlineMessage(
            inline_message_id=str(unit.get("inline_message_id", "") or ""),
            unit_id=unit_id,
            inline_proxy=self,
        )

    async def _delete_unit_message(
        self,
        call=None,
        *,
        unit_id: Optional[str] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        keep_unit: bool = False,
    ) -> bool:
        found_id, unit = self._find_unit(
            unit_id=unit_id, chat_id=chat_id, message_id=message_id
        )
        if not unit:
            return False

        target_chat = chat_id if chat_id is not None else unit.get("chat")
        target_msg = message_id if message_id is not None else unit.get("message_id")
        if target_chat is None or target_msg is None:
            return False

        client = getattr(self._kernel, "client", None)
        if client is None or not hasattr(client, "delete_messages"):
            return False

        try:
            await client.delete_messages(target_chat, target_msg)
        except Exception as e:
            self._kernel.logger.debug(
                f"[hikka_compat] _delete_unit_message failed: {e}"
            )
            return False

        if not keep_unit:
            self._units.pop(found_id, None)
        if call and hasattr(call, "answer"):
            try:
                await call.answer("")
            except Exception:
                pass
        return True

    async def _unload_unit(self, unit_id: str) -> bool:
        unit = self._units.pop(unit_id, None)
        if not unit:
            return False

        for key in list(self._custom_map):
            payload = self._custom_map.get(key) or {}
            if payload.get("unit_id") == unit_id:
                self._custom_map.pop(key, None)

        on_unload = unit.get("on_unload")
        if callable(on_unload):
            try:
                await _maybe_await(on_unload())
            except Exception as e:
                self._kernel.logger.debug(f"[hikka_compat] unit on_unload failed: {e}")
        return True

    async def _close_unit_handler(self, call):
        unit_id = getattr(call, "unit_id", None)
        return await self._delete_unit_message(call, unit_id=unit_id)

    async def _unload_unit_handler(self, call):
        unit_id = getattr(call, "unit_id", None)
        if not unit_id:
            return False
        deleted = await self._delete_unit_message(call, unit_id=unit_id, keep_unit=True)
        await self._unload_unit(unit_id)
        return deleted

    async def _answer_unit_handler(
        self, call, *, text: str = "", show_alert: bool = False
    ):
        if hasattr(call, "answer"):
            try:
                return await call.answer(text, show_alert=show_alert)
            except TypeError:
                return await call.answer(text, alert=show_alert)
            except Exception:
                return False
        return False

    @staticmethod
    async def _plain_send(message, text: str, **kwargs):
        try:
            return await message.edit(text, parse_mode="html")
        except Exception:
            try:
                return await message.respond(text, parse_mode="html")
            except Exception:
                return None


def _get_members(
    mod, ending: str, attribute: Optional[str] = None, strict: bool = False
) -> dict:
    result = {}
    for method_name in dir(type(mod)):
        if isinstance(getattr(type(mod), method_name, None), property):
            continue
        method = getattr(mod, method_name, None)
        if not callable(method):
            continue
        matches_ending = (
            (method_name == ending) if strict else method_name.endswith(ending)
        )
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
        self.db = getattr(kernel, "_hikka_compat_db_facade", None)
        if self.db is None:
            self.db = _KernelDbFacade(kernel)
            setattr(kernel, "_hikka_compat_db_facade", self.db)
        self.client = kernel.client
        self.inline = None
        self.allclients = [kernel.client]
        self.translator = getattr(kernel, "_hikka_compat_translator", None)
        if self.translator is None:
            self.translator = _CompatTranslatorFacade()
            setattr(kernel, "_hikka_compat_translator", self.translator)
        self._libraries = getattr(kernel, "_hikka_compat_libraries", [])
        self.aliases = getattr(kernel, "aliases", {})
        self.secure_boot = bool(getattr(kernel, "secure_boot", False))
        self._patched_register = None

    def lookup(self, name: str):
        _, inst = _find_kernel_module(self._kernel, name)
        if inst is not None:
            lowered = str(name).lower()
            if lowered in {"loader", "Loader".lower()}:
                return _CompatLoaderProxy(self._kernel, inst)
            return inst
        if str(name).lower() == "loader":
            return _CompatLoaderProxy(self._kernel)
        return None

    def get_prefix(self, *_args, **_kwargs) -> str:
        return getattr(self._kernel, "custom_prefix", ".")

    def get_prefixes(self, *_args, **_kwargs) -> list:
        return [self.get_prefix()]

    @property
    def commands(self) -> dict:
        return getattr(self._kernel, "command_handlers", {})

    @property
    def inline_handlers(self) -> dict:
        return getattr(self._kernel, "inline_handlers", {})

    @property
    def callback_handlers(self) -> dict:
        result = {}
        for inst in self.modules:
            result.update(get_callback_handlers(inst))
        return result

    @property
    def watchers(self) -> dict:
        result = {}
        for inst in self.modules:
            result.update(get_watchers(inst))
        return result

    @property
    def modules(self) -> list:
        return [inst for _, inst in _iter_kernel_module_items(self._kernel)]

    @property
    def libraries(self) -> list:
        return self._libraries

    def add_alias(self, alias: str, command: str, *_args) -> bool:
        alias = str(alias).strip()
        command = str(command).strip()
        if not alias or not command:
            return False
        self.aliases[alias] = command
        return True

    def add_aliases(self, aliases: dict) -> int:
        count = 0
        for alias, command in (aliases or {}).items():
            count += int(self.add_alias(alias, command))
        return count

    def remove_alias(self, alias: str) -> bool:
        if alias not in self.aliases:
            return False
        self.aliases.pop(alias, None)
        return True

    def get_classname(self, module) -> str:
        if isinstance(module, str):
            found = self.lookup(module)
            return found.__class__.__name__ if found else module
        return module.__class__.__name__

    def dispatch(self, command: str):
        command = str(command).strip()
        if command in self.commands:
            return command, self.commands[command]
        target = self.aliases.get(command)
        if target and target in self.commands:
            return target, self.commands[target]
        return command, None

    @property
    def register_module(self):
        if self._patched_register is not None:
            return self._patched_register
        return self._register_module

    @register_module.setter
    def register_module(self, value):
        self._patched_register = value

    async def _register_module(self, spec, *args, **kwargs):
        del args
        origin = (
            kwargs.get("origin") or getattr(spec, "origin", "")
            if spec is not None
            else ""
        )
        if spec is None:
            return self.lookup(Path(origin).stem) if origin else None

        source = None
        loader_obj = getattr(spec, "loader", None)
        with contextlib.suppress(Exception):
            if loader_obj is not None and hasattr(loader_obj, "get_source"):
                source = loader_obj.get_source(getattr(spec, "name", None))
        with contextlib.suppress(Exception):
            if (
                source is None
                and loader_obj is not None
                and hasattr(loader_obj, "get_data")
            ):
                source = loader_obj.get_data(
                    getattr(spec, "origin", getattr(spec, "name", ""))
                )
        if isinstance(source, bytes):
            source = source.decode("utf-8", errors="replace")
        if not source:
            return self.lookup(Path(origin).stem) if origin else None

        stem = str(
            kwargs.get("module_name")
            or getattr(spec, "name", "")
            or Path(origin or "compat_module").stem
        ).split(".")[-1]
        stem = (
            re.sub(r"[^0-9A-Za-z_]+", "_", stem).strip("_")
            or f"extmod_{_rand_token(8)}"
        )
        tmp_dir = Path(self._kernel.MODULES_LOADED_DIR)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"{stem}.py"
        await asyncio.to_thread(tmp_path.write_text, source, encoding="utf-8")

        from .fake_package import load_hikka_module
        from .types import LoadError

        ok, err, _ = await load_hikka_module(self._kernel, str(tmp_path), stem)
        if not ok:
            raise LoadError(err or f"Failed to register module {stem}")
        return self.lookup(stem)

    async def unload_module(self, module_name: str) -> bool:
        try:
            from .fake_package import unload_hikka_module

            return await unload_hikka_module(self._kernel, module_name)
        except Exception:
            return False

    async def register_all(self, no_external: bool = False):
        del no_external
        return self.modules

    def register_commands(self, instance) -> int:
        count = 0
        for name, method in getattr(instance, "commands", {}).items():
            self._kernel.command_handlers[name] = method
            self._kernel.command_owners[name] = instance.__class__.__name__
            count += 1
        return count

    def unregister_commands(self, instance, *_args) -> int:
        removed = 0
        for name in list(getattr(instance, "commands", {})):
            self._kernel.command_handlers.pop(name, None)
            self._kernel.command_owners.pop(name, None)
            removed += 1
        return removed

    def register_inline_stuff(self, instance) -> int:
        count = 0
        for name, method in get_inline_handlers(instance).items():
            self._kernel.inline_handlers[name] = method
            self._kernel.inline_handlers_owners[name] = instance.__class__.__name__
            count += 1
        return count

    def unregister_inline_stuff(self, instance, *_args) -> int:
        removed = 0
        for name in list(get_inline_handlers(instance)):
            self._kernel.inline_handlers.pop(name, None)
            self._kernel.inline_handlers_owners.pop(name, None)
            removed += 1
        return removed

    def register_watchers(self, instance) -> int:
        watchers = getattr(self._kernel, "_hikka_compat_watchers", [])
        watchers.append(instance)
        setattr(self._kernel, "_hikka_compat_watchers", watchers)
        return len(get_watchers(instance))

    def unregister_watchers(self, instance, *_args) -> int:
        watchers = getattr(self._kernel, "_hikka_compat_watchers", [])
        if instance in watchers:
            watchers.remove(instance)
        setattr(self._kernel, "_hikka_compat_watchers", watchers)
        return len(get_watchers(instance))

    def register_raw_handlers(self, instance) -> int:
        handlers = getattr(self._kernel, "_hikka_compat_raw_handlers", [])
        handlers.append(instance)
        setattr(self._kernel, "_hikka_compat_raw_handlers", handlers)
        return len(
            [
                getattr(instance, name)
                for name in dir(instance)
                if callable(getattr(instance, name, None))
                and getattr(getattr(instance, name), "is_raw_handler", False)
            ]
        )

    def unregister_raw_handlers(self, instance, *_args) -> int:
        handlers = getattr(self._kernel, "_hikka_compat_raw_handlers", [])
        if instance in handlers:
            handlers.remove(instance)
        setattr(self._kernel, "_hikka_compat_raw_handlers", handlers)
        return True

    def send_config_one(self, instance) -> bool:
        config = getattr(instance, "config", None)
        if not config:
            return False
        saved_data = {}
        for owner in _instance_owner_names(instance):
            saved = self.db.pointer(owner, "__config__", {})
            data = saved.todict() if hasattr(saved, "todict") else dict(saved)
            saved_data.update(data)
        for option in getattr(config, "_config", {}):
            env_key = f"{instance.__class__.__name__}.{option}"
            if env_key in os.environ:
                saved_data[option] = os.environ[env_key]
        for option, value in saved_data.items():
            try:
                config[option] = value
            except Exception:
                continue
        return True

    async def send_ready_one(self, instance, *args, **kwargs) -> bool:
        if getattr(instance, "_hikka_compat_ready", False):
            return True
        try:
            await _maybe_await(instance.client_ready(self.client, self.db))
        except TypeError:
            await _maybe_await(instance.client_ready())
        except Exception:
            return False
        return True

    async def check_security(self, message, func) -> bool:
        dispatcher = getattr(self.client, "dispatcher", None)
        security = getattr(dispatcher, "security", None)
        if security and hasattr(security, "check"):
            try:
                return bool(await security.check(message=message, func=func))
            except Exception:
                pass
        return True

    async def reload_translations(self) -> bool:
        return True


class Module:
    strings: dict = {"name": "UnknownHikkaModule"}
    strings_ru: dict = {}
    strings_en: dict = {}

    def __init__(self):
        pass

    def _mcub_bind(self, kernel, module_type: str = "native") -> None:
        from .client import FakeClient

        self._kernel = kernel
        self._module_type = module_type

        if not hasattr(kernel, "_hikka_compat_inline_proxy"):
            inline_proxy = InlineProxy(kernel)
            setattr(kernel, "_hikka_compat_inline_proxy", inline_proxy)
        else:
            inline_proxy = kernel._hikka_compat_inline_proxy

        inline_proxy._bind_module(self)

        is_hikka = module_type == "hikka"
        self.client = FakeClient(kernel.client, inline_proxy, is_hikka=is_hikka)
        self._client = self.client

        if getattr(self._client._client, "dispatcher", None) is None:
            self._client._client.dispatcher = types.SimpleNamespace()
        if getattr(self._client._client.dispatcher, "security", None) is None:
            self._client._client.dispatcher.security = _CompatSecurityManager(
                self._client
            )
        _raw_strings = type(self).__dict__.get("strings", {"name": type(self).__name__})
        self._db_owner = _raw_strings.get("name") or type(self).__name__
        self.name = _raw_strings.get("name", self._db_owner)
        self.db = DbProxy(kernel, self._db_owner)
        self._db = self.db
        self.inline = self.client._inline_proxy
        self.tg_id = getattr(kernel, "ADMIN_ID", None)
        self._tg_id = self.tg_id
        self.allmodules = _AllModulesStub(kernel)
        self.allmodules.inline = self.inline
        self.strings = _StringsShim(self, _translator_stub)
        self.translator = _translator_stub

    def get(self, key: str, default=None):
        return self._db.get(self._db_owner, key, default)

    def set(self, key: str, value) -> None:
        self._db.set(self._db_owner, key, value)

    def pointer(self, key: str, default=None, item_type=None):
        return self._db.pointer(self._db_owner, key, default, item_type)

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

    @property
    def aiogram_watchers(self) -> dict:
        return _get_members(self, "aiogram_watcher")

    @commands.setter
    def commands(self, _):
        pass

    @heroku_commands.setter
    def heroku_commands(self, _):
        pass

    @inline_handlers.setter
    def inline_handlers(self, _):
        pass

    @heroku_inline_handlers.setter
    def heroku_inline_handlers(self, _):
        pass

    @callback_handlers.setter
    def callback_handlers(self, _):
        pass

    @heroku_callback_handlers.setter
    def heroku_callback_handlers(self, _):
        pass

    @watchers.setter
    def watchers(self, _):
        pass

    @heroku_watchers.setter
    def heroku_watchers(self, _):
        pass

    def get_prefix(self, *_args, **_kwargs) -> str:
        return getattr(self._kernel, "custom_prefix", ".")

    def get_prefixes(self, *_args, **_kwargs) -> list:
        return [self.get_prefix()]

    def lookup(self, module_name: str) -> Optional["Module"]:
        _, inst = _find_kernel_module(self._kernel, module_name)
        if inst is not None:
            if str(module_name).lower() == "loader":
                return _CompatLoaderProxy(self._kernel, inst)
            return inst
        if str(module_name).lower() == "loader":
            return _CompatLoaderProxy(self._kernel)
        return None

    def get_string(self, key: str) -> str:
        return self.strings.get(key) or key

    async def animate(
        self, message, frames: list, interval: float, *, inline: bool = False
    ):
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

    async def invoke(
        self,
        command: str,
        args: Optional[str] = None,
        peer=None,
        message=None,
        edit: bool = False,
    ):
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

    def config_complete(self):
        pass

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    async def on_dlmod(self) -> None:
        pass

    async def client_ready(self, client=None, db=None) -> None:
        pass

    async def request_join(self, *args, **kwargs) -> bool:
        return True

    async def import_lib(
        self,
        url: str,
        *,
        suspend_on_error: bool = False,
        _did_requirements: bool = False,
    ):
        from .loader import USER_INSTALL, VALID_PIP_PACKAGES
        from .types import SelfSuspend, StringLoader

        async def _raise(exc: Exception):
            if suspend_on_error:
                raise SelfSuspend("Required library is not available or is corrupted.")
            raise exc

        try:
            normalized_url = _normalize_source_url(str(url).strip())
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(normalized_url) as response:
                    response.raise_for_status()
                    code = await response.text()
        except Exception as e:
            await _raise(e)

        module_name = (
            f"__hikka_mcub_library__."
            f"{uuid.uuid5(uuid.NAMESPACE_URL, normalized_url).hex}"
        )
        origin = f"<hikka_compat library {normalized_url}>"
        spec = importlib.machinery.ModuleSpec(
            module_name,
            StringLoader(code, origin),
            origin=origin,
        )

        try:
            lib_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = lib_module
            spec.loader.exec_module(lib_module)
        except ImportError as e:
            if _did_requirements:
                sys.modules.pop(module_name, None)
                await _raise(e)

            requirements = []
            match = VALID_PIP_PACKAGES.search(code)
            if match:
                requirements = [
                    pkg
                    for pkg in map(str.strip, match.group(1).split())
                    if pkg and not pkg.startswith(("-", "_", "."))
                ]
            if not requirements and getattr(e, "name", None):
                requirements = [e.name]

            if not requirements:
                sys.modules.pop(module_name, None)
                await _raise(e)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "-q",
                "--disable-pip-version-check",
                "--no-warn-script-location",
                *["--user"] if USER_INSTALL else [],
                *requirements,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await proc.wait()
            sys.modules.pop(module_name, None)
            importlib.invalidate_caches()
            if rc != 0:
                await _raise(e)
            return await self.import_lib(
                normalized_url,
                suspend_on_error=suspend_on_error,
                _did_requirements=True,
            )
        except Exception as e:
            sys.modules.pop(module_name, None)
            await _raise(e)

        lib_obj = next(
            (
                value()
                for value in vars(lib_module).values()
                if inspect.isclass(value)
                and issubclass(value, Library)
                and value is not Library
            ),
            None,
        )

        if lib_obj is None:
            sys.modules.pop(module_name, None)
            await _raise(ImportError("Invalid library. No Library subclass found"))

        libraries = getattr(self._kernel, "_hikka_compat_libraries", None)
        if not isinstance(libraries, list):
            libraries = []
            setattr(self._kernel, "_hikka_compat_libraries", libraries)

        existing = next(
            (
                lib
                for lib in libraries
                if getattr(lib, "name", None) == lib_obj.__class__.__name__
            ),
            None,
        )
        if existing is not None:
            return existing

        lib_obj.source_url = normalized_url.strip("/")
        lib_obj.allmodules = self.allmodules
        lib_obj.internal_init()

        init_method = getattr(lib_obj, "init", None)
        if callable(init_method):
            try:
                await _maybe_await(init_method())
            except Exception as e:
                sys.modules.pop(module_name, None)
                await _raise(e)

        libraries.append(lib_obj)
        return lib_obj


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

    def _lib_pointer(self, key: str, default=None, item_type=None):
        return self._db.pointer(self.__class__.__name__, key, default, item_type)
