# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, NamedTuple

_GLOBAL_SCOPE = "*"


SecurityId = int | str
SecurityHandler = Callable[..., Any]


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

BITMAP = {
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

# Matches Heroku/Hikka's historical value: all bits except EVERYONE.
ALL = (1 << 13) - 1
VALID_PERMISSIONS = ALL | EVERYONE


class SecurityGroup(NamedTuple):
    """Represents a named trusted/security group."""

    name: str
    users: list[int]
    permissions: list[dict[str, Any]]


def _sec(func: SecurityHandler, flags: int) -> SecurityHandler:
    """Attach Heroku/Hikka-style security flags to *func*."""

    prev = getattr(func, "security", 0)
    setattr(func, "security", prev | OWNER | flags)
    return func


def owner(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, OWNER)


def _deprecated(name: str) -> Callable[[SecurityHandler], SecurityHandler]:
    def decorator(func: SecurityHandler) -> SecurityHandler:
        logging.getLogger(__name__).debug(
            "Using deprecated security decorator `%s`, which has no effect",
            name,
        )
        return func

    return decorator


sudo = _deprecated("sudo")
support = _deprecated("support")


def group_owner(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_OWNER)


def group_admin_add_admins(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN_ADD_ADMINS)


def group_admin_change_info(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN_CHANGE_INFO)


def group_admin_ban_users(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN_BAN_USERS)


def group_admin_delete_messages(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN_DELETE_MESSAGES)


def group_admin_pin_messages(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN_PIN_MESSAGES)


def group_admin_invite_users(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN_INVITE_USERS)


def group_admin(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_ADMIN)


def group_member(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, GROUP_MEMBER)


def pm(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, PM)


def unrestricted(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, ALL)


def inline_everyone(func: SecurityHandler) -> SecurityHandler:
    return _sec(func, EVERYONE)


@dataclass(frozen=True)
class EventSecurityMeta:
    """Small, sync-only event snapshot used by chat security rules."""

    chat_id: SecurityId | None = None
    user_id: SecurityId | None = None
    raw_text: str = ""
    message_id: SecurityId | None = None


@dataclass(frozen=True)
class SecurityChatDecision:
    """Result of a security delivery decision."""

    allowed: bool
    reason: str = ""
    scope: str = _GLOBAL_SCOPE
    chat_id: SecurityId | None = None
    user_id: SecurityId | None = None


@dataclass
class SecurityChatRules:
    """Rules for a single scope: global (``*``) or a concrete module."""

    allowed_chats: set[SecurityId] = field(default_factory=set)
    ignored_chats: set[SecurityId] = field(default_factory=set)
    blacklisted_users: set[SecurityId] = field(default_factory=set)

    def is_empty(self) -> bool:
        return not (self.allowed_chats or self.ignored_chats or self.blacklisted_users)


class SecurityChats:
    """Central chat/user security API for module calls and launchers.

    Modules can configure either global rules (``module=None``) or rules for a
    concrete module name.  A launcher passes its module name to
    :meth:`can_process_event`; the manager then applies global rules first and
    module-local rules second.

    Chat rules are permissive by default:
    - ``ignored_chats`` always blocks matching chat ids;
    - if ``allowed_chats`` is non-empty, only those chats are allowed;
    - events without a chat id are not blocked by chat allow-lists, but user
      blacklist rules are still applied when a sender id is available.
    """

    LOG_CACHE_LIMIT = 2048

    def __init__(self, kernel: Any | None = None) -> None:
        self.kernel = kernel
        self.logger = getattr(kernel, "logger", None) or logging.getLogger(__name__)
        self.default = DEFAULT_PERMISSIONS
        self.bounding_mask = VALID_PERMISSIONS
        self.owner: list[SecurityId] = self._load_owner_ids()
        self.all_users: list[SecurityId] = list(self.owner)
        self._rules: dict[str, SecurityChatRules] = {}
        self._logged_blacklist_keys: list[tuple[Any, ...]] = []
        self._logged_blacklist_seen: set[tuple[Any, ...]] = set()

    def refresh_owners(self) -> list[SecurityId]:
        """Refresh and return known owner/admin ids from the kernel."""

        self.owner = self._load_owner_ids()
        owner_set = set(self.owner)
        if set(self.all_users) != owner_set:
            self.all_users = list(self.owner)
        return self.owner

    def get_flags(self, func: SecurityHandler | int | None) -> int:
        """Return Heroku/Hikka-style security flags for a handler or raw mask."""

        if isinstance(func, int):
            config = func
        elif func is None:
            config = self.default
        else:
            config = getattr(func, "security", self.default)

        try:
            config = int(config)
        except (TypeError, ValueError):
            self.logger.error("Security config is not an int: %r", config)
            return self.default

        unknown = config & ~VALID_PERMISSIONS
        if unknown:
            self.logger.error("Security config contains unknown bits: %r", unknown)
            config &= VALID_PERMISSIONS

        return config & self.bounding_mask

    async def check(
        self,
        event: Any,
        func: SecurityHandler | int | None = None,
        *,
        module: str | None = None,
        action: str = "event",
        inline_cmd: str | None = None,
    ) -> bool:
        """Heroku-compatible async check entrypoint.

        MCUB keeps the core chat/user allow-list check synchronous; this async
        wrapper exists so dispatcher code and modules can use the familiar
        Heroku/Hikka ``security.check(...)`` shape when needed.
        """

        return self.check_sync(
            event,
            func,
            module=module,
            action=action,
            inline_cmd=inline_cmd,
        )

    def check_sync(
        self,
        event: Any,
        func: SecurityHandler | int | None = None,
        *,
        module: str | None = None,
        action: str = "event",
        inline_cmd: str | None = None,
    ) -> bool:
        """Synchronous security check used by MCUB dispatchers."""

        if not self.can_process_event(event, module=module, action=action):
            return False
        return self._matches_permission_flags(event, self.get_flags(func), inline_cmd)

    def _matches_permission_flags(
        self,
        event: Any,
        flags: int,
        inline_cmd: str | None = None,
    ) -> bool:
        if flags & EVERYONE:
            return True

        meta = self.event_meta(event)
        if self._is_owner_event(event, meta):
            return True

        if inline_cmd and flags & PM:
            return True

        if flags & PM and self._event_is_private(event):
            return True

        group_bits = GROUP_OWNER | GROUP_ADMIN_ANY | GROUP_MEMBER
        if flags & group_bits and self._event_is_group(event):
            return True

        return False

    def _load_owner_ids(self) -> list[SecurityId]:
        kernel = self.kernel
        client = getattr(kernel, "client", None)
        candidates = (
            getattr(kernel, "ADMIN_ID", None),
            getattr(kernel, "tg_id", None),
            getattr(client, "tg_id", None),
            getattr(client, "user_id", None),
        )

        owners: list[SecurityId] = []
        seen: set[SecurityId] = set()
        for value in candidates:
            normalized = self._normalize_id(value)
            if normalized is None or normalized in seen:
                continue
            owners.append(normalized)
            seen.add(normalized)
        return owners

    def _is_owner_event(self, event: Any, meta: EventSecurityMeta) -> bool:
        if self._event_attr(event, "out", default=False):
            return True

        user_id = meta.user_id
        if user_id is None:
            return False
        return user_id in self.refresh_owners()

    def _event_is_private(self, event: Any) -> bool:
        explicit = self._event_attr(event, "is_private", default=None)
        if explicit is not None:
            return bool(explicit)

        meta = self.event_meta(event)
        return meta.chat_id is not None and meta.chat_id == meta.user_id

    def _event_is_group(self, event: Any) -> bool:
        explicit = self._event_attr(event, "is_group", default=None)
        if explicit is not None:
            return bool(explicit)
        if self._event_is_private(event):
            return False
        return self.event_meta(event).chat_id is not None

    @staticmethod
    def _event_attr(event: Any, attr: str, default: Any = None) -> Any:
        for source in (
            event,
            getattr(event, "message", None),
            getattr(event, "query", None),
            getattr(event, "original_update", None),
        ):
            if source is None:
                continue
            value = getattr(source, attr, None)
            if value is not None:
                return value
        return default

    def allow_chat(self, chat_id: Any, *, module: str | None = None) -> None:
        """Allow *chat_id* for the global scope or for *module* only."""

        normalized = self._normalize_id(chat_id)
        if normalized is None:
            return
        rules = self._rules_for(module)
        rules.ignored_chats.discard(normalized)
        rules.allowed_chats.add(normalized)

    def allow_chats(
        self, chat_ids: Iterable[Any], *, module: str | None = None
    ) -> None:
        """Add several allowed chats."""

        for chat_id in chat_ids:
            self.allow_chat(chat_id, module=module)

    def set_allowed_chats(
        self, chat_ids: Iterable[Any], *, module: str | None = None
    ) -> None:
        """Replace the allow-list for a scope."""

        rules = self._rules_for(module)
        rules.allowed_chats = self._normalize_many(chat_ids)
        rules.ignored_chats.difference_update(rules.allowed_chats)

    def clear_allowed_chats(self, *, module: str | None = None) -> None:
        """Disable allow-list mode for a scope."""

        self._rules_for(module).allowed_chats.clear()

    def ignore_chat(self, chat_id: Any, *, module: str | None = None) -> None:
        """Block *chat_id* for the global scope or for *module* only."""

        normalized = self._normalize_id(chat_id)
        if normalized is None:
            return
        rules = self._rules_for(module)
        rules.allowed_chats.discard(normalized)
        rules.ignored_chats.add(normalized)

    block_chat = ignore_chat
    deny_chat = ignore_chat

    def ignore_chats(
        self, chat_ids: Iterable[Any], *, module: str | None = None
    ) -> None:
        """Block several chats."""

        for chat_id in chat_ids:
            self.ignore_chat(chat_id, module=module)

    def unignore_chat(self, chat_id: Any, *, module: str | None = None) -> None:
        """Remove *chat_id* from the ignored chat set."""

        normalized = self._normalize_id(chat_id)
        if normalized is None:
            return
        self._rules_for(module).ignored_chats.discard(normalized)

    unblock_chat = unignore_chat

    def blacklist_user(self, user_id: Any, *, module: str | None = None) -> None:
        """Block events from *user_id*."""

        normalized = self._normalize_id(user_id)
        if normalized is None:
            return
        self._rules_for(module).blacklisted_users.add(normalized)

    def blacklist_users(
        self, user_ids: Iterable[Any], *, module: str | None = None
    ) -> None:
        """Block events from several users."""

        for user_id in user_ids:
            self.blacklist_user(user_id, module=module)

    def unblacklist_user(self, user_id: Any, *, module: str | None = None) -> None:
        """Remove *user_id* from the blacklist."""

        normalized = self._normalize_id(user_id)
        if normalized is None:
            return
        self._rules_for(module).blacklisted_users.discard(normalized)

    whitelist_user = unblacklist_user

    def reset(self, *, module: str | None = None) -> None:
        """Clear all rules for one scope."""

        self._rules.pop(self._scope(module), None)

    def reset_all(self) -> None:
        """Clear all chat/user security rules."""

        self._rules.clear()
        self._logged_blacklist_keys.clear()
        self._logged_blacklist_seen.clear()

    def snapshot(self) -> dict[str, dict[str, tuple[SecurityId, ...]]]:
        """Return an immutable-ish snapshot useful for module UIs/debugging."""

        result: dict[str, dict[str, tuple[SecurityId, ...]]] = {}
        for scope, rules in self._rules.items():
            result[scope] = {
                "allowed_chats": tuple(rules.allowed_chats),
                "ignored_chats": tuple(rules.ignored_chats),
                "blacklisted_users": tuple(rules.blacklisted_users),
            }
        return result

    def can_process_event(
        self,
        event: Any,
        *,
        module: str | None = None,
        action: str = "event",
    ) -> bool:
        """Return True when a command/watcher/event may be delivered."""

        return self.check_event(event, module=module, action=action).allowed

    def check_event(
        self,
        event: Any,
        *,
        module: str | None = None,
        action: str = "event",
    ) -> SecurityChatDecision:
        """Evaluate *event* against global and module-local rules."""

        meta = self.event_meta(event)

        for scope, rules in self._iter_scope_rules(module):
            if meta.user_id is not None and meta.user_id in rules.blacklisted_users:
                self._log_blacklisted_sender(meta)
                return SecurityChatDecision(
                    allowed=False,
                    reason=f"{action}:user_blacklisted",
                    scope=scope,
                    chat_id=meta.chat_id,
                    user_id=meta.user_id,
                )

        if meta.chat_id is None:
            return SecurityChatDecision(
                allowed=True,
                reason="chat_id_missing",
                scope=self._scope(module),
                chat_id=None,
                user_id=meta.user_id,
            )

        for scope, rules in self._iter_scope_rules(module):
            if meta.chat_id in rules.ignored_chats:
                return SecurityChatDecision(
                    allowed=False,
                    reason=f"{action}:chat_ignored",
                    scope=scope,
                    chat_id=meta.chat_id,
                    user_id=meta.user_id,
                )
            if rules.allowed_chats and meta.chat_id not in rules.allowed_chats:
                return SecurityChatDecision(
                    allowed=False,
                    reason=f"{action}:chat_not_allowed",
                    scope=scope,
                    chat_id=meta.chat_id,
                    user_id=meta.user_id,
                )

        return SecurityChatDecision(
            allowed=True,
            reason="allowed",
            scope=self._scope(module),
            chat_id=meta.chat_id,
            user_id=meta.user_id,
        )

    def event_meta(self, event: Any) -> EventSecurityMeta:
        """Extract chat/user/text ids from Telethon, proxy, or simple events."""

        message = getattr(event, "message", None)
        query = getattr(event, "query", None)
        update = getattr(event, "original_update", None)
        sources = (event, message, query, update)

        chat_id = self._first_id(
            sources,
            (
                "chat_id",
                "peer_id",
                "input_chat",
                "channel_id",
            ),
        )
        user_id = self._first_id(
            sources,
            (
                "sender_id",
                "user_id",
                "from_id",
                "from_user",
                "sender",
                "user",
            ),
        )
        message_id = self._first_id(sources, ("id", "message_id"))

        return EventSecurityMeta(
            chat_id=chat_id,
            user_id=user_id,
            raw_text=self._extract_text(sources),
            message_id=message_id,
        )

    def _rules_for(self, module: str | None) -> SecurityChatRules:
        scope = self._scope(module)
        rules = self._rules.get(scope)
        if rules is None:
            rules = SecurityChatRules()
            self._rules[scope] = rules
        return rules

    def _iter_scope_rules(
        self, module: str | None
    ) -> Iterable[tuple[str, SecurityChatRules]]:
        global_rules = self._rules.get(_GLOBAL_SCOPE)
        if global_rules is not None and not global_rules.is_empty():
            yield _GLOBAL_SCOPE, global_rules

        scope = self._scope(module)
        if scope == _GLOBAL_SCOPE:
            return
        module_rules = self._rules.get(scope)
        if module_rules is not None and not module_rules.is_empty():
            yield scope, module_rules

    @staticmethod
    def _scope(module: str | None) -> str:
        if module is None:
            return _GLOBAL_SCOPE
        text = str(module).strip()
        return text or _GLOBAL_SCOPE

    @classmethod
    def _normalize_many(cls, values: Iterable[Any]) -> set[SecurityId]:
        result: set[SecurityId] = set()
        for value in values:
            normalized = cls._normalize_id(value)
            if normalized is not None:
                result.add(normalized)
        return result

    @classmethod
    def _first_id(
        cls, sources: Iterable[Any], attrs: Iterable[str]
    ) -> SecurityId | None:
        for source in sources:
            if source is None:
                continue
            for attr in attrs:
                value = getattr(source, attr, None)
                normalized = cls._normalize_id(value)
                if normalized is not None:
                    return normalized
        return None

    @classmethod
    def _normalize_id(cls, value: Any) -> SecurityId | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return int(text)
            except ValueError:
                return text
        for attr in ("user_id", "chat_id", "channel_id", "id"):
            attr_value = getattr(value, attr, None)
            if attr_value is not None and attr_value is not value:
                normalized = cls._normalize_id(attr_value)
                if normalized is not None:
                    return normalized
        return None

    @classmethod
    def _extract_text(cls, sources: Iterable[Any]) -> str:
        for source in sources:
            if source is None:
                continue
            for attr in ("raw_text", "text", "message", "data"):
                value = getattr(source, attr, None)
                if value is None:
                    continue
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="replace")
                if isinstance(value, str):
                    return value
        return ""

    def _log_blacklisted_sender(self, meta: EventSecurityMeta) -> None:
        key = (meta.user_id, meta.chat_id, meta.message_id, meta.raw_text)
        if key in self._logged_blacklist_seen:
            return
        self._logged_blacklist_seen.add(key)
        self._logged_blacklist_keys.append(key)
        if len(self._logged_blacklist_keys) > self.LOG_CACHE_LIMIT:
            old_key = self._logged_blacklist_keys.pop(0)
            self._logged_blacklist_seen.discard(old_key)

        self.logger.warning(
            "[security] blocked blacklisted user user_id=%s chat_id=%s text=%r",
            meta.user_id,
            meta.chat_id,
            meta.raw_text,
        )


