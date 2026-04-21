# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.4.0-beta
# description: Trusted users can execute owner commands / Доверенные пользователи могут выполнять команды владельца
import json

from core_inline.api.inline import make_cb_button
from core_inline.lib.manager import InlineManager
from core.langpacks import get_all_module_strings
from utils.strings import Strings

ACCESS_CATEGORIES = {
    "modules": {
        "en": {
            "label": "Modules",
            "desc": "unloading, cleaning and managing installed modules",
        },
        "ru": {
            "label": "Модули",
            "desc": "выгрузка, очистка и управление уже установленными модулями",
        },
        "commands": [],
        "is_module_cmds": True,
    },
    "loader": {
        "en": {
            "label": "Module Loader",
            "desc": "install external modules from files, links and presets",
        },
        "ru": {
            "label": "Установка модулей",
            "desc": "установка внешних модулей из файлов, ссылок и пресетов",
        },
        "commands": ["iload", "dlm", "um", "reload", "addrepo", "delrepo"],
    },
    "config": {
        "en": {"label": "Config", "desc": "userbot settings and basic parameters"},
        "ru": {"label": "Конфиг", "desc": "настройки юзербота и базовые параметры"},
        "commands": [
            "cfg",
            "fcfg",
            "setprefix",
            "addalias",
            "delalias",
            "lang",
            "cleardb",
            "clearmodules",
            "clearcache",
            "api_protection",
            "piped",
            "api_reset",
        ],
    },
    "backup": {
        "en": {"label": "Backups", "desc": "database and modules backup"},
        "ru": {"label": "Бэкапы", "desc": "резервные копии базы и модулей"},
        "commands": ["backup", "restore", "backupsettings", "backuptime"],
    },
    "terminal": {
        "en": {"label": "Terminal", "desc": "system shell commands on server"},
        "ru": {"label": "Терминал", "desc": "системные shell-команды на сервере"},
        "commands": ["t", "tkill"],
    },
    "eval": {
        "en": {"label": "Code / Eval", "desc": "eval and code execution"},
        "ru": {"label": "Код / Eval", "desc": "eval и выполнение кода"},
        "commands": ["py"],
    },
    "security": {
        "en": {
            "label": "Security",
            "desc": "owner, security, targeted rules and accesses",
        },
        "ru": {
            "label": "Безопасность",
            "desc": "owner, security, targeted rules и доступы",
        },
        "commands": [
            "trust",
            "untrust",
            "trustlist",
            "trustcmd",
            "sgroup",
            "watcher",
            "timedtrusted",
            "nonickuser",
            "nonickusers",
            "trustaccess",
        ],
    },
    "system": {
        "en": {"label": "System", "desc": "update, restart and system maintenance"},
        "ru": {"label": "Система", "desc": "update, restart и системное обслуживание"},
        "commands": ["restart", "update", "stop", "rollback"],
    },
    "inline": {
        "en": {"label": "Inline", "desc": "use inline commands and bot"},
        "ru": {"label": "Inline", "desc": "использовать инлайн-команды и бота"},
        "commands": [],
    },
    "callback": {
        "en": {"label": "Callback", "desc": "press callback buttons"},
        "ru": {"label": "Callback", "desc": "нажимать на callback-кнопки"},
        "commands": [],
    },
}

# Flat map: command → category key (built once at import time)
_CMD_TO_CAT: dict[str, str] = {}
for _cat_key, _cat_info in ACCESS_CATEGORIES.items():
    for _cmd in _cat_info.get("commands", []):
        _CMD_TO_CAT[_cmd] = _cat_key

# Display order: pairs → 2 per row, singletons → 1 per row
_CATEGORY_ROWS = [
    ("modules", "loader"),
    ("config", "backup"),
    ("terminal", "eval"),
    ("security", "system"),
    ("inline", "callback"),
]

# Presets
PRESETS = {
    "user": {
        "en": {"label": "👤 User"},
        "ru": {"label": "👤 Пользователь"},
        "access": {k: (k == "modules") for k in ACCESS_CATEGORIES},
    },
    "programmer": {
        "en": {"label": "💻 Programmer"},
        "ru": {"label": "💻 Программист"},
        "access": {
            k: (k in ("modules", "eval", "terminal")) for k in ACCESS_CATEGORIES
        },
    },
    "moderator": {
        "en": {"label": "🛡 Moderator"},
        "ru": {"label": "🛡 Модератор"},
        "access": {
            k: (k in ("modules", "loader", "config")) for k in ACCESS_CATEGORIES
        },
    },
}


