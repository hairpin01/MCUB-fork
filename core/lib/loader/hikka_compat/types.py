# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import copy as _copy
import time as _time
import types as _types
import typing as _typing
from importlib.abc import SourceLoader as _SourceLoader
from typing import Any, Callable, Optional, Union

JSONSerializable = Union[str, int, float, bool, list, dict, None]
HerokuReplyMarkup = Union[_typing.List[_typing.List[dict]], _typing.List[dict], dict]
ListLike = Union[list, set, tuple]
Command = Callable[..., _typing.Awaitable[_typing.Any]]


class StringLoader(_SourceLoader):
    def __init__(self, data: str, origin: str):
        self.data = data.encode("utf-8") if isinstance(data, str) else data
        self.origin = origin

    def get_source(self, _=None) -> str:
        return self.data.decode("utf-8")

    def get_code(self, fullname: str):
        src = self.get_data(fullname)
        return compile(src, self.origin, "exec", dont_inherit=True) if src else None

    def get_filename(self, *args, **kwargs) -> str:
        return self.origin

    def get_data(self, *args, **kwargs) -> bytes:
        return self.data


class LoadError(Exception):
    def __init__(self, error_message: str = ""):
        self._error = error_message
        super().__init__(error_message)

    def __str__(self) -> str:
        return self._error


class CoreOverwriteError(LoadError):
    def __init__(self, module: Optional[str] = None, command: Optional[str] = None):
        self.type = "module" if module else "command"
        self.target = module or command
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"{'Module' if self.type == 'module' else 'Command'} {self.target} will not be overwritten"


class CoreUnloadError(Exception):
    def __init__(self, module: str):
        self.module = module
        super().__init__()

    def __str__(self) -> str:
        return f"Module {self.module} will not be unloaded, because it's core"


class SelfUnload(Exception):
    def __init__(self, error_message: str = ""):
        self._error = error_message
        super().__init__(error_message)

    def __str__(self) -> str:
        return self._error


class SelfSuspend(Exception):
    def __init__(self, error_message: str = ""):
        self._error = error_message
        super().__init__(error_message)

    def __str__(self) -> str:
        return self._error


class StopLoop(Exception):
    pass


class CacheRecordEntity:
    def __init__(self, hashable_entity, resolved_entity, exp: int):
        self.entity = _copy.deepcopy(resolved_entity)
        self._hashable_entity = _copy.deepcopy(hashable_entity)
        self._exp = round(_time.time() + exp)
        self.ts = _time.time()

    @property
    def expired(self) -> bool:
        return self._exp < _time.time()

    def __eq__(self, other) -> bool:
        return hash(other) == hash(self)

    def __hash__(self) -> int:
        return hash(self._hashable_entity)

    def __str__(self) -> str:
        return f"CacheRecordEntity of {self.entity}"


class CacheRecordPerms:
    def __init__(self, hashable_entity, hashable_user, resolved_perms, exp: int):
        self.perms = _copy.deepcopy(resolved_perms)
        self._hashable_entity = _copy.deepcopy(hashable_entity)
        self._hashable_user = _copy.deepcopy(hashable_user)
        self._exp = round(_time.time() + exp)
        self.ts = _time.time()

    @property
    def expired(self) -> bool:
        return self._exp < _time.time()

    def __eq__(self, other) -> bool:
        return hash(other) == hash(self)

    def __hash__(self) -> int:
        return hash((self._hashable_entity, self._hashable_user))

    def __str__(self) -> str:
        return f"CacheRecordPerms of {self.perms}"


class CacheRecordFullChannel:
    def __init__(self, channel_id: int, full_channel, exp: int):
        self.channel_id = channel_id
        self.full_channel = full_channel
        self._exp = round(_time.time() + exp)
        self.ts = _time.time()

    @property
    def expired(self) -> bool:
        return self._exp < _time.time()

    def __eq__(self, other) -> bool:
        return hash(other) == hash(self)

    def __hash__(self) -> int:
        return hash(self.channel_id)

    def __str__(self) -> str:
        return f"CacheRecordFullChannel of {self.channel_id}"


class CacheRecordFullUser:
    def __init__(self, user_id: int, full_user, exp: int):
        self.user_id = user_id
        self.full_user = full_user
        self._exp = round(_time.time() + exp)
        self.ts = _time.time()

    @property
    def expired(self) -> bool:
        return self._exp < _time.time()

    def __eq__(self, other) -> bool:
        return hash(other) == hash(self)

    def __hash__(self) -> int:
        return hash(self.user_id)

    def __str__(self) -> str:
        return f"CacheRecordFullUser of {self.user_id}"


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


def get_commands(mod) -> dict:
    return _get_members(mod, "cmd", "is_command")


def get_inline_handlers(mod) -> dict:
    return _get_members(mod, "_inline_handler", "is_inline_handler")


def get_callback_handlers(mod) -> dict:
    return _get_members(mod, "_callback_handler", "is_callback_handler")


def get_watchers(mod) -> dict:
    return _get_members(mod, "watcher", "is_watcher", strict=True)


class PointerDict(dict):
    """Dict with pointer-like behavior for module config."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pointer_keys = set()
        for k, v in self.items():
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                self._pointer_keys.add(k)

    def pointer(self, key: str, default=None):
        return self.get(key, default)

    def _resolve_pointer(self, key: str):
        val = self.get(key)
        if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
            inner_key = val[1:-1]
            return self.get(inner_key, val)
        return val


class PointerList(list):
    """List with pointer-like behavior for module config."""

    def pointer(self, index: int, default=None):
        try:
            return self[index]
        except IndexError:
            return default


_types_mod = _types.ModuleType("__hikka_mcub_compat_types__")
for _name, _val in {
    "JSONSerializable": JSONSerializable,
    "HerokuReplyMarkup": HerokuReplyMarkup,
    "ListLike": ListLike,
    "Command": Command,
    "StringLoader": StringLoader,
    "LoadError": LoadError,
    "CoreOverwriteError": CoreOverwriteError,
    "CoreUnloadError": CoreUnloadError,
    "SelfUnload": SelfUnload,
    "SelfSuspend": SelfSuspend,
    "StopLoop": StopLoop,
    "CacheRecordEntity": CacheRecordEntity,
    "CacheRecordPerms": CacheRecordPerms,
    "CacheRecordFullChannel": CacheRecordFullChannel,
    "CacheRecordFullUser": CacheRecordFullUser,
    "get_commands": get_commands,
    "get_inline_handlers": get_inline_handlers,
    "get_callback_handlers": get_callback_handlers,
    "get_watchers": get_watchers,
    "PointerDict": PointerDict,
    "PointerList": PointerList,
}.items():
    setattr(_types_mod, _name, _val)
