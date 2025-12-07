
# автор переноса: @Hairpin00
# автор модуль hikki  @hikka_mods
from telethon import events
from telethon.tl.types import DocumentAttributeVideo
import aiohttp
import asyncio
import re
from io import BytesIO

class TikTokDownloader:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.api_url = "https://www.tikwm.com/api/"

    def get_url(self, text: str):
        urls = re.findall(r"https?://[^\s]+", text)
        return urls[0] if urls else None

    async def download_tiktok(self, url: str):
        try:
            async with aiohttp.ClientSession() as session:
                params = {"url": url, "hd": 1}
                async with session.get(
                    self.api_url,
                    params=params,
                    headers=self.headers,
                    timeout=10
                ) as response:
                    if response.status != 200:
                        return None, "Ошибка API"

                    data = await response.json()
                    if data.get("code") != 0:
                        return None, "Не удалось получить видео"

                    video_data = data.get("data", {})


                    video_url = video_data.get("hdplay") or video_data.get("play")
                    if not video_url:
                        return None, "Не удалось получить ссылку на видео"


                    title = video_data.get("title", "tiktok_video")[:50]
                    video_id = video_data.get("id", "video")

                    async with session.get(video_url, timeout=30) as video_response:
                        if video_response.status != 200:
                            return None, "Ошибка загрузки видео"


                        video_bytes = await video_response.read()


                        author = video_data.get("author", {}).get("nickname", "Неизвестно")

                        caption = f"🎬 **TikTok видео**\n"
                        caption += f"👤 **Автор:** {author}\n"
                        if title and title != "tiktok_video":
                            caption += f"📝 **Описание:** {title}\n"

                        return video_bytes, caption, video_id

        except asyncio.TimeoutError:
            return None, "Таймаут при загрузке видео"
        except Exception as e:
            return None, f"Ошибка: {str(e)}"

def register(client):
    tiktok = TikTokDownloader()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.tiktok\s+(.+)$'))
    async def tiktok_handler(event):

        try:
            url = tiktok.get_url(event.pattern_match.group(1))
            if not url:
                await event.edit("❌ **Не найден URL в сообщении!**\n"
                               "Пример: `.tiktok https://vm.tiktok.com/...`")
                return

            await event.edit("⬇️ **Скачиваю видео...**")


            video_bytes, caption, video_id = await tiktok.download_tiktok(url)

            if not video_bytes:
                await event.edit(f"❌ **{caption}**")  # caption содержит ошибку
                return

            await event.edit("📤 **Отправляю видео...**")


            video_io = BytesIO(video_bytes)
            video_io.name = f"tiktok_{video_id}.mp4"


            await client.send_file(
                event.chat_id,
                video_io,
                caption=caption,
                supports_streaming=True,
                attributes=[
                    DocumentAttributeVideo(
                        duration=0,
                        w=0,
                        h=0,
                        round_message=False,
                        supports_streaming=True
                    )
                ]
            )

            await event.delete()

        except Exception as e:
            await event.edit(f"❌ **Ошибка:**\n```\n{str(e)}\n```")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.tt\s+(.+)$'))
    async def tt_short_handler(event):
        await tiktok_handler(event)
