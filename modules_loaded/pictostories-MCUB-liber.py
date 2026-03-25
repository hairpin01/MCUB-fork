# =======================================
#   _  __         __  __           _
#  | |/ /___     |  \/  | ___   __| |___
#  | ' // _ \    | |\/| |/ _ \ / _` / __|
#  | . \  __/    | |  | | (_) | (_| \__ \
#  |_|\_\___|    |_|  |_|\___/ \__,_|___/
#           @ke_mods
# =======================================
#
#  LICENSE: CC BY-ND 4.0 (Attribution-NoDerivatives 4.0 International)
#  --------------------------------------
#  https://creativecommons.org/licenses/by-nd/4.0/legalcode
# =======================================

# meta developer: @ke_mods
# requires: pillow
# version: 1.0.0
# author: @ke_mods
# description: Grid 3x3 for stories

import io
from PIL import Image
from telethon import functions, types


def register(kernel):
    strings = {
        "ru": {
            "no_rep": "❗️ Реплай на фото!",
            "work": "🕔 Обрабатываю...",
            "done": "✅ Готово! Проверяй профиль.",
            "err": "❌ Ошибка: {}",
        },
        "en": {
            "no_rep": "❗️ Reply to photo!",
            "work": "🕔 Processing...",
            "done": "✅ Done! Check your profile.",
            "err": "❌ Error: {}",
        },
    }

    @kernel.register_command("pts")
    # <reply to photo> - make 3x3 grid
    async def pts_cmd(event):
        lang = kernel.config.get("language", "ru")
        t = strings.get(lang, strings["ru"])

        reply = await event.get_reply_message()
        if not reply or not reply.media:
            await event.edit(t["no_rep"])
            return

        try:
            photo_bytes = await reply.download_media(bytes)
            img = Image.open(io.BytesIO(photo_bytes))
        except Exception as e:
            await event.edit(t["err"].format(str(e)))
            return

        await event.edit(t["work"])

        w, h = img.size

        if abs(w / h - 0.8) > 0.05:
            img = img.resize((w, int(w * 1.25)), Image.LANCZOS)
            w, h = img.size

        parts = []
        pw, ph = w // 3, h // 3

        for r in range(3):
            for c in range(3):
                x, y = c * pw, r * ph
                parts.append(img.crop((x, y, x + pw, y + ph)))

        parts.reverse()

        for part in parts:
            out = io.BytesIO()
            part.save(out, "JPEG")
            out.seek(0)

            uploaded_file = await kernel.client.upload_file(out, file_name="s.jpg")

            result = await kernel.client(
                functions.stories.SendStoryRequest(
                    peer=types.InputPeerSelf(),
                    media=types.InputMediaUploadedPhoto(uploaded_file),
                    privacy_rules=[types.InputPrivacyValueAllowAll()],
                )
            )

            try:
                story_id = None
                for update in result.updates:
                    if hasattr(update, "story_id"):
                        story_id = update.story_id
                    elif hasattr(update, "id"):
                        story_id = update.id
                    if story_id:
                        break

                if story_id:
                    await kernel.client(
                        functions.stories.TogglePinnedRequest(
                            peer=types.InputPeerSelf(), id=[story_id], pinned=True
                        )
                    )
            except Exception:
                pass

        await event.edit(t["done"])