def register(kernel):
    client = kernel.client
    language = kernel.config.get("language", "en")
    inline_manager = InlineManager(kernel)

    _cache = {"owner_username": None}

    _strings_data = {"name": "trusted", **get_all_module_strings("trusted")}
    _strings = Strings(kernel, _strings_data)
    s = _strings._active

    async def get_trusted_list():
        data = await kernel.db_get("trusted", "users")
        if not data:
            return []
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return []

    async def save_trusted_list(users):
        await kernel.db_set("trusted", "users", json.dumps(users))

    async def get_nonick_list():
        data = await kernel.db_get("trusted", "nonick")
        if not data:
            return []
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return []

    async def save_nonick_list(users):
        await kernel.db_set("trusted", "nonick", json.dumps(users))

    async def get_expired_trusted() -> dict:
        """Get dict of user_id -> expiry_timestamp for temporary trusts."""
        data = await kernel.db_get("trusted", "expired")
        if not data:
            return {}
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return {}

    async def save_expired_trusted(expired: dict):
        await kernel.db_set("trusted", "expired", json.dumps(expired))

    async def is_sgroup_member(user_id: int) -> bool:
        """Check if user is a member of any security group."""
        groups = await get_sgroups()
        for gdata in groups.values():
            if user_id in gdata.get("users", []):
                return True
        return False

    async def get_sgroups() -> dict:
        """Get all security groups."""
        data = await kernel.db_get("trusted", "sgroups")
        if not data:
            return {}
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return {}

    async def save_sgroups(groups: dict):
        await kernel.db_set("trusted", "sgroups", json.dumps(groups))

    async def get_access(user_id: int) -> dict:
        """Return per-user access dict. Defaults: all False."""
        data = await kernel.db_get("trusted_access", str(user_id))
        if not data:
            return dict.fromkeys(ACCESS_CATEGORIES, False)
        try:
            stored = (
                json.loads(data) if isinstance(data, str) else json.loads(str(data))
            )
            # Fill any missing keys with False
            return {cat: stored.get(cat, False) for cat in ACCESS_CATEGORIES}
        except Exception:
            return dict.fromkeys(ACCESS_CATEGORIES, False)

    async def save_access(user_id: int, access: dict):
        await kernel.db_set("trusted_access", str(user_id), json.dumps(access))

    async def get_cmd_access(user_id: int) -> dict:
        """Return per-user command access dict. Keys are command names."""
        data = await kernel.db_get("trusted_cmd_access", str(user_id))
        if not data:
            return {}
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return {}

    async def save_cmd_access(user_id: int, cmd_access: dict):
        await kernel.db_set("trusted_cmd_access", str(user_id), json.dumps(cmd_access))

    def get_all_commands() -> list:
        """Get list of all registered command names from kernel."""
        return (
            list(kernel.command_handlers.keys())
            if hasattr(kernel, "command_handlers")
            else []
        )

    async def get_owner_username():
        if _cache["owner_username"] is not None:
            return _cache["owner_username"]
        try:
            me = await client.get_me()
            _cache["owner_username"] = me.username
            return _cache["owner_username"]
        except Exception:
            return None

    async def get_user_display(user_id: int) -> str:
        try:
            user = await client.get_entity(user_id)
            if getattr(user, "username", None):
                return f"@{user.username}"
            return getattr(user, "first_name", None) or str(user_id)
        except Exception:
            return str(user_id)

    async def get_user_id(event) -> int | None:
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply:
                return reply.sender_id
        args = event.text.split(maxsplit=1)
        if len(args) > 1:
            target = args[1].strip().split()[0]  # only first word
            if target.lstrip("-").isdigit():
                return int(target)
            username = target.lstrip("@")
            try:
                entity = await client.get_entity(username)
                return entity.id
            except Exception:
                pass
        return None

    def _get_command_category(cmd: str) -> str:
        """Return category key for a command; falls back to 'modules'."""
        return _CMD_TO_CAT.get(cmd, "modules")

    def _build_access_text(
        user_display: str, access: dict, group_access: dict | None = None
    ) -> str:
        lines = [s["trustaccess_title"].format(user=user_display)]
        body_lines = []
        for cat_key, cat_info in ACCESS_CATEGORIES.items():
            allowed = access.get(cat_key, False)
            group_allowed = False
            if group_access is not None:
                for _gname, gdata in group_access.items():
                    if gdata.get("access", {}).get(cat_key, False):
                        group_allowed = True
                        break
            if allowed and not group_allowed:
                state_word = s["access_allowed"]
            elif group_allowed and not allowed:
                state_word = s["access_allowed_group"]
            elif allowed and group_allowed:
                state_word = s["access_allowed"]
            else:
                state_word = s["access_denied"]
            icon = "✅" if (allowed or group_allowed) else "🚫"
            localized = cat_info.get(language, cat_info["en"])
            body_lines.append(
                f"{icon} {localized['label']} — <em>{state_word}</em>\n"
                f"└ {localized['desc']}"
            )
        lines.append(
            "<blockquote expandable>" + "\n".join(body_lines) + "</blockquote>"
        )
        lines.append(s["trustaccess_footer"])
        return "\n".join(lines)

    def _build_access_buttons(
        kernel, user_id: int, access: dict, msg_ref, group_access: dict | None = None
    ) -> list:
        """Build inline button rows using make_cb_button for temporary callbacks."""

        async def on_toggle(event, uid, cat_key):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            cur = await get_access(uid)
            cur[cat_key] = not cur.get(cat_key, False)
            await save_access(uid, cur)
            if cat_key == "inline":
                if cur[cat_key]:
                    await inline_manager.allow_user(uid)
                else:
                    await inline_manager.deny_user(uid)
            name = await get_user_display(uid)
            groups = await get_sgroups()
            g_access = {
                gname: gdata
                for gname, gdata in groups.items()
                if uid in gdata.get("users", [])
            }
            new_text = _build_access_text(name, cur, g_access)
            new_buttons = _build_access_buttons(kernel, uid, cur, None, g_access)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_preset(event, uid, preset_key):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            preset = PRESETS[preset_key]
            await save_access(uid, dict(preset["access"]))
            if preset["access"].get("inline", False):
                await inline_manager.allow_user(uid)
            else:
                await inline_manager.deny_user(uid)
            name = await get_user_display(uid)
            new_access = dict(preset["access"])
            groups = await get_sgroups()
            g_access = {
                gname: gdata
                for gname, gdata in groups.items()
                if uid in gdata.get("users", [])
            }
            new_text = _build_access_text(name, new_access, g_access)
            new_buttons = _build_access_buttons(kernel, uid, new_access, None, g_access)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_allow_all(event, uid):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            full = dict.fromkeys(ACCESS_CATEGORIES, True)
            await save_access(uid, full)
            if full.get("inline", False):
                await inline_manager.allow_user(uid)
            else:
                await inline_manager.deny_user(uid)
            name = await get_user_display(uid)
            groups = await get_sgroups()
            g_access = {
                gname: gdata
                for gname, gdata in groups.items()
                if uid in gdata.get("users", [])
            }
            new_text = _build_access_text(name, full, g_access)
            new_buttons = _build_access_buttons(kernel, uid, full, None, g_access)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_deny_all(event, uid):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            none_ = dict.fromkeys(ACCESS_CATEGORIES, False)
            await save_access(uid, none_)
            await inline_manager.deny_user(uid)
            name = await get_user_display(uid)
            groups = await get_sgroups()
            g_access = {
                gname: gdata
                for gname, gdata in groups.items()
                if uid in gdata.get("users", [])
            }
            new_text = _build_access_text(name, none_, g_access)
            new_buttons = _build_access_buttons(kernel, uid, none_, None, g_access)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_close(event, uid):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            try:
                await kernel.client.delete_messages(event.chat_id, [event.message.id])
            except Exception:
                pass

        TTL = 600
        rows = []

        # Category toggle rows (layout from _CATEGORY_ROWS)
        for row_cats in _CATEGORY_ROWS:
            row = []
            for cat_key in row_cats:
                cat_info = ACCESS_CATEGORIES[cat_key]
                localized = cat_info.get(language, cat_info["en"])
                allowed = access.get(cat_key, False)

                group_allowed = False
                if group_access is not None:
                    for _gname, gdata in group_access.items():
                        if gdata.get("access", {}).get(cat_key, False):
                            group_allowed = True
                            break

                is_allowed = allowed or group_allowed
                icon = "✅" if is_allowed else "🚫"
                label = f"{icon} {localized['label']}"
                row.append(
                    make_cb_button(
                        kernel,
                        label,
                        on_toggle,
                        args=[user_id, cat_key],
                        ttl=TTL,
                        style="success" if is_allowed else "danger",
                    )
                )
            rows.append(row)

        preset_row = []
        for preset_key, preset_info in PRESETS.items():
            localized = preset_info.get(language, preset_info["en"])
            preset_row.append(
                make_cb_button(
                    kernel,
                    localized["label"],
                    on_preset,
                    args=[user_id, preset_key],
                    ttl=TTL,
                    style="primary",
                )
            )
        rows.append(preset_row)

        async def on_cmds(event, uid):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            access = await get_access(uid)
            cmd_access = await get_cmd_access(uid)
            name = await get_user_display(uid)
            text, rows = _build_percmd_menu(uid, access, cmd_access, name)
            await event.edit(text, buttons=rows, parse_mode="html")

        rows.append(
            [
                make_cb_button(
                    kernel,
                    s["btn_cmds"],
                    on_cmds,
                    args=[user_id],
                    ttl=TTL,
                    style="primary",
                ),
            ]
        )

        # Allow all / Deny all
        rows.append(
            [
                make_cb_button(
                    kernel,
                    s["btn_allow_all"],
                    on_allow_all,
                    args=[user_id],
                    ttl=TTL,
                    style="success",
                ),
                make_cb_button(
                    kernel,
                    s["btn_deny_all"],
                    on_deny_all,
                    args=[user_id],
                    ttl=TTL,
                    style="danger",
                ),
            ]
        )

        # Close
        rows.append(
            [
                make_cb_button(
                    kernel,
                    s["btn_close"],
                    on_close,
                    args=[user_id],
                    ttl=TTL,
                    style="primary",
                ),
            ]
        )

        return rows

    def _get_cmd_default_access(cmd: str, access: dict) -> bool:
        """Get default access for a command based on its category."""
        category = _get_command_category(cmd)
        return access.get(category, False)

    def _build_percmd_menu(
        user_id: int, access: dict, cmd_access: dict, name: str, page: int = 0
    ) -> tuple:
        """Build per-command menu with pagination."""
        ITEMS_PER_PAGE = 10

        async def on_toggle_cmd(event, uid, cmd, current_allowed, current_page):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            cmd_access = await get_cmd_access(uid)
            cmd_access[cmd] = not current_allowed
            await save_cmd_access(uid, cmd_access)
            access = await get_access(uid)
            name = await get_user_display(uid)
            text, rows = _build_percmd_menu(uid, access, cmd_access, name, current_page)
            await event.edit(text, buttons=rows, parse_mode="html")

        async def on_back(event, uid):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            access = await get_access(uid)
            name = await get_user_display(uid)
            groups = await get_sgroups()
            g_access = {
                gname: gdata
                for gname, gdata in groups.items()
                if uid in gdata.get("users", [])
            }
            text = _build_access_text(name, access, g_access)
            buttons = _build_access_buttons(kernel, uid, access, None, g_access)
            await event.edit(text, buttons=buttons, parse_mode="html")

        async def on_prev(event, uid, current_page):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            if current_page > 0:
                access = await get_access(uid)
                cmd_access = await get_cmd_access(uid)
                name = await get_user_display(uid)
                text, rows = _build_percmd_menu(
                    uid, access, cmd_access, name, current_page - 1
                )
                await event.edit(text, buttons=rows, parse_mode="html")

        async def on_next(event, uid, current_page):
            sender = event.sender_id
            is_admin = sender == kernel.ADMIN_ID
            is_sgroup = await is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await event.answer()
                return
            all_cmds = get_all_commands()
            total_pages = (len(all_cmds) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            if current_page < total_pages - 1:
                access = await get_access(uid)
                cmd_access = await get_cmd_access(uid)
                name = await get_user_display(uid)
                text, rows = _build_percmd_menu(
                    uid, access, cmd_access, name, current_page + 1
                )
                await event.edit(text, buttons=rows, parse_mode="html")

        TTL = 600
        all_cmds = get_all_commands()
        total_pages = (len(all_cmds) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(all_cmds))
        page_cmds = all_cmds[start_idx:end_idx]

        lines = [s["percmd_title"].format(user=name), "<blockquote>"]
        for cmd in page_cmds:
            if cmd in cmd_access:
                allowed = cmd_access[cmd]
            else:
                allowed = _get_cmd_default_access(cmd, access)
            icon = "✅" if allowed else "🚫"
            state = s["access_allowed"] if allowed else s["access_denied"]
            lines.append(f"{icon} <code>{cmd}</code> — <em>{state}</em>")
        if total_pages > 1:
            lines.append(f"<em>{page + 1}/{total_pages}</em>")
        lines.append("</blockquote>")

        text = "\n".join(lines)

        rows = []
        for cmd in page_cmds:
            if cmd in cmd_access:
                allowed = cmd_access[cmd]
            else:
                allowed = _get_cmd_default_access(cmd, access)
            icon = "✅" if allowed else "🚫"
            rows.append(
                [
                    make_cb_button(
                        kernel,
                        f"{icon} {cmd}",
                        on_toggle_cmd,
                        args=[user_id, cmd, allowed, page],
                        ttl=TTL,
                        style="success" if allowed else "danger",
                    )
                ]
            )

        nav_row = []
        if page > 0:
            nav_row.append(
                make_cb_button(
                    kernel,
                    "<",
                    on_prev,
                    args=[user_id, page],
                    ttl=TTL,
                    style="primary",
                )
            )
        if page < total_pages - 1:
            nav_row.append(
                make_cb_button(
                    kernel,
                    ">",
                    on_next,
                    args=[user_id, page],
                    ttl=TTL,
                    style="primary",
                )
            )
        if nav_row:
            rows.append(nav_row)

        rows.append(
            [
                make_cb_button(
                    kernel,
                    s["percmd_back"],
                    on_back,
                    args=[user_id],
                    ttl=TTL,
                    style="primary",
                )
            ]
        )

        return text, rows

    @kernel.register.command(
        "trustaccess",
        doc_en="manage trusted user access permissions",
        doc_ru="управление правами доступа доверенного пользователя",
    )
    async def trustaccess_handler(event):
        """Manage trusted user's access permissions"""
        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["trustaccess_usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id not in trusted:
            await event.edit(s["trust_not_in_list"], parse_mode="html")
            return

        access = await get_access(user_id)
        name = await get_user_display(user_id)

        groups = await get_sgroups()
        group_access = {
            gname: gdata
            for gname, gdata in groups.items()
            if user_id in gdata.get("users", [])
        }

        text = _build_access_text(name, access, group_access)
        buttons = _build_access_buttons(kernel, user_id, access, None, group_access)

        await kernel.inline_form(event.chat_id, text, buttons=buttons, ttl=600)
        await event.delete()

    @kernel.register.command(
        "trust",
        alias=["addowner"],
        doc_en="add user to trusted list",
        doc_ru="добавить пользователя в доверенные",
    )
    async def trust_handler(event):
        """Add a user to the trusted list with confirmation and time options"""

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id in trusted:
            await event.edit(s["trust_already"], parse_mode="html")
            return

        await get_user_display(user_id)

        async def on_time_select(event, uid, seconds):
            if event.sender_id != kernel.ADMIN_ID:
                await event.answer()
                return
            if seconds == 0:
                await _show_nonick_step(event, uid)
            else:
                import time

                expiry = int(time.time()) + seconds
                expired = await get_expired_trusted()
                expired[str(uid)] = expiry
                await save_expired_trusted(expired)
                await _show_nonick_step(event, uid, timed=True, seconds=seconds)

        async def _show_nonick_step(event, uid, timed=False, seconds=0):
            if event.sender_id != kernel.ADMIN_ID:
                await event.answer()
                return
            name = await get_user_display(uid)
            owner_uname = await get_owner_username()

            if owner_uname:
                desc = s["nonick_step_desc"].format(
                    prefix=kernel.custom_prefix,
                    alias=owner_uname,
                )
            else:
                desc = s["nonick_step_desc_no_alias"]

            if timed:
                time_str = _format_duration(seconds)
                text = (
                    s["trust_added_timed"].format(time=time_str)
                    + "\n\n"
                    + s["nonick_step_title"].format(name=name)
                    + "\n"
                    + "<blockquote>"
                    + desc
                    + "</blockquote>"
                )
            else:
                text = (
                    s["nonick_step_title"].format(name=name)
                    + "\n"
                    + "<blockquote>"
                    + desc
                    + "</blockquote>"
                )

            buttons = [
                [
                    make_cb_button(
                        kernel,
                        s["btn_nonick_yes"],
                        on_nonick,
                        args=[uid, True, timed, seconds],
                        ttl=TTL,
                        style="success",
                    ),
                    make_cb_button(
                        kernel,
                        s["btn_nonick_no"],
                        on_nonick,
                        args=[uid, False, timed, seconds],
                        ttl=TTL,
                        style="danger",
                    ),
                ]
            ]
            await event.edit(text, buttons=buttons, parse_mode="html")

        async def on_nonick(event, uid, nonick, timed=False, seconds=0):
            if event.sender_id != kernel.ADMIN_ID:
                await event.answer()
                return
            trusted = await get_trusted_list()
            if uid not in trusted:
                trusted.append(uid)
                await save_trusted_list(trusted)
                default_access = {
                    cat: (cat in ("modules", "inline", "callback"))
                    for cat in ACCESS_CATEGORIES
                }
                await save_access(uid, default_access)
                if default_access.get("inline", False):
                    await inline_manager.allow_user(uid)

            nonick_list = await get_nonick_list()
            if nonick and uid not in nonick_list:
                nonick_list.append(uid)
                await save_nonick_list(nonick_list)
            elif not nonick and uid in nonick_list:
                nonick_list.remove(uid)
                await save_nonick_list(nonick_list)

            await get_user_display(uid)
            if timed:
                time_str = _format_duration(seconds)
                await event.edit(
                    s["trust_added_timed"].format(time=time_str),
                    parse_mode="html",
                )
            else:
                await event.edit(
                    s["trust_added"],
                    parse_mode="html",
                )

        def _format_duration(seconds: int) -> str:
            if seconds >= 86400:
                days = seconds // 86400
                unit = "дней" if language == "ru" else "days"
                return f"{days} {unit}"
            elif seconds >= 3600:
                hours = seconds // 3600
                unit = "часов" if language == "ru" else "hours"
                return f"{hours} {unit}"
            else:
                minutes = seconds // 60
                unit = "минут" if language == "ru" else "minutes"
                return f"{minutes} {unit}"

        async def on_cancel(event):
            try:
                await kernel.client.delete_messages(event.chat_id, [event.message.id])
            except Exception:
                pass

        TTL = 600

        text = (
            s["trust_time_title"]
            + "\n"
            + "<blockquote>"
            + s["trust_time_desc"].format(time="")
            + "</blockquote>"
        )

        rows = [
            [
                make_cb_button(
                    kernel,
                    s["btn_1h"],
                    on_time_select,
                    args=[user_id, 3600],
                    ttl=TTL,
                    style="primary",
                ),
                make_cb_button(
                    kernel,
                    s["btn_24h"],
                    on_time_select,
                    args=[user_id, 86400],
                    ttl=TTL,
                    style="primary",
                ),
                make_cb_button(
                    kernel,
                    s["btn_7d"],
                    on_time_select,
                    args=[user_id, 604800],
                    ttl=TTL,
                    style="primary",
                ),
            ],
            [
                make_cb_button(
                    kernel,
                    s["btn_permanent"],
                    on_time_select,
                    args=[user_id, 0],
                    ttl=TTL,
                    style="success",
                ),
                make_cb_button(
                    kernel,
                    s["btn_cancel"],
                    on_cancel,
                    args=[],
                    ttl=TTL,
                    style="danger",
                ),
            ],
        ]
        await kernel.inline_form(event.chat_id, text, buttons=rows)

    @kernel.register.command(
        "untrust",
        alias=["delowner"],
        doc_en="remove user from trusted list",
        doc_ru="удалить пользователя из доверенных",
    )
    async def untrust_handler(event):
        """Remove a user from the trusted list"""
        if event.sender_id != kernel.ADMIN_ID:
            await event.edit(s["not_owner"], parse_mode="html")
            return

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id not in trusted:
            await event.edit(s["trust_not_in_list"], parse_mode="html")
            return

        trusted.remove(user_id)
        await save_trusted_list(trusted)

        nonick_list = await get_nonick_list()
        if user_id in nonick_list:
            nonick_list.remove(user_id)
            await save_nonick_list(nonick_list)

        await inline_manager.deny_user(user_id)
        kernel.callback_permissions.prohibit(user_id)
        await event.edit(s["trust_removed"], parse_mode="html")

    @kernel.register.command(
        "trustlist",
        alias=["listowner"],
        doc_en="show list of trusted users",
        doc_ru="показать список доверенных пользователей",
    )
    async def trustlist_handler(event):
        """Show list of all trusted users"""
        trusted = await get_trusted_list()
        if not trusted:
            await event.edit(s["trustlist_empty"], parse_mode="html")
            return

        nonick_list = await get_nonick_list()
        lines = [s["trustlist_title"]]
        for uid in trusted:
            name = await get_user_display(uid)
            nn = " 🔑" if uid in nonick_list else ""
            lines.append(f"• {name} (<code>{uid}</code>){nn}")

        await event.edit("\n".join(lines), parse_mode="html")

    @kernel.register.command(
        "trustcmd",
        doc_en="manage per-command access for trusted",
        doc_ru="управление доступом к командам для доверенных",
    )
    async def trustcmd_handler(event):
        """Manage per-command access for trusted users"""
        args = event.text.split(maxsplit=2)
        if len(args) < 2:
            await event.edit(s["trustcmd_usage"], parse_mode="html")
            return

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["trustcmd_usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id not in trusted:
            await event.edit(s["trust_not_in_list"], parse_mode="html")
            return

        all_cmds = get_all_commands()
        if len(args) < 3:
            # check for "list" subcommand (no third arg needed)
            if len(args) == 2 and args[1].lower() == "list":
                pass
            else:
                await event.edit(s["trustcmd_usage"], parse_mode="html")
                return

        if len(args) >= 3:
            cmd_arg = args[2].lstrip("+_-")
            cmd_name = cmd_arg.lower()
        else:
            cmd_name = ""

        if cmd_name in all_cmds:
            is_add = args[2].startswith("+")
            is_remove = args[2].startswith("-")

            cmd_access = await get_cmd_access(user_id)

            if is_add:
                cmd_access[cmd_name] = True
                status_key = "trustcmd_added"
            elif is_remove:
                cmd_access[cmd_name] = False
                status_key = "trustcmd_removed"
            else:
                await event.edit(s["trustcmd_usage"], parse_mode="html")
                return

            await save_cmd_access(user_id, cmd_access)
            name = await get_user_display(user_id)
            msg = s[status_key].format(cmd=cmd_name, user=name)
            await event.edit(msg, parse_mode="html")
            return

        if cmd_name == "list" or (len(args) == 2 and args[1].lower() == "list"):
            cmd_access = await get_cmd_access(user_id)
            name = await get_user_display(user_id)

            if not cmd_access:
                await event.edit(s["trustcmd_list_empty"], parse_mode="html")
                return

            lines = [s["trustcmd_list_title"].format(user=name), "<blockquote>"]
            for cmd, allowed in cmd_access.items():
                icon = "✅" if allowed else "🚫"
                state = s["access_allowed"] if allowed else s["access_denied"]
                lines.append(f"{icon} <code>{cmd}</code> — <em>{state}</em>")
            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")
            return

        await event.edit(
            s["trustcmd_not_found"].format(cmd=cmd_name), parse_mode="html"
        )

    @kernel.register.command(
        "nonickuser",
        doc_en="toggle NoNick mode for trusted user",
        doc_ru="включить/выключить режим NoNick для доверенного",
    )
    async def nonickuser_handler(event):
        """Toggle NoNick mode for a trusted user"""
        if event.sender_id != kernel.ADMIN_ID:
            await event.edit(s["not_owner"], parse_mode="html")
            return

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["nonick_usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id not in trusted:
            await event.edit(s["trust_not_in_list"], parse_mode="html")
            return

        nonick_list = await get_nonick_list()
        name = await get_user_display(user_id)

        if user_id in nonick_list:
            nonick_list.remove(user_id)
            await save_nonick_list(nonick_list)
            await event.edit(
                s["nonick_toggled_off"].format(name=name), parse_mode="html"
            )
        else:
            nonick_list.append(user_id)
            await save_nonick_list(nonick_list)
            await event.edit(
                s["nonick_toggled_on"].format(name=name), parse_mode="html"
            )

    @kernel.register.command(
        "nonickusers",
        doc_en="show list of users with NoNick",
        doc_ru="показать список пользователей с NoNick",
    )
    async def nonickusers_handler(event):
        """Show list of trusted users with NoNick enabled"""
        nonick_list = await get_nonick_list()
        if not nonick_list:
            await event.edit(s["nonick_list_empty"], parse_mode="html")
            return

        lines = [s["nonick_list_title"]]
        for uid in nonick_list:
            name = await get_user_display(uid)
            lines.append(f"• {name} (<code>{uid}</code>)")

        await event.edit("\n".join(lines), parse_mode="html")

    @kernel.register.command(
        "watchers",
        doc_en="show list of active watchers",
        doc_ru="показать список активных вотчеров",
    )
    async def watchers_handler(event):
        """Show list of all active watchers"""
        try:
            watchers = kernel.register.get_watchers()
            if not watchers:
                await event.edit(s["watchers_empty"], parse_mode="html")
                return

            lines = [s["watchers_title"] + "<blockquote expandable>"]
            for i, watcher in enumerate(watchers, 1):
                event_obj = watcher["event"]
                func_name = watcher["method"]
                module_name = watcher["module"]
                status = "on" if watcher["enabled"] else "off"
                direction = ""
                if getattr(event_obj, "incoming", False):
                    direction = " [in]"
                elif getattr(event_obj, "out", False):
                    direction = " [out]"
                lines.append(
                    f"<code>{i}.</code> <b>{module_name}.{func_name}</b>{direction} — <i>{status}</i>"
                )
            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")
        except Exception as e:
            await kernel.handle_error(e, source="watchers", event=event)

    @kernel.register.command(
        "watchersdebug",
        doc_en="debug watchers with filter",
        doc_ru="отладка вотчеров с фильтром",
    )
    async def watchers_debug_handler(event):
        """Debug watchers with optional filter"""
        try:
            args = event.text.split(maxsplit=1)
            filter_text = args[1].lower() if len(args) > 1 else ""
            watchers = kernel.register.get_watchers()
            builder_snapshot = []
            if hasattr(kernel, "_debug_event_builders_snapshot"):
                builder_snapshot = kernel._debug_event_builders_snapshot()

            lines = [s["watchers_debug_title"] + "<blockquote expandable>"]
            matched = 0

            for watcher in watchers:
                module_name = watcher["module"]
                watcher_name = watcher["method"]
                full_name = f"{module_name}.{watcher_name}"
                if filter_text and filter_text not in full_name.lower():
                    continue

                wrapper_name = getattr(watcher["wrapper"], "__name__", watcher_name)
                builder_marker = f"{type(watcher['event']).__name__}:{wrapper_name}"
                in_builders = builder_marker in builder_snapshot
                direction = []
                if watcher["tags"].get("incoming"):
                    direction.append("incoming")
                if watcher["tags"].get("out"):
                    direction.append("out")
                if not direction:
                    direction.append("any")

                lines.append(
                    f"<b>{full_name}</b> — "
                    f"<code>enabled={watcher['enabled']}</code> "
                    f"<code>bound={in_builders}</code> "
                    f"<code>dir={','.join(direction)}</code>"
                )
                matched += 1

            if not matched:
                await event.edit(s["watchers_debug_empty"], parse_mode="html")
                return

            lines.append("</blockquote>")
            if builder_snapshot:
                lines.append("<blockquote expandable>")
                for item in builder_snapshot[:40]:
                    lines.append(f"<code>{item}</code>")
                if len(builder_snapshot) > 40:
                    lines.append(f"<i>... +{len(builder_snapshot) - 40}</i>")
                lines.append("</blockquote>")

            await event.edit("\n".join(lines), parse_mode="html")
        except Exception as e:
            await kernel.handle_error(e, source="watchersdebug", event=event)

    async def toggle_watcher_handler(event):
        """Toggle a specific watcher on/off"""
        if event.sender_id != kernel.ADMIN_ID:
            await event.edit(s["not_owner"], parse_mode="html")
            return

        args = event.text.split(maxsplit=2)
        if len(args) < 3:
            await event.edit(s["watcher_usage"], parse_mode="html")
            return

        module_name = args[1]
        watcher_name = args[2]
        watchers = kernel.register.get_watchers()
        watcher_info = next(
            (
                w
                for w in watchers
                if w["module"] == module_name and w["method"] == watcher_name
            ),
            None,
        )

        if watcher_info is None:
            await event.edit(
                s["watcher_not_found"].format(module=module_name, watcher=watcher_name),
                parse_mode="html",
            )
            return

        if watcher_info["enabled"]:
            ok = kernel.register.disable_watcher(module_name, watcher_name)
            key = "watcher_disabled"
        else:
            ok = kernel.register.enable_watcher(module_name, watcher_name)
            key = "watcher_enabled"

        if not ok:
            await event.edit(
                s["watcher_not_found"].format(module=module_name, watcher=watcher_name),
                parse_mode="html",
            )
            return

        await event.edit(
            s[key].format(module=module_name, watcher=watcher_name),
            parse_mode="html",
        )

    @kernel.register.command(
        "watcher",
        doc_en="enable/disable specific watcher",
        doc_ru="включить/выключить конкретный вотчер",
    )
    async def watcher_toggle_handler(event):
        """Enable or disable a specific watcher"""
        await toggle_watcher_handler(event)

    @kernel.register.watcher(out=False, incoming=True)
    async def trusted_watcher(event):
        """Process commands from trusted users with access control"""
        msg = getattr(event, "message", event)
        if getattr(msg, "out", False):
            return

        text = getattr(msg, "text", "") or ""
        sender_id = getattr(event, "sender_id", None)

        trusted = await get_trusted_list()
        if sender_id not in trusted:
            return

        if not text.startswith(kernel.custom_prefix):
            return

        cmd_body = text[len(kernel.custom_prefix) :]
        parts = cmd_body.split()
        if not parts:
            return

        cmd_token = parts[0]
        rest = parts[1:]

        owner_uname = await get_owner_username()
        owner_alias = f"@{owner_uname}" if owner_uname else None

        has_alias = False
        actual_cmd = cmd_token

        if owner_alias and cmd_token.lower().endswith(owner_alias.lower()):
            stripped = cmd_token[: -len(owner_alias)]
            if stripped:
                actual_cmd = stripped
                has_alias = True

        nonick_list = await get_nonick_list()
        sender_has_nonick = sender_id in nonick_list

        if not has_alias and not sender_has_nonick:
            return

        resolved_cmd = actual_cmd
        all_aliases = kernel.register.get_all_aliases()
        if resolved_cmd in all_aliases:
            resolved_cmd = all_aliases[resolved_cmd]

        category = _get_command_category(resolved_cmd)
        access = await get_access(sender_id)

        cmd_access = await get_cmd_access(sender_id)
        user_has_access = False

        if resolved_cmd in cmd_access:
            if not cmd_access[resolved_cmd]:
                groups = await get_sgroups()
                for _gname, gdata in groups.items():
                    if sender_id in gdata.get("users", []):
                        if gdata.get("access", {}).get(category, False):
                            user_has_access = True
                            break
                if not user_has_access:
                    return
            else:
                user_has_access = True
        elif not access.get(category, False):
            groups = await get_sgroups()
            for _gname, gdata in groups.items():
                if sender_id in gdata.get("users", []):
                    if gdata.get("access", {}).get(category, False):
                        user_has_access = True
                        break
            if not user_has_access:
                return

        cmd_text = kernel.custom_prefix + actual_cmd
        if rest:
            cmd_text += " " + " ".join(rest)

        if actual_cmd not in kernel.command_handlers:
            if actual_cmd not in all_aliases:
                return
            actual_cmd = all_aliases.get(actual_cmd, actual_cmd)
            if actual_cmd not in kernel.command_handlers:
                return

        cmd = await kernel.client.send_message(
            event.chat_id, cmd_text, reply_to=event.reply_to_msg_id
        )

        class _MessageEventProxy:
            def __init__(self, msg):
                self._msg = msg

            def __getattr__(self, name):
                return getattr(self._msg, name)

            @property
            def message(self):
                return self._msg

            @property
            def is_reply(self):
                return bool(getattr(self._msg, "reply_to", None))

            @property
            def reply_to_msg_id(self):
                rt = getattr(self._msg, "reply_to", None)
                return getattr(rt, "reply_to_msg_id", None) if rt else None

            async def edit(self, *args, **kwargs):
                return await self._msg.edit(*args, **kwargs)

            async def reply(self, *args, **kwargs):
                return await self._msg.reply(*args, **kwargs)

            async def get_reply_message(self):
                return await self._msg.get_reply_message()

            def no_owner(self):
                return True

        await kernel.process_command(_MessageEventProxy(cmd))

    @kernel.register.loop(interval=30, autostart=True)
    async def update_callback_permissions(_kernel):
        trusted = await get_trusted_list()
        for uid in trusted:
            access = await get_access(uid)
            if access.get("inline", False) or access.get("callback", False):
                _kernel.callback_permissions.allow(uid, "", duration_seconds=60)
            else:
                _kernel.callback_permissions.prohibit(uid)

    @kernel.register.loop(interval=60, autostart=True)
    async def check_expired_trusted(_kernel):
        """Remove expired temporary trusted users"""
        import time

        expired = await get_expired_trusted()
        if not expired:
            return

        current_time = int(time.time())
        trusted = await get_trusted_list()
        changed = False

        for uid_str, expiry in list(expired.items()):
            if current_time >= expiry:
                uid = int(uid_str)
                if uid in trusted:
                    trusted.remove(uid)
                    changed = True

                nonick_list = await get_nonick_list()
                if uid in nonick_list:
                    nonick_list.remove(uid)
                    await save_nonick_list(nonick_list)

                await inline_manager.deny_user(uid)
                _kernel.callback_permissions.prohibit(uid)

                del expired[uid_str]
                changed = True

                try:
                    name = await get_user_display(uid)
                except:
                    name = str(uid)

                await _kernel.client.send_message(
                    _kernel.ADMIN_ID,
                    s["trust_expired"].format(user=name),
                    parse_mode="html",
                )

        if changed:
            await save_trusted_list(trusted)
            await save_expired_trusted(expired)

    @kernel.register.command(
        "timedtrusted",
        doc_en="show temporary trusted users with expiry",
        doc_ru="показать временных доверенных с истечением",
    )
    async def timedtrusted_handler(event):
        """Show list of temporary trusted users with expiry times"""
        expired = await get_expired_trusted()
        if not expired:
            await event.edit(s["timed_trusted_empty"], parse_mode="html")
            return

        import time

        current_time = int(time.time())
        lines = [s["timed_trusted_title"]]

        for uid_str, expiry in expired.items():
            uid = int(uid_str)
            name = await get_user_display(uid)
            remaining = expiry - current_time
            if remaining > 0:
                if remaining >= 86400:
                    time_str = f"{remaining // 86400}d"
                elif remaining >= 3600:
                    time_str = f"{remaining // 3600}h"
                else:
                    time_str = f"{remaining // 60}m"
                lines.append(
                    f"• {name} (<code>{uid}</code>){s['trust_expiring'].format(time=time_str)}"
                )

        await event.edit("\n".join(lines), parse_mode="html")

    @kernel.register.command(
        "sgroup", doc_en="manage access groups", doc_ru="управление группами доступа"
    )
    async def sgroup_handler(event):
        """Manage access groups"""
        args = event.text.split(maxsplit=2)
        if len(args) < 2:
            await event.edit(s["sgroup_usage"], parse_mode="html")
            return

        action = args[1].lower()
        groups = await get_sgroups()

        if action == "create":
            if len(args) < 3:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            name = args[2].strip()
            if name in groups:
                await event.edit(
                    s["sgroup_already_exists"].format(name=name), parse_mode="html"
                )
                return
            groups[name] = {
                "users": [],
                "access": dict.fromkeys(ACCESS_CATEGORIES, False),
            }
            await save_sgroups(groups)
            await event.edit(s["sgroup_created"].format(name=name), parse_mode="html")
            return

        if action == "delete":
            if len(args) < 3:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            name = args[2].strip()
            if name not in groups:
                await event.edit(
                    s["sgroup_not_found"].format(name=name), parse_mode="html"
                )
                return
            del groups[name]
            await save_sgroups(groups)
            await event.edit(s["sgroup_deleted"].format(name=name), parse_mode="html")
            return

        if action == "add":
            if len(args) < 3:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            sub = args[2].split(maxsplit=1)
            if len(sub) < 2:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            name = sub[0].strip()
            user_part = sub[1].strip()
            if user_part.lstrip("-").isdigit():
                user_id = int(user_part)
            else:
                try:
                    entity = await client.get_entity(user_part.lstrip("@"))
                    user_id = entity.id
                except Exception:
                    await event.edit(s["sgroup_usage"], parse_mode="html")
                    return
            if name not in groups:
                await event.edit(
                    s["sgroup_not_found"].format(name=name), parse_mode="html"
                )
                return
            if user_id in groups[name]["users"]:
                await event.edit(s["sgroup_user_in_group"], parse_mode="html")
                return
            groups[name]["users"].append(user_id)
            await save_sgroups(groups)
            user_name = await get_user_display(user_id)
            await event.edit(
                s["sgroup_user_added"].format(user=user_name, group=name),
                parse_mode="html",
            )
            return

        if action == "remove":
            if len(args) < 3:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            sub = args[2].split(maxsplit=1)
            if len(sub) < 2:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            name = sub[0].strip()
            user_part = sub[1].strip()
            if user_part.lstrip("-").isdigit():
                user_id = int(user_part)
            else:
                try:
                    entity = await client.get_entity(user_part.lstrip("@"))
                    user_id = entity.id
                except Exception:
                    await event.edit(s["sgroup_usage"], parse_mode="html")
                    return
            if name not in groups:
                await event.edit(
                    s["sgroup_not_found"].format(name=name), parse_mode="html"
                )
                return
            if user_id not in groups[name]["users"]:
                await event.edit(s["sgroup_user_not_in_group"], parse_mode="html")
                return
            groups[name]["users"].remove(user_id)
            await save_sgroups(groups)
            user_name = await get_user_display(user_id)
            await event.edit(
                s["sgroup_user_removed"].format(user=user_name, group=name),
                parse_mode="html",
            )
            return

        if action == "access":
            if len(args) < 3:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            name = args[2].strip()
            if name not in groups:
                await event.edit(
                    s["sgroup_not_found"].format(name=name), parse_mode="html"
                )
                return

            async def on_toggle_sg_cat(event, gname, cat_key, current_state):
                groups = await get_sgroups()
                if gname in groups:
                    groups[gname]["access"][cat_key] = not current_state
                    await save_sgroups(groups)
                access = groups[gname]["access"]
                text = _build_sgroup_access_text(gname, access)
                buttons = _build_sgroup_access_buttons(gname, access)
                await event.edit(text, buttons=buttons, parse_mode="html")

            async def on_back_sg(event, gname):
                await show_sgroup_menu(event, gname)

            async def on_allow_all_sg(event, gname):
                groups = await get_sgroups()
                if gname in groups:
                    groups[gname]["access"] = dict.fromkeys(ACCESS_CATEGORIES, True)
                    await save_sgroups(groups)
                access = groups[gname]["access"]
                text = _build_sgroup_access_text(gname, access)
                buttons = _build_sgroup_access_buttons(gname, access)
                await event.edit(text, buttons=buttons, parse_mode="html")

            async def on_deny_all_sg(event, gname):
                groups = await get_sgroups()
                if gname in groups:
                    groups[gname]["access"] = dict.fromkeys(ACCESS_CATEGORIES, False)
                    await save_sgroups(groups)
                access = groups[gname]["access"]
                text = _build_sgroup_access_text(gname, access)
                buttons = _build_sgroup_access_buttons(gname, access)
                await event.edit(text, buttons=buttons, parse_mode="html")

            TTL = 600
            access = groups[name]["access"]

            text = _build_sgroup_access_text(name, access)

            rows = []
            for row_cats in _CATEGORY_ROWS:
                row = []
                for cat_key in row_cats:
                    cat_info = ACCESS_CATEGORIES[cat_key]
                    localized = cat_info.get(language, cat_info["en"])
                    allowed = access.get(cat_key, False)
                    icon = "✅" if allowed else "🚫"
                    label = f"{icon} {localized['label']}"
                    row.append(
                        make_cb_button(
                            kernel,
                            label,
                            on_toggle_sg_cat,
                            args=[name, cat_key, allowed],
                            ttl=TTL,
                            style="success" if allowed else "danger",
                        )
                    )
                rows.append(row)

            rows.append(
                [
                    make_cb_button(
                        kernel,
                        s["btn_allow_all"],
                        on_allow_all_sg,
                        args=[name],
                        ttl=TTL,
                        style="success",
                    ),
                    make_cb_button(
                        kernel,
                        s["btn_deny_all"],
                        on_deny_all_sg,
                        args=[name],
                        ttl=TTL,
                        style="danger",
                    ),
                ]
            )

            rows.append(
                [
                    make_cb_button(
                        kernel,
                        s["percmd_back"],
                        on_back_sg,
                        args=[name],
                        ttl=TTL,
                        style="primary",
                    )
                ]
            )

            await kernel.inline_form(event.chat_id, text, buttons=rows)
            await event.delete()
            return

        if action == "list":
            if not groups:
                await event.edit(s["sgroup_list_empty"], parse_mode="html")
                return
            lines = [s["sgroup_list_title"]]
            for gname, gdata in groups.items():
                users_count = len(gdata.get("users", []))
                access_on = sum(1 for v in gdata.get("access", {}).values() if v)
                lines.append(
                    f"• <b>{gname}</b> — {users_count} users, {access_on} access"
                )
            await event.edit("\n".join(lines), parse_mode="html")
            return

        if action == "info":
            if len(args) < 3:
                await event.edit(s["sgroup_usage"], parse_mode="html")
                return
            name = args[2].strip()
            if name not in groups:
                await event.edit(
                    s["sgroup_not_found"].format(name=name), parse_mode="html"
                )
                return

            async def on_sgroup_menu(event, gname):
                await show_sgroup_menu(event, gname)

            await show_sgroup_menu(event, name)
            return

        await event.edit(s["sgroup_usage"], parse_mode="html")

    async def show_sgroup_menu(event, name: str):
        """Show inline menu for managing a security group"""
        groups = await get_sgroups()
        if name not in groups:
            await event.edit(s["sgroup_not_found"].format(name=name), parse_mode="html")
            return

        group = groups[name]
        gname = name

        async def on_add_user(event, gname):
            await event.edit(
                s["sgroup_usage"] + "\n\n" + s["sgroup_btn_add_user"], parse_mode="html"
            )

        async def on_remove_user(event, gname):
            await event.edit(
                s["sgroup_usage"] + "\n\n" + s["sgroup_btn_remove_user"],
                parse_mode="html",
            )

        async def on_access(event, gname):
            groups = await get_sgroups()
            if gname not in groups:
                return
            access = groups[gname]["access"]
            text = _build_sgroup_access_text(gname, access)
            buttons = _build_sgroup_access_buttons(gname, access)
            await event.edit(text, buttons=buttons, parse_mode="html")

        async def on_delete_group(event, gname):
            groups = await get_sgroups()
            if gname not in groups:
                return

            async def on_confirm_delete(event, gname):
                groups = await get_sgroups()
                if gname in groups:
                    del groups[gname]
                    await save_sgroups(groups)
                await event.edit(
                    s["sgroup_deleted"].format(name=gname), parse_mode="html"
                )

            async def on_cancel_delete(event, gname):
                await show_sgroup_menu(event, gname)

            TTL = 600
            text = s["sgroup_confirm_delete"].format(name=gname)
            buttons = [
                [
                    make_cb_button(
                        kernel,
                        s["btn_confirm_delete"],
                        on_confirm_delete,
                        args=[gname],
                        ttl=TTL,
                        style="danger",
                    ),
                    make_cb_button(
                        kernel,
                        s["btn_cancel"],
                        on_cancel_delete,
                        args=[gname],
                        ttl=TTL,
                        style="primary",
                    ),
                ]
            ]
            await event.edit(text, buttons=buttons, parse_mode="html")

        TTL = 600

        lines = [s["sgroup_menu_title"].format(name=name)]

        if group["users"]:
            lines.append("\n<b>Users:</b>")
            for uid in group["users"]:
                u_name = await get_user_display(uid)
                lines.append(f"• {u_name} (<code>{uid}</code>)")
        else:
            lines.append("\n<b>Users:</b> — " + s["sgroup_info_users_empty"])

        access = group.get("access", {})
        access_on = [cat for cat, val in access.items() if val]
        if access_on:
            lines.append(f"\n<b>Access:</b> {', '.join(access_on)}")
        else:
            lines.append("\n<b>Access:</b> " + s["sgroup_info_access_empty"])

        text = "\n".join(lines)

        rows = [
            [
                make_cb_button(
                    kernel,
                    s["sgroup_btn_add_user"],
                    on_add_user,
                    args=[gname],
                    ttl=TTL,
                    style="success",
                )
            ],
            [
                make_cb_button(
                    kernel,
                    s["sgroup_btn_remove_user"],
                    on_remove_user,
                    args=[gname],
                    ttl=TTL,
                    style="danger",
                )
            ],
            [
                make_cb_button(
                    kernel,
                    s["sgroup_btn_access"],
                    on_access,
                    args=[gname],
                    ttl=TTL,
                    style="primary",
                )
            ],
            [
                make_cb_button(
                    kernel,
                    s["sgroup_btn_delete"],
                    on_delete_group,
                    args=[gname],
                    ttl=TTL,
                    style="danger",
                )
            ],
        ]

        await event.edit(text, buttons=rows, parse_mode="html")

    def _build_sgroup_access_text(group_name: str, access: dict) -> str:
        lines = [f"🔐 <b>Access for group {group_name}:</b>"]
        body_lines = []
        for cat_key, cat_info in ACCESS_CATEGORIES.items():
            allowed = access.get(cat_key, False)
            icon = "✅" if allowed else "🚫"
            state_word = s["access_allowed"] if allowed else s["access_denied"]
            localized = cat_info.get(language, cat_info["en"])
            body_lines.append(
                f"{icon} {localized['label']} — <em>{state_word}</em>\n└ {localized['desc']}"
            )
        lines.append(
            "<blockquote expandable>" + "\n".join(body_lines) + "</blockquote>"
        )
        lines.append(s["trustaccess_footer"])
        return "\n".join(lines)

    def _build_sgroup_access_buttons(group_name: str, access: dict) -> list:
        async def on_toggle_sg_cat(event, gname, cat_key, current_state):
            groups = await get_sgroups()
            if gname in groups:
                groups[gname]["access"][cat_key] = not current_state
                await save_sgroups(groups)
            g_access = groups[gname]["access"]
            text = _build_sgroup_access_text(gname, g_access)
            buttons = _build_sgroup_access_buttons(gname, g_access)
            await event.edit(text, buttons=buttons, parse_mode="html")

        async def on_back_sg(event, gname):
            await show_sgroup_menu(event, gname)

        async def on_allow_all_sg(event, gname):
            groups = await get_sgroups()
            if gname in groups:
                groups[gname]["access"] = dict.fromkeys(ACCESS_CATEGORIES, True)
                await save_sgroups(groups)
            g_access = groups[gname]["access"]
            text = _build_sgroup_access_text(gname, g_access)
            buttons = _build_sgroup_access_buttons(gname, g_access)
            await event.edit(text, buttons=buttons, parse_mode="html")

        async def on_deny_all_sg(event, gname):
            groups = await get_sgroups()
            if gname in groups:
                groups[gname]["access"] = dict.fromkeys(ACCESS_CATEGORIES, False)
                await save_sgroups(groups)
            g_access = groups[gname]["access"]
            text = _build_sgroup_access_text(gname, g_access)
            buttons = _build_sgroup_access_buttons(gname, g_access)
            await event.edit(text, buttons=buttons, parse_mode="html")

        TTL = 600
        rows = []

        for row_cats in _CATEGORY_ROWS:
            row = []
            for cat_key in row_cats:
                cat_info = ACCESS_CATEGORIES[cat_key]
                localized = cat_info.get(language, cat_info["en"])
                allowed = access.get(cat_key, False)
                icon = "✅" if allowed else "🚫"
                label = f"{icon} {localized['label']}"
                row.append(
                    make_cb_button(
                        kernel,
                        label,
                        on_toggle_sg_cat,
                        args=[group_name, cat_key, allowed],
                        ttl=TTL,
                        style="success" if allowed else "danger",
                    )
                )
            rows.append(row)

        rows.append(
            [
                make_cb_button(
                    kernel,
                    s["btn_allow_all"],
                    on_allow_all_sg,
                    args=[group_name],
                    ttl=TTL,
                    style="success",
                ),
                make_cb_button(
                    kernel,
                    s["btn_deny_all"],
                    on_deny_all_sg,
                    args=[group_name],
                    ttl=TTL,
                    style="danger",
                ),
            ]
        )

        rows.append(
            [
                make_cb_button(
                    kernel,
                    s["percmd_back"],
                    on_back_sg,
                    args=[group_name],
                    ttl=TTL,
                    style="primary",
                )
            ]
        )

        return rows

    @kernel.register.on_load()
    async def inline_allow_owner(_kernel):
        trusted = await get_trusted_list()
        for uid in trusted:
            access = await get_access(uid)
            if access.get("inline", False):
                await inline_manager.allow_user(uid)
        await get_owner_username()
