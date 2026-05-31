# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
"""Safe proxies and pointer types for Heroku API compat."""

from __future__ import annotations

import json
import logging
import typing

logger = logging.getLogger(__name__)


class PointerList(list):
    """Pointer to list saved in database - persists every mutation."""

    def __init__(
        self,
        db,
        module: str,
        key: str,
        default: typing.Optional[typing.Any] = None,
    ):
        self._db = db
        self._module = module
        self._key = key
        self._default = default
        super().__init__(db.get(module, key, default) or [])

    @property
    def data(self) -> list:
        return list(self)

    @data.setter
    def data(self, value: list):
        self.clear()
        self.extend(value)
        self._save()

    def __repr__(self):
        return f"PointerList({list(self)})"

    def __str__(self):
        return f"PointerList({list(self)})"

    def __delitem__(self, __i):
        a = super().__delitem__(__i)
        self._save()
        return a

    def __setitem__(self, __i, __v):
        a = super().__setitem__(__i, __v)
        self._save()
        return a

    def __iadd__(self, __x):
        a = super().__iadd__(__x)
        self._save()
        return a

    def __imul__(self, __x):
        a = super().__imul__(__x)
        self._save()
        return a

    def append(self, value):
        super().append(value)
        self._save()

    def extend(self, value):
        super().extend(value)
        self._save()

    def insert(self, index, value):
        super().insert(index, value)
        self._save()

    def remove(self, value):
        super().remove(value)
        self._save()

    def pop(self, index=-1):
        a = super().pop(index)
        self._save()
        return a

    def clear(self):
        super().clear()
        self._save()

    def _save(self):
        self._db.set(self._module, self._key, list(self))


class PointerDict(dict):
    """Pointer to dict saved in database - persists every mutation."""

    def __init__(
        self,
        db,
        module: str,
        key: str,
        default: typing.Optional[typing.Any] = None,
    ):
        self._db = db
        self._module = module
        self._key = key
        self._default = default
        saved = db.get(module, key, None)
        super().__init__(saved if isinstance(saved, dict) else (default or {}))

    @property
    def data(self) -> dict:
        return dict(self)

    @data.setter
    def data(self, value: dict):
        self.clear()
        self.update(value)
        self._save()

    def __repr__(self):
        return f"PointerDict({dict(self)})"

    def __str__(self):
        return f"PointerDict({dict(self)})"

    def __delitem__(self, __i):
        a = super().__delitem__(__i)
        self._save()
        return a

    def __setitem__(self, __i, __v):
        a = super().__setitem__(__i, __v)
        self._save()
        return a

    def __ior__(self, __x):
        a = super().__ior__(__x)
        self._save()
        return a

    def pop(self, __i, *args):
        a = super().pop(__i, *args)
        self._save()
        return a

    def popitem(self):
        a = super().popitem()
        self._save()
        return a

    def clear(self):
        super().clear()
        self._save()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._save()

    def setdefault(self, __key, __default=None):
        result = super().setdefault(__key, __default)
        self._save()
        return result

    def _save(self):
        self._db.set(self._module, self._key, dict(self))


class SafeClientProxy:
    """
    Wraps Telethon client with restricted API for hikka modules.

    Only exposes safe methods; blocks sensitive operations (call,
    invite, promote, delete_account, etc.).
    """

    _ALLOWED = frozenset(
        {
            "send_message",
            "send_file",
            "edit_message",
            "delete_messages",
            "get_entity",
            "get_me",
            "get_dialogs",
            "get_messages",
            "get_permissions",
            "get_full_user",
            "get_full_channel",
            "resolve_entity",
            "forward_messages",
            "get_common_chats",
            "is_bot",
            "parse_mode",
        }
    )

    _ALLOWED_CALLS = frozenset(
        {
            "GetHistoryRequest",
            "GetDialogsRequest",
            "CheckUsernameRequest",
            "UpdateUsernameRequest",
            "GetFullUserRequest",
            "GetFullChannelRequest",
            "GetCommonChatsRequest",
        }
    )

    def __init__(self, client, owner_id: int | None = None):
        self._client = client
        self._owner_id = owner_id or getattr(client, "tg_id", None)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(f"Access denied: {name}")

        target = getattr(self._client, name, None)
        if target is None or name not in self._ALLOWED:
            raise AttributeError(
                f"SafeClientProxy: '{name}' is not allowed for modules"
            )
        return target

    async def __call__(self, request, *args, **kwargs):
        """Block MTProto calls except whitelisted ones."""
        req_name = type(request).__name__
        if req_name not in self._ALLOWED_CALLS:
            raise RuntimeError(
                f"SafeClientProxy: MTProto call '{req_name}' is not allowed "
                f"for modules"
            )
        return await self._client(request, *args, **kwargs)

    @property
    def tg_id(self) -> int | None:
        return self._owner_id

    @property
    def _bot(self) -> typing.Any:
        """Aiogram bot reference (compat stub)."""
        return None

    # passthrough properties
    @property
    def parse_mode(self):
        return getattr(self._client, "parse_mode", "html")


