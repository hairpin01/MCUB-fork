# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
from __future__ import annotations

import json
import re
import shlex
import time
from html import escape
from typing import Any

# MCUB sdk
from telethon.tl.types import User
from utils.helpers import get_args_raw
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
        if len(args) > index:
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
        if not await self.kernel.is_sudo(call.sender_id):
            await call.answer()
            return
        sudo_users: list[int] = await self._db_get_json(self.DB_KEY_SUDO, [])
        if user_id not in sudo_users:
            sudo_users.append(user_id)
            await self._db_set_json(self.DB_KEY_SUDO, sudo_users)
        await call.edit(self.strings("sudo_added", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_unsudo(self, call: InlineMessage, user_id: int) -> None:
        if not await self.kernel.is_sudo(call.sender_id):
            await call.answer()
            return
        sudo_users: list[int] = await self._db_get_json(self.DB_KEY_SUDO, [])
        if user_id in sudo_users:
            sudo_users.remove(user_id)
            await self._db_set_json(self.DB_KEY_SUDO, sudo_users)
        await call.edit(self.strings("sudo_removed", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_sadmin(self, call: InlineMessage, user_id: int) -> None:
        if not await self.kernel.is_sudo(call.sender_id):
            await call.answer()
            return
        admin_users: list[int] = await self._db_get_json(self.DB_KEY_ADMIN, [])
        if user_id not in admin_users:
            admin_users.append(user_id)
            await self._db_set_json(self.DB_KEY_ADMIN, admin_users)
        await call.edit(self.strings("admin_added", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_unsadmin(self, call: InlineMessage, user_id: int) -> None:
        if not await self.kernel.is_sudo(call.sender_id):
            await call.answer()
            return
        admin_users: list[int] = await self._db_get_json(self.DB_KEY_ADMIN, [])
        if user_id in admin_users:
            admin_users.remove(user_id)
            await self._db_set_json(self.DB_KEY_ADMIN, admin_users)
        await call.edit(self.strings("admin_removed", user=user_id), parse_mode="html")

    @callback
    async def _on_confirm_delete_group(self, call: InlineMessage, name: str) -> None:
        if not await self.kernel.is_sudo(call.sender_id):
            await call.answer()
            return
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
        if not await self.kernel.is_sudo(call.sender_id):
            await call.answer()
            return
        await call.edit(self.strings["action_cancelled"], parse_mode="html")

    @command("addsudo", doc_ru=".addsudo <reply|@username|ID>", doc_en=".addsudo <reply|@username|ID>")
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

    @command("unsudo", doc_ru=".unsudo <reply|@username|ID>", doc_en=".unsudo <reply|@username|ID>")
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

    @command("addadmin", doc_ru=".addadmin <reply|@username|ID>", doc_en=".addadmin <reply|@username|ID>")
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

    @command("unadmin", doc_ru=".unadmin <reply|@username|ID>", doc_en=".unadmin <reply|@username|ID>")
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

    @staticmethod
    def _grant_rule(tokens, *, legacy=False):
        if not tokens:
            raise ValueError
        target, *options = tokens
        explicit_command = target.startswith("command:")
        if explicit_command:
            target = target[len("command:"):]
        prefix, sep, name = target.partition(":")
        if sep:
            if prefix not in {"inline", "userbot", "guest", "bot", "callback", "input"} or not name:
                raise ValueError
        elif explicit_command or not legacy or not target or target.startswith("-"):
            raise ValueError
        elif target != "*":
            target = f"userbot:{target}"
        kind = "button" if sep and prefix in {"callback", "input"} else "command"
        if explicit_command and kind != "command":
            raise ValueError
        rule = {"type": kind, "target": target, "allow": "all"}
        scope = None
        if legacy and options and options[0] in {"all", "*", "chat", "pm", "group", "groups", "chats", "private", "personal messages"}:
            scope = options.pop(0)
        while options:
            flag = options.pop(0)
            if flag in {"--chat", "--pm"} and scope is None:
                scope = flag[2:]
            elif flag == "--temp" and "temp" not in rule:
                units = {}
                while options and not options[0].startswith("--"):
                    match = re.fullmatch(r"([hms])([0-9]{1,9})", options.pop(0))
                    if not match or match[1] in units:
                        raise ValueError
                    units[match[1]] = int(match[2])
                seconds = sum(units.get(k, 0) * n for k, n in (("h", 3600), ("m", 60), ("s", 1)))
                if not seconds:
                    raise ValueError
                rule["temp"] = int(time.time()) + seconds
            else:
                raise ValueError
        rule["allow"] = scope or "all"
        return rule

    @command("tsec", doc_ru=".tsec [all|@username|ID|reply] <rule> [--chat|--pm] [--temp hN mN sN]", doc_en=".tsec [all|@username|ID|reply] <rule> [--chat|--pm] [--temp hN mN sN]")
    async def cmd_tsec(self, event: Event) -> None:
        if not await self.kernel.is_admin_async(event.sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return
        try:
            tokens = shlex.split(get_args_raw(event))
            recipient = None
            if tokens and ":" not in tokens[0]:
                recipient = tokens.pop(0)
            if recipient is None and not event.is_reply:
                raise ValueError
            rule = self._grant_rule(tokens)
        except ValueError:
            await self.answer(event, self.strings["tsec_usage"], as_html=True)
            return
        if recipient == "all":
            key = self.DB_KEY_EVERYONE
            data = bucket = await self._db_get_json(key, [])
        else:
            uid = None
            if recipient is None:
                reply = await event.get_reply_message()
                uid = getattr(reply, "sender_id", None)
            elif recipient.isascii() and recipient.isdecimal():
                uid = int(recipient) if len(recipient) <= 19 else None
            elif re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_]*", recipient):
                try:
                    entity = await self.client.get_entity(recipient)
                except ValueError:
                    entity = None
                if isinstance(entity, User):
                    uid = entity.id
            if not uid or uid <= 0:
                await self.answer(event, self.strings["user_not_found"], as_html=True)
                return
            recipient = str(uid)
            key = self.DB_KEY_PERSONAL
            data = await self._db_get_json(key, {})
            if not isinstance(data, dict):
                await self.answer(event, self.strings["tsec_usage"], as_html=True)
                return
            bucket = data.setdefault(recipient, [])
        if rule not in bucket:
            bucket.append(rule)
            await self._db_set_json(key, data)
        await self.answer(event, f"<code>{recipient}</code>: <code>{escape(rule['target'])}</code> ({rule['allow']})", as_html=True)

    @staticmethod
    def _same_grant(stored: Any, selector: dict[str, Any]) -> bool:
        return (
            isinstance(stored, dict)
            and stored.get("type", "command") == selector["type"]
            and stored.get("target") == selector["target"]
            and stored.get("allow", "all") == selector["allow"]
        )

    @command("utsec", doc_ru=".utsec [all|@username|ID|reply] <rule> [--chat|--pm] [--temp hN mN sN]", doc_en=".utsec [all|@username|ID|reply] <rule> [--chat|--pm] [--temp hN mN sN]")
    async def cmd_utsec(self, event: Event) -> None:
        if not await self.kernel.is_admin_async(event.sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return
        try:
            tokens = shlex.split(get_args_raw(event))
            recipient = None
            if tokens and ":" not in tokens[0]:
                recipient = tokens.pop(0)
            if recipient is None and not event.is_reply:
                raise ValueError
            selector = self._grant_rule(tokens)
        except ValueError:
            await self.answer(event, self.strings["utsec_usage"], as_html=True)
            return

        if recipient == "all":
            key = self.DB_KEY_EVERYONE
            data = await self._db_get_json(key, [])
            if not isinstance(data, list):
                data = []
            bucket = data
        else:
            uid = None
            if recipient is None:
                reply = await event.get_reply_message()
                uid = getattr(reply, "sender_id", None)
            elif recipient.isascii() and recipient.isdecimal():
                uid = int(recipient) if len(recipient) <= 19 else None
            elif re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_]*", recipient):
                try:
                    entity = await self.client.get_entity(recipient)
                except ValueError:
                    entity = None
                if isinstance(entity, User):
                    uid = entity.id
            if not uid or uid <= 0:
                await self.answer(event, self.strings["user_not_found"], as_html=True)
                return
            recipient = str(uid)
            key = self.DB_KEY_PERSONAL
            data = await self._db_get_json(key, {})
            if not isinstance(data, dict):
                await self.answer(event, self.strings["utsec_usage"], as_html=True)
                return
            bucket = data.get(recipient, [])
            if not isinstance(bucket, list):
                bucket = []

        remaining = [r for r in bucket if not self._same_grant(r, selector)]
        removed = len(bucket) - len(remaining)
        if not removed:
            await self.answer(event, self.strings("utsec_not_found", recipient=recipient or "?", target=escape(selector["target"])), as_html=True)
            return
        if recipient == "all":
            data = remaining
        else:
            data[recipient] = remaining
            if not remaining:
                data.pop(recipient, None)
        await self._db_set_json(key, data)
        await self.answer(event, self.strings("utsec_removed", recipient=recipient or "?", target=escape(selector["target"]), count=removed), as_html=True)

    @command("sgroup", doc_ru=".sgroup [create <group>|delete <group>|add <group> <user>|remove <group> <user>|grant <group> <rule>]", doc_en=".sgroup [create <group>|delete <group>|add <group> <user>|remove <group> <user>|grant <group> <rule>]")
    async def cmd_sgroup(self, event: Event) -> None:
        sender_id = getattr(event, "sender_id", None)
        if hasattr(self.kernel, "is_admin_async") and not await self.kernel.is_admin_async(sender_id):
            await self.answer(event, self.strings["not_owner"], as_html=True)
            return

        raw_args = self.args(event).args
        if not raw_args:
            groups: dict[str, Any] = await self._db_get_json(self.DB_KEY_GROUPS, {})
            if not groups:
                await self.answer(
                    event,
                    self.strings["sgroup_list_empty"] + chr(10) * 2 + self.strings["sgroup_args_hint"],
                    as_html=True,
                )
                return
            title = self.strings["sgroup_list_title"]
            lines = [title]
            for name, g in groups.items():
                u_count = len(g.get("users", []))
                p_count = len(g.get("permissions", []))
                lines.append(f"• <b>{name}</b>: {u_count} users, {p_count} rules")
            await self.answer(event, "\n".join(lines) + "\n\n" + self.strings["sgroup_args_hint"], as_html=True)
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

        elif action == "add" and len(raw_args) > 1 and (
            len(raw_args) > 2 or getattr(event, "is_reply", False)
        ):
            name = raw_args[1].lower()
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            target_str = raw_args[2] if len(raw_args) > 2 else None
            uid = int(target_str) if target_str and target_str.isdigit() else None
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

        elif action == "remove" and len(raw_args) > 1 and (
            len(raw_args) > 2 or getattr(event, "is_reply", False)
        ):
            name = raw_args[1].lower()
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            target_str = raw_args[2] if len(raw_args) > 2 else None
            uid = int(target_str) if target_str and target_str.isdigit() else None
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
            if name not in groups:
                await self.answer(event, self.strings("sgroup_not_found", name=name), as_html=True)
                return
            try:
                rule = self._grant_rule(shlex.split(get_args_raw(event))[2:], legacy=True)
            except ValueError:
                await self.answer(event, self.strings["sgroup_usage"], as_html=True)
                return
            if rule not in groups[name]["permissions"]:
                groups[name]["permissions"].append(rule)
                await self._db_set_json(self.DB_KEY_GROUPS, groups)
            await self.answer(event, f"<code>{escape(name)}</code>: <code>{escape(rule['target'])}</code> ({rule['allow']})", as_html=True)
        else:
            await self.answer(event, self.strings["sgroup_usage"], as_html=True)
