# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

import json


class InlineManager:
    MODULE = "inline_permissions"

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

    async def is_allowed(self, user_id: int, command: str | None = None) -> bool:
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
                if user_id in allowed.get("global", []):
                    return True
                if command and user_id in allowed.get(command, []):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass

        # Also check trusted users list (from modules/trusted.py)
        try:
            data = await self.kernel.db_get("trusted", "users")
            if data:
                trusted = (
                    json.loads(data) if isinstance(data, str) else json.loads(str(data))
                )
                if user_id in trusted:
                    return True
        except Exception:
            pass

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
