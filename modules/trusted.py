# author: @Hairpin01
# version: 1.1.0-beta
# description: Trusted users can execute owner commands

import json
from core_inline.lib.manager import InlineManager


def register(kernel):
    client = kernel.client
    language = kernel.config.get("language", "en")
    inline_manager = InlineManager(kernel)

    strings = {
        "en": {
            "not_owner": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Only the owner can use this command.',
            "trust_added": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>User added to trusted list.</b>',
            "trust_removed": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>User removed from trusted list.</b>',
            "trust_already": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> <i>User is already trusted.</i>',
            "trust_not_in_list": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> User is not in trusted list.',
            "trustlist_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Trusted list is empty.',
            "trustlist_title": '<tg-emoji emoji-id="5332771595331077100">💙</tg-emoji> Trusted users:',
            "usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Usage: <code>.trust</code> / <code>.untrust</code> (reply or @username)',
            "watchers_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Active watchers:</b>',
            "watchers_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> No active watchers.',
            "watchers_debug_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Watchers debug:</b>',
            "watchers_debug_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> No watchers matched.',
            "watcher_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Usage: <code>.watcher module watcher</code>',
            "watcher_disabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher disabled:</b> <code>{module}.{watcher}</code>',
            "watcher_enabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher enabled:</b> <code>{module}.{watcher}</code>',
            "watcher_not_found": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Watcher not found: <code>{module}.{watcher}</code>',
        },
        "ru": {
            "not_owner": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Только владелец может использовать эту команду.',
            "trust_added": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Пользователь добавлен в список доверенных.</b>',
            "trust_removed": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Пользователь удалён из списка доверенных.</b>',
            "trust_already": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> <i>Пользователь уже в списке доверенных.</i>',
            "trust_not_in_list": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Пользователь не в списке доверенных.',
            "trustlist_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Список доверенных пуст.',
            "trustlist_title": '<tg-emoji emoji-id="5332771595331077100">💙</tg-emoji> Доверенные пользователи:',
            "usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Использование: <code>.trust</code> / <code>.untrust</code> (реплай или @username)',
            "watchers_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Активные смотрители:</b>',
            "watchers_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Активных смотрителей нет.',
            "watchers_debug_title": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> <b>Отладка watchers:</b>',
            "watchers_debug_empty": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Подходящих watchers нет.',
            "watcher_usage": '<tg-emoji emoji-id="5409117246062625941">⚙️</tg-emoji> Использование: <code>.watcher модуль watcher</code>',
            "watcher_disabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher отключен:</b> <code>{module}.{watcher}</code>',
            "watcher_enabled": '<tg-emoji emoji-id="5330561907671727296">✅</tg-emoji> <b>Watcher включен:</b> <code>{module}.{watcher}</code>',
            "watcher_not_found": '<tg-emoji emoji-id="5408830797513784663">🚫</tg-emoji> Watcher не найден: <code>{module}.{watcher}</code>',
        },
    }

    lang_strings = strings.get(language, strings["en"])

    async def get_user_id(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply:
                return reply.sender_id
        args = event.text.split(maxsplit=1)
        if len(args) > 1:
            username = args[1].lstrip("@")
            try:
                entity = await client.get_entity(username)
                return entity.id
            except Exception:
                pass
        return None

    async def get_trusted_list():
        data = await kernel.db_get("trusted", "users")
        if not data:
            return []
        try:
            if isinstance(data, str):
                return json.loads(data)
            return json.loads(str(data))
        except Exception:
            return []

    async def save_trusted_list(users):
        await kernel.db_set("trusted", "users", json.dumps(users))

    @kernel.register.command("trust", alias=["addowner"])
    # add trust users
    async def trust_handler(event):
        if event.sender_id != kernel.ADMIN_ID:
            await event.edit(lang_strings["not_owner"], parse_mode="html")
            return

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(lang_strings["usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id in trusted:
            await event.edit(lang_strings["trust_already"], parse_mode="html")
            return

        trusted.append(user_id)
        await save_trusted_list(trusted)
        await inline_manager.allow_user(user_id)
        await event.edit(lang_strings["trust_added"], parse_mode="html")

    @kernel.register.command("untrust", alias=["delowner"])
    # delete trust users
    async def untrust_handler(event):
        if event.sender_id != kernel.ADMIN_ID:
            await event.edit(lang_strings["not_owner"], parse_mode="html")
            return

        user_id = await get_user_id(event)
        if not user_id:
            await event.edit(lang_strings["usage"], parse_mode="html")
            return

        trusted = await get_trusted_list()
        if user_id not in trusted:
            await event.edit(lang_strings["trust_not_in_list"], parse_mode="html")
            return

        trusted.remove(user_id)
        await save_trusted_list(trusted)
        await inline_manager.deny_user(user_id)
        kernel.callback_permissions.prohibit(user_id)
        await event.edit(lang_strings["trust_removed"], parse_mode="html")

    @kernel.register.command("trustlist", alias=["listowner"])
    # list trust users
    async def trustlist_handler(event):
        trusted = await get_trusted_list()
        if not trusted:
            await event.edit(lang_strings["trustlist_empty"], parse_mode="html")
            return

        lines = [lang_strings["trustlist_title"]]
        for uid in trusted:
            try:
                user = await client.get_entity(uid)
                name = (
                    f"@{user.username}"
                    if hasattr(user, "username") and user.username
                    else user.first_name or str(uid)
                )
                lines.append(f"• {name} (<code>{uid}</code>)")
            except Exception:
                lines.append(f"• <code>{uid}</code>")

        await event.edit("\n".join(lines), parse_mode="html")

    @kernel.register.command("watchers")
    # list watchers
    async def watchers_handler(event):
        try:
            watchers = kernel.register.get_watchers()

            if not watchers:
                await event.edit(lang_strings["watchers_empty"], parse_mode="html")
                return

            lines = [lang_strings["watchers_title"] + "<blockquote expandable>"]
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
        try:
            args = event.text.split(maxsplit=1)
            filter_text = args[1].lower() if len(args) > 1 else ""
            watchers = kernel.register.get_watchers()
            builder_snapshot = []
            if hasattr(kernel, "_debug_event_builders_snapshot"):
                builder_snapshot = kernel._debug_event_builders_snapshot()

            lines = [lang_strings["watchers_debug_title"] + "<blockquote expandable>"]
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
                await event.edit(
                    lang_strings["watchers_debug_empty"], parse_mode="html"
                )
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
        if event.sender_id != kernel.ADMIN_ID:
            await event.edit(lang_strings["not_owner"], parse_mode="html")
            return

        args = event.text.split(maxsplit=2)
        if len(args) < 3:
            await event.edit(lang_strings["watcher_usage"], parse_mode="html")
            return

        module_name = args[1]
        watcher_name = args[2]
        watchers = kernel.register.get_watchers()
        watcher_info = next(
            (
                watcher
                for watcher in watchers
                if watcher["module"] == module_name
                and watcher["method"] == watcher_name
            ),
            None,
        )

        if watcher_info is None:
            await event.edit(
                lang_strings["watcher_not_found"].format(
                    module=module_name, watcher=watcher_name
                ),
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
                lang_strings["watcher_not_found"].format(
                    module=module_name, watcher=watcher_name
                ),
                parse_mode="html",
            )
            return

        await event.edit(
            lang_strings[key].format(module=module_name, watcher=watcher_name),
            parse_mode="html",
        )

    @kernel.register.command("watcher")
    async def watcher_toggle_handler(event):
        await toggle_watcher_handler(event)

    @kernel.register.watcher(out=False, incoming=True)
    async def trusted_watcher(event):
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

        cmd_name = (
            text[len(kernel.custom_prefix) :].split()[0]
            if len(text) > len(kernel.custom_prefix)
            else ""
        )

        if cmd_name not in kernel.command_handlers:
            return

        cmd = await kernel.client.send_message(
            event.chat_id, text, reply_to=event.reply_to_msg_id
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
