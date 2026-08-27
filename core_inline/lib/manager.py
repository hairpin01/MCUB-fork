# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

import json


class InlineManager:
    MODULE = "inline_permissions"
    EVERYONE_ALL = "all"
    EVERYONE_GROUPS = "groups"
    EVERYONE_PM = "pm"

    def __init__(self, kernel):
        self.kernel = kernel

    async def is_admin(self, user_id: int) -> bool:
        admin_id = getattr(self.kernel, "ADMIN_ID", None)
        if admin_id is None:
            return False
        try:
            return int(admin_id) > 0 and int(user_id) == int(admin_id)
        except (ValueError, TypeError):
            return False

    async def is_trusted(self, user_id: int) -> bool:
        """Return whether the user is present in the trusted users list."""
        try:
            data = await self.kernel.db_get("trusted", "users")
            if not data:
                return False
            trusted = (
                json.loads(data) if isinstance(data, str) else json.loads(str(data))
            )
            return user_id in trusted
        except Exception:
            return False

    async def is_allowed(
        self,
        user_id: int,
        command: str | None = None,
        context=None,
    ) -> bool:
        if await self.is_admin(user_id):
            return True

        # Check inline_permissions module
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if all_users:
                allowed = json.loads(all_users)
                denied = allowed.get("denied", {})
                if command and isinstance(denied, dict):
                    if user_id in denied.get(command, []):
                        return False
                everyone_mode = self._normalize_everyone_mode(allowed.get("everyone"))
                if everyone_mode and self._everyone_mode_matches(
                    everyone_mode, context
                ):
                    return True
                if user_id in allowed.get("global", []):
                    return True
                if command and user_id in allowed.get(command, []):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass

        # Also check trusted users list (from modules/trusted.py)
        if await self.is_trusted(user_id):
            return True

        return False

    async def allow_user(self, user_id: int, command: str | None = None) -> bool:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            allowed = json.loads(all_users) if all_users else {"global": []}

            target = "global" if command is None else command
            if target not in allowed:
                allowed[target] = []

            denied = allowed.get("denied", {})
            if command is not None and isinstance(denied, dict):
                denied_users = denied.get(command, [])
                if user_id in denied_users:
                    denied_users.remove(user_id)
                if denied_users:
                    denied[command] = denied_users
                else:
                    denied.pop(command, None)
                if denied:
                    allowed["denied"] = denied
                else:
                    allowed.pop("denied", None)

            if user_id not in allowed[target]:
                allowed[target].append(user_id)

            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            self.kernel.logger.error(f"InlineManager allow_user error: {e}")
            return False

    async def deny_user(self, user_id: int, command: str | None = None) -> bool:
        try:
            if await self.is_admin(user_id):
                return False

            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return False

            allowed = json.loads(all_users)
            target = "global" if command is None else command

            if command is not None:
                denied = allowed.get("denied", {})
                if not isinstance(denied, dict):
                    denied = {}
                denied_users = denied.setdefault(command, [])
                if user_id not in denied_users:
                    denied_users.append(user_id)
                allowed["denied"] = denied

            if target in allowed and user_id in allowed[target]:
                allowed[target].remove(user_id)
            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            self.kernel.logger.error(f"InlineManager deny_user error: {e}")
            return False

    async def is_everyone_allowed(self) -> bool:
        return bool(await self.get_everyone_mode())

    async def get_everyone_mode(self) -> str | None:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return None
            allowed = json.loads(all_users)
            return self._normalize_everyone_mode(allowed.get("everyone"))
        except Exception:
            return None

    async def allow_everyone(self, mode: str = EVERYONE_ALL) -> bool:
        try:
            mode = self._normalize_everyone_mode(mode) or self.EVERYONE_ALL
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            allowed = json.loads(all_users) if all_users else {"global": []}
            allowed["everyone"] = mode
            if "global" not in allowed:
                allowed["global"] = []
            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            self.kernel.logger.error(f"InlineManager allow_everyone error: {e}")
            return False

    async def deny_everyone(self) -> bool:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return True
            allowed = json.loads(all_users)
            allowed.pop("everyone", None)
            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            self.kernel.logger.error(f"InlineManager deny_everyone error: {e}")
            return False

    def _normalize_everyone_mode(self, value) -> str | None:
        if value is True:
            return self.EVERYONE_ALL
        if not value:
            return None
        mode = str(value).strip().lower()
        aliases = {
            "all": self.EVERYONE_ALL,
            "any": self.EVERYONE_ALL,
            "everywhere": self.EVERYONE_ALL,
            "global": self.EVERYONE_ALL,
            "groups": self.EVERYONE_GROUPS,
            "group": self.EVERYONE_GROUPS,
            "chat": self.EVERYONE_GROUPS,
            "chats": self.EVERYONE_GROUPS,
            "pm": self.EVERYONE_PM,
            "pms": self.EVERYONE_PM,
            "private": self.EVERYONE_PM,
            "private_chat": self.EVERYONE_PM,
            "ls": self.EVERYONE_PM,
            "dm": self.EVERYONE_PM,
        }
        return aliases.get(mode)

    def _everyone_mode_matches(self, mode: str, context=None) -> bool:
        if mode == self.EVERYONE_ALL:
            return True
        kind = self._context_kind(context)
        return kind == mode

    def _context_kind(self, context=None) -> str | None:
        if context is None:
            return None
        if isinstance(context, str):
            return self._normalize_context_word(context)

        for attr in ("chat_type", "peer_type"):
            kind = self._normalize_context_word(getattr(context, attr, None))
            if kind:
                return kind

        query = getattr(context, "query", None)
        for attr in ("chat_type", "peer_type"):
            kind = self._normalize_context_word(getattr(query, attr, None))
            if kind:
                return kind

        if getattr(context, "is_private", None) is True:
            return self.EVERYONE_PM
        if getattr(context, "is_group", None) is True:
            return self.EVERYONE_GROUPS
        return None

    def _normalize_context_word(self, value) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        cls = value.__class__.__name__.lower() if not isinstance(value, str) else ""
        combined = f"{text} {cls}"
        if any(word in combined for word in ("private", "pm", "user", "sender")):
            return self.EVERYONE_PM
        if any(
            word in combined
            for word in ("group", "chat", "mega", "channel", "broadcast")
        ):
            return self.EVERYONE_GROUPS
        return None

    async def get_allowed_users(self, command: str | None = None) -> list:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return []

            allowed = json.loads(all_users)
            target = "global" if command is None else command
            return allowed.get(target, [])
        except Exception:
            return []

    async def clear_all(self) -> bool:
        try:
            await self.kernel.db_delete(self.MODULE, "allowed_users")
            return True
        except Exception as e:
            self.kernel.logger.error(f"InlineManager clear_all error: {e}")
            return False