class SafeDatabaseProxy:
    """Wraps database access for modules - restricts to own namespace."""

    def __init__(self, db, module_name: str):
        self._db = db
        self._module_name = module_name

    def get(self, key: str, default: typing.Any = None) -> typing.Any:
        return self._db.get(self._module_name, key, default)

    def set(self, key: str, value: typing.Any) -> bool:
        return self._db.set(self._module_name, key, value)

    def __getitem__(self, key: str) -> typing.Any:
        return self.get(key)

    def __setitem__(self, key: str, value: typing.Any):
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return self.get(key, _MISSING) is not _MISSING

    def keys(self):
        return self._db.keys(self._module_name)

    def values(self):
        return self._db.values(self._module_name)

    def items(self):
        return self._db.items(self._module_name)

    def get_key(self, key: str, default: typing.Any = None) -> typing.Any:
        return self.get(key, default)

    def PointerList(self, key: str, default: list | None = None) -> PointerList:
        return PointerList(self._db, self._module_name, key, default)

    def PointerDict(self, key: str, default: dict | None = None) -> PointerDict:
        return PointerDict(self._db, self._module_name, key, default)


class SafeInlineProxy:
    """Wraps inline manager for modules with restricted access."""

    def __init__(self, inline_proxy, module_name: str):
        self._inline = inline_proxy
        self._module_name = module_name

    @property
    def _bot(self) -> typing.Any:
        """Aiogram bot reference (compat stub)."""
        return getattr(self._inline, "_bot", None)

    @property
    def bot(self) -> typing.Any:
        return self._bot

    @property
    def bot_username(self) -> str:
        return getattr(self._inline, "bot_username", "")

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(f"SafeInlineProxy: access denied: {name}")
        return getattr(self._inline, name)

    async def form(self, *args, **kwargs):
        if hasattr(self._inline, "form"):
            return await self._inline.form(*args, **kwargs)
        logger.warning("InlineProxy.form not implemented")
        return False

    async def gallery(self, *args, **kwargs):
        if hasattr(self._inline, "gallery"):
            return await self._inline.gallery(*args, **kwargs)
        logger.warning("InlineProxy.gallery not implemented")
        return False

    async def list(self, *args, **kwargs):
        if hasattr(self._inline, "list"):
            return await self._inline.list(*args, **kwargs)
        logger.warning("InlineProxy.list not implemented")
        return False

    async def query_gallery(self, *args, **kwargs):
        if hasattr(self._inline, "query_gallery"):
            return await self._inline.query_gallery(*args, **kwargs)
        logger.warning("InlineProxy.query_gallery not implemented")
        return False


class SafeAllModulesProxy:
    """Wrapper that provides safe .client, .db, .inline to every module."""

    def __init__(
        self,
        real_allmodules,
        safe_client: SafeClientProxy | None = None,
        safe_allclients=None,
        safe_db: SafeDatabaseProxy | None = None,
        safe_inline: SafeInlineProxy | None = None,
    ):
        self._target = real_allmodules
        self.client = safe_client or real_allmodules.client
        self.allclients = safe_allclients or getattr(
            real_allmodules, "allclients", None
        )
        self.db = safe_db or real_allmodules.db
        self.inline = safe_inline or getattr(real_allmodules, "inline", None)

    def __getattr__(self, name: str):
        return getattr(self._target, name)

    def __call__(self, *args, **kwargs):
        return self._target(*args, **kwargs)

    def _get_real_allmodules(self):
        return self._target


_MISSING = object()
