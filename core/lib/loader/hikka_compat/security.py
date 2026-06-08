# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

import logging
import types
from typing import NamedTuple

logger = logging.getLogger(__name__)

OWNER = 1 << 0
SUDO = 1 << 1
SUPPORT = 1 << 2
GROUP_OWNER = 1 << 3
GROUP_ADMIN_ADD_ADMINS = 1 << 4
GROUP_ADMIN_CHANGE_INFO = 1 << 5
GROUP_ADMIN_BAN_USERS = 1 << 6
GROUP_ADMIN_DELETE_MESSAGES = 1 << 7
GROUP_ADMIN_PIN_MESSAGES = 1 << 8
GROUP_ADMIN_INVITE_USERS = 1 << 9
GROUP_ADMIN = 1 << 10
GROUP_MEMBER = 1 << 11
PM = 1 << 12
EVERYONE = 1 << 13

GROUP_ADMIN_ANY = (
    GROUP_ADMIN_ADD_ADMINS
    | GROUP_ADMIN_CHANGE_INFO
    | GROUP_ADMIN_BAN_USERS
    | GROUP_ADMIN_DELETE_MESSAGES
    | GROUP_ADMIN_PIN_MESSAGES
    | GROUP_ADMIN_INVITE_USERS
    | GROUP_ADMIN
)

DEFAULT_PERMISSIONS = OWNER
PUBLIC_PERMISSIONS = GROUP_OWNER | GROUP_ADMIN_ANY | GROUP_MEMBER | PM
ALL = (1 << 13) - 1

BITMAP: dict[str, int] = {
    "OWNER": OWNER,
    "GROUP_OWNER": GROUP_OWNER,
    "GROUP_ADMIN_ADD_ADMINS": GROUP_ADMIN_ADD_ADMINS,
    "GROUP_ADMIN_CHANGE_INFO": GROUP_ADMIN_CHANGE_INFO,
    "GROUP_ADMIN_BAN_USERS": GROUP_ADMIN_BAN_USERS,
    "GROUP_ADMIN_DELETE_MESSAGES": GROUP_ADMIN_DELETE_MESSAGES,
    "GROUP_ADMIN_PIN_MESSAGES": GROUP_ADMIN_PIN_MESSAGES,
    "GROUP_ADMIN_INVITE_USERS": GROUP_ADMIN_INVITE_USERS,
    "GROUP_ADMIN": GROUP_ADMIN,
    "GROUP_MEMBER": GROUP_MEMBER,
    "PM": PM,
    "EVERYONE": EVERYONE,
}


def _sec(func, flags: int):
    prev = getattr(func, "security", 0)
    func.security = prev | OWNER | flags
    return func


def _deprecated_sec(name: str):
    def decorator(func):
        return func

    return decorator


def owner(func):
    return _sec(func, OWNER)


def group_owner(func):
    return _sec(func, GROUP_OWNER)


def group_admin(func):
    return _sec(func, GROUP_ADMIN)


def group_admin_add_admins(func):
    return _sec(func, GROUP_ADMIN_ADD_ADMINS)


def group_admin_change_info(func):
    return _sec(func, GROUP_ADMIN_CHANGE_INFO)


def group_admin_ban_users(func):
    return _sec(func, GROUP_ADMIN_BAN_USERS)


def group_admin_delete_messages(func):
    return _sec(func, GROUP_ADMIN_DELETE_MESSAGES)


def group_admin_pin_messages(func):
    return _sec(func, GROUP_ADMIN_PIN_MESSAGES)


def group_admin_invite_users(func):
    return _sec(func, GROUP_ADMIN_INVITE_USERS)


def group_member(func):
    return _sec(func, GROUP_MEMBER)


def pm(func):
    return _sec(func, PM)


def unrestricted(func):
    return _sec(func, ALL)


def inline_everyone(func):
    return _sec(func, EVERYONE)


class SecurityGroup(NamedTuple):
    name: str
    users: list[int]
    permissions: list[dict]


