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
            for i, (wrapper, event_obj, _) in enumerate(watchers, 1):
                func_name = getattr(wrapper, "__name__", str(wrapper))
                module_name = getattr(wrapper, "__module__", "unknown")

                direction = ""
                if getattr(event_obj, "incoming", False):
                    direction = " [in]"
                elif getattr(event_obj, "out", False):
                    direction = " [out]"

                lines.append(
                    f"<code>{i}.</code> <b>{func_name}</b>{direction} — <i>{module_name}</i>"
                )

            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")

        except Exception as e:
            await kernel.handle_error(e, source="watchers", event=event)

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
