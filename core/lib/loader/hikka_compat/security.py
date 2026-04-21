# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import types
from typing import NamedTuple

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
