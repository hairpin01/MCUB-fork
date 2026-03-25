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
# github repo (MCUB): https://github.com/hairpin01/repo-MCUB-fork
# source modules (original): https://raw.githubusercontent.com/radiocycle/Modules/refs/heads/master/randomanimepic.py
# Port Autor Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires:
# author: @ke_mods && port: @Hairpin00
# version: 1.4.0
# description: anime pic
# ----------------------- End ------------------------------

import asyncio
import aiohttp


def register(kernel):
    @kernel.register_command("rapic")
    # random anime pic
    async def random_anime_pic_cmd(event):
        strings = {
            "ru": {
                "img": "✅ Ваша аниме-картинка\n🔗 Ссылка: {}",
                "loading": "✨ Загрузка изображения...",
                "error": "🚫 Произошла непредвиденная ошибка...",
            },
            "en": {
                "img": "✅ Your anime pic\n🔗 URL: {}",
                "loading": "✨ Loading image...",
                "error": "🚫 An unexpected error occurred...",
            },
        }

        lang = kernel.config.get("language", "ru")
        current_strings = strings.get(lang, strings["ru"])

        loading_msg = await event.edit(current_strings["loading"])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.nekosia.cat/api/v1/images/cute?count=1"
                ) as res:
                    res.raise_for_status()
                    data = await res.json()
                    image_url = data["image"]["original"]["url"]

            await loading_msg.delete()

            await kernel.client.send_file(
                event.chat_id,
                file=image_url,
                caption=current_strings["img"].format(image_url),
                reply_to=event.reply_to_msg_id,
            )

        except Exception as e:
            await loading_msg.edit(current_strings["error"])
            await kernel.handle_error(e, source="rapic_cmd", event=event)
            await asyncio.sleep(5)
