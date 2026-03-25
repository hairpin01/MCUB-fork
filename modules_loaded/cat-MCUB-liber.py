# github: https://github.com/hairpin01/repo-MCUB-fork/liber/
# Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires: aiohttp
# author: @Hairpin00
# version: 1.0.0
# description: ru: Случайное фото кота / en: Random cat photo
# ----------------------- End ------------------------------
import aiohttp


def register(kernel):
    language = kernel.config.get("language", "ru")

    # strings ru/en
    strings = {
        "ru": {
            "searching": "<tg-emoji emoji-id='5339287777978643630'>🐱</tg-emoji> Ищем котика...",
            "api_error": "<tg-emoji emoji-id='5121063440311386962'>😿</tg-emoji> Ошибка API",
            "error_caption": "<tg-emoji emoji-id='5121063440311386962'>😿</tg-emoji> Ошибка",
            "full_logs": "Полные логи",
            "photo_caption": "<tg-emoji emoji-id='5337019352346553898'>🐱</tg-emoji>",
        },
        "en": {
            "searching": "<tg-emoji emoji-id='5339287777978643630'>🐱</tg-emoji> Looking for a cat...",
            "api_error": "<tg-emoji emoji-id='5121063440311386962'>😿</tg-emoji> API error",
            "error_caption": '<tg-emoji emoji-id="5121063440311386962">😿</tg-emoji> Error',
            "full_logs": "Full logs:",
            "photo_caption": '<tg-emoji emoji-id="5337019352346553898">🐱</tg-emoji>',
        },
    }
    lang_strings = strings.get(language, strings["ru"])

    @kernel.register.command("cat")
    # ru: отправить котика / en: send random cat
    async def cat_handler(event):
        try:

            msg = await event.edit(lang_strings["searching"], parse_mode="html")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.thecatapi.com/v1/images/search"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_url = data[0]["url"]

                        # delete
                        await event.delete()
                        await kernel.client.send_file(
                            event.chat_id,
                            image_url,
                            caption=lang_strings["photo_caption"],
                            parse_mode="html",
                        )
                    else:
                        await msg.edit(lang_strings["api_error"], parse_mode="html")

        except Exception as e:
            await kernel.handle_error(
                e, source="cat-MCUB-liber:cat_handler", event=event
            )
            error = f"<b>{lang_strings['error_caption']}</b>\n{lang_strings['full_logs']}\n<pre>{e}</pre>"
            await event.edit(error, parse_mode="html")
