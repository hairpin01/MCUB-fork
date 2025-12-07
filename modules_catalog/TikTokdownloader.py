
# автор переноса: @Hairpin00
# автор идеи hikki  @hikka_mods

from telethon import events
from telethon.tl.types import DocumentAttributeVideo
import aiohttp
import asyncio
import re
from io import BytesIO
import time

class TikTokDownloader:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.api_url = "https://www.tikwm.com/api/"

    def get_url(self, text: str):
        urls = re.findall(r"https?://[^\s]+", text)
        return urls[0] if urls else None

    async def download_tiktok(self, url: str, progress_callback=None):

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
                        return None, "Ошибка API", None, None, None

                    data = await response.json()
                    if data.get("code") != 0:
                        return None, "Не удалось получить видео", None, None, None

                    video_data = data.get("data", {})


                    video_url = video_data.get("hdplay") or video_data.get("play")
                    if not video_url:
                        return None, "Не удалось получить ссылку на видео", None, None, None


                    title = video_data.get("title", "tiktok_video")[:50]
                    video_id = video_data.get("id", "video")


                    async with session.head(video_url) as head_response:
                        total_size = int(head_response.headers.get('content-length', 0))


                    async with session.get(video_url, timeout=30) as video_response:
                        if video_response.status != 200:
                            return None, "Ошибка загрузки видео", None, None, None

                        downloaded = 0
                        chunks = []


                        async for chunk in video_response.content.iter_any():
                            chunks.append(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                await progress_callback(downloaded, total_size)

                        video_bytes = b"".join(chunks)


                        author = video_data.get("author", {}).get("nickname", "Неизвестно")

                        caption = f"🎬 **TikTok видео**\n"
                        caption += f"👤 **Автор:** {author}\n"
                        if title and title != "tiktok_video":
                            caption += f"📝 **Описание:** {title}\n"

                        return video_bytes, caption, video_id, total_size

        except asyncio.TimeoutError:
            return None, "Таймаут при загрузке видео", None, None, None
        except Exception as e:
            return None, f"Ошибка: {str(e)}", None, None, None

def format_size(bytes_size):

    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def create_progress_bar(percentage, length=10):

    filled = int(length * percentage / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"{bar} {percentage:.1f}%"

async def update_progress_message(event, downloaded, total_size):

    if total_size > 0:
        percentage = (downloaded / total_size) * 100
        progress_bar = create_progress_bar(percentage)
        size_info = f"{format_size(downloaded)} / {format_size(total_size)}"

        message = f"⬇️ **Скачиваю видео...**\n\n"
        message += f"{progress_bar}\n"
        message += f"📦 {size_info}"

        try:
            await event.edit(message)
        except:
            pass

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


            start_time = time.time()
            await event.edit("⬇️ **Скачиваю видео...**\n\n"
                           "⏳ Получаю информацию...")


            last_update = time.time()
            async def progress_callback(downloaded, total_size):
                nonlocal last_update

                if time.time() - last_update > 1.5:
                    await update_progress_message(event, downloaded, total_size)
                    last_update = time.time()


            video_bytes, caption, video_id, total_size = await tiktok.download_tiktok(url, progress_callback)

            if not video_bytes:
                await event.edit(f"❌ **{caption}**")
                return


            if total_size > 0:
                progress_bar = create_progress_bar(100)
                message = f"✅ **Видео скачано!**\n\n"
                message += f"{progress_bar}\n"
                message += f"📦 {format_size(total_size)}\n"
                message += f"⏱ {time.time() - start_time:.1f} сек"
                await event.edit(message)
            else:
                await event.edit("✅ **Видео скачано!**\n\n"
                               "📤 **Отправляю...**")


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
