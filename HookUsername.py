# requires: aiohttp
# author: @neistv
# version: 1.0.0
# description: Hook username module
# banner_url: https://github.com/neistv/mods/raw/main/assets/HookUsername.png

import io
import re
import logging
import aiohttp
from telethon import Button
from telethon.tl import functions
from telethon.tl.types import InputChatUploadedPhoto
from utils import get_args_raw, escape_html

logging.basicConfig(level=logging.INFO)


def register(kernel):
    MODULE_NAME = "HookUsername"

    @kernel.register.on_install()
    async def init_config(k):
        config = await k.get_module_config(MODULE_NAME)
        if not config:
            await k.save_module_config(
                MODULE_NAME,
                {
                    "channel_title": "Этот юзернейм зарезервирован.",
                    "channel_about": "",
                    "channel_avatar_url": "https://raw.githubusercontent.com/neistv/mods/main/assets/rezerv.png",
                },
            )

    async def check_username(username: str) -> bool:
        try:
            return await kernel.client(
                functions.account.CheckUsernameRequest(username=username)
            )
        except Exception as e:
            kernel.logger.error(f"Ошибка при проверке юзернейма {username}: {e}")
            return False

    async def grab_username(username: str) -> tuple[bool, str]:
        config = await kernel.get_module_config(MODULE_NAME)
        channel_title = config.get("channel_title", "Этот юзернейм зарезервирован.")
        channel_about = config.get("channel_about", "")
        channel_avatar_url = config.get("channel_avatar_url", "")

        try:

            result = await kernel.client(
                functions.channels.CreateChannelRequest(
                    title=channel_title,
                    about=channel_about,
                    megagroup=False,
                )
            )
            channel = result.chats[0]

            await kernel.client(
                functions.channels.UpdateUsernameRequest(
                    channel=channel,
                    username=username,
                )
            )

            avatar_url = channel_avatar_url.strip()
            if avatar_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            avatar_url, allow_redirects=True
                        ) as resp:
                            img_bytes = await resp.read()
                    buf = io.BytesIO(img_bytes)
                    buf.name = "avatar.png"
                    uploaded = await kernel.client.upload_file(buf)
                    await kernel.client(
                        functions.channels.EditPhotoRequest(
                            channel=channel,
                            photo=InputChatUploadedPhoto(file=uploaded),
                        )
                    )
                    # Удаляем служебные сообщения о создании канала
                    async for msg in kernel.client.iter_messages(channel, limit=10):
                        if msg.action:
                            await msg.delete()
                except Exception as e:
                    kernel.logger.warning(f"Ошибка загрузки аватарки: {e}")

            return True, f"t.me/{username}"
        except Exception as e:
            kernel.logger.exception(f"Ошибка при захвате {username}: {e}")
            return False, str(e)

    @kernel.register.command("uz")
    async def uz_command(event):
        """Команда .uz <username>"""
        args = get_args_raw(event).strip().lstrip("@")
        if not args:
            await event.edit("<b>Укажи юзернейм!!</b>", parse_mode="html")
            return

        if re.search(r"[а-яА-ЯёЁ]", args):
            await event.edit(
                "<b><tg-emoji emoji-id=5220197908342648622>❗️</tg-emoji>"
                " В юзернейме не может быть русских букв!!</b>",
                parse_mode="html",
            )
            return

        available = await check_username(args)

        if available:
            buttons = [
                [
                    {"text": "✔ занять", "type": "callback", "data": f"grab:{args}"},
                    {"text": "✖", "type": "callback", "data": "close"},
                ]
            ]
            success, msg = await kernel.inline_form(
                event.chat_id,
                title=(
                    f"Юзак <b>@{escape_html(args)}</b> — свободен!!!\n\n"
                    f"Хочешь занять этот юзернейм?"
                ),
                buttons=buttons,
            )
            if not success:
                await event.edit("Не удалось отправить форму.")
        else:
            await kernel.inline_form(
                event.chat_id,
                title=(
                    f"<tg-emoji emoji-id='5220197908342648622'>❗️</tg-emoji> "
                    f"<b>@{escape_html(args)}</b> — занят."
                ),
                buttons=[[{"text": "✖ закрыть", "type": "callback", "data": "close"}]],
            )

    @kernel.register.event("callbackquery", bot_client=True, pattern=b"(grab:|close)")
    async def handle_callback(event):
        data = event.data.decode("utf-8")
        if data.startswith("grab:"):
            username = data.split(":", 1)[1]
            await event.answer("Захватываю...", alert=False)
            success, info = await grab_username(username)
            if success:
                await event.edit(
                    f"<tg-emoji emoji-id='5219901967916084166'>💥</tg-emoji> "
                    f"<b>@{escape_html(username)}</b> успешно занят!\n\n"
                    f"Канал: {escape_html(info)}",
                    parse_mode="html",
                    buttons=[[Button.inline("✖ закрыть", b"close")]],
                )
            else:
                await event.edit(
                    f"<tg-emoji emoji-id='5220197908342648622'>❗️</tg-emoji> "
                    f"<b>Ошибка:</b>\n<code>{escape_html(info)}</code>",
                    parse_mode="html",
                    buttons=[[Button.inline("✖ закрыть", b"close")]],
                )
        elif data == "close":
            await kernel.client.delete_messages(event.chat_id, [event.message_id])
