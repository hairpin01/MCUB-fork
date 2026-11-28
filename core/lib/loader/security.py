# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import logging
import time
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
ALL = (1 << 13) - 1
VALID_PERMISSIONS = ALL | EVERYONE


class SecurityGroup(NamedTuple):
    """Represents a named trusted/security group."""

    name: str
    users: list[int]
    permissions: list[dict[str, Any]]


def _sec(func: SecurityHandler, flags: int) -> SecurityHandler:
    prev = getattr(func, "security", 0)
    func.security = prev | OWNER | flags
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
    """Rules for a single scope: global (*) or a concrete module."""

    allowed_chats: set[SecurityId] = field(default_factory=set)
    ignored_chats: set[SecurityId] = field(default_factory=set)
    blacklisted_users: set[SecurityId] = field(default_factory=set)

    def is_empty(self) -> bool:
        return not (self.allowed_chats or self.ignored_chats or self.blacklisted_users)


class SecurityChats:
    """Unified security authority for chats, users, groups and action permissions."""

    LOG_CACHE_LIMIT = 2048
    DB_KEY_SUDO = "sudo_users"
    DB_KEY_ADMIN = "admin_users"
    DB_KEY_GROUPS = "groups"
    DB_KEY_PERSONAL = "personal_rules"
    DB_KEY_EVERYONE = "everyone_rules"
    DB_MOD = "security"

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

        # In-memory runtime cache for security_v2 rules
        self._sudo_cache: set[int] | None = None
        self._admin_cache: set[int] | None = None
        self._groups_cache: dict[str, dict[str, Any]] | None = None
        self._personal_cache: dict[str, list[dict[str, Any]]] | None = None
        self._everyone_cache: list[dict[str, Any]] | None = None
        self._cache_timestamp: float = 0.0

    def refresh_owners(self) -> list[SecurityId]:
        self.owner = self._load_owner_ids()
        owner_set = set(self.owner)
        if set(self.all_users) != owner_set:
            self.all_users = list(self.owner)
        return self.owner

    def invalidate_cache(self) -> None:
        """Clear memory cache so next checks read freshly updated DB rules."""
        self._sudo_cache = None
        self._admin_cache = None
        self._groups_cache = None
        self._personal_cache = None
        self._everyone_cache = None
        self._cache_timestamp = 0.0

    async def _ensure_cache_loaded(self) -> None:
        now = time.time()
        if self._sudo_cache is not None and (now - self._cache_timestamp) < 3.0:
            return

        db = getattr(self.kernel, "db", None) or self.kernel
        if not db or not hasattr(db, "db_get"):
            if self._sudo_cache is None:
                self._sudo_cache = set()
                self._admin_cache = set()
                self._groups_cache = {}
                self._personal_cache = {}
                self._everyone_cache = []
            return

        try:
            import json

            raw_sudo = await db.db_get(self.DB_MOD, self.DB_KEY_SUDO)
            raw_admin = await db.db_get(self.DB_MOD, self.DB_KEY_ADMIN)
            raw_groups = await db.db_get(self.DB_MOD, self.DB_KEY_GROUPS)
            raw_personal = await db.db_get(self.DB_MOD, self.DB_KEY_PERSONAL)
            raw_everyone = await db.db_get(self.DB_MOD, self.DB_KEY_EVERYONE)

            self._sudo_cache = set(json.loads(raw_sudo)) if raw_sudo else set()
            self._admin_cache = set(json.loads(raw_admin)) if raw_admin else set()
            self._groups_cache = json.loads(raw_groups) if raw_groups else {}
            self._personal_cache = json.loads(raw_personal) if raw_personal else {}
            self._everyone_cache = json.loads(raw_everyone) if raw_everyone else []
            self._cache_timestamp = now
        except Exception as e:
            self.logger.error("[security] failed to load security_v2 rules from db: %s", e)
            if self._sudo_cache is None:
                self._sudo_cache = set()
                self._admin_cache = set()
                self._groups_cache = {}
                self._personal_cache = {}
                self._everyone_cache = []

    async def is_sudo(self, user_id: int | None) -> bool:
        """Return True if user_id belongs to the root SUDO group or is the primary owner."""
        if user_id is None:
            return False

        # Primary account owners are always sudo
        owners = self.refresh_owners()
        if user_id in owners:
            return True

        await self._ensure_cache_loaded()
        return bool(self._sudo_cache and user_id in self._sudo_cache)

    async def is_admin(self, user_id: int | None) -> bool:
        """Return True if user_id is in SUDO or ADMIN group."""
        if user_id is None:
            return False

        if await self.is_sudo(user_id):
            return True

        await self._ensure_cache_loaded()
        return bool(self._admin_cache and user_id in self._admin_cache)

    def _matches_target(self, rule_pattern: str, target: str) -> bool:
        """Match call_target against pattern (exact or wildcards like 'userbot:*', '*')."""
        if rule_pattern == "*" or rule_pattern == target:
            return True
        if rule_pattern.endswith(":*"):
            prefix = rule_pattern[:-1]
            return target.startswith(prefix)
        return False

    def _matches_context(self, rule: dict[str, Any], context: Any) -> bool:
        """Evaluate allow (chat / personal messages) and temp (expiry)."""
        now = time.time()
        expiry = rule.get("temp")
        if expiry is not None and isinstance(expiry, (int, float)) and expiry > 0:
            if now > expiry:
                return False

        allow_scope = rule.get("allow", "all")
        if allow_scope in ("all", "*"):
            return True

        if context is None:
            return True

        is_private = False
        is_group = False
        if isinstance(context, str):
            c_lower = context.lower()
            is_private = any(w in c_lower for w in ("pm", "private", "personal"))
            is_group = any(w in c_lower for w in ("chat", "group", "supergroup", "channel"))
        else:
            if getattr(context, "is_private", None) is True:
                is_private = True
            elif getattr(context, "is_group", None) is True or getattr(context, "is_channel", None) is True:
                is_group = True
            else:
                meta = self.event_meta(context)
                if meta.chat_id is not None and meta.chat_id == meta.user_id:
                    is_private = True
                elif meta.chat_id is not None:
                    is_group = True

        if allow_scope in ("personal messages", "pm", "private"):
            return is_private
        if allow_scope in ("chat", "group", "chats", "groups"):
            return is_group

        return True

    async def is_allow(
        self,
        call_type: str,
        call_target: str,
        user_id: int | None,
        context: Any = None,
        *,
        allow_user: Any = None,
    ) -> bool:
        """Unified access evaluation.

        call_type: 'command' | 'button'
        call_target: 'userbot:cmd' | 'inline:cmd' | 'guest:cmd' | 'bot:cmd' | 'callback:token' | 'input:token'
        user_id: sender id
        context: event or string context
        allow_user: button-specific restriction ('all' or specific user_id)
        """
        # 1. Button specific allow_user check comes first
        if call_type == "button" and allow_user is not None:
            if allow_user == "all":
                return True
            if isinstance(allow_user, int) and user_id == allow_user:
                return True
            if isinstance(allow_user, (list, tuple, set)) and user_id in allow_user:
                return True

        if user_id is None:
            return False

        # 2. SUDO can do everything without restrictions
        if await self.is_sudo(user_id):
            return True

        # 3. Check chat/user security rules (blacklist & ignored chats)
        if context is not None and not self.can_process_event(context, action=call_type):
            return False

        # 4. ADMIN group can do everything EXCEPT modifying security_module
        if await self.is_admin(user_id):
            if "security_module" in call_target or call_target in (
                "userbot:sudo",
                "userbot:unsudo",
                "userbot:sadmin",
                "userbot:unsadmin",
                "userbot:sgroup",
                "userbot:security",
                "userbot:sec",
            ):
                return False
            return True

        await self._ensure_cache_loaded()

        # 5. Owner of personal teams (specific rules per user)
        if self._personal_cache:
            user_rules = self._personal_cache.get(str(user_id), [])
            for r in user_rules:
                if r.get("type", "command") == call_type and self._matches_target(
                    r.get("target", ""), call_target
                ):
                    if self._matches_context(r, context):
                        return True

        # 6. Group owner (custom created groups)
        if self._groups_cache:
            for _gname, gdata in self._groups_cache.items():
                if user_id in gdata.get("users", []):
                    for r in gdata.get("permissions", []):
                        if r.get("type", "command") == call_type and self._matches_target(
                            r.get("target", ""), call_target
                        ):
                            if self._matches_context(r, context):
                                return True

        # 7. Everyone can (global rules applicable to everyone)
        if self._everyone_cache:
            for r in self._everyone_cache:
                if r.get("type", "command") == call_type and self._matches_target(
                    r.get("target", ""), call_target
                ):
                    if self._matches_context(r, context):
                        return True

        return False

    def get_flags(self, func: SecurityHandler | int | None) -> int:
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
        normalized = self._normalize_id(chat_id)
        if normalized is None:
            return
        rules = self._rules_for(module)
        rules.ignored_chats.discard(normalized)
        rules.allowed_chats.add(normalized)

    def allow_chats(self, chat_ids: Iterable[Any], *, module: str | None = None) -> None:
        for chat_id in chat_ids:
            self.allow_chat(chat_id, module=module)

    def set_allowed_chats(self, chat_ids: Iterable[Any], *, module: str | None = None) -> None:
        rules = self._rules_for(module)
        rules.allowed_chats = self._normalize_many(chat_ids)
        rules.ignored_chats.difference_update(rules.allowed_chats)

    def clear_allowed_chats(self, *, module: str | None = None) -> None:
        self._rules_for(module).allowed_chats.clear()

    def ignore_chat(self, chat_id: Any, *, module: str | None = None) -> None:
        normalized = self._normalize_id(chat_id)
        if normalized is None:
            return
        rules = self._rules_for(module)
        rules.allowed_chats.discard(normalized)
        rules.ignored_chats.add(normalized)

    block_chat = ignore_chat
    deny_chat = ignore_chat

    def ignore_chats(self, chat_ids: Iterable[Any], *, module: str | None = None) -> None:
        for chat_id in chat_ids:
            self.ignore_chat(chat_id, module=module)

    def unignore_chat(self, chat_id: Any, *, module: str | None = None) -> None:
        normalized = self._normalize_id(chat_id)
        if normalized is None:
            return
        self._rules_for(module).ignored_chats.discard(normalized)

    unblock_chat = unignore_chat

    def blacklist_user(self, user_id: Any, *, module: str | None = None) -> None:
        normalized = self._normalize_id(user_id)
        if normalized is None:
            return
        self._rules_for(module).blacklisted_users.add(normalized)

    def blacklist_users(self, user_ids: Iterable[Any], *, module: str | None = None) -> None:
        for user_id in user_ids:
            self.blacklist_user(user_id, module=module)

    def unblacklist_user(self, user_id: Any, *, module: str | None = None) -> None:
        normalized = self._normalize_id(user_id)
        if normalized is None:
            return
        self._rules_for(module).blacklisted_users.discard(normalized)

    whitelist_user = unblacklist_user

    def reset(self, *, module: str | None = None) -> None:
        self._rules.pop(self._scope(module), None)

    def reset_all(self) -> None:
        self._rules.clear()
        self._logged_blacklist_keys.clear()
        self._logged_blacklist_seen.clear()

    def snapshot(self) -> dict[str, dict[str, tuple[SecurityId, ...]]]:
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
        return self.check_event(event, module=module, action=action).allowed

    def check_event(
        self,
        event: Any,
        *,
        module: str | None = None,
        action: str = "event",
    ) -> SecurityChatDecision:
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
    "SUDO",
    "SUPPORT",
    "VALID_PERMISSIONS",
    "EventSecurityMeta",
    "Security",
    "SecurityChatDecision",
    "SecurityChatRules",
    "SecurityChats",
    "SecurityGroup",
    "SecurityManager",
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