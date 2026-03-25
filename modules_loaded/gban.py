# author: @Hairpin00
# version: 1.0.0
# description: Global ban — bans a user in every group where you are admin

import asyncio
import html as html_module
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.messages import DeleteChatUserRequest
from telethon.tl.types import ChatBannedRights, Channel, Chat

CUSTOM_EMOJI = {
    "🫥": '<tg-emoji emoji-id="5309893756244206277">🫥</tg-emoji>',
    "🫡": '<tg-emoji emoji-id="5382224089295365367">🫡</tg-emoji>',
    "❤️": '<tg-emoji emoji-id="5339359847529876299">❤️</tg-emoji>',
}

# How often to refresh the progress message (every N groups processed)
PROGRESS_UPDATE_EVERY = 5


def register(kernel):
    client = kernel.client
    language = kernel.config.get("language", "en")

    strings = {
        "ru": {
            "no_target":      "❌ Укажи пользователя: ответь на сообщение или передай username / ID",
            "user_not_found": "❌ Пользователь не найден",
            "scanning":       "Сканирование групп...",
            "progress":       "Глобальная блокировка... ({done}/{total})",
            "banned":         "Пользователь заблокирован",
            "banned_in":      "Заблокирован в {count} из {total} групп",
            "already_banned": "Уже заблокирован в {count} группах — пропущено",
            "no_groups":      "❌ Не найдено групп, где ты админ",
        },
        "en": {
            "no_target":      "❌ Specify a user: reply to a message or provide a username / ID",
            "user_not_found": "❌ User not found",
            "scanning":       "Scanning groups...",
            "progress":       "Global ban in progress... ({done}/{total})",
            "banned":         "User banned",
            "banned_in":      "Banned in {count} of {total} groups",
            "already_banned": "Already banned in {count} group(s) — skipped",
            "no_groups":      "❌ No groups found where you are admin",
        },
    }

    lang = strings.get(language, strings["en"])

    # Permanent ban rights (view_messages=True blocks the user completely)
    BAN_RIGHTS = ChatBannedRights(until_date=None, view_messages=True)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _user_link(user) -> str:
        name = html_module.escape(
            getattr(user, "first_name", None) or str(user.id)
        )
        return f'<a href="tg://user?id={user.id}">{name}</a>'

    async def _collect_admin_groups() -> list:
        """Return list of (entity, title) for every group/supergroup where we are admin."""
        groups = []
        async for dialog in client.iter_dialogs():
            entity = dialog.entity

            # Skip DMs and broadcast channels
            if not isinstance(entity, (Channel, Chat)):
                continue
            if isinstance(entity, Channel) and entity.broadcast:
                continue

            try:
                if isinstance(entity, Channel):
                    perms = await client.get_permissions(entity, "me")
                    if perms and perms.ban_users:
                        groups.append((entity, dialog.title))
                elif isinstance(entity, Chat):
                    # Basic group — check admin flag
                    full = await client.get_entity(entity.id)
                    if getattr(full, "admin_rights", None) or getattr(full, "creator", False):
                        groups.append((entity, dialog.title))
            except Exception:
                pass

        return groups

    async def _ban_in(entity, target) -> bool:
        """Ban target in one group. Returns True on success."""
        try:
            if isinstance(entity, Channel):
                await client(EditBannedRequest(entity, target, BAN_RIGHTS))
            else:
                # Basic Chat — only kick is possible
                await client(DeleteChatUserRequest(entity.id, target))
            return True
        except Exception:
            return False

    # ── command ──────────────────────────────────────────────────────────────

    @kernel.register.command("gban")
    async def gban_handler(event):
        args_text = event.text[len(kernel.custom_prefix) + 5 :].strip()
        reply = await event.get_reply_message()

        # ── resolve target ────────────────────────────────────────────────
        target = None
        try:
            if reply:
                target = await client.get_entity(reply.sender_id)
            elif args_text:
                ident = int(args_text) if args_text.lstrip("-").isdigit() else args_text
                target = await client.get_entity(ident)
            else:
                await event.edit(lang["no_target"], parse_mode="html")
                return
        except Exception:
            await event.edit(lang["user_not_found"], parse_mode="html")
            return

        # ── phase 1: collect groups ───────────────────────────────────────
        await event.edit(
            f'{CUSTOM_EMOJI["🫥"]} <b>{lang["scanning"]}</b>',
            parse_mode="html",
        )

        groups = await _collect_admin_groups()

        if not groups:
            await event.edit(lang["no_groups"], parse_mode="html")
            return

        total = len(groups)

        # ── phase 2: ban loop ─────────────────────────────────────────────
        banned_count = 0
        done = 0

        for entity, title in groups:
            success = await _ban_in(entity, target)
            if success:
                banned_count += 1
            done += 1

            # Refresh progress every N steps
            if done % PROGRESS_UPDATE_EVERY == 0 or done == total:
                try:
                    await event.edit(
                        f'{CUSTOM_EMOJI["🫥"]} <b>'
                        + lang["progress"].format(done=done, total=total)
                        + "</b>",
                        parse_mode="html",
                    )
                except Exception:
                    pass

            await asyncio.sleep(0.3)   # gentle flood-limit guard

        # ── phase 3: final report ─────────────────────────────────────────
        user_link = _user_link(target)

        response = (
            f'{CUSTOM_EMOJI["❤️"]} <b>{lang["banned"]}</b>: {user_link}\n\n'
            f'{CUSTOM_EMOJI["🫡"]} <b>'
            + lang["banned_in"].format(count=banned_count, total=total)
            + "</b>"
        )

        await event.edit(response, parse_mode="html")

    # ── ungban ────────────────────────────────────────────────────────────────

    UNBAN_RIGHTS = ChatBannedRights(until_date=None, view_messages=False)

    ungban_strings = {
        "ru": {
            "no_target":      "❌ Укажи пользователя: ответь на сообщение или передай username / ID",
            "user_not_found": "❌ Пользователь не найден",
            "scanning":       "Сканирование групп...",
            "progress":       "Глобальная разблокировка... ({done}/{total})",
            "unbanned":       "Пользователь разблокирован",
            "unbanned_in":    "Разблокирован в {count} из {total} групп",
            "no_groups":      "❌ Не найдено групп, где ты админ",
        },
        "en": {
            "no_target":      "❌ Specify a user: reply to a message or provide a username / ID",
            "user_not_found": "❌ User not found",
            "scanning":       "Scanning groups...",
            "progress":       "Global unban in progress... ({done}/{total})",
            "unbanned":       "User unbanned",
            "unbanned_in":    "Unbanned in {count} of {total} groups",
            "no_groups":      "❌ No groups found where you are admin",
        },
    }

    ulang = ungban_strings.get(language, ungban_strings["en"])

    @kernel.register.command("ungban")
    async def ungban_handler(event):
        args_text = event.text[len(kernel.custom_prefix) + 7 :].strip()
        reply = await event.get_reply_message()

        target = None
        try:
            if reply:
                target = await client.get_entity(reply.sender_id)
            elif args_text:
                ident = int(args_text) if args_text.lstrip("-").isdigit() else args_text
                target = await client.get_entity(ident)
            else:
                await event.edit(ulang["no_target"], parse_mode="html")
                return
        except Exception:
            await event.edit(ulang["user_not_found"], parse_mode="html")
            return

        await event.edit(
            f'{CUSTOM_EMOJI["🫥"]} <b>{ulang["scanning"]}</b>',
            parse_mode="html",
        )

        groups = await _collect_admin_groups()

        if not groups:
            await event.edit(ulang["no_groups"], parse_mode="html")
            return

        total = len(groups)
        unbanned_count = 0
        done = 0

        for entity, title in groups:
            try:
                if isinstance(entity, Channel):
                    await client(EditBannedRequest(entity, target, UNBAN_RIGHTS))
                    unbanned_count += 1
            except Exception:
                pass

            done += 1

            if done % PROGRESS_UPDATE_EVERY == 0 or done == total:
                try:
                    await event.edit(
                        f'{CUSTOM_EMOJI["🫥"]} <b>'
                        + ulang["progress"].format(done=done, total=total)
                        + "</b>",
                        parse_mode="html",
                    )
                except Exception:
                    pass

            await asyncio.sleep(0.3)

        user_link = _user_link(target)

        response = (
            f'{CUSTOM_EMOJI["❤️"]} <b>{ulang["unbanned"]}</b>: {user_link}\n\n'
            f'{CUSTOM_EMOJI["🫡"]} <b>'
            + ulang["unbanned_in"].format(count=unbanned_count, total=total)
            + "</b>"
        )

        await event.edit(response, parse_mode="html")