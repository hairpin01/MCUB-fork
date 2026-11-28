# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
from __future__ import annotations

import json
from typing import Any

# MCUB sdk
from core.lib.types import (
    Event,
    InlineMessage,
)
from core.lib.loader.module_base import (
    ModuleBase,
    command,
    callback,
)

class SecurityModule(ModuleBase):
    name = "security_module"
    version = "1.0.0"
    author = "@hairpin01"
    description: dict[str, str] = {
        "en": "Unified access control, sudo, admin and security groups",
        "ru": "Единая система прав доступа: sudo, admin и группы безопасности",
        "uk": "Єдина система прав доступу: sudo, admin та групи безпеки",
    }

    strings = {"name": "security_chats"}

    DB_MOD = "security"
    DB_KEY_SUDO = "sudo_users"
    DB_KEY_ADMIN = "admin_users"
    DB_KEY_GROUPS = "groups"
    DB_KEY_PERSONAL = "personal_rules"
    DB_KEY_EVERYONE = "everyone_rules"

    async def _db_get_json(self, key: str, default: Any) -> Any:
        try:
            raw = await self.db.db_get(self.DB_MOD, key)
            if not raw:
                return default
            return json.loads(raw) if isinstance(raw, str) else json.loads(str(raw))
        except Exception:
            return default

    async def _db_set_json(self, key: str, value: Any) -> None:
        await self.db.db_set(self.DB_MOD, key, json.dumps(value))
        sec = getattr(self.kernel, "security", None)
        if sec and hasattr(sec, "invalidate_cache"):
            sec.invalidate_cache()

    async def _resolve_user(self, event: Event, index=0) -> int | None:
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply and reply.sender_id:
                return int(reply.sender_id)

        args = self.args(event).args
        if args:
            target = args[index].strip()
            if target.lstrip("-").isdigit():
                return int(target)
            username = target.lstrip("@")
            try:
                entity = await self.client.get_entity(username)
                if entity:
                    return int(entity.id)
            except Exception:
                pass
        return None

    @callback
    async def _on_confirm_sudo(self, call: InlineMessage, user_id: int) -> None:
        sudo_users: list[int] = await self._db_get_json(self.DB_KEY_SUDO, [])
        if user_id not in sudo_users:
            sudo_users.append(user_id)
            await self._db_set_json(self.DB_KEY_SUDO, sudo_users)
        await call.edit(self.strings("sudo_added", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_unsudo(self, call: InlineMessage, user_id: int) -> None:
        sudo_users: list[int] = await self._db_get_json(self.DB_KEY_SUDO, [])
        if user_id in sudo_users:
            sudo_users.remove(user_id)
            await self._db_set_json(self.DB_KEY_SUDO, sudo_users)
        await call.edit(self.strings("sudo_removed", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_sadmin(self, call: InlineMessage, user_id: int) -> None:
        admin_users: list[int] = await self._db_get_json(self.DB_KEY_ADMIN, [])
        if user_id not in admin_users:
            admin_users.append(user_id)
            await self._db_set_json(self.DB_KEY_ADMIN, admin_users)
        await call.edit(self.strings("admin_added", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_unsadmin(self, call: InlineMessage, user_id: int) -> None:
        admin_users: list[int] = await self._db_get_json(self.DB_KEY_ADMIN, [])
        if user_id in admin_users:
            admin_users.remove(user_id)
            await self._db_set_json(self.DB_KEY_ADMIN, admin_users)
        await call.edit(self.strings("admin_removed", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_delete_group(self, call: InlineMessage, name: str) -> None:
        groups: dict[str, Any] = await self._db_get_json(self.DB_KEY_GROUPS, {})
        if name in groups:
            del groups[name]
            await self._db_set_json(self.DB_KEY_GROUPS, groups)
            text = self.strings("sgroup_deleted", name=name)
        else:
            text = self.strings("sgroup_not_found", name=name)
        await call.edit(text, parse_mode="html")

    @callback
    async def _on_cancel(self, call: InlineMessage) -> None:
        await call.edit(self.strings["action_cancelled"], parse_mode="html")

    @command("addsudo", doc_ru="Добавить пользователя в SUDO", doc_en="Add user to SUDO")
    async def cmd_sudo(self, event: Event) -> None:
        sender_id = getattr(event, "sender_id", None)
        if hasattr(self.kernel, "is_sudo") and not await self.kernel.is_sudo(sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return

        user_id = await self._resolve_user(event)
        if not user_id:
            await self.answer(event, self.strings["usage_sudo"], as_html=True)
            return

        sudo_users: list[int] = await self._db_get_json(self.DB_KEY_SUDO, [])
        if user_id in sudo_users:
            await self.answer(event, self.strings["sec_user_already"], as_html=True)
            return

        confirm_text = self.strings("confirm_sudo_title", user=user_id)
        buttons = [
            [
                self.Button.inline(self.strings["btn_confirm"], self._on_confirm_sudo, args=(user_id,)),
                self.Button.inline(self.strings["btn_cancel"], self._on_cancel),
            ]
        ]
        await self.inline(event.chat_id, confirm_text, buttons=buttons)

    @command("unsudo", doc_ru="Удалить пользователя из SUDO", doc_en="Remove user from SUDO")
    async def cmd_unsudo(self, event: Event) -> None:
        sender_id = getattr(event, "sender_id", None)
        if hasattr(self.kernel, "is_sudo") and not await self.kernel.is_sudo(sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return

        user_id = await self._resolve_user(event)
        if not user_id:
            await self.answer(event, self.strings["usage_unsudo"], as_html=True)
            return

        sudo_users: list[int] = await self._db_get_json(self.DB_KEY_SUDO, [])
        if user_id not in sudo_users:
            await self.answer(event, self.strings["sec_user_not_in_list"], as_html=True)
            return

        confirm_text = self.strings("confirm_unsudo_title", user=user_id)
        buttons = [
            [
                self.Button.inline(self.strings["btn_confirm"], self._on_confirm_unsudo, args=(user_id,)),
                self.Button.inline(self.strings["btn_cancel"], self._on_cancel),
            ]
        ]
        await self.inline(event.chat_id, confirm_text, buttons=buttons)

    @command("addadmin", doc_ru="Добавить пользователя в ADMIN", doc_en="Add user to ADMIN")
    async def cmd_sadmin(self, event: Event) -> None:
        sender_id = getattr(event, "sender_id", None)
        if hasattr(self.kernel, "is_sudo") and not await self.kernel.is_sudo(sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return

        user_id = await self._resolve_user(event)
        if not user_id:
            await self.answer(event, self.strings["usage_sadmin"], as_html=True)
            return

        admin_users: list[int] = await self._db_get_json(self.DB_KEY_ADMIN, [])
        if user_id in admin_users:
            await self.answer(event, self.strings["sec_user_already"], as_html=True)
            return

        confirm_text = self.strings("confirm_sadmin_title", user=user_id)
        buttons = [
            [
                self.Button.inline(self.strings["btn_confirm"], self._on_confirm_sadmin, args=(user_id,)),
                self.Button.inline(self.strings["btn_cancel"], self._on_cancel),
            ]
        ]
        await self.inline(event.chat_id, confirm_text, buttons=buttons)

    @command("unadmin", doc_ru="Удалить пользователя из ADMIN", doc_en="Remove user from ADMIN")
    async def cmd_unsadmin(self, event: Event) -> None:
        sender_id = getattr(event, "sender_id", None)
        if hasattr(self.kernel, "is_sudo") and not await self.kernel.is_sudo(sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return

        user_id = await self._resolve_user(event)
        if not user_id:
            await self.answer(event, self.strings["usage_unsadmin"], as_html=True)
            return

        admin_users: list[int] = await self._db_get_json(self.DB_KEY_ADMIN, [])
        if user_id not in admin_users:
            await self.answer(event, self.strings["sec_user_not_in_list"], as_html=True)
            return

        confirm_text = self.strings("confirm_unsadmin_title", user=user_id)
        buttons = [
            [
                self.Button.inline(self.strings["btn_confirm"], self._on_confirm_unsadmin, args=(user_id,)),
                self.Button.inline(self.strings["btn_cancel"], self._on_cancel),
            ]
        ]
        await self.inline(event.chat_id, confirm_text, buttons=buttons)

    @command("sgroup", doc_ru="Управление группами безопасности", doc_en="Security group management")
    async def cmd_sgroup(self, event: Event) -> None:
        sender_id = getattr(event, "sender_id", None)
        if hasattr(self.kernel, "is_admin_async") and not await self.kernel.is_admin_async(sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return

        raw_args = self.args(event).args
        if not raw_args:
            groups: dict[str, Any] = await self._db_get_json(self.DB_KEY_GROUPS, {})
            if not groups:
                await self.answer(event, self.strings["sgroup_list_empty"], as_html=True)
                return
            title = self.strings["sgroup_list_title"]
            lines = [title]
            for name, g in groups.items():
                u_count = len(g.get("users", []))
                p_count = len(g.get("permissions", []))
                lines.append(f"• <b>{name}</b>: {u_count} users, {p_count} rules")
            await self.answer(event, "\n".join(lines), as_html=True)
            return

        action = raw_args[0].lower()
        groups = await self._db_get_json(self.DB_KEY_GROUPS, {})

        if action == "create" and len(raw_args) > 1:
            name = raw_args[1].lower()
            if name in groups:
                await self.answer(event, self.strings("sgroup_already_exists", name=name), as_html=True)
                return
            groups[name] = {"users": [], "permissions": []}
            await self._db_set_json(self.DB_KEY_GROUPS, groups)
            await self.answer(event, self.strings("sgroup_created", name=name), as_html=True)

        elif action == "delete" and len(raw_args) > 1:
            name = raw_args[1].lower()
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            confirm_text = self.strings("sgroup_confirm_delete", name=name)
            buttons = [
                [
                    self.Button.inline(self.strings["btn_confirm_delete"], self._on_confirm_delete_group, args=(name,)),
                    self.Button.inline(self.strings["btn_cancel"], self._on_cancel),
                ]
            ]
            await self.inline(event.chat_id, confirm_text, buttons=buttons)

        elif action == "add" and len(raw_args) > 2:
            name = raw_args[1].lower()
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            target_str = raw_args[2]
            uid = int(target_str) if target_str.isdigit() else None
            if not uid:
                uid = await self._resolve_user(event, index=2)
            if not uid:
                await self.answer(event, self.strings["user_not_found"], as_html=True)
                return
            if uid in groups[name]["users"]:
                await self.answer(event, self.strings["sgroup_user_in_group"], as_html=True)
                return
            groups[name]["users"].append(uid)
            await self._db_set_json(self.DB_KEY_GROUPS, groups)
            await self.answer(event, self.strings("sgroup_user_added", user=uid, group=name), as_html=True)

        elif action == "remove" and len(raw_args) > 2:
            name = raw_args[1].lower()
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            target_str = raw_args[2]
            uid = int(target_str) if target_str.isdigit() else None
            if not uid:
                uid = await self._resolve_user(event, index=2)
            if not uid:
                await self.answer(event, self.strings["user_not_found"], as_html=True)
                return
            if uid not in groups[name]["users"]:
                await self.answer(event, self.strings["sgroup_user_not_in_group"], as_html=True)
                return
            groups[name]["users"].remove(uid)
            await self._db_set_json(self.DB_KEY_GROUPS, groups)
            await self.answer(event, self.strings("sgroup_user_removed", user=uid, group=name), as_html=True)

        elif action == "grant" and len(raw_args) > 2:
            name = raw_args[1].lower()
            target = raw_args[2]
            allow = raw_args[3] if len(raw_args) > 3 else "all"
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            rule = {"type": "command", "target": target, "allow": allow}
            groups[name]["permissions"].append(rule)
            await self._db_set_json(self.DB_KEY_GROUPS, groups)
            await self.answer(event, f"✅ <code>{name}</code>: <code>{target}</code> (allow={allow})", as_html=True)
        else:
            await self.answer(event, self.strings["sgroup_usage"], as_html=True)