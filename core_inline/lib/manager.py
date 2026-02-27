import json


class InlineManager:
    MODULE = "inline_permissions"

    def __init__(self, kernel):
        self.kernel = kernel

    async def is_admin(self, user_id: int) -> bool:
        return hasattr(self.kernel, "ADMIN_ID") and int(user_id) == int(self.kernel.ADMIN_ID)

    async def is_allowed(self, user_id: int, command: str = None) -> bool:
        if await self.is_admin(user_id):
            return True

        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if all_users:
                allowed = json.loads(all_users)
                if user_id in allowed.get("global", []):
                    return True
                if command and user_id in allowed.get(command, []):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass

        return False

    async def allow_user(self, user_id: int, command: str = None) -> bool:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            allowed = json.loads(all_users) if all_users else {"global": []}

            target = "global" if command is None else command
            if target not in allowed:
                allowed[target] = []

            if user_id not in allowed[target]:
                allowed[target].append(user_id)

            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            self.kernel.logger.error(f"InlineManager allow_user error: {e}")
            return False

    async def deny_user(self, user_id: int, command: str = None) -> bool:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return False

            allowed = json.loads(all_users)
            target = "global" if command is None else command

            if target in allowed and user_id in allowed[target]:
                allowed[target].remove(user_id)
                await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
                return True
            return False
        except Exception as e:
            self.kernel.logger.error(f"InlineManager deny_user error: {e}")
            return False

    async def get_allowed_users(self, command: str = None) -> list:
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
