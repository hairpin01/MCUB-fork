from __future__ import annotations

# author: @Hairpin01
# version: 1.3.0-beta
# description: Trusted users can execute owner commands


import json
from telethon import Button
from core_inline.lib.manager import InlineManager
from core_inline.api.inline import make_cb_button

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
            "nonickuser",
            "nonickusers",
            "addowner",
            "delowner",
            "listowner",
        ],
    },
    "system": {
        "en": {"label": "System", "desc": "update, restart and system maintenance"},
        "ru": {"label": "Система", "desc": "update, restart и системное обслуживание"},
        "commands": ["restart", "update", "stop", "rollback"],
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

    strings = {
        "en": {
            "not_owner": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Only the owner can use this command.',
            "usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Usage: <code>.trust</code> / <code>.untrust</code> (reply, @username or ID)',
            "trust_added": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>User added to trusted list.</b>',
            "trust_added_full": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>User added to trusted list.</b>',
            "trust_removed": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>User removed from trusted list.</b>',
            "trust_already": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> <i>User is already trusted.</i>',
            "trust_not_in_list": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> User is not in trusted list.',
            "trustlist_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Trusted list is empty.',
            "trustlist_title": '<tg-emoji emoji-id="5332771595331077100">💙</tg-emoji> <b>Trusted users:</b>',
            "confirm_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Add user to trusted?</b>',
            "confirm_user_line": "👤 <b>User:</b> {name} (<code>{uid}</code>)",
            "confirm_warning": '<tg-emoji emoji-id="5116275208906343429">‼️</tg-emoji> <b>Warning:</b> The user will gain access to <b>all owner commands</b> of the userbot!',
            "btn_confirm": "Confirm",
            "btn_cancel": "Cancel",
            "confirm_cancelled": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Cancelled.',
            "nonick_step_title": '<tg-emoji emoji-id="5332723564711804828">✨</tg-emoji> <b>Enable NoNick for {name}?</b>',
            "nonick_step_desc": (
                "With <b>NoNick</b> enabled, the user will be able to execute commands simply like"
                " <code>{prefix}command</code>."
            ),
            "nonick_step_desc_no_alias": (
                "With <b>NoNick</b> enabled the user can run commands without any suffix.\n"
                "Without it they must include the owner's <code>@username</code> suffix."
            ),
            "btn_nonick_yes": "Enable NoNick",
            "btn_nonick_no": "No NoNick",
            "nonick_toggled_on": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> NoNick <b>enabled</b> for {name}.',
            "nonick_toggled_off": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> NoNick <b>disabled</b> for {name}.',
            "nonick_not_trusted": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> User is not in the trusted list.',
            "nonick_list_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> No trusted users with NoNick.',
            "nonick_list_title": '<tg-emoji emoji-id="5332771595331077100">💙</tg-emoji> <b>Trusted users with NoNick:</b>',
            "nonick_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Usage: <code>.nonickuser</code> (reply, @username or ID)',
            "watchers_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Active watchers:</b>',
            "watchers_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> No active watchers.',
            "watchers_debug_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Watchers debug:</b>',
            "watchers_debug_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> No watchers matched.',
            "watcher_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Usage: <code>.watcher module watcher</code>',
            "watcher_disabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher disabled:</b> <code>{module}.{watcher}</code>',
            "watcher_enabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher enabled:</b> <code>{module}.{watcher}</code>',
            "watcher_not_found": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Watcher not found: <code>{module}.{watcher}</code>',
            "trustaccess_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Usage: <code>.trustaccess</code> (reply or @username or ID)',
            "trustaccess_not_trusted": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> User is not in the trusted list.',
            "trustaccess_footer": "<em>If access is off, the bot will simply ignore the corresponding commands.</em>",
            "trustaccess_title": "🔐 <b>Owner access for {user}</b>",
            "btn_close": "🙈 Close this menu",
            "btn_allow_all": "Allow all",
            "btn_deny_all": "Deny all",
            "btn_basic": "Basic set",
            "access_allowed": "allowed",
            "access_denied": "denied",
        },
        "ru": {
            "not_owner": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Только владелец может использовать эту команду.',
            "usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Использование: <code>.trust</code> / <code>.untrust</code> (реплай, @username или ID)',
            "trust_added": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Пользователь добавлен в список доверенных.</b>',
            "trust_added_full": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Пользователь добавлен в список доверенных.</b>',
            "trust_removed": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Пользователь удалён из списка доверенных.</b>',
            "trust_already": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> <i>Пользователь уже в списке доверенных.</i>',
            "trust_not_in_list": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Пользователь не в списке доверенных.',
            "trustlist_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Список доверенных пуст.',
            "trustlist_title": '<tg-emoji emoji-id="5332771595331077100">💙</tg-emoji> <b>Доверенные пользователи:</b>',
            "confirm_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Добавить пользователя в доверенные?</b>',
            "confirm_user_line": "👤 <b>Пользователь:</b> {name} (<code>{uid}</code>)",
            "confirm_warning": '<tg-emoji emoji-id="5116275208906343429">‼️</tg-emoji> <b>Внимание:</b> Пользователь получит доступ ко <b>всем командам владельца</b> юзербота!',
            "btn_confirm": "Подтвердить",
            "btn_cancel": "Отмена",
            "confirm_cancelled": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Отменено.',
            "nonick_step_title": '<tg-emoji emoji-id="5332723564711804828">✨</tg-emoji> <b>Включить NoNick для {name}?</b>',
            "nonick_step_desc": (
                "При включённом <b>NoNick</b> пользователь сможет выполнять команды просто как "
                "<code>{prefix}команда</code>.\n"
                "Без него нужно писать <code>{prefix}команда@{alias}</code>."
            ),
            "nonick_step_desc_no_alias": (
                "При включённом <b>NoNick</b> пользователь сможет выполнять команды без суффикса.\n"
                "Без него нужно указывать <code>@username</code> владельца."
            ),
            "btn_nonick_yes": "Включить NoNick",
            "btn_nonick_no": "Без NoNick",
            "nonick_toggled_on": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> NoNick <b>включён</b> для {name}.',
            "nonick_toggled_off": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> NoNick <b>выключен</b> для {name}.',
            "nonick_not_trusted": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Пользователь не в списке доверенных.',
            "nonick_list_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Нет доверенных пользователей с NoNick.',
            "nonick_list_title": '<tg-emoji emoji-id="5332771595331077100">💙</tg-emoji> <b>Доверенные пользователи с NoNick:</b>',
            "nonick_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Использование: <code>.nonickuser</code> (реплай, @username или ID)',
            "watchers_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Активные смотрители:</b>',
            "watchers_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Активных смотрителей нет.',
            "watchers_debug_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Отладка watchers:</b>',
            "watchers_debug_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Подходящих watchers нет.',
            "watcher_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Использование: <code>.watcher модуль watcher</code>',
            "watcher_disabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher отключен:</b> <code>{module}.{watcher}</code>',
            "watcher_enabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher включен:</b> <code>{module}.{watcher}</code>',
            "watcher_not_found": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Watcher не найден: <code>{module}.{watcher}</code>',
            "trustaccess_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Использование: <code>.trustaccess</code> (реплай, @username или ID)',
            "trustaccess_not_trusted": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Пользователь не в списке доверенных.',
            "trustaccess_footer": "<em>Если доступ выключен, бот просто проигнорирует соответствующие команды.</em>",
            "trustaccess_title": "🔐 <b>Доступ owner для {user}</b>",
            "btn_close": "🙈 Закрыть это меню",
            "btn_allow_all": "Разрешить всё",
            "btn_deny_all": "Запретить всё",
            "btn_basic": "Базовый набор",
            "access_allowed": "разрешено",
            "access_denied": "запрещено",
        },
    }

    s = strings.get(language, strings["en"])

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

    async def get_access(user_id: int) -> dict:
        """Return per-user access dict. Defaults: all False."""
        data = await kernel.db_get("trusted_access", str(user_id))
        if not data:
            return {cat: False for cat in ACCESS_CATEGORIES}
        try:
            stored = (
                json.loads(data) if isinstance(data, str) else json.loads(str(data))
            )
            # Fill any missing keys with False
            return {cat: stored.get(cat, False) for cat in ACCESS_CATEGORIES}
        except Exception:
            return {cat: False for cat in ACCESS_CATEGORIES}

    async def save_access(user_id: int, access: dict):
        await kernel.db_set("trusted_access", str(user_id), json.dumps(access))

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
            target = args[1].strip()
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

    def _build_access_text(user_display: str, access: dict) -> str:
        lines = [s["trustaccess_title"].format(user=user_display)]
        body_lines = []
        for cat_key, cat_info in ACCESS_CATEGORIES.items():
            allowed = access.get(cat_key, False)
            icon = "✅" if allowed else "🚫"
            state_word = s["access_allowed"] if allowed else s["access_denied"]
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

    def _build_access_buttons(kernel, user_id: int, access: dict, msg_ref) -> list:
        """Build inline button rows using make_cb_button for temporary callbacks."""

        async def on_toggle(event, uid, cat_key):
            cur = await get_access(uid)
            cur[cat_key] = not cur.get(cat_key, False)
            await save_access(uid, cur)
            name = await get_user_display(uid)
            new_text = _build_access_text(name, cur)
            new_buttons = _build_access_buttons(kernel, uid, cur, None)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_preset(event, uid, preset_key):
            preset = PRESETS[preset_key]
            await save_access(uid, dict(preset["access"]))
            name = await get_user_display(uid)
            new_access = dict(preset["access"])
            new_text = _build_access_text(name, new_access)
            new_buttons = _build_access_buttons(kernel, uid, new_access, None)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_allow_all(event, uid):
            full = {cat: True for cat in ACCESS_CATEGORIES}
            await save_access(uid, full)
            name = await get_user_display(uid)
            new_text = _build_access_text(name, full)
            new_buttons = _build_access_buttons(kernel, uid, full, None)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_deny_all(event, uid):
            none_ = {cat: False for cat in ACCESS_CATEGORIES}
            await save_access(uid, none_)
            name = await get_user_display(uid)
            new_text = _build_access_text(name, none_)
            new_buttons = _build_access_buttons(kernel, uid, none_, None)
            try:
                await event.edit(new_text, buttons=new_buttons, parse_mode="html")
            except Exception:
                pass

        async def on_close(event, uid):
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
                icon = "✅" if allowed else "🚫"
                label = f"{icon} {localized['label']}"
                row.append(
                    make_cb_button(
                        kernel,
                        label,
                        on_toggle,
                        args=[user_id, cat_key],
                        ttl=TTL,
                        style="success" if allowed else "danger",
                    )
                )
            rows.append(row)

        # Preset: Базовый набор — shows sub-row of preset buttons
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

    @kernel.register.command("trustaccess")
    @kernel.register.owner(only_admin=True)
    async def trustaccess_handler(event):
        """Manage trusted user's access permissions"""
        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["trustaccess_usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id not in trusted:
            await event.edit(s["trustaccess_not_trusted"], parse_mode="html")
            return

        access = await get_access(user_id)
        name = await get_user_display(user_id)
        text = _build_access_text(name, access)
        buttons = _build_access_buttons(kernel, user_id, access, None)

        await kernel.inline_form(event.chat_id, text, buttons=buttons, ttl=600)
        await event.delete()

    @kernel.register.command("trust", alias=["addowner"])
    @kernel.register.owner(only_admin=True)
    async def trust_handler(event):
        """Add a user to the trusted list with confirmation"""

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(s["usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id in trusted:
            await event.edit(s["trust_already"], parse_mode="html")
            return

        name = await get_user_display(user_id)

        text = (
            s["confirm_title"]
            + "\n"
            + "<blockquote>"
            + s["confirm_warning"]
            + "</blockquote>"
        )
        buttons = [
            [
                Button.inline(
                    s["btn_confirm"],
                    f"trust_confirm_{user_id}".encode(),
                    style="success",
                ),
                Button.inline(s["btn_cancel"], b"trust_cancel", style="primary"),
            ]
        ]
        await kernel.inline_form(event.chat_id, text, buttons=buttons)

    async def trust_callback(event):
        """Handle trust confirmation callbacks (confirm, cancel, nonick toggle)"""
        if event.sender_id != kernel.ADMIN_ID:
            return await event.answer("only not owner click to buttons")

        data = event.data.decode("utf-8")

        if data == "trust_cancel":
            await event.edit(s["confirm_cancelled"], parse_mode="html")
            return

        if data.startswith("trust_confirm_"):
            user_id = int(data[len("trust_confirm_") :])
            name = await get_user_display(user_id)
            owner_uname = await get_owner_username()

            if owner_uname:
                desc = s["nonick_step_desc"].format(
                    prefix=kernel.custom_prefix,
                    alias=owner_uname,
                )
            else:
                desc = s["nonick_step_desc_no_alias"]

            text = (
                s["nonick_step_title"].format(name=name)
                + "\n"
                + "<blockquote>"
                + desc
                + "</blockquote>"
            )
            buttons = [
                [
                    Button.inline(
                        s["btn_nonick_yes"],
                        f"trust_nonick_yes_{user_id}".encode(),
                        style="success",
                    ),
                    Button.inline(
                        s["btn_nonick_no"],
                        f"trust_nonick_no_{user_id}".encode(),
                        style="danger",
                    ),
                ]
            ]
            await event.edit(text, buttons=buttons, parse_mode="html")
            return

        for prefix, nonick in (
            ("trust_nonick_yes_", True),
            ("trust_nonick_no_", False),
        ):
            if data.startswith(prefix):
                user_id = int(data[len(prefix) :])

                trusted = await get_trusted_list()
                if user_id not in trusted:
                    trusted.append(user_id)
                    await save_trusted_list(trusted)
                    await inline_manager.allow_user(user_id)
                    default_access = {
                        cat: (cat == "modules") for cat in ACCESS_CATEGORIES
                    }
                    await save_access(user_id, default_access)

                nonick_list = await get_nonick_list()
                if nonick and user_id not in nonick_list:
                    nonick_list.append(user_id)
                    await save_nonick_list(nonick_list)
                elif not nonick and user_id in nonick_list:
                    nonick_list.remove(user_id)
                    await save_nonick_list(nonick_list)

                await event.edit(
                    s["trust_added_full"],
                    parse_mode="html",
                )
                return

    kernel.register_callback_handler("trust_", trust_callback)

    @kernel.register.command("untrust", alias=["delowner"])
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

    @kernel.register.command("trustlist", alias=["listowner"])
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

    @kernel.register.command("nonickuser")
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
            await event.edit(s["nonick_not_trusted"], parse_mode="html")
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

    @kernel.register.command("nonickusers")
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

    @kernel.register.command("watchers")
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

    @kernel.register.command("watchersdebug")
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

    @kernel.register.command("watcher")
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
        if not access.get(category, False):
            # Silently ignore — user has no access to this category
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
            _kernel.callback_permissions.allow(uid, "", duration_seconds=60)

    @kernel.register.on_load()
    async def inline_allow_owner(_kernel):
        trusted = await get_trusted_list()
        for uid in trusted:
            await inline_manager.allow_user(uid)
        await get_owner_username()