class SecurityChecker:
    """
    Runtime permission checker for Hikka/Heroku modules.
    Validates user permissions against command security bitmaps.
    """

    def __init__(self, client=None, db=None, owner_id: int | None = None):
        self._client = client
        self._db = db
        self._owner_id = owner_id
        self._cache: dict[str, tuple[int, int | bool]] = {}

        self.owner: int | None = owner_id
        self.sudo: list[int] = []
        self.support: list[int] = []
        self.groups: list[SecurityGroup] = []

        if db is not None:
            self._load_from_db()

    def _load_from_db(self):
        try:
            sec = self._db.get("heroku.security", "config", {})
            self.owner = sec.get("owner", self._owner_id)
            self.sudo = sec.get("sudo", [])
            self.support = sec.get("support", [])
            self.groups = [SecurityGroup(**g) for g in sec.get("groups", [])]
        except Exception:
            pass

    @property
    def all_users(self) -> list[int]:
        users = set()
        if self.owner:
            users.add(self.owner)
        users.update(self.sudo)
        users.update(self.support)
        return list(users)

    def get_flags(self, user_id: int) -> int:
        flags = 0
        if user_id == self.owner:
            flags |= OWNER | SUDO | SUPPORT
        if user_id in self.sudo:
            flags |= SUDO | SUPPORT
        if user_id in self.support:
            flags |= SUPPORT
        return flags

    async def check(self, func, event) -> bool:
        security = getattr(func, "security", 0)
        if not security:
            return True

        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if user_id is None:
            user_id = getattr(event, "sender_id", None)
        if user_id is None:
            return True

        user_flags = self.get_flags(user_id)

        if security & OWNER and (user_flags & OWNER):
            return True
        if security & (SUDO | SUPPORT) and (user_flags & (SUDO | SUPPORT)):
            return True
        if security & EVERYONE:
            return True

        chat_id = getattr(event, "chat_id", None)
        if chat_id is None:
            msg = getattr(event, "message", None) or getattr(event, "_event", None)
            chat_id = getattr(msg, "chat_id", None) if msg else None

        if security & PM and chat_id is not None and chat_id == user_id:
            return True

        if (
            chat_id is not None
            and isinstance(chat_id, int)
            and chat_id > 0
            and security & PM
        ):
            return True

        if (
            chat_id is not None
            and isinstance(chat_id, int)
            and chat_id < 0
            and security & GROUP_MEMBER
        ):
            return True

        if chat_id is not None and isinstance(chat_id, int) and chat_id < 0:
            admin_flags = self._get_admin_flags(chat_id, user_id)
            if admin_flags is not None:
                if security & GROUP_ADMIN_ANY and admin_flags & GROUP_ADMIN_ANY:
                    return True
                if security & GROUP_OWNER and admin_flags & GROUP_OWNER:
                    return True
                if security & GROUP_MEMBER:
                    return True

        return False

    def _get_admin_flags(self, chat_id: int, user_id: int) -> int | None:
        cache_key = f"{chat_id}:{user_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            ts, flags = cached
            if ts > 0:
                return flags

        if self._client is None:
            return None

        try:
            import asyncio

            asyncio.ensure_future(self._resolve_admin_flags(chat_id, user_id))
            return 0
        except Exception:
            return None

    async def _resolve_admin_flags(self, chat_id: int, user_id: int) -> int:
        cache_key = f"{chat_id}:{user_id}"
        flags = 0

        if self._client is None:
            return flags

        try:

            entity = await self._client.get_entity(chat_id)
            participant = await self._client.get_permissions(entity, user_id)

            if hasattr(participant, "is_creator") and participant.is_creator:
                flags |= GROUP_OWNER | GROUP_ADMIN_ANY | GROUP_MEMBER
            elif hasattr(participant, "admin_rights") and participant.admin_rights:
                rights = participant.admin_rights
                flags |= GROUP_MEMBER
                if rights.add_admins:
                    flags |= GROUP_ADMIN_ADD_ADMINS
                if rights.change_info:
                    flags |= GROUP_ADMIN_CHANGE_INFO
                if rights.ban_users:
                    flags |= GROUP_ADMIN_BAN_USERS
                if rights.delete_messages:
                    flags |= GROUP_ADMIN_DELETE_MESSAGES
                if rights.pin_messages:
                    flags |= GROUP_ADMIN_PIN_MESSAGES
                if rights.invite_users:
                    flags |= GROUP_ADMIN_INVITE_USERS
            else:
                flags |= GROUP_MEMBER

            self._cache[cache_key] = (60, flags)
            return flags
        except Exception as e:
            logger.debug("Failed to resolve admin flags: %s", e)
            self._cache[cache_key] = (0, 0)
            return 0

    def clear_cache(self):
        self._cache.clear()


sudo = _deprecated_sec("sudo")
support = _deprecated_sec("support")


class SecurityGroup(NamedTuple):
    name: str
    users: list[int]
    permissions: list[dict]

    def todict(self) -> dict:
        return {
            "name": self.name,
            "users": list(self.users),
            "permissions": list(self.permissions),
        }


class _SecurityModule(types.ModuleType):
    pass


_security_mod = _SecurityModule("__hikka_mcub_compat_security__")
for _name, _val in {
    "OWNER": OWNER,
    "SUDO": SUDO,
    "SUPPORT": SUPPORT,
    "GROUP_OWNER": GROUP_OWNER,
    "GROUP_ADMIN_ADD_ADMINS": GROUP_ADMIN_ADD_ADMINS,
    "GROUP_ADMIN_CHANGE_INFO": GROUP_ADMIN_CHANGE_INFO,
    "GROUP_ADMIN_BAN_USERS": GROUP_ADMIN_BAN_USERS,
    "GROUP_ADMIN_DELETE_MESSAGES": GROUP_ADMIN_DELETE_MESSAGES,
    "GROUP_ADMIN_PIN_MESSAGES": GROUP_ADMIN_PIN_MESSAGES,
    "GROUP_ADMIN_INVITE_USERS": GROUP_ADMIN_INVITE_USERS,
    "GROUP_ADMIN": GROUP_ADMIN,
    "GROUP_MEMBER": GROUP_MEMBER,
    "PM": PM,
    "EVERYONE": EVERYONE,
    "GROUP_ADMIN_ANY": GROUP_ADMIN_ANY,
    "DEFAULT_PERMISSIONS": DEFAULT_PERMISSIONS,
    "PUBLIC_PERMISSIONS": PUBLIC_PERMISSIONS,
    "ALL": ALL,
    "BITMAP": BITMAP,
    "owner": owner,
    "group_owner": group_owner,
    "group_admin": group_admin,
    "group_admin_add_admins": group_admin_add_admins,
    "group_admin_change_info": group_admin_change_info,
    "group_admin_ban_users": group_admin_ban_users,
    "group_admin_delete_messages": group_admin_delete_messages,
    "group_admin_pin_messages": group_admin_pin_messages,
    "group_admin_invite_users": group_admin_invite_users,
    "group_member": group_member,
    "pm": pm,
    "unrestricted": unrestricted,
    "inline_everyone": inline_everyone,
    "sudo": sudo,
    "support": support,
    "SecurityGroup": SecurityGroup,
}.items():
    setattr(_security_mod, _name, _val)