SecurityManager = SecurityChats
Security = SecurityChats


__all__ = [
    "ALL",
    "BITMAP",
    "DEFAULT_PERMISSIONS",
    "EVERYONE",
    "EventSecurityMeta",
    "GROUP_ADMIN",
    "GROUP_ADMIN_ADD_ADMINS",
    "GROUP_ADMIN_ANY",
    "GROUP_ADMIN_BAN_USERS",
    "GROUP_ADMIN_CHANGE_INFO",
    "GROUP_ADMIN_DELETE_MESSAGES",
    "GROUP_ADMIN_INVITE_USERS",
    "GROUP_ADMIN_PIN_MESSAGES",
    "GROUP_MEMBER",
    "GROUP_OWNER",
    "OWNER",
    "PM",
    "PUBLIC_PERMISSIONS",
    "SUPPORT",
    "SUDO",
    "Security",
    "SecurityChatDecision",
    "SecurityChatRules",
    "SecurityChats",
    "SecurityGroup",
    "SecurityManager",
    "VALID_PERMISSIONS",
    "group_admin",
    "group_admin_add_admins",
    "group_admin_ban_users",
    "group_admin_change_info",
    "group_admin_delete_messages",
    "group_admin_invite_users",
    "group_admin_pin_messages",
    "group_member",
    "group_owner",
    "inline_everyone",
    "owner",
    "pm",
    "sudo",
    "support",
    "unrestricted",
]
